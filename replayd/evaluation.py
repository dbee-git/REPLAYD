"""Evaluation helpers for creator-reviewed candidate timestamps.

Only measure *temporal candidate spotting*, not semantic goal classification.
Matching is one-to-one and maximizes number of matched events within tolerance.
"""
from __future__ import annotations

import math


def match_events(predicted: list[float], actual: list[float], tolerance_seconds: float = 5.0) -> list[tuple[int, int, float]]:
    """Find a maximum-cardinality bipartite match between predictions and labels.

    Results are (prediction_index, label_index, absolute_time_error_sec). A
    shorter time error is preferred locally when multiple matches are possible.
    """
    if not math.isfinite(tolerance_seconds) or tolerance_seconds < 0:
        raise ValueError("tolerance_seconds must be finite and nonnegative")
    if any(not math.isfinite(t) for t in [*predicted, *actual]):
        raise ValueError("All event timestamps must be finite")

    eligible = [sorted(
        (j for j, value in enumerate(actual) if abs(t - value) <= tolerance_seconds),
        key=lambda j: (abs(t - actual[j]), j)
    ) for t in predicted]

    label_owner: dict[int, int] = {}

    def augment(pred_i: int, seen: set[int]) -> bool:
        for label_j in eligible[pred_i]:
            if label_j in seen:
                continue
            seen.add(label_j)
            if label_j not in label_owner or augment(label_owner[label_j], seen):
                label_owner[label_j] = pred_i
                return True
        return False

    for pred_i in range(len(predicted)):
        augment(pred_i, set())

    return sorted(
        ((pred_i, label_j, abs(predicted[pred_i] - actual[label_j]))
         for label_j, pred_i in label_owner.items()),
        key=lambda pair: pair[0]
    )


def event_metrics(predicted: list[float], actual: list[float], tolerance_seconds: float = 5.0) -> dict:
    """One-to-one candidate spotting precision / recall / F1 at a time tolerance.

    Label *every* relevant event in the clip before interpreting precision;
    labeling only goals makes unrelated true highlights look like false positives.
    """
    tp = len(match_events(predicted, actual, tolerance_seconds))
    fp = len(predicted) - tp
    fn = len(actual) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positives": tp, "false_positives": fp, "false_negatives": fn,
        "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
    }
