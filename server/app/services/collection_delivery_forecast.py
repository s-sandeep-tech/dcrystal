"""Gamma-Exponential Party-to-Office survival model (shape/rate convention).

See docs/collection_delivery_forecast.md for assumptions and validation limits.
"""
from math import exp, expm1, isfinite, log, log1p


PRIOR_SHAPE = 1.0
PRIOR_RATE_DAYS = 1.0
MIN_COMPLETED = 5


def delivery_forecast(completed_count, completed_days, pending_days, pending_buckets):
    """Buckets contain (elapsed days, target days or None, record count).

    Pending survival to the observation date is already included in the
    posterior exposure. Do not condition on that elapsed time a second time.
    """
    n = int(completed_count or 0)
    exposure = float(completed_days or 0) + float(pending_days or 0)
    result = {
        'model': 'Gamma-Exponential v1', 'validation': 'Not historically validated',
        'completed_count': n, 'prior_shape': PRIOR_SHAPE,
        'prior_rate_days': PRIOR_RATE_DAYS, 'available': False,
        'reason': 'At least 5 valid completed receipts and positive exposure are required.',
        'mean_days': None, 'predictive_low_days': None, 'predictive_high_days': None,
        'pending_breach_pct': None, 'expected_breaches': None,
        'pending_remaining_days': None, 'pending_count': 0,
        'assessed_pending_count': 0, 'missing_target_count': 0,
        'observed_overdue_count': 0,
    }
    buckets = []
    for age, target, count in pending_buckets:
        age, count = float(age), int(count)
        if not isfinite(age) or age < 0 or count <= 0:
            raise ValueError('Invalid pending observation')
        valid_target = target is not None and isfinite(float(target)) and float(target) >= 0
        target = float(target) if valid_target else None
        result['pending_count'] += count
        if target is None:
            result['missing_target_count'] += count
        else:
            result['assessed_pending_count'] += count
            if age > target:
                result['observed_overdue_count'] += count
        buckets.append((age, target, count))
    if n < MIN_COMPLETED or not isfinite(exposure) or exposure <= 0:
        return result

    # Likelihood: lambda**n * exp(-lambda * total observed days).
    shape, rate = PRIOR_SHAPE + n, PRIOR_RATE_DAYS + exposure
    result.update(
        available=True, reason=None, posterior_shape=shape, posterior_rate_days=rate,
        mean_days=rate / (shape - 1.0),
        predictive_low_days=rate * expm1(-log(0.95) / shape),
        predictive_high_days=rate * expm1(-log(0.05) / shape),
    )
    if result['pending_count']:
        # Constant-hazard assumption: all existing pending records share this
        # remaining-time distribution after their censoring informs the model.
        result['pending_remaining_days'] = result['mean_days']
    if result['assessed_pending_count']:
        expected = 0.0
        for age, target, count in buckets:
            if target is not None:
                remaining_to_target = max(target - age, 0.0)
                probability = exp(-shape * log1p(remaining_to_target / rate))
                expected += count * probability
        result['expected_breaches'] = expected
        result['pending_breach_pct'] = 100.0 * expected / result['assessed_pending_count']
    return result
