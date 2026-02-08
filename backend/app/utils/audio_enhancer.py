from __future__ import annotations

import logging
from typing import List

import numpy as np

logger = logging.getLogger("audio_enhancer")


class AudioEnhancer:
    def __init__(self) -> None:
        self._noise_floor = 0.0
        self._initialized = True

    def reset(self) -> None:
        self._noise_floor = 0.0

    def process(self, samples: np.ndarray | List[float]) -> np.ndarray:
        if samples is None:
            return np.array([], dtype=np.float32)
        data = np.asarray(samples, dtype=np.float32)
        if data.size == 0:
            return data

        # 简易能量归一与噪声门控，避免过度处理
        energy = float(np.mean(np.abs(data)))
        if self._noise_floor == 0.0:
            self._noise_floor = energy
        if energy < self._noise_floor * 0.5:
            return data

        peak = np.max(np.abs(data))
        if peak > 1e-6:
            data = data / peak * min(peak, 0.9)
        return data


__all__ = ["AudioEnhancer"]
