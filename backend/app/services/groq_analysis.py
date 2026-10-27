"""Groq transport adapter; source prompts and output contracts stay unchanged."""
from copy import deepcopy
import asyncio
import json
import logging
import math
from asyncio import get_running_loop, Semaphore
from types import SimpleNamespace
from weakref import WeakKeyDictionary

import httpx

from app.core.config import settings

ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions'
logger = logging.getLogger(__name__)
MAX_CONNECTION_ATTEMPTS = 3
_request_gates = WeakKeyDictionary()


def request_gate():
    # Keep gates per loop, including uvloop implementations which need not
    # allow custom attributes. Drop closed loops with formerly bound waiters.
    loop = get_running_loop()
    for previous in list(_request_gates):
        if previous.is_closed():
            del _request_gates[previous]
    gate = _request_gates.get(loop)
    if gate is None:
        gate = SimpleNamespace(lock=Semaphore(1), ready_at=0.0)
        _request_gates[loop] = gate
    return gate


def retry_after(response):
    try:
        seconds = float(response.headers['retry-after'])
        return seconds if math.isfinite(seconds) and seconds >= 0 else None
    except (KeyError, ValueError):
        return None


def connection_reason(error):
    """Log exception types/codes, never request bodies, headers or keys."""
    reasons = []
    seen = set()
    while error is not None and id(error) not in seen and len(reasons) < 6:
        seen.add(id(error))
        reason = type(error).__name__
        for attribute in ('errno', 'winerror', 'verify_code'):
            code = getattr(error, attribute, None)
            if isinstance(code, int):
                reason += f'({attribute}={code})'
        reasons.append(reason)
        error = error.__cause__ or error.__context__
    return ' -> '.join(reasons)


async def post_with_connection_retry(client, body, gate=None, deadline=None):
    from app.services.gemini_analysis import GeminiAnalysisError

    for attempt in range(1, MAX_CONNECTION_ATTEMPTS + 1):
        try:
            response = await client.post(
                ENDPOINT,
                headers={'Authorization': 'Bearer ' + settings.GROQ_API_KEY.get_secret_value().strip()},
                json=body)
        except httpx.TimeoutException:
            # Keep the existing document timeout/retry semantics. All network
            # attempts and backoff below share one request deadline as well.
            raise
        except httpx.RequestError as error:
            retryable = isinstance(error, (httpx.NetworkError, httpx.RemoteProtocolError))
            logger.warning('Groq connection failed model=%s attempt=%s/%s reason=%s',
                           settings.GROQ_MODEL, attempt, MAX_CONNECTION_ATTEMPTS, connection_reason(error))
            if not retryable or attempt == MAX_CONNECTION_ATTEMPTS:
                raise GeminiAnalysisError('groq_connection_failed',
                    f'Cannot connect to Groq after {attempt} attempt(s). Please retry later.') from None
            await asyncio.sleep(0.5 * attempt)
            continue
        delay = retry_after(response)
        transient_rate_limit = (response.status_code == 429 and delay is not None
                                and response.headers.get('x-ratelimit-remaining-requests') != '0')
        transient_server_error = response.status_code in (500, 502, 503, 504)
        if not transient_rate_limit and not transient_server_error:
            return response
        delay = max(.1, delay if delay is not None else .5 * attempt)
        if transient_rate_limit and gate is not None:
            gate.ready_at = max(gate.ready_at, get_running_loop().time() + delay)
        # Never retry before the provider's requested time or turn a daily/
        # long rate limit into a misleading document timeout.
        if (attempt == MAX_CONNECTION_ATTEMPTS or
                deadline is not None and get_running_loop().time() + delay >= deadline):
            return response
        logger.warning('Groq temporary HTTP failure status=%s attempt=%s/%s retry_after_seconds=%.2f',
                       response.status_code, attempt, MAX_CONNECTION_ATTEMPTS, delay)
        await asyncio.sleep(delay)


