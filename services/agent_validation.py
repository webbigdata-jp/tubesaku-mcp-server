"""Public search input validation. Errors contain field names, never submitted values."""
import re
from datetime import date


class SearchValidationError(ValueError):
    pass


def integer(value, name, minimum=1, maximum=10):
    if isinstance(value, bool) or not re.fullmatch(r'[+-]?[0-9]+', str(value)):
        raise SearchValidationError(f'{name} must be an integer between {minimum} and {maximum}')
    # Bound conversion work for direct HTTP input too.
    if len(str(value)) > 12:
        raise SearchValidationError(f'{name} must be between {minimum} and {maximum}')
    number = int(value)
    if not minimum <= number <= maximum:
        raise SearchValidationError(f'{name} must be between {minimum} and {maximum}')
    return number


def search_text(value, name, maximum=200):
    if not isinstance(value, str):
        raise SearchValidationError(f'{name} must be text (at most {maximum} characters)')
    value = value.strip()
    if len(value) > maximum:
        raise SearchValidationError(f'{name} must be at most {maximum} characters')
    return value


def search_date(value, name):
    if value in ('', None):
        return None
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise SearchValidationError(f'{name} must use YYYY-MM-DD')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise SearchValidationError(f'{name} must be a valid date in YYYY-MM-DD') from None


def date_range(date_from, date_to):
    start = search_date(date_from, 'date_from')
    end = search_date(date_to, 'date_to')
    if start and end and end < start:
        raise SearchValidationError('date_to must be on or after date_from')
    return start, end


def debut_year(value):
    return None if value in ('', None) else integer(value, 'debut_year', 2000, 2100)


def current_category(value):
    value = search_text(value, 'category', 3)
    if value and not re.fullmatch(r'[0-9]{1,3}', value):
        raise SearchValidationError('category must be a numeric YouTube category ID (for example 20 for games)')
    return value


def search_time(value, name):
    if value in ('', None):
        return None
    if not isinstance(value, str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?', value):
        raise SearchValidationError(f'{name} must use HH:MM or HH:MM:SS in JST (00:00-23:59:59)')
    parts = tuple(int(part) for part in value.split(':'))
    return parts + (0,) if len(parts) == 2 else parts
