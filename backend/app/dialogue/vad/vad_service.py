from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import numpy as np

from app.dialogue.vad.silero_vad import SileroVadModel
from app.utils.audio_constants import BUFFER_SIZE
from app.utils.audio_enhancer import AudioEnhancer
from app.utils.opus_processor import OpusProcessor

logger = logging.getLogger("vad_service")


class VadStatus(str, Enum):
    NO_SPEECH = "NO_SPEECH"
    SPEECH_START = "SPEECH_START"
    SPEECH_CONTINUE = "SPEECH_CONTINUE"
    SPEECH_END = "SPEECH_END"
    ERROR = "ERROR"


@dataclass
class VadResult:
    status: VadStatus
    data: Optional[bytes]

    def is_speech_active(self) -> bool:
        return self.status in (VadStatus.SPEECH_START, VadStatus.SPEECH_CONTINUE)

    def is_speech_end(self) -> bool:
        return self.status == VadStatus.SPEECH_END


class _VadState:
    def __init__(self, pre_buffer_ms: int) -> None:
        self.speaking = False
        self.speech_time = 0.0
        self.silence_time = 0.0
        self.silence_duration_ms = 0
        self.total_audio_duration_ms = 0
        self.consecutive_silence_frames = 0
        self.consecutive_speech_frames = 0
        self.silence_frame_count = 0
        self.avg_energy = 0.0
        self.probs: List[float] = []
        self.original_probs: List[float] = []
        self.frame_counter = 0
        self.silero_state = [[[0.0] * 128] * 1] * 2

        self.pre_buffer: List[bytes] = []
        self.pre_buffer_size = 0
        self.max_pre_buffer_size = pre_buffer_ms * 32

        self.pcm_data: List[bytes] = []
        self.opus_data: List[bytes] = []

        self.pcm_accumulator = bytearray()
        self.last_accum_time = time.time()

    def set_speaking(self, speaking: bool) -> None:
        self.speaking = speaking
        if speaking:
            self.speech_time = time.time()
            self.silence_time = 0.0
        elif self.silence_time == 0.0:
            self.silence_time = time.time()

    def get_silence_duration(self) -> int:
        if self.silence_time == 0.0:
            return 0
        return int((time.time() - self.silence_time) * 1000)

    def update_silence(self, is_silent: bool, frame_duration_ms: int) -> None:
        self.total_audio_duration_ms += frame_duration_ms
        if is_silent:
            self.consecutive_silence_frames += 1
            self.consecutive_speech_frames = 0
            self.silence_duration_ms += frame_duration_ms
            if self.silence_time == 0.0:
                self.silence_time = time.time()
        else:
            self.consecutive_speech_frames += 1
            if self.consecutive_speech_frames >= 2:
                self.consecutive_silence_frames = 0
                self.silence_duration_ms = 0
                self.silence_time = 0.0
                self.silence_frame_count = 0

    def update_energy(self, energy: float, is_silent: bool) -> None:
        if self.avg_energy == 0.0:
            self.avg_energy = energy
        else:
            smoothing = 0.85 if is_silent else 0.95
            self.avg_energy = smoothing * self.avg_energy + (1 - smoothing) * energy

    def add_original_prob(self, prob: float) -> None:
        self.original_probs.append(prob)
        if len(self.original_probs) > 10:
            self.original_probs.pop(0)
        self.frame_counter += 1

    def get_last_original_prob(self) -> float:
        return self.original_probs[-1] if self.original_probs else 0.0

    def add_to_pre_buffer(self, data: bytes) -> None:
        if self.speaking:
            return
        self.pre_buffer.append(bytes(data))
        self.pre_buffer_size += len(data)
        while self.pre_buffer_size > self.max_pre_buffer_size and self.pre_buffer:
            removed = self.pre_buffer.pop(0)
            self.pre_buffer_size -= len(removed)

    def drain_pre_buffer(self) -> bytes:
        if not self.pre_buffer:
            return b""
        result = b"".join(self.pre_buffer)
        self.pre_buffer.clear()
        self.pre_buffer_size = 0
        return result

    def accumulate(self, pcm: bytes) -> None:
        if pcm:
            self.pcm_accumulator.extend(pcm)
            self.last_accum_time = time.time()

    def drain_accumulator(self) -> bytes:
        data = bytes(self.pcm_accumulator)
        self.pcm_accumulator = bytearray()
        return data

    def get_accum_size(self) -> int:
        return len(self.pcm_accumulator)

    def is_accum_timed_out(self) -> bool:
        return (time.time() - self.last_accum_time) > 0.3

    def add_pcm(self, pcm: bytes) -> None:
        if pcm:
            self.pcm_data.append(bytes(pcm))

    def add_opus(self, opus: bytes) -> None:
        if opus:
            self.opus_data.append(bytes(opus))

    def reset(self) -> None:
        self.speaking = False
        self.speech_time = 0.0
        self.silence_time = 0.0
        self.silence_duration_ms = 0
        self.total_audio_duration_ms = 0
        self.consecutive_silence_frames = 0
        self.consecutive_speech_frames = 0
        self.silence_frame_count = 0
        self.avg_energy = 0.0
        self.probs.clear()
        self.original_probs.clear()
        self.frame_counter = 0
        self.silero_state = [[[0.0] * 128] * 1] * 2
        self.pre_buffer.clear()
        self.pre_buffer_size = 0
        self.pcm_data.clear()
        self.opus_data.clear()
        self.pcm_accumulator = bytearray()
        self.last_accum_time = time.time()


