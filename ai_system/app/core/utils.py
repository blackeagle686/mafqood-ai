"""Utility helpers for models and preprocessing."""
import logging

logger = logging.getLogger(__name__)


def ensure_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]
