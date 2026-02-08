from __future__ import annotations

# 音频基础常量，与 Java 版保持一致
AUDIO_PATH = "audio"
FRAME_SIZE = 960
SAMPLE_RATE = 16000
CHANNELS = 1
BITRATE = 48000
BUFFER_SIZE = 512
OPUS_FRAME_DURATION_MS = 60

__all__ = [
    "AUDIO_PATH",
    "FRAME_SIZE",
    "SAMPLE_RATE",
    "CHANNELS",
    "BITRATE",
    "BUFFER_SIZE",
    "OPUS_FRAME_DURATION_MS",
]
