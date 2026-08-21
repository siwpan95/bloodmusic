"""
全局常量 —— 采样率、BPM、默认音量等基线的唯一来源。
"""

# ── 音频引擎基线 ──
SR = 44100               # 采样率 (Hz)
BPM_DEFAULT = 120        # 默认 BPM
BEAT_DEFAULT = 60.0 / BPM_DEFAULT

# ── 默认音量 ──
VOL_SFX = 0.35
VOL_MUSIC = 0.18
VOL_PREVIEW = 0.25

# ── WAV 格式 ──
WAV_BIT_DEPTH = 16
WAV_MAX_AMP = 2 ** (WAV_BIT_DEPTH - 1) - 1  # 32767

# ── 导出标准 ──
NORMALIZE_DBFS = -1.0                    # 导出归一化目标 (dBFS)
DEFAULT_OGG_BITRATE = 128000             # OGG 默认比特率 (bps)
