"""Validate explicit lease deadlines without accepting local or ambiguous times."""
from datetime import datetime, timezone


def deadline(value, now=None):
    """Return a future UTC deadline from an ISO timestamp with an explicit offset."""
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError('Choose an expiry date and time.')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('Expiry must be an ISO date and time with a timezone.') from None
    if result.tzinfo is None:
        raise ValueError('Expiry must include a timezone.')
    result = result.astimezone(timezone.utc)
    if result <= (now or datetime.now(timezone.utc)):
        raise ValueError('Choose a future expiry; expired environments cannot be revived.')
    return result.isoformat()
