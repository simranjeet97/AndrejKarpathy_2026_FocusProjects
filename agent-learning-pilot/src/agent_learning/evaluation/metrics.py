"""Evaluation metrics calculation module."""

from __future__ import annotations

from typing import Sequence


def success_rate(results: Sequence[dict]) -> float:
    if not results:
        return 0.0
    solved = sum(1 for r in results if r.get("success", False))
    return solved / len(results)


def transfer_gain(condition_rate: float, baseline_rate: float) -> float:
    return condition_rate - baseline_rate


def retention_score(before_rate: float, after_rate: float) -> float:
    if before_rate == 0.0:
        return 1.0 if after_rate == 0.0 else 0.0
    return after_rate / before_rate


def non_regression_score(original_rate: float, retest_rate: float) -> float:
    return retest_rate - original_rate


def cost_efficiency(transfer_gain_val: float, additional_calls: float) -> float:
    if additional_calls <= 0:
        return 0.0
    return transfer_gain_val / additional_calls


def capability_per_million_tokens(
    transfer_gain_val: float, additional_tokens: float
) -> float:
    if additional_tokens <= 0:
        return 0.0
    return (transfer_gain_val / additional_tokens) * 1_000_000
