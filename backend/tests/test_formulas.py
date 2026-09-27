"""Tests for scoring formulas."""
from datetime import date, timedelta

import pytest

from app.scoring.formulas import (
    clamp,
    momentum_arrow,
    momentum_raw,
    momentum_score,
    opportunity,
    peak_day,
    percentile_ranks,
    platform_fit,
    sale_chance,
    window_fit,
)


class TestPercentileRanks:
    """Tests for percentile_ranks function."""

    def test_empty_dict(self):
        """Empty dict returns empty dict."""
        assert percentile_ranks({}) == {}

    def test_single_element(self):
        """Single element returns 50.0."""
        assert percentile_ranks({"a": 1.0}) == {"a": 50.0}

    def test_three_elements(self):
        """Three elements with duplicates."""
        result = percentile_ranks({"a": 1, "b": 2, "c": 2})
        # For value 1: 0 values < 1, 0 values == 1, so (0 + 0.5*0) / 3 * 100 = 0%
        # Actually: (count_less + 0.5 * count_equal) / n * 100
        # For a=1: count_less=0, count_equal=1, n=3: (0 + 0.5*1) / 3 * 100 = 16.666...
        # For b=2: count_less=1, count_equal=2, n=3: (1 + 0.5*2) / 3 * 100 = 200/3 = 66.666...
        # For c=2: same as b = 66.666...
        assert result["a"] == pytest.approx(16.7, abs=0.1)
        assert result["b"] == pytest.approx(66.7, abs=0.1)
        assert result["c"] == pytest.approx(66.7, abs=0.1)


class TestMomentumRaw:
    """Tests for momentum_raw function."""

    def test_constant_then_increase(self):
        """Seven 1s then three 2s."""
        result = momentum_raw([1.0] * 7 + [2.0] * 3)
        # recent = mean(2, 2, 2) = 2.0
        # anterior = mean(1, 1, 1, 1, 1, 1, 1) = 1.0
        # clamped((2.0/1.0) - 1, -1, 2) = clamped(1.0, -1, 2) = 1.0
        assert result == 1.0

    def test_zero_to_positive(self):
        """Seven 0s then three 5s."""
        result = momentum_raw([0.0] * 7 + [5.0] * 3)
        # anterior = 0.0, recent = 5.0 > 0
        # Should return 2.0
        assert result == 2.0

    def test_all_zeros(self):
        """All zeros."""
        result = momentum_raw([0.0] * 10)
        # anterior = 0.0, recent = 0.0
        # Should return 0.0
        assert result == 0.0

    def test_positive_to_zero(self):
        """Seven 10s then three 0s."""
        result = momentum_raw([10.0] * 7 + [0.0] * 3)
        # recent = 0.0
        # anterior = 10.0
        # (0.0 / 10.0) - 1 = -1.0
        # clamped(-1.0, -1, 2) = -1.0
        assert result == -1.0


class TestMomentumScore:
    """Tests for momentum_score function."""

    def test_zero_momentum(self):
        """Momentum of 0 gives 33.333."""
        result = momentum_score(0.0)
        assert result == pytest.approx(33.333, abs=0.01)

    def test_positive_momentum(self):
        """Positive momentum increases score."""
        result = momentum_score(1.0)
        # (1 + 1) / 3 * 100 = 2/3 * 100 = 66.666...
        assert result == pytest.approx(66.666, abs=0.01)

    def test_negative_momentum(self):
        """Negative momentum decreases score."""
        result = momentum_score(-1.0)
        # (-1 + 1) / 3 * 100 = 0 / 3 * 100 = 0.0
        assert result == pytest.approx(0.0, abs=0.01)


class TestWindowFit:
    """Tests for window_fit function."""

    def test_perfect_timing(self):
        """Peak on or before delivery gives 1.0."""
        peak = date(2026, 10, 1)
        delivery = date(2026, 10, 1)
        assert window_fit(peak, delivery) == 1.0

    def test_one_week_delay(self):
        """Delivery 7 days after peak gives 0.5."""
        peak = date(2026, 10, 1)
        delivery = date(2026, 10, 8)
        assert window_fit(peak, delivery) == 0.5

    def test_two_weeks_delay(self):
        """Delivery 14 days after peak gives 0.25."""
        peak = date(2026, 10, 1)
        delivery = date(2026, 10, 15)
        assert window_fit(peak, delivery) == 0.25

    def test_early_delivery(self):
        """Delivery before peak gives 1.0."""
        peak = date(2026, 10, 15)
        delivery = date(2026, 10, 1)
        assert window_fit(peak, delivery) == 1.0


