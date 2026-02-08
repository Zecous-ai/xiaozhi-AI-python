from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List

from app.dialogue.thread_player import ThreadPlayer
from app.dialogue.sentence import Sentence
from app.utils.audio_constants import OPUS_FRAME_DURATION_MS
from app.utils.audio_utils import read_as_opus, merge_audio_files

logger = logging.getLogger("file_player")


class FilePlayer(ThreadPlayer):
    ONLY_TEXT_SLEEP_TIME_MS = 500

    def __init__(self, session, message_service, session_manager, sys_message_service=None) -> None:
        super().__init__(session, message_service, session_manager)
        self._is_playing = True
        self._audio_files_to_merge: List[str] = []
        self._sys_message_service = sys_message_service

    def on_stop(self) -> None:
        self._is_playing = False
        logger.debug("FilePlayer停止播放 - SessionId: %s", self.session.session_id)

    def run(self) -> None:
        self._is_playing = True
        start_ts = time.time() * 1000.0
        play_position = -OPUS_FRAME_DURATION_MS * 2

        while self._is_playing and (
            not self.get_queue().empty()
            or (self.session.synthesizer and self.session.synthesizer.is_dialog() and not self.session.synthesizer.is_aborted())
        ):
            if self.get_queue().empty():
                time.sleep(0.06)
                continue
            try:
                sentence: Sentence = self.get_queue().get_nowait()
            except Exception:
                time.sleep(0.06)
                continue

            audio_path = sentence.audio_path
            text = sentence.text

            if audio_path is None:
                if text:
                    if sentence.is_only_emoji():
                        self.send_emotion(None)
                    else:
                        self.send_sentence_start(text)
                        self.send_emotion(None)
                    time.sleep(self.ONLY_TEXT_SLEEP_TIME_MS / 1000.0)
                continue

            self.send_sentence_start(text)
            self.send_emotion(None)

            if sentence.should_merge and audio_path:
                self._audio_files_to_merge.append(str(audio_path))

            opus_frames = read_as_opus(str(audio_path))
            if not opus_frames:
                continue

            for frame in opus_frames:
                if not self.session.is_open():
                    break
                if self.session.synthesizer and self.session.synthesizer.is_aborted():
                    self._is_playing = False
                    break
                self.session_manager.update_last_activity(self.session.session_id)
                target_send_time = start_ts + play_position
                delay = (target_send_time - (time.time() * 1000.0)) / 1000.0
                if delay > 0:
                    time.sleep(delay)
                self.send_opus_frame(frame)
                play_position += OPUS_FRAME_DURATION_MS

            play_position += OPUS_FRAME_DURATION_MS * 5

        time.sleep(0.5)
        self.send_stop()
        self._is_playing = False
        self._save_assistant_response()

    def _save_assistant_response(self) -> None:
        assistant_time_millis = self.session.assistant_time_millis
        if not assistant_time_millis:
            return
        if not self._audio_files_to_merge:
            return
        try:
            path = self.session.get_audio_path("assistant", assistant_time_millis)
            merge_audio_files(path, self._audio_files_to_merge)
            self._audio_files_to_merge.clear()
            if self._sys_message_service:
                device_id = self.session.sys_device.get("deviceId", "").replace("-", ":")
                role_id = self.session.sys_device.get("roleId")
                create_time = ""
                if assistant_time_millis:
                    create_time = datetime.fromtimestamp(assistant_time_millis / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
                if device_id and role_id and create_time:
                    self._sys_message_service.update_message_by_audio_file(device_id, int(role_id), "assistant", create_time, str(path))
        except Exception as exc:
            logger.error("保存助手音频失败: %s", exc)


__all__ = ["FilePlayer"]
