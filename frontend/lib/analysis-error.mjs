// Translate only known error categories; never display raw provider text.
export function analysisErrorText(message, t) {
  const code = message.split(':', 1)[0];
  const messages = {
  "renderer_unavailable": "PowerPoint preview requires LibreOffice on the backend. Ask the service owner to install it, then retry.",
  "gemini_daily_quota_exceeded": "Gemini daily project/API-key quota is exhausted. Wait for reset or use a project with available quota and upload again.",
  "gemini_quota_exceeded": "Gemini returned HTTP 429: quota or request/token rate limit reached. Check Usage in Google AI Studio, wait and upload again; daily exhaustion was not confirmed.",
  "gemini_output_limit": "Gemini stopped with MAX_TOKENS: the output token ceiling was reached and the summary remained truncated after repair. This does not mean quota exhaustion. Split the document and upload again.",
  "gemini_context_limit": "Gemini rejected input exceeding its context or request-size limit. Split the document and upload again.",
  "gemini_input_limit": "An input segment exceeds the application input budget. Split the document and upload again.",
  "gemini_reduce_limit": "Intermediate findings could not be condensed within safe processing limits. Split the document and upload again.",
  "gemini_unavailable": "Gemini is temporarily unavailable: the service returned a server/overload error after retries. Wait and upload again.",
  "gemini_connection_failed": "A network error prevented connection to Gemini. Check connectivity and upload again.",
  "gemini_incomplete_response": "Gemini returned output but it still omitted major topics or changed technical terms after repair. Quality checks failed; token/quota exhaustion was not confirmed. Retry or split the document.",
  "gemini_invalid_response": "Gemini returned malformed/unreadable JSON or output exceeding the length contract after repair. Token/quota exhaustion was not confirmed. Upload again.",
  "gemini_blocked": "Gemini blocked or stopped the response before completion. Review the source and retry with permitted content.",
  "invalid_result": "AI output or citations failed the application structure/evidence checks. The invalid summary was not saved; upload again."
};
  if (messages[code]) return t(messages[code]);
  let match;
  if ((match = message.match(/^gemini_request_timeout: Gemini request exceeded (\d+) seconds\./)))
    return t('Gemini did not respond within {0} seconds per request. Provider retries were exhausted; upload again. The BR deadline is unchanged.', match[1]);
  if ((match = message.match(/^(Bullet|Contract batch) processing exceeded the ([\d.]+)-second target\./)))
    return t('The BR processing deadline of {0} seconds was exceeded, including queue time and retries. The task was cancelled; split the document or retry.', match[2]);
  if ((match = message.match(/^Processing (?:exceeded (\d+) seconds|timed out after \d+ attempts \((\d+) seconds per attempt\))/)))
    return t('Document processing exceeded {0} seconds per attempt. Processing retries were exhausted; split the document or retry.', match[1] || match[2]);
  return null;
}
