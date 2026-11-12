"""Log metrics using route templates, never raw URLs, headers or request bodies."""
import logging
from time import monotonic

logger = logging.getLogger('app.operations')


async def log_request(request, call_next):
    started = monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get('route')
        template = getattr(route, 'path', '<unmatched>')
        duration_ms = round((monotonic() - started) * 1000)
        level = logging.WARNING if status >= 500 or duration_ms >= 2000 else logging.INFO
        logger.log(level, 'http_request method=%s route=%s status=%s duration_ms=%s',
                   request.method, template, status, duration_ms)
