"""实时音频预览播放器 (sounddevice)"""

import threading
from typing import Optional

import numpy as np
import sounddevice as sd

from ..core.constants import SR


class PreviewPlayer:
    """实时音频预览播放器。

    Usage:
        player = PreviewPlayer()
        player.play(audio_array)      # 播放
        player.play(audio_array, loop=True)  # 循环
        player.stop()
    """

    def __init__(self):
        self.current_stream: Optional[sd.OutputStream] = None
        self._audio_buffer: np.ndarray = np.array([])
        self._play_pos = 0
        self._is_playing = False
        self._lock = threading.Lock()
        self._loop = False

    def _callback(self, outdata, frames, _time_info, _status):
        with self._lock:
            if not self._is_playing or len(self._audio_buffer) == 0:
                outdata[:] = np.zeros((frames, 1), dtype=np.float32)
                return

            end_pos = self._play_pos + frames
            if end_pos >= len(self._audio_buffer):
                if self._loop:
                    remaining = frames - (len(self._audio_buffer) - self._play_pos)
                    tail = self._audio_buffer[self._play_pos:]
                    head = self._audio_buffer[:remaining]
                    chunk = np.concatenate([tail, head])
                    self._play_pos = remaining
                else:
                    chunk = self._audio_buffer[self._play_pos:
                                               self._play_pos + frames]
                    pad_needed = frames - len(chunk)
                    if pad_needed > 0:
                        chunk = np.pad(chunk, (0, pad_needed))
                    self._is_playing = False
                    self._play_pos = 0
            else:
                chunk = self._audio_buffer[self._play_pos:end_pos]
                self._play_pos = end_pos

            if chunk.ndim == 1:
                outdata[:, 0] = chunk
            elif chunk.ndim == 2 and chunk.shape[1] == 1:
                outdata[:, 0] = chunk.flatten()
            elif chunk.ndim == 2 and chunk.shape[1] == 2:
                outdata[:, 0] = chunk[:, 0]
            else:
                outdata[:, 0] = chunk.flatten()[:frames]

    def play(self, audio_data: np.ndarray, loop: bool = False):
        self.stop()
        with self._lock:
            self._audio_buffer = audio_data.astype(np.float32)
            if self._audio_buffer.ndim == 0 or len(self._audio_buffer) == 0:
                return
            if self._audio_buffer.ndim == 2 and self._audio_buffer.shape[1] >= 2:
                self._audio_buffer = self._audio_buffer[:, 0]
            self._play_pos = 0
            self._is_playing = True
            self._loop = loop

        try:
            self.current_stream = sd.OutputStream(
                samplerate=SR, channels=1, dtype="float32",
                callback=self._callback, blocksize=1024, latency="low",
            )
            self.current_stream.start()
        except Exception as _e:
            import sys
            print(f"[PreviewPlayer] 音频设备错误：{_e}", file=sys.stderr)
            self._is_playing = False

    def stop(self):
        with self._lock:
            self._is_playing = False
        if self.current_stream is not None:
            try:
                self.current_stream.stop()
                self.current_stream.close()
            except Exception:
                pass
            self.current_stream = None

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._is_playing
