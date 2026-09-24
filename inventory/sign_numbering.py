"""Project-scoped sign suggestions. Call allocation inside the write transaction."""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .models import TabRecord


def coordinate(value):
    try:
        number = Decimal(str(value).strip())
        return number.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP) if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def canonical(value):
    return str(value or '').strip().upper()


def next_number(values, prefix):
    numbers = [int(match.group(1)) for value in values if (match := re.fullmatch(prefix + r'(\d+)', canonical(value)))]
    return prefix + str(max(numbers, default=0) + 1)


def suggest(project, data, exclude_pk=None, allocate=False):
    records = list(TabRecord.objects.filter(project=project, tab='sign').exclude(pk=exclude_pk).values_list('data', flat=True))
    latitude, longitude = coordinate(data.get('LATITUDE')), coordinate(data.get('LONGITUDE'))
    matches = [r for r in records if latitude is not None and longitude is not None and coordinate(r.get('LATITUDE')) == latitude and coordinate(r.get('LONGITUDE')) == longitude and canonical(r.get('POLE_ID'))]
    pole = canonical(data.get('POLE_ID')) or (canonical(matches[0].get('POLE_ID')) if matches else '')
    if not pole and allocate:
        pole = next_number([r.get('POLE_ID') for r in records], 'P')
    sign = canonical(data.get('SIGN'))
    if not sign and pole:
        sign = next_number([r.get('SIGN') for r in records if canonical(r.get('POLE_ID')) == pole], 'S')
    if allocate and any(canonical(r.get('POLE_ID')) == pole and canonical(r.get('SIGN')) == sign for r in records):
        raise ValueError(f'Pole ID {pole} and Sign ID {sign} already exist in this project. Choose a different Sign ID.')
    return {'POLE_ID': pole, 'SIGN': sign}