class TestOpportunity:
    """Tests for opportunity function."""

    def test_standard_weights(self):
        """Opportunity with standard weights."""
        weights = {"demand": 0.40, "momentum": 0.25, "saturation": 0.35}
        result = opportunity(80, 50, 20, 1.0, weights)
        # (0.4*80 + 0.25*50 + 0.35*(100-20)) * 1.0 = (32 + 12.5 + 28) * 1.0 = 72.5
        assert result == 72.5

    def test_higher_saturation(self):
        """Higher saturation (more crowded market) lowers opportunity."""
        weights = {"demand": 0.40, "momentum": 0.25, "saturation": 0.35}
        result = opportunity(80, 50, 50, 1.0, weights)
        # (0.4*80 + 0.25*50 + 0.35*(100-50)) * 1.0 = (32 + 12.5 + 17.5) * 1.0 = 62.0
        assert result == 62.0

    def test_with_partial_fit(self):
        """Fit factor multiplies the entire weighted sum."""
        weights = {"demand": 0.40, "momentum": 0.25, "saturation": 0.35}
        result = opportunity(80, 50, 20, 0.5, weights)
        # (0.4*80 + 0.25*50 + 0.35*(100-20)) * 0.5 = 72.5 * 0.5 = 36.25 → 36.2 or 36.3
        assert result == pytest.approx(36.2, abs=0.05)

    def test_zero_with_full_saturation(self):
        """Full saturation with zero demand and momentum gives zero."""
        weights = {"demand": 0.40, "momentum": 0.25, "saturation": 0.35}
        result = opportunity(0, 0, 100, 1.0, weights)
        # (0.4*0 + 0.25*0 + 0.35*(100-100)) * 1.0 = 0.0
        assert result == 0.0


class TestPeakDay:
    """Tests for peak_day function."""

    def test_with_event(self):
        """With event, returns event_day - lead_days."""
        today = date(2026, 9, 27)
        event_day = date(2026, 10, 31)
        result = peak_day(today, 0.5, event_day=event_day, lead_days=21)
        # 31/10 - 21 days = 10/10
        expected = date(2026, 10, 10)
        assert result == expected

    def test_without_event_positive_momentum(self):
        """Without event, positive momentum returns today + 10."""
        today = date(2026, 9, 27)
        result = peak_day(today, 0.5, event_day=None, lead_days=21)
        expected = today + timedelta(days=10)
        assert result == expected

    def test_without_event_negative_momentum(self):
        """Without event, non-positive momentum returns today."""
        today = date(2026, 9, 27)
        result = peak_day(today, -0.5, event_day=None, lead_days=21)
        assert result == today

    def test_without_event_zero_momentum(self):
        """Without event, zero momentum returns today."""
        today = date(2026, 9, 27)
        result = peak_day(today, 0.0, event_day=None, lead_days=21)
        assert result == today


class TestPlatformFit:
    """fit = força no país × afinidade da loja com o tipo de tema."""

    def test_generalist_store_fits_every_category(self):
        assert platform_fit(0.8, [], "anime") == 0.8

    def test_category_the_store_is_strong_in(self):
        assert platform_fit(0.8, ["rpg_miniaturas"], "rpg_miniaturas") == 0.8

    def test_category_outside_the_store_strengths(self):
        assert platform_fit(0.8, ["rpg_miniaturas"], "decoracao") == pytest.approx(0.56)


class TestSaleChance:
    """Tests for sale_chance function."""

    def test_high_opportunity(self):
        """Opportunity >= 70 is Alta."""
        assert sale_chance(70) == "Alta"
        assert sale_chance(75) == "Alta"

    def test_medium_opportunity(self):
        """Opportunity 40-69 is Média."""
        assert sale_chance(69.9) == "Média"
        assert sale_chance(50) == "Média"
        assert sale_chance(40) == "Média"

    def test_low_opportunity(self):
        """Opportunity < 40 is Baixa."""
        assert sale_chance(39.9) == "Baixa"
        assert sale_chance(30) == "Baixa"


class TestMomentumArrow:
    """Tests for momentum_arrow function."""

    def test_up_arrow(self):
        """Momentum > 0.1 is up."""
        assert momentum_arrow(0.5) == "up"
        assert momentum_arrow(2.0) == "up"

    def test_down_arrow(self):
        """Momentum < -0.1 is down."""
        assert momentum_arrow(-0.5) == "down"
        assert momentum_arrow(-1.0) == "down"

    def test_flat_arrow(self):
        """Momentum between -0.1 and 0.1 is flat."""
        assert momentum_arrow(0.0) == "flat"
        assert momentum_arrow(0.05) == "flat"
        assert momentum_arrow(-0.05) == "flat"


class TestClamp:
    """Tests for clamp helper function."""

    def test_within_bounds(self):
        """Value within bounds is unchanged."""
        assert clamp(5, 0, 10) == 5

    def test_below_min(self):
        """Value below min is clamped to min."""
        assert clamp(-5, 0, 10) == 0

    def test_above_max(self):
        """Value above max is clamped to max."""
        assert clamp(15, 0, 10) == 10
