from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Tuple


@dataclass
class InferenceResult:
    probability: float
    state: list


class VadModel(Protocol):
    def initialize(self) -> None:
        ...

    def get_speech_probability(self, samples: list[float]) -> float:
        ...

    def infer(self, samples: list[float], prev_state: list | None) -> InferenceResult:
        ...

    def reset(self) -> None:
        ...

    def close(self) -> None:
        ...


__all__ = ["InferenceResult", "VadModel"]