class VadService:
    MIN_PCM_LENGTH = 960
    LOG_FRAME_INTERVAL = 1
    SILENCE_FRAME_THRESHOLD = 2

    def __init__(self, role_service, session_manager, vad_model: Optional[SileroVadModel] = None) -> None:
        self._states: Dict[str, _VadState] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._enhancers: Dict[str, AudioEnhancer] = {}
        self._role_service = role_service
        self._session_manager = session_manager
        self._vad_model = vad_model or SileroVadModel()
        self._pre_buffer_ms = 500
        self._tail_keep_ms = 300
        self._audio_enhancement_enabled = False
        self._opus_processor = OpusProcessor()

    def configure(self, pre_buffer_ms: int, tail_keep_ms: int, enhancement_enabled: bool) -> None:
        self._pre_buffer_ms = pre_buffer_ms
        self._tail_keep_ms = tail_keep_ms
        self._audio_enhancement_enabled = enhancement_enabled

    def init_session(self, session_id: str) -> None:
        with self._get_lock(session_id):
            state = self._states.get(session_id)
            if state is None:
                state = _VadState(self._pre_buffer_ms)
                self._states[session_id] = state
            else:
                state.reset()
            logger.info("VAD 初始化: %s", session_id)

    def is_session_initialized(self, session_id: str) -> bool:
        with self._get_lock(session_id):
            return session_id in self._states

    def reset_session(self, session_id: str) -> None:
        with self._get_lock(session_id):
            state = self._states.pop(session_id, None)
            if state:
                state.reset()
            self._locks.pop(session_id, None)
            enhancer = self._enhancers.pop(session_id, None)
            if enhancer:
                enhancer.reset()
            logger.info("VAD 重置: %s", session_id)

    def process_audio(self, session_id: str, opus_data: bytes) -> Optional[VadResult]:
        if not self.is_session_initialized(session_id):
            return None

        with self._get_lock(session_id):
            try:
                speech_threshold = 0.4
                silence_threshold = 0.3
                energy_threshold = 0.001
                silence_timeout_ms = 800
                device = self._session_manager.get_device_config(session_id)
                if device and device.get("roleId"):
                    role = self._role_service.select_role_by_id(int(device.get("roleId")))
                    if role:
                        speech_threshold = float(role.get("vadSpeechTh") or speech_threshold)
                        silence_threshold = float(role.get("vadSilenceTh") or silence_threshold)
                        energy_threshold = float(role.get("vadEnergyTh") or energy_threshold)
                        silence_timeout_ms = int(role.get("vadSilenceMs") or silence_timeout_ms)

                state = self._states.setdefault(session_id, _VadState(self._pre_buffer_ms))

                state.add_opus(opus_data)

                pcm_data = self._opus_processor.opus_to_pcm(opus_data)
                if not pcm_data:
                    return VadResult(VadStatus.NO_SPEECH, None)

                samples = self._bytes_to_floats(pcm_data)
                enhanced_pcm = pcm_data
                if self._audio_enhancement_enabled:
                    enhancer = self._get_enhancer(session_id)
                    samples = enhancer.process(samples).tolist()
                    enhanced_pcm = self._floats_to_bytes(samples)

                energy = self._calc_energy(samples)
                speech_prob = self._detect_speech(state, samples)
                speech_prob = min(1.0, speech_prob)
                state.add_original_prob(speech_prob)
                state.add_to_pre_buffer(enhanced_pcm)

                if len(enhanced_pcm) < self.MIN_PCM_LENGTH and not state.speaking:
                    state.accumulate(enhanced_pcm)
                    if state.get_accum_size() < self.MIN_PCM_LENGTH and not state.is_accum_timed_out():
                        return VadResult(VadStatus.NO_SPEECH, None)
                    enhanced_pcm = state.drain_accumulator()
                    if not enhanced_pcm:
                        return VadResult(VadStatus.NO_SPEECH, None)
                    samples = self._bytes_to_floats(enhanced_pcm)
                    if self._audio_enhancement_enabled:
                        enhancer = self._get_enhancer(session_id)
                        samples = enhancer.process(samples).tolist()
                        enhanced_pcm = self._floats_to_bytes(samples)
                    energy = self._calc_energy(samples)
                    speech_prob = self._detect_speech(state, samples)
                    speech_prob = min(1.0, speech_prob)

                frame_duration_ms = int(len(pcm_data) / 32)
                is_initial = state.frame_counter < 10
                if is_initial:
                    has_energy = energy > energy_threshold * 0.3
                    is_speech = speech_prob > speech_threshold * 0.6 and has_energy
                else:
                    has_energy = energy > energy_threshold
                    is_speech = speech_prob > speech_threshold and has_energy

                is_very_low = energy < energy_threshold
                is_silence = (
                    speech_prob < silence_threshold
                    or (speech_prob < speech_threshold and not has_energy)
                    or is_very_low
                )

                state.update_energy(energy, is_silence)
                state.update_silence(is_silence, frame_duration_ms)

                if not state.speaking and is_speech:
                    state.pcm_data.clear()
                    state.set_speaking(True)
                    state.silence_frame_count = 0
                    state.pcm_accumulator = bytearray()
                    state.last_accum_time = time.time()
                    pre_buffer = state.drain_pre_buffer()
                    result = pre_buffer if pre_buffer else enhanced_pcm
                    state.add_pcm(result)
                    return VadResult(VadStatus.SPEECH_START, result)

                if state.speaking and is_silence:
                    silence_duration = state.get_silence_duration()
                    if silence_duration > silence_timeout_ms:
                        state.set_speaking(False)
                        silence_to_remove = silence_duration - self._tail_keep_ms
                        if silence_to_remove > 0:
                            total_silence_frames = state.silence_frame_count
                            frames_to_remove = 0
                            if total_silence_frames > 0 and silence_duration > 0:
                                frames_to_remove = min(
                                    int((total_silence_frames * silence_to_remove) / silence_duration + 0.999),
                                    total_silence_frames,
                                )
                            for _ in range(frames_to_remove):
                                if state.pcm_data:
                                    state.pcm_data.pop()
                                if state.opus_data:
                                    state.opus_data.pop()
                        state.silence_frame_count = 0
                        enhancer = self._enhancers.get(session_id)
                        if enhancer:
                            enhancer.reset()
                        state.silero_state = [[[0.0] * 128] * 1] * 2
                        state.pcm_accumulator = bytearray()
                        state.last_accum_time = time.time()
                        return VadResult(VadStatus.SPEECH_END, enhanced_pcm)

                    state.add_pcm(enhanced_pcm)
                    state.silence_frame_count += 1
                    return VadResult(VadStatus.SPEECH_CONTINUE, enhanced_pcm)

                if state.speaking:
                    state.add_pcm(enhanced_pcm)
                    state.silence_frame_count = 0
                    return VadResult(VadStatus.SPEECH_CONTINUE, enhanced_pcm)

                return VadResult(VadStatus.NO_SPEECH, None)
            except Exception as exc:
                logger.error("VAD 处理失败: %s", exc, exc_info=True)
                return VadResult(VadStatus.ERROR, None)

    def get_pcm_data(self, session_id: str) -> List[bytes]:
        with self._get_lock(session_id):
            state = self._states.get(session_id)
            return state.pcm_data.copy() if state else []

    def get_opus_data(self, session_id: str) -> List[bytes]:
        with self._get_lock(session_id):
            state = self._states.get(session_id)
            return state.opus_data.copy() if state else []

    def _get_lock(self, session_id: str) -> threading.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = threading.Lock()
        return self._locks[session_id]

    def _get_enhancer(self, session_id: str) -> AudioEnhancer:
        if session_id not in self._enhancers:
            self._enhancers[session_id] = AudioEnhancer()
        return self._enhancers[session_id]

    def _detect_speech(self, state: _VadState, samples: List[float]) -> float:
        if not samples:
            return 0.0
        try:
            if len(samples) == BUFFER_SIZE:
                result = self._vad_model.infer(samples, state.silero_state)
                state.silero_state = result.state
                return result.probability
            if len(samples) < BUFFER_SIZE:
                padded = samples + [0.0] * (BUFFER_SIZE - len(samples))
                result = self._vad_model.infer(padded, state.silero_state)
                state.silero_state = result.state
                return result.probability
            max_prob = 0.0
            step = BUFFER_SIZE // 2
            for offset in range(0, len(samples) - BUFFER_SIZE + 1, step):
                chunk = samples[offset : offset + BUFFER_SIZE]
                result = self._vad_model.infer(chunk, state.silero_state)
                state.silero_state = result.state
                max_prob = max(max_prob, result.probability)
            return max_prob
        except Exception as exc:
            logger.error("VAD 检测失败: %s", exc)
            return 0.0

    @staticmethod
    def _bytes_to_floats(pcm: bytes) -> List[float]:
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        return samples.tolist()

    @staticmethod
    def _floats_to_bytes(samples: List[float]) -> bytes:
        arr = np.array(samples, dtype=np.float32)
        arr = np.clip(arr, -1.0, 1.0)
        pcm = (arr * 32767.0).astype(np.int16)
        return pcm.tobytes()

    @staticmethod
    def _calc_energy(samples: List[float]) -> float:
        if not samples:
            return 0.0
        return float(np.mean(np.abs(samples)))


__all__ = ["VadService", "VadStatus", "VadResult"]
