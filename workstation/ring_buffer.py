"""无锁环形缓冲区 (Lock-Free Ring Buffer)

SPSC (Single Producer, Single Consumer) 实现，用于实时音频流传输。
基于 ctypes 原子操作 + 内存视图，避免 GIL 竞争。
"""

import ctypes
import threading
from typing import Optional


class RingBuffer:
    """无锁环形缓冲区 - 单生产者单消费者 (SPSC)

    使用独立的读写游标，避免锁争用。生产者只写 write_idx，
    消费者只写 read_idx，互不干扰。

    内存布局: [samples ... | padding]
               ^read_idx     ^write_idx
    """

    def __init__(self, capacity: int, channels: int = 2):
        """
        Args:
            capacity: 每通道样本容量 (必须是 2 的幂，内部自动对齐)
            channels: 声道数
        """
        # 对齐到 2 的幂
        self._capacity = 1
        while self._capacity < capacity:
            self._capacity <<= 1
        self._mask = self._capacity - 1
        self._channels = channels

        # 平面存储: buffer[channel][sample_index]
        import array
        self._buffer = [
            array.array("f", [0.0] * self._capacity)
            for _ in range(channels)
        ]

        # 原子游标 (使用 ctypes 保证跨线程可见性)
        self._read_idx = ctypes.c_uint64(0)
        self._write_idx = ctypes.c_uint64(0)

        # 统计
        self._overrun_count = ctypes.c_uint64(0)
        self._underrun_count = ctypes.c_uint64(0)

    # ---------- 属性 ----------

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def channels(self) -> int:
        return self._channels

    @property
    def readable(self) -> int:
        """可读样本数"""
        w = self._write_idx.value
        r = self._read_idx.value
        if w >= r:
            return w - r
        return self._capacity - r + w

    @property
    def writable(self) -> int:
        """可写样本数"""
        return self._capacity - self.readable

    @property
    def is_empty(self) -> bool:
        return self.readable == 0

    @property
    def is_full(self) -> bool:
        return self.writable == 0

    @property
    def overrun_count(self) -> int:
        return self._overrun_count.value

    @property
    def underrun_count(self) -> int:
        return self._underrun_count.value

    # ---------- 写入 (Producer) ----------

    def write(self, data: list[list[float]], n_samples: Optional[int] = None) -> int:
        """写入音频数据。

        Args:
            data: [channel][sample] 格式
            n_samples: 要写入的样本数，默认全部

        Returns:
            实际写入的样本数
        """
        if n_samples is None:
            if not data or not data[0]:
                return 0
            n_samples = len(data[0])

        available = self.writable
        if available < n_samples:
            self._overrun_count.value += 1
            n_samples = available
        if n_samples == 0:
            return 0

        import array
        w = self._write_idx.value & self._mask

        for ch in range(min(self._channels, len(data))):
            buf = self._buffer[ch]
            src = data[ch]
            first_part = min(n_samples, self._capacity - w)
            buf[w:w + first_part] = array.array("f", src[:first_part])
            if first_part < n_samples:
                remainder = n_samples - first_part
                buf[0:remainder] = array.array("f", src[first_part:first_part + remainder])

        self._write_idx.value += n_samples
        return n_samples

    def write_interleaved(self, data: list[float], n_samples: Optional[int] = None) -> int:
        """写入交错格式音频 [L,R,L,R,...]。

        Returns:
            实际写入的帧数
        """
        if n_samples is None:
            n_samples = len(data) // self._channels

        frame_count = min(n_samples, self.writable)
        if frame_count == 0:
            return 0

        w = self._write_idx.value & self._mask

        for i in range(frame_count):
            idx = (w + i) & self._mask
            for ch in range(self._channels):
                self._buffer[ch][idx] = data[i * self._channels + ch]

        self._write_idx.value += frame_count
        return frame_count

    # ---------- 读取 (Consumer) ----------

    def read(self, out: list[list[float]], n_samples: int) -> int:
        """读取音频数据到预分配的缓冲区。

        Args:
            out: [channel][sample] 预分配输出
            n_samples: 要读取的样本数

        Returns:
            实际读取的样本数
        """
        available = self.readable
        if available < n_samples:
            self._underrun_count.value += 1
            n_samples = available
            # 填充静音
            for ch_out in out:
                ch_out[n_samples:] = [0.0] * (len(ch_out) - n_samples)
        if n_samples == 0:
            for ch_out in out:
                ch_out[:] = [0.0] * len(ch_out)
            return 0

        r = self._read_idx.value & self._mask

        for ch in range(min(self._channels, len(out))):
            ch_out = out[ch]
            buf = self._buffer[ch]
            first_part = min(n_samples, self._capacity - r)
            ch_out[:first_part] = buf[r:r + first_part]
            if first_part < n_samples:
                remainder = n_samples - first_part
                ch_out[first_part:first_part + remainder] = buf[0:remainder]

        self._read_idx.value += n_samples
        return n_samples

    def read_interleaved(self, out: list[float], n_frames: int) -> int:
        """读取交错格式音频。

        Args:
            out: 预分配列表，长度 >= n_frames * channels
            n_frames: 要读取的帧数

        Returns:
            实际读取的帧数
        """
        available = self.readable
        actual = min(n_frames, available)
        if actual == 0:
            out[:] = [0.0] * len(out)
            self._underrun_count.value += 1
            return 0

        r = self._read_idx.value & self._mask

        for i in range(actual):
            idx = (r + i) & self._mask
            for ch in range(self._channels):
                out[i * self._channels + ch] = self._buffer[ch][idx]

        self._read_idx.value += actual
        return actual

    # ---------- 工具 ----------

    def reset(self) -> None:
        """清空缓冲区，重置游标"""
        self._read_idx.value = 0
        self._write_idx.value = 0
        self._overrun_count.value = 0
        self._underrun_count.value = 0

    def stats(self) -> dict:
        return {
            "capacity": self._capacity,
            "channels": self._channels,
            "readable": self.readable,
            "writable": self.writable,
            "fill_pct": self.readable / self._capacity * 100,
            "overruns": self._overrun_count.value,
            "underruns": self._underrun_count.value,
        }

    def __repr__(self):
        s = self.stats()
        return (f"<RingBuffer cap={s['capacity']} "
                f"fill={s['fill_pct']:.0f}% "
                f"over={s['overruns']} under={s['underruns']}>")


class RingBufferPool:
    """环形缓冲池：管理多个 RingBuffer，用于多轨并行处理"""

    def __init__(self, capacity: int, channels: int = 2,
                 pool_size: int = 32):
        self._pool: list[RingBuffer] = [
            RingBuffer(capacity, channels)
            for _ in range(pool_size)
        ]
        self._available: list[int] = list(range(pool_size))
        self._lock = threading.Lock()

    def acquire(self) -> Optional[RingBuffer]:
        """从池中获取一个缓冲区"""
        with self._lock:
            if self._available:
                idx = self._available.pop()
                return self._pool[idx]
        return None

    def release(self, buf: RingBuffer) -> None:
        """归还缓冲区"""
        buf.reset()
        with self._lock:
            try:
                idx = self._pool.index(buf)
                self._available.append(idx)
            except ValueError:
                pass  # 不属于此池

    @property
    def available_count(self) -> int:
        with self._lock:
            return len(self._available)

    @property
    def total(self) -> int:
        return len(self._pool)
