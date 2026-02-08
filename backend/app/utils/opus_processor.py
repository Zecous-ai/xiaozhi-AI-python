from __future__ import annotations

import logging
from array import array
from typing import List, Optional

try:
    from opuslib import Decoder, Encoder, APPLICATION_AUDIO
except Exception:  # pragma: no cover - 运行环境可能缺少 libopus
    Decoder = None
    Encoder = None
    APPLICATION_AUDIO = None

from app.utils.audio_constants import CHANNELS, FRAME_SIZE, SAMPLE_RATE

logger = logging.getLogger("opus_processor")


class LeftoverState:
    def __init__(self) -> None:
        self.leftover_buffer = array("h", [0] * FRAME_SIZE)
        self.leftover_count = 0
        self.is_first = True

    def clear(self) -> None:
        self.leftover_count = 0
        self.is_first = True
        for i in range(len(self.leftover_buffer)):
            self.leftover_buffer[i] = 0


class OpusProcessor:
    def __init__(self) -> None:
        if Decoder is None or Encoder is None:
            self.decoder = None
            self.encoder = None
        else:
            self.decoder = Decoder(SAMPLE_RATE, CHANNELS)
            self.encoder = Encoder(SAMPLE_RATE, CHANNELS, APPLICATION_AUDIO)
        self.leftover = LeftoverState()

    def opus_to_pcm(self, data: bytes) -> bytes:
        if not data:
            return b""
        if self.decoder is None:
            logger.error("Opus 解码器不可用，请安装 libopus/opuslib")
            return b""
        try:
            pcm = self.decoder.decode(data, FRAME_SIZE, False)
            return pcm
        except Exception as exc:
            logger.warning("Opus 解码失败: %s", exc)
            self.decoder = Decoder(SAMPLE_RATE, CHANNELS) if Decoder else None
            return b""

    def pcm_to_opus(self, pcm: bytes, is_stream: bool) -> List[bytes]:
        if not pcm:
            return []
        if self.encoder is None:
            logger.error("Opus 编码器不可用，请安装 libopus/opuslib")
            return []

        # PCM 必须是 16-bit little endian
        if len(pcm) % 2 != 0:
            pcm = pcm[:-1]
        shorts = array("h")
        shorts.frombytes(pcm)

        frames: List[bytes] = []
        state = self.leftover

        if is_stream and (state.leftover_count > 0 or not state.is_first):
            combined = array("h", state.leftover_buffer[: state.leftover_count])
            combined.extend(shorts)
        else:
            combined = array("h", shorts)
            if is_stream:
                state.is_first = False

        frame_count = len(combined) // FRAME_SIZE
        remaining = len(combined) % FRAME_SIZE

        for i in range(frame_count):
            start = i * FRAME_SIZE
            frame = combined[start : start + FRAME_SIZE]
            try:
                encoded = self.encoder.encode(frame.tobytes(), FRAME_SIZE)
                if encoded:
                    frames.append(encoded)
            except Exception as exc:
                logger.warning("Opus 编码失败: %s", exc)

        if is_stream:
            state.leftover_count = remaining
            if remaining > 0:
                if len(state.leftover_buffer) < remaining:
                    state.leftover_buffer = array("h", [0] * FRAME_SIZE)
                for i in range(remaining):
                    state.leftover_buffer[i] = combined[frame_count * FRAME_SIZE + i]
            else:
                state.clear()

        return frames


__all__ = ["OpusProcessor", "LeftoverState"]
