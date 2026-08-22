"""Statistical utilities for pilot result reporting."""

from __future__ import annotations

import math
from typing import Sequence


def mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def std_dev(values: Sequence[float]) -> float:
    if len(values) <= 1:
        return 0.0
    avg = mean(values)
    variance = sum((x - avg) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def confidence_interval_95(values: Sequence[float]) -> tuple[float, float]:
    """Calculate approximate 95% confidence interval."""
    if len(values) <= 1:
        m = mean(values)
        return (m, m)
    avg = mean(values)
    sd = std_dev(values)
    margin = 1.96 * (sd / math.sqrt(len(values)))
    return (avg - margin, avg + margin)
