from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional


_FIELDS = (
    "cpu",
    "ram_gb",
    "storage_gb",
    "storage_type",
    "bandwidth_tb",
    "price_monthly",
)

_STORAGE_TYPES = ("nvme", "ssd", "hdd")


class MLSpecExtractor:
    """Lightweight ML-style extractor for infrastructure spec strings.

    Uses regex-based parsing and token-frequency priors learned from training data.
    """

    def __init__(self) -> None:
        self._storage_token_counts: Dict[str, Counter[str]] = {
            storage_type: Counter() for storage_type in _STORAGE_TYPES
        }
        self._storage_type_counts: Counter[str] = Counter()
        self._is_fitted = False

    def fit(self, training_data: Iterable[dict] | str | Path) -> "MLSpecExtractor":
        examples = self._load_examples(training_data)
        for row in examples:
            text = str(row.get("text", ""))
            storage_type = row.get("storage_type")
            if storage_type in _STORAGE_TYPES:
                self._storage_type_counts[storage_type] += 1
                tokens = _tokenize(text)
                self._storage_token_counts[storage_type].update(tokens)
        self._is_fitted = True
        return self

    def predict(self, text: str) -> dict:
        return self.extract_one(text)

    def extract_one(self, text: str) -> dict:
        text = text or ""
        cpu = _parse_cpu(text)
        ram_gb = _parse_ram(text)
        storage_gb, storage_type = _parse_storage(text)
        bandwidth_tb = _parse_bandwidth(text)
        price_monthly = _parse_price(text)

        if storage_type is None:
            storage_type = self._infer_storage_type(text)

        return {
            "cpu": cpu,
            "ram_gb": ram_gb,
            "storage_gb": storage_gb,
            "storage_type": storage_type,
            "bandwidth_tb": bandwidth_tb,
            "price_monthly": price_monthly,
        }

    def extract_many(self, texts: Iterable[str]) -> List[dict]:
        return [self.extract_one(text) for text in texts]

    def _infer_storage_type(self, text: str) -> Optional[str]:
        if not self._is_fitted:
            return None

        tokens = _tokenize(text)
        if not tokens:
            return None

        scores: Dict[str, int] = {}
        for storage_type in _STORAGE_TYPES:
            token_counts = self._storage_token_counts[storage_type]
            score = sum(token_counts.get(token, 0) for token in tokens)
            # Light prior toward frequent classes in small datasets.
            score += self._storage_type_counts.get(storage_type, 0)
            scores[storage_type] = score

        best_type = max(scores, key=scores.get)
        if scores[best_type] == 0:
            return None
        return best_type

    @staticmethod
    def _load_examples(training_data: Iterable[dict] | str | Path) -> List[dict]:
        if isinstance(training_data, (str, Path)):
            path = Path(training_data)
            rows = []
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    rows.append(json.loads(line))
            return rows
        return list(training_data)


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _to_gb(value: float, unit: str) -> float:
    unit = unit.lower()
    if unit == "tb":
        return value * 1024.0
    if unit == "mb":
        return value / 1024.0
    return value


def _to_tb(value: float, unit: str) -> float:
    unit = unit.lower()
    if unit == "gb":
        return value / 1024.0
    if unit == "mb":
        return value / (1024.0 * 1024.0)
    return value


def _round_or_none(value: Optional[float], places: int = 3) -> Optional[float]:
    if value is None:
        return None
    return round(value, places)


def _parse_cpu(text: str) -> Optional[int]:
    m = re.search(r"\b(\d{1,3})\s*(?:v?cpu|cores?)\b", text, flags=re.I)
    if m:
        return int(m.group(1))

    word_map = {
        "single": 1,
        "dual": 2,
        "quad": 4,
        "hexa": 6,
        "octa": 8,
        "deca": 10,
    }
    m = re.search(r"\b(single|dual|quad|hexa|octa|deca)\s*core\b", text, flags=re.I)
    if m:
        return word_map[m.group(1).lower()]
    return None


def _parse_ram(text: str) -> Optional[float]:
    patterns = [
        r"\b(\d+(?:\.\d+)?)\s*(mb|gb|tb)\s*(?:ram|memory)\b",
        r"\b(?:ram|memory)\s*[:=-]?\s*(\d+(?:\.\d+)?)\s*(mb|gb|tb)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return _round_or_none(_to_gb(float(m.group(1)), m.group(2)))
    return None


def _parse_storage(text: str) -> tuple[Optional[float], Optional[str]]:
    type_m = re.search(r"\b(nvme|ssd|hdd|solid[-\s]?state)\b", text, flags=re.I)
    storage_type = None
    if type_m:
        raw = type_m.group(1).lower().replace(" ", "-")
        storage_type = "ssd" if "solid" in raw else raw

    patterns = [
        r"\b(?:storage|disk|drive)\s*[:=-]?\s*(\d+(?:\.\d+)?)\s*(mb|gb|tb)\b",
        r"\b(\d+(?:\.\d+)?)\s*(mb|gb|tb)\s*(?:storage|disk|drive|nvme|ssd|hdd|solid[-\s]?state)\b",
        r"\b(?:nvme|ssd|hdd|solid[-\s]?state)\s*(\d+(?:\.\d+)?)\s*(mb|gb|tb)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return _round_or_none(_to_gb(float(m.group(1)), m.group(2))), storage_type
    return None, storage_type


def _parse_bandwidth(text: str) -> Optional[float]:
    patterns = [
        r"\b(\d+(?:\.\d+)?)\s*(mb|gb|tb)\s*(?:bandwidth|transfer|traffic)\b",
        r"\b(?:bandwidth|transfer|traffic)\s*[:=-]?\s*(\d+(?:\.\d+)?)\s*(mb|gb|tb)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return _round_or_none(_to_tb(float(m.group(1)), m.group(2)))
    return None


def _parse_price(text: str) -> Optional[float]:
    patterns = [
        r"\$\s*(\d+(?:\.\d+)?)\s*(?:/\s*mo|/\s*month|per\s*month|monthly|mo\b|month\b)",
        r"\bmonthly\s*[:=-]?\s*\$?\s*(\d+(?:\.\d+)?)\b",
        r"\b(\d+(?:\.\d+)?)\s*\$\s*(?:/\s*mo|/\s*month|per\s*month|monthly|mo\b|month\b)?",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return _round_or_none(float(m.group(1)), places=2)
    return None
