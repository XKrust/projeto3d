"""Pure scoring formulas for Radar 3D."""
from datetime import date, timedelta
from typing import TypeVar

K = TypeVar("K")


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max."""
    return max(min_val, min(max_val, value))


def percentile_ranks(values: dict[K, float]) -> dict[K, float]:
    """
    Calculate percentile ranks for a dictionary of values.

    Formula: (count_less + 0.5 * count_equal) / n * 100
    Single element returns 50.0.
    Empty dict returns empty dict.

    Args:
        values: Dictionary mapping keys to numeric values

    Returns:
        Dictionary with same keys, mapped to percentile ranks
    """
    if not values:
        return {}

    n = len(values)
    if n == 1:
        # Single element is always 50th percentile
        key = next(iter(values.keys()))
        return {key: 50.0}

    result = {}
    for key, val in values.items():
        # Count values less than and equal to current value
        count_less = sum(1 for v in values.values() if v < val)
        count_equal = sum(1 for v in values.values() if v == val)

        percentile = (count_less + 0.5 * count_equal) / n * 100
        result[key] = percentile

    return result


def momentum_raw(series: list[float]) -> float:
    """
    Calculate raw momentum from a 10-day series.

    The series contains the last 10 days, from oldest to newest.
    - recent = mean of last 3 days
    - anterior = mean of first 7 days
    - If anterior == 0: return 2.0 if recent > 0, else 0.0
    - Otherwise: clamp(recent / anterior - 1, -1, 2)

    Args:
        series: List of 10 float values, oldest to newest

    Returns:
        Momentum value
    """
    if len(series) != 10:
        raise ValueError("series must have exactly 10 elements")

    anterior = sum(series[:7]) / 7
    recent = sum(series[7:]) / 3

    if anterior == 0:
        return 2.0 if recent > 0 else 0.0

    return clamp(recent / anterior - 1, -1, 2)


def momentum_score(m: float) -> float:
    """
    Convert raw momentum to a score (0-100 scale).

    Formula: (m + 1) / 3 * 100

    Args:
        m: Raw momentum value

    Returns:
        Momentum score
    """
    return (m + 1) / 3 * 100


def window_fit(peak: date, delivery: date) -> float:
    """
    Calculate window fit factor for timing.

    - If peak >= delivery: return 1.0
    - Otherwise: 0.5 ** (days_late / 7)

    Args:
        peak: Peak date
        delivery: Delivery date

    Returns:
        Fit factor (0.0 to 1.0)
    """
    if peak >= delivery:
        return 1.0

    days_late = (delivery - peak).days
    return 0.5 ** (days_late / 7)


def opportunity(
    demand: float, momentum: float, saturation: float, fit: float, weights: dict
) -> float:
    """
    Calculate overall opportunity score.

    Combines demand, momentum, and saturation with weights and a time-fit factor.
    Rounded to 1 decimal place.

    Formula: (w_demand·demand + w_momentum·momentum + w_saturation·(100 - saturation)) · fit

    Notes:
        - Saturation enters as (100 - saturation): higher saturation means lower opportunity
        - Fit multiplies the entire weighted sum (timing window effect)

    Args:
        demand: Demand score (0-100)
        momentum: Momentum score (0-100)
        saturation: Saturation score (0-100)
        fit: Window fit factor (0-1)
        weights: Dictionary with keys 'demand', 'momentum', 'saturation'

    Returns:
        Opportunity score
    """
    weighted_sum = (
        demand * weights["demand"]
        + momentum * weights["momentum"]
        + (100 - saturation) * weights["saturation"]
    )
    return round(weighted_sum * fit, 1)


def peak_day(
    today: date, m_raw: float, event_day: date | None = None, lead_days: int = 21
) -> date:
    """
    Calculate the optimal peak day for market opportunity.

    - With event: return event_day - lead_days
    - Without event: return today + 10 if m_raw > 0, else today

    Args:
        today: Current date
        m_raw: Raw momentum value
        event_day: Specific event date (optional)
        lead_days: Days to look ahead for optimal peak

    Returns:
        Optimal peak date
    """
    if event_day is not None:
        return event_day - timedelta(days=lead_days)

    if m_raw > 0:
        return today + timedelta(days=10)

    return today


def platform_fit(strength: float, market_match: bool, present: bool) -> float:
    """
    Calculate platform fit for market.

    Formula: strength * (1 if market_match else 0) * (1.0 if present else 0.5)

    Args:
        strength: Platform strength (0-1)
        market_match: Whether platform matches target market
        present: Whether platform is already present in market

    Returns:
        Fit score
    """
    match_factor = 1 if market_match else 0
    presence_factor = 1.0 if present else 0.5
    return strength * match_factor * presence_factor


def sale_chance(opp: float) -> str:
    """
    Categorize opportunity score to sales chance.

    - >= 70: "Alta"
    - 40 to 69: "Média"
    - < 40: "Baixa"

    Args:
        opp: Opportunity score

    Returns:
        Sales chance category in Portuguese
    """
    if opp >= 70:
        return "Alta"
    elif opp >= 40:
        return "Média"
    else:
        return "Baixa"


def momentum_arrow(m_raw: float) -> str:
    """
    Represent momentum direction as arrow emoji/text.

    - > 0.1: "up"
    - < -0.1: "down"
    - otherwise: "flat"

    Args:
        m_raw: Raw momentum value

    Returns:
        Direction indicator
    """
    if m_raw > 0.1:
        return "up"
    elif m_raw < -0.1:
        return "down"
    else:
        return "flat"
