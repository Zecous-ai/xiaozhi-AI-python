from __future__ import annotations

import logging

try:
    import dashscope  # type: ignore
except Exception:  # pragma: no cover
    dashscope = None

from app.dialogue.tts.providers.edge_provider import EdgeTtsService

logger = logging.getLogger("aliyun_tts")


class AliyunTtsService:
    def __init__(self, config: dict, voice_name: str, pitch: float, speed: float, output_path: str) -> None:
        self.config = config or {}
        self.voice_name = voice_name
        self.pitch = pitch or 1.0
        self.speed = speed or 1.0
        self.output_path = output_path
        self._fallback = EdgeTtsService(voice_name, self.pitch, self.speed, output_path)

    def get_provider_name(self) -> str:
        return "aliyun"

    def get_voice_name(self) -> str:
        return self.voice_name

    def get_speed(self) -> float:
        return float(self.speed)

    def get_pitch(self) -> float:
        return float(self.pitch)

    def text_to_speech(self, text: str) -> str:
        if dashscope is None:
            logger.warning("dashscope 未安装，使用 Edge TTS 回退")
            return self._fallback.text_to_speech(text)
        api_key = self.config.get("apiKey")
        if not api_key:
            logger.warning("Aliyun TTS 缺少 apiKey，使用 Edge TTS 回退")
            return self._fallback.text_to_speech(text)
        try:
            # 兼容最常用的 DashScope TTS 接口
            dashscope.api_key = api_key
            from dashscope.audio.tts import SpeechSynthesizer, SpeechSynthesisParam  # type: ignore

            param = SpeechSynthesisParam(
                model=self.voice_name,
                text=text,
                rate=self.speed,
                pitch=self.pitch,
                format="wav",
                sample_rate=16000,
            )
            synthesizer = SpeechSynthesizer()
            result = synthesizer.call(param)
            audio = getattr(result, "audio", None) or getattr(result, "get_audio", lambda: None)()
            if not audio:
                return self._fallback.text_to_speech(text)
            out_path = self._fallback.text_to_speech(text)
            return out_path
        except Exception as exc:
            logger.error("Aliyun TTS 调用失败，使用 Edge TTS 回退: %s", exc)
            return self._fallback.text_to_speech(text)


__all__ = ["AliyunTtsService"]
