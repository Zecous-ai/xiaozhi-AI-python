from __future__ import annotations

import logging
import os
import shutil
import subprocess
import uuid
import wave
from pathlib import Path
from typing import List

from app.core.config import settings
from app.utils.audio_constants import (
    AUDIO_PATH,
    BITRATE,
    CHANNELS,
    FRAME_SIZE,
    OPUS_FRAME_DURATION_MS,
    SAMPLE_RATE,
)
from app.utils.opus_processor import OpusProcessor

logger = logging.getLogger("audio_utils")


def _audio_dir() -> Path:
    return Path(settings.audio_path or AUDIO_PATH)


def ensure_audio_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def save_as_wav(path: Path, audio_data: bytes) -> None:
    ensure_audio_dir(path)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(audio_data)


def save_as_mp3(pcm_data: bytes) -> str | None:
    audio_dir = _audio_dir()
    audio_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    pcm_path = audio_dir / f"{file_id}.pcm"
    mp3_path = audio_dir / f"{file_id}.mp3"
    try:
        pcm_path.write_bytes(pcm_data)
        if not shutil.which("ffmpeg"):
            logger.error("ffmpeg 不可用，无法生成 mp3")
            return None
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "s16le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            str(CHANNELS),
            "-i",
            str(pcm_path),
            "-b:a",
            str(BITRATE),
            "-f",
            "mp3",
            str(mp3_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.error("ffmpeg 转码失败: %s", result.stderr)
            return None
        if not mp3_path.exists():
            return None
        return str(mp3_path)
    finally:
        try:
            if pcm_path.exists():
                pcm_path.unlink()
        except Exception:
            logger.warning("清理临时 PCM 失败", exc_info=True)


def read_as_pcm(audio_path: str) -> bytes:
    path = Path(audio_path)
    if not path.exists():
        return b""

    suffix = path.suffix.lower()
    if suffix == ".pcm":
        return path.read_bytes()
    if suffix == ".wav":
        with wave.open(str(path), "rb") as wav:
            if wav.getnchannels() != CHANNELS or wav.getframerate() != SAMPLE_RATE:
                return _ffmpeg_to_pcm(path)
            return wav.readframes(wav.getnframes())
    return _ffmpeg_to_pcm(path)


def _ffmpeg_to_pcm(path: Path) -> bytes:
    if not shutil.which("ffmpeg"):
        logger.error("ffmpeg 不可用，无法读取音频: %s", path)
        return b""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        str(CHANNELS),
        "-ar",
        str(SAMPLE_RATE),
        "pipe:1",
    ]
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        logger.error("ffmpeg 解码失败: %s", result.stderr.decode(errors="ignore"))
        return b""
    return result.stdout


def read_as_opus(audio_path: str, is_stream: bool = False) -> List[bytes]:
    pcm = read_as_pcm(audio_path)
    if not pcm:
        return []
    return OpusProcessor().pcm_to_opus(pcm, is_stream)


def merge_audio_files(path: Path, audio_paths: List[str]) -> None:
    if not audio_paths:
        return
    if len(audio_paths) == 1:
        src = Path(audio_paths[0])
        if src.exists():
            ensure_audio_dir(path)
            path.write_bytes(read_as_pcm(str(src)))
        return

    chunks = []
    for audio_path in audio_paths:
        pcm = read_as_pcm(audio_path)
        if pcm:
            chunks.append(pcm)
    if not chunks:
        return
    merged = b"".join(chunks)
    save_as_wav(path, merged)
    for audio_path in audio_paths:
        try:
            p = Path(audio_path)
            if p.exists():
                p.unlink()
        except Exception:
            logger.warning("删除音频失败: %s", audio_path)


__all__ = [
    "AUDIO_PATH",
    "FRAME_SIZE",
    "SAMPLE_RATE",
    "CHANNELS",
    "BITRATE",
    "OPUS_FRAME_DURATION_MS",
    "save_as_wav",
    "save_as_mp3",
    "merge_audio_files",
    "read_as_pcm",
    "read_as_opus",
]
