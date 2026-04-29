import re
import time
from datetime import datetime, timedelta


DURATION_RE = re.compile(
    r'^(?P<n>\d+)(?P<u>[smhdw])$',
    re.IGNORECASE,
)
HHMM_RE = re.compile(r'^(?P<h>\d{1,2}):(?P<m>\d{2})$')

_DURATION_UNITS = {
    's': 1,
    'm': 60,
    'h': 3600,
    'd': 86400,
    'w': 604800,
}


def parse_when(token: str) -> int:
    """Return absolute unix ts for when the reminder fires."""
    token = token.strip()
    now = int(time.time())

    m = DURATION_RE.match(token)
    if m:
        n = int(m.group('n'))
        unit = m.group('u').lower()
        return now + n * _DURATION_UNITS[unit]

    m = HHMM_RE.match(token)
    if m:
        h, mm = int(m.group('h')), int(m.group('m'))
        if not (0 <= h < 24 and 0 <= mm < 60):
            raise ValueError('Invalid HH:MM')
        target = datetime.now().replace(
            hour=h, minute=mm, second=0, microsecond=0
        )
        if target.timestamp() <= now:
            target += timedelta(days=1)
        return int(target.timestamp())

    try:
        dt = datetime.fromisoformat(token)
        ts = int(dt.timestamp())
        if ts <= now:
            raise ValueError('Datetime is in the past')
        return ts
    except ValueError:
        pass

    raise ValueError(
        'Use Nm/Nh/Nd/Nw, HH:MM, or YYYY-MM-DD HH:MM'
    )


def parse_command(text: str) -> tuple[str, str]:
    """Split body into (when_token, message_text)."""
    parts = text.strip().split(maxsplit=1)
    if not parts:
        raise ValueError('Empty')
    when = parts[0]
    body = parts[1] if len(parts) > 1 else ''
    if when.startswith(('"', "'")):
        quote = when[0]
        rest = text.strip()[1:]
        end = rest.find(quote)
        if end == -1:
            raise ValueError('Unterminated quoted datetime')
        when = rest[:end]
        body = rest[end + 1 :].strip()
    return when, body


def humanize(seconds: int) -> str:
    if seconds < 60:
        return f'{seconds}s'
    if seconds < 3600:
        return f'{seconds // 60}m'
    if seconds < 86400:
        return f'{seconds // 3600}h {(seconds % 3600) // 60}m'
    return f'{seconds // 86400}d {(seconds % 86400) // 3600}h'