def request_body(gemini_body):
    config = gemini_body['generationConfig']
    schema = deepcopy(config.get('responseJsonSchema') or config['responseFormat']['text']['schema'])

    def require_fields(node):
        if isinstance(node, dict):
            if node.get('type') == 'object':
                node['required'] = list(node.get('properties', {}))
                node['additionalProperties'] = False
            for value in node.values():
                require_fields(value)
        elif isinstance(node, list):
            for value in node:
                require_fields(value)

    # Strict JSON Schema requires every property to be present; nullable
    # optional fields (e.g. limitation) retain the same meaning and validation.
    require_fields(schema)
    messages = [{'role': 'system', 'content': ''.join(
        part['text'] for part in gemini_body['systemInstruction']['parts'])}]
    messages.extend({'role': 'user' if item['role'] == 'user' else 'assistant',
                     'content': ''.join(part['text'] for part in item['parts'])}
                    for item in gemini_body['contents'])
    body = {'model': settings.GROQ_MODEL, 'messages': messages,
            'max_completion_tokens': min(config['maxOutputTokens'], settings.GROQ_MAX_OUTPUT_TOKENS), 'n': 1,
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'document_analysis', 'strict': True, 'schema': schema}}}
    if settings.GROQ_MODEL.startswith('openai/gpt-oss-'):
        body['reasoning_effort'] = 'low'
    elif settings.GROQ_MODEL == 'qwen/qwen3.8-27b':
        body['reasoning_effort'] = settings.GROQ_REASONING_EFFORT
    body['temperature'] = 0.2
    return body


async def generate_groq(gemini_body):
    # Import at call time so the Gemini adapter can dispatch here without a
    # module import cycle; reuse the job's existing safe error handling.
    from app.services.gemini_analysis import GeminiAnalysisError

    try:
        # The deadline covers retries AND backoff; retries cannot multiply
        # the configured request budget or bypass the job's cancellation.
        async with asyncio.timeout(settings.GROQ_REQUEST_TIMEOUT_SECONDS):
            gate = request_gate()
            deadline = get_running_loop().time() + settings.GROQ_REQUEST_TIMEOUT_SECONDS
            async with gate.lock:
                wait = gate.ready_at - get_running_loop().time()
                if wait > 0:
                    if get_running_loop().time() + wait >= deadline:
                        raise GeminiAnalysisError('groq_quota_exceeded', 'Groq rate limit is still active. Please retry later.')
                    await asyncio.sleep(wait)
                async with httpx.AsyncClient(timeout=httpx.Timeout(
                        settings.GROQ_REQUEST_TIMEOUT_SECONDS,
                        connect=min(10, settings.GROQ_REQUEST_TIMEOUT_SECONDS))) as client:
                    response = await post_with_connection_retry(client, request_body(gemini_body), gate, deadline)
    except (httpx.TimeoutException, TimeoutError):
        raise TimeoutError('Groq request timed out.') from None
    if response.status_code in (400, 401, 403, 404, 422):
        if response.status_code == 400:
            try:
                error = response.json().get('error', {})
                if error.get('code') == 'json_validate_failed':
                    code = ('groq_output_limit' if 'max completion tokens' in str(error.get('message', '')).lower()
                            else 'groq_invalid_response')
                    raise GeminiAnalysisError(code, 'Groq could not produce a complete valid structured analysis.')
            except (ValueError, TypeError, AttributeError):
                pass
        raise GeminiAnalysisError('groq_configuration_error', 'Check GROQ_API_KEY, model access and structured output support.')
    if response.status_code == 429:
        raise GeminiAnalysisError('groq_quota_exceeded', 'Groq quota/rate limit reached. Please retry later.')
    if not response.is_success:
        raise GeminiAnalysisError('groq_unavailable', 'Groq is temporarily unavailable. Please retry later.')
    try:
        data = response.json()
        choice = data['choices'][0]
        if choice.get('finish_reason') == 'length':
            raise GeminiAnalysisError('groq_output_limit', 'Groq output was truncated. Check GROQ_MAX_OUTPUT_TOKENS and the model quota.')
        if choice.get('finish_reason') != 'stop' or choice['message'].get('refusal'):
            raise GeminiAnalysisError('groq_blocked', 'Groq did not return a complete analysis.')
        result = json.loads(choice['message']['content'])
        usage = data.get('usage') or {}
        return result, {'promptTokenCount': usage.get('prompt_tokens'),
                        'candidatesTokenCount': usage.get('completion_tokens'),
                        'totalTokenCount': usage.get('total_tokens')}
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise GeminiAnalysisError('groq_invalid_response', 'Groq returned an invalid or blocked response.') from None
