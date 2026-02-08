from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import onnxruntime as ort

from app.core.config import settings
from app.dialogue.vad.vad_model import InferenceResult
from app.utils.audio_constants import BUFFER_SIZE, SAMPLE_RATE

logger = logging.getLogger("silero_vad")


class SileroVadModel:
    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path or settings.vad_model_path
        self.session: Optional[ort.InferenceSession] = None
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.initialized = False

    def initialize(self) -> None:
        if self.initialized:
            return
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.log_severity_level = 3
        self.session = ort.InferenceSession(self.model_path, sess_options=opts, providers=["CPUExecutionProvider"])
        self.reset()
        self.initialized = True
        logger.info("Silero VAD 初始化完成")

    def reset(self) -> None:
        self.state = np.zeros((2, 1, 128), dtype=np.float32)

    def close(self) -> None:
        self.session = None
        self.initialized = False

    def get_speech_probability(self, samples: list[float]) -> float:
        result = self.infer(samples, self.state.tolist())
        self.state = np.array(result.state, dtype=np.float32)
        return result.probability

    def infer(self, samples: list[float], prev_state: list | None) -> InferenceResult:
        if not self.initialized:
            self.initialize()
        if self.session is None:
            return InferenceResult(0.0, prev_state or self.state.tolist())
        if len(samples) != BUFFER_SIZE:
            raise ValueError(f"Silero VAD 输入必须为 {BUFFER_SIZE}")

        x = np.array([samples], dtype=np.float32)
        state = np.array(prev_state if prev_state is not None else self.state, dtype=np.float32)
        sr = np.array([SAMPLE_RATE], dtype=np.int64)

        try:
            outputs = self.session.run(None, {"input": x, "sr": sr, "state": state})
            prob = float(outputs[0][0][0])
            next_state = outputs[1].tolist()
            return InferenceResult(probability=prob, state=next_state)
        except Exception as exc:
            logger.error("Silero VAD 推理失败: %s", exc)
            return InferenceResult(0.0, prev_state or self.state.tolist())


__all__ = ["SileroVadModel"]
