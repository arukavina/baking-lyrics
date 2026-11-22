"""
Per client fixed window rate limiting stored in DynamoDB (``{prefix}-ratelimit``), so the limit holds across
Lambda instances and gunicorn workers.

Each window is one item keyed ``<ip>#<route>#<window seconds>#<window number>`` whose counter is bumped with a
conditional ADD that fails once the limit is reached; the item expires through the table TTL (``ttl``).
Any DynamoDB failure (missing table, credentials, outage) is logged and treated as "not limited": a limiter
outage must never take the API down.

Limits use the "10 per minute;100 per day" format (units: second, minute, hour, day).
"""

# Generic
import json
import logging
import re
import time

# Libs
from botocore.exceptions import ClientError

logger = logging.getLogger('baking-api')

UNIT_SECONDS = {'second': 1, 'minute': 60, 'hour': 3600, 'day': 86400}
_LIMIT = re.compile(r'^\s*(\d+)\s*(?:per|/)\s*(second|minute|hour|day)s?\s*$', re.IGNORECASE)

# Expired items are kept a bit longer than their window (TTL deletion is not immediate anyway)
TTL_MARGIN_SECONDS = 60


def parse_limits(spec):
    """
    :param spec: e.g. "10 per minute;100 per day"
    :return: list of (count, window seconds), e.g. [(10, 60), (100, 86400)]
    """
    limits = []
    for part in filter(None, (p.strip() for p in spec.split(';'))):
        match = _LIMIT.match(part)
        if match is None:
            raise ValueError(f'Invalid rate limit: {part!r}. Expected e.g. "10 per minute".')
        limits.append((int(match.group(1)), UNIT_SECONDS[match.group(2).lower()]))
    return limits


def client_ip(request):
    """
    The client address of a Flask request.

    Behind the Lambda Function URL and the AWS Lambda Web Adapter, `remote_addr` is the adapter on localhost, so:
    the client IP of the Function URL request context first (the adapter always sets the x-amzn-request-context
    header itself, field http.sourceIp, so clients cannot forge it), else the left-most X-Forwarded-For entry
    (local runs behind a proxy), else remote_addr.
    """
    context = request.headers.get('X-Amzn-Request-Context')
    if context:
        try:
            source_ip = json.loads(context).get('http', {}).get('sourceIp')
        except (ValueError, AttributeError):
            source_ip = None
        if source_ip:
            return source_ip

    forwarded = request.headers.get('X-Forwarded-For', '')
    first = forwarded.split(',')[0].strip()
    if first:
        return first

    return request.remote_addr


def _hit(table, key, limit, window_seconds, now):
    """Counts one request in the window. Returns True when the limit was already reached."""
    window = int(now) // window_seconds
    try:
        table.update_item(
            Key={'pk': f'{key}#{window_seconds}#{window}'},
            UpdateExpression='ADD #count :one SET #ttl = if_not_exists(#ttl, :ttl)',
            ConditionExpression='attribute_not_exists(#count) OR #count < :limit',
            ExpressionAttributeNames={'#count': 'request_count', '#ttl': 'ttl'},
            ExpressionAttributeValues={':one': 1, ':limit': limit,
                                       ':ttl': (window + 1) * window_seconds + TTL_MARGIN_SECONDS},
        )
    except ClientError as error:
        if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return True
        raise
    return False


def is_rate_limited(table, ip, route, limits, now=None):
    """
    Counts a request of `ip` on `route` in every window of `limits` (shortest first) and tells whether one of them
    is exhausted. Never raises.
    :param table: boto3 Table of the ratelimit table
    :param ip: client address (requests without one are never limited)
    :param route: name of the limited route, e.g. "shares"
    :param limits: list of (count, window seconds), see parse_limits
    :param now: epoch seconds (tests)
    :return: bool
    """
    if not ip:
        return False
    now = time.time() if now is None else now
    try:
        for limit, window_seconds in sorted(limits, key=lambda item: item[1]):
            if _hit(table, f'{ip}#{route}', limit, window_seconds, now):
                return True
    except Exception:  # fail open
        logger.warning('Rate limit check failed for %s/%s', ip, route, exc_info=True)
    return False
