"""SFX 音效预设库 — UI / 卡牌 / 战斗 / 系统"""

from typing import Dict

from ..core.oscillator import OscType
from ..core.envelope import EnvShape
from ..core.voice import SynthVoice
from ..effects.chain import EffectChain


# ═══════════════════════════════════════════════════════════
#  UI 音效
# ═══════════════════════════════════════════════════════════
UI_FX_PRESETS: Dict[str, SynthVoice] = {
    "button_click": SynthVoice(
        freq=800.0, osc_type=OscType.SQUARE, duration=0.06,
        volume=0.6, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(lp_filter_hz=4000, bit_crush=8),
        harmonics=[(1.5, 0.3)],
    ),
    "button_hover": SynthVoice(
        freq=1200.0, osc_type=OscType.SINE, duration=0.04,
        volume=0.35, env_shape=EnvShape.PERCUSSIVE, pitch_mod=3,
    ),
    "menu_open": SynthVoice(
        freq=440.0, osc_type=OscType.SINE, duration=0.25,
        volume=0.5, env_shape=EnvShape.SWELL, pitch_mod=7,
        effect_chain=EffectChain(reverb_mix=0.15, reverb_decay=0.4),
    ),
    "menu_close": SynthVoice(
        freq=660.0, osc_type=OscType.SINE, duration=0.22,
        volume=0.45, env_shape=EnvShape.REVERSE, pitch_mod=-5,
    ),
    "confirm": SynthVoice(
        freq=523.25, osc_type=OscType.TRIANGLE, duration=0.2,
        volume=0.55, env_shape=EnvShape.PERCUSSIVE,
        harmonics=[(2.0, 0.2)],
        effect_chain=EffectChain(reverb_mix=0.1),
    ),
    "cancel": SynthVoice(
        freq=330.0, osc_type=OscType.SAW, duration=0.18,
        volume=0.4, env_shape=EnvShape.PERCUSSIVE, pitch_mod=-4,
        effect_chain=EffectChain(lp_filter_hz=3000),
    ),
    "notification": SynthVoice(
        freq=880.0, osc_type=OscType.SINE, duration=0.12,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE,
        vibrato_rate=6, vibrato_depth=2,
    ),
    "error": SynthVoice(
        freq=200.0, osc_type=OscType.SQUARE, duration=0.25,
        volume=0.45, env_shape=EnvShape.PERCUSSIVE, pitch_mod=-7,
        effect_chain=EffectChain(distortion=0.3, bit_crush=6),
        harmonics=[(1.5, 0.4), (2.0, 0.2)],
    ),
    "scroll": SynthVoice(
        freq=600.0, osc_type=OscType.SINE, duration=0.03,
        volume=0.25, env_shape=EnvShape.PERCUSSIVE,
    ),
}

# ═══════════════════════════════════════════════════════════
#  卡牌音效
# ═══════════════════════════════════════════════════════════
CARD_FX_PRESETS: Dict[str, SynthVoice] = {
    "card_play": SynthVoice(
        freq=520.0, osc_type=OscType.TRIANGLE, duration=0.18,
        volume=0.6, env_shape=EnvShape.PLUCK, pitch_mod=5,
        effect_chain=EffectChain(reverb_mix=0.12),
        harmonics=[(2.0, 0.15), (3.0, 0.08)], detune=5,
    ),
    "card_draw": SynthVoice(
        freq=380.0, osc_type=OscType.SAW, duration=0.1,
        volume=0.45, env_shape=EnvShape.PERCUSSIVE, pitch_mod=-3,
        effect_chain=EffectChain(lp_filter_hz=5000, hp_filter_hz=150),
        harmonics=[(0.5, 0.2)],
    ),
    "card_hover": SynthVoice(
        freq=900.0, osc_type=OscType.SINE, duration=0.035,
        volume=0.28, env_shape=EnvShape.PERCUSSIVE, pitch_mod=4,
    ),
    "card_select": SynthVoice(
        freq=700.0, osc_type=OscType.TRIANGLE, duration=0.1,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE, pitch_mod=7,
        effect_chain=EffectChain(reverb_mix=0.08),
    ),
    "shuffle": SynthVoice(
        freq=300.0, osc_type=OscType.NOISE_WHITE, duration=0.35,
        volume=0.35, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(
            lp_filter_hz=6000, hp_filter_hz=400,
            reverb_mix=0.1, reverb_decay=0.25,
        ),
    ),
    "card_reveal": SynthVoice(
        freq=350.0, osc_type=OscType.SINE, duration=0.4,
        volume=0.5, env_shape=EnvShape.SWELL, pitch_mod=12,
        harmonics=[(2.0, 0.2), (3.0, 0.08)],
        effect_chain=EffectChain(reverb_mix=0.18, reverb_decay=0.5),
    ),
    "card_exhaust": SynthVoice(
        freq=250.0, osc_type=OscType.SAW, duration=0.3,
        volume=0.4, env_shape=EnvShape.REVERSE, pitch_mod=-8,
        effect_chain=EffectChain(lp_filter_hz=3000, reverb_mix=0.12),
    ),
    "card_upgrade": SynthVoice(
        freq=440.0, osc_type=OscType.SINE, duration=0.5,
        volume=0.55, env_shape=EnvShape.SWELL, pitch_mod=12,
        vibrato_rate=5, vibrato_depth=2,
        harmonics=[(2.0, 0.25), (3.0, 0.1), (4.0, 0.05)],
        effect_chain=EffectChain(reverb_mix=0.2, reverb_decay=0.6),
    ),
    "ethereal_pass": SynthVoice(
        freq=600.0, osc_type=OscType.SINE, duration=0.3,
        volume=0.4, env_shape=EnvShape.PAD,
        harmonics=[(2.0, 0.3), (3.0, 0.15), (4.0, 0.08), (5.0, 0.03)],
        vibrato_rate=4.5, vibrato_depth=3,
        effect_chain=EffectChain(
            reverb_mix=0.3, reverb_decay=0.8,
            lp_filter_hz=5000, stereo_width=0.4,
        ),
    ),
}

# ═══════════════════════════════════════════════════════════
#  战斗音效
# ═══════════════════════════════════════════════════════════
COMBAT_FX_PRESETS: Dict[str, SynthVoice] = {
    "attack_melee": SynthVoice(
        freq=180.0, osc_type=OscType.NOISE_BROWN, duration=0.15,
        volume=0.75, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(
            lp_filter_hz=2500, hp_filter_hz=80,
            distortion=0.4, bit_crush=8,
        ),
        harmonics=[(3.0, 0.3)],
    ),
    "attack_magic": SynthVoice(
        freq=1200.0, osc_type=OscType.SAW, duration=0.35,
        volume=0.6, env_shape=EnvShape.SWELL, pitch_mod=-8,
        harmonics=[(1.5, 0.4), (2.0, 0.25), (2.5, 0.15), (3.33, 0.1)],
        effect_chain=EffectChain(reverb_mix=0.25, reverb_decay=0.6, distortion=0.15),
    ),
    "block_hit": SynthVoice(
        freq=320.0, osc_type=OscType.SQUARE, duration=0.08,
        volume=0.65, env_shape=EnvShape.PERCUSSIVE, pitch_mod=-6,
        effect_chain=EffectChain(lp_filter_hz=2000, distortion=0.25, bit_crush=10),
    ),
    "damage_taken": SynthVoice(
        freq=150.0, osc_type=OscType.SAW, duration=0.3,
        volume=0.6, env_shape=EnvShape.REVERSE, pitch_mod=-12,
        effect_chain=EffectChain(
            lp_filter_hz=2000, reverb_mix=0.15,
            distortion=0.2, stereo_width=0.3,
        ),
    ),
    "heal": SynthVoice(
        freq=523.25, osc_type=OscType.SINE, duration=0.5,
        volume=0.5, env_shape=EnvShape.SWELL, pitch_mod=7,
        harmonics=[(2.0, 0.2), (3.0, 0.1)],
        vibrato_rate=5, vibrato_depth=2,
        effect_chain=EffectChain(reverb_mix=0.2, reverb_decay=0.7),
    ),
    "dodge": SynthVoice(
        freq=2000.0, osc_type=OscType.NOISE_WHITE, duration=0.08,
        volume=0.35, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(lp_filter_hz=8000, hp_filter_hz=3000),
    ),
    "critical_hit": SynthVoice(
        freq=280.0, osc_type=OscType.NOISE_BROWN, duration=0.25,
        volume=0.8, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(
            lp_filter_hz=3500, distortion=0.5, bit_crush=6, reverb_mix=0.15,
        ),
        harmonics=[(2.0, 0.3), (4.0, 0.15)],
    ),
    "enemy_death": SynthVoice(
        freq=200.0, osc_type=OscType.SAW, duration=0.6,
        volume=0.6, env_shape=EnvShape.REVERSE, pitch_mod=-16,
        effect_chain=EffectChain(
            lp_filter_hz=2500, reverb_mix=0.25, reverb_decay=1.0,
            distortion=0.2, stereo_width=0.5,
        ),
        harmonics=[(0.5, 0.3), (1.5, 0.2)],
    ),
    "player_hurt": SynthVoice(
        freq=100.0, osc_type=OscType.SQUARE, duration=0.2,
        volume=0.55, env_shape=EnvShape.PERCUSSIVE, pitch_mod=-5,
        effect_chain=EffectChain(lp_filter_hz=1500, distortion=0.3, bit_crush=8),
    ),
    "shield_gain": SynthVoice(
        freq=450.0, osc_type=OscType.TRIANGLE, duration=0.25,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE, pitch_mod=4,
        effect_chain=EffectChain(reverb_mix=0.12, lp_filter_hz=4000),
    ),
    "poison_tick": SynthVoice(
        freq=800.0, osc_type=OscType.SINE, duration=0.12,
        volume=0.35, env_shape=EnvShape.PERCUSSIVE, pitch_mod=-2,
        effect_chain=EffectChain(distortion=0.15, bit_crush=10, reverb_mix=0.08),
    ),
    "weak_hit": SynthVoice(
        freq=260.0, osc_type=OscType.NOISE_PINK, duration=0.07,
        volume=0.35, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(lp_filter_hz=1800, hp_filter_hz=100),
    ),
}

# ═══════════════════════════════════════════════════════════
#  系统音效
# ═══════════════════════════════════════════════════════════
SYSTEM_FX_PRESETS: Dict[str, SynthVoice] = {
    "level_up": SynthVoice(
        freq=440.0, osc_type=OscType.SINE, duration=0.8,
        volume=0.6, env_shape=EnvShape.SWELL,
        harmonics=[(2.0, 0.3), (3.0, 0.15)],
        effect_chain=EffectChain(reverb_mix=0.2, reverb_decay=0.8, stereo_width=0.3),
    ),
    "achievement": SynthVoice(
        freq=523.25, osc_type=OscType.TRIANGLE, duration=1.0,
        volume=0.55, env_shape=EnvShape.SWELL,
        harmonics=[(1.5, 0.2), (2.0, 0.3), (2.5, 0.15), (3.0, 0.1), (4.0, 0.05)],
        vibrato_rate=4, vibrato_depth=2,
        effect_chain=EffectChain(reverb_mix=0.25, reverb_decay=1.0, stereo_width=0.4),
    ),
    "gold_pickup": SynthVoice(
        freq=988.0, osc_type=OscType.SINE, duration=0.12,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE, pitch_mod=2,
    ),
    "item_pickup": SynthVoice(
        freq=660.0, osc_type=OscType.TRIANGLE, duration=0.15,
        volume=0.45, env_shape=EnvShape.PERCUSSIVE, pitch_mod=4,
        harmonics=[(2.0, 0.15)],
        effect_chain=EffectChain(reverb_mix=0.08),
    ),
    "potion_use": SynthVoice(
        freq=392.0, osc_type=OscType.SINE, duration=0.3,
        volume=0.48, env_shape=EnvShape.SWELL, pitch_mod=5,
        effect_chain=EffectChain(reverb_mix=0.15, reverb_decay=0.5),
    ),
    "transition": SynthVoice(
        freq=300.0, osc_type=OscType.NOISE_PINK, duration=0.6,
        volume=0.35, env_shape=EnvShape.SWELL,
        effect_chain=EffectChain(
            lp_filter_hz=3000, reverb_mix=0.2, reverb_decay=0.8, stereo_width=0.5,
        ),
    ),
    "game_over": SynthVoice(
        freq=220.0, osc_type=OscType.SAW, duration=1.2,
        volume=0.5, env_shape=EnvShape.REVERSE, pitch_mod=-12,
        effect_chain=EffectChain(
            lp_filter_hz=2000, reverb_mix=0.3, reverb_decay=1.5, stereo_width=0.4,
        ),
    ),
    "victory_fanfare": SynthVoice(
        freq=523.25, osc_type=OscType.TRIANGLE, duration=1.5,
        volume=0.58, env_shape=EnvShape.SWELL,
        harmonics=[(1.5, 0.2), (2.0, 0.25), (2.5, 0.1)],
        effect_chain=EffectChain(reverb_mix=0.25, reverb_decay=1.2, stereo_width=0.5),
    ),
    "elite_alert": SynthVoice(
        freq=740.0, osc_type=OscType.SQUARE, duration=0.3,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE,
        vibrato_rate=6, vibrato_depth=1.5,
        effect_chain=EffectChain(distortion=0.15, bit_crush=10),
    ),
    "boss_appear": SynthVoice(
        freq=100.0, osc_type=OscType.SAW, duration=1.0,
        volume=0.65, env_shape=EnvShape.SWELL, pitch_mod=-8,
        effect_chain=EffectChain(
            lp_filter_hz=1500, reverb_mix=0.3, reverb_decay=1.2,
            distortion=0.25, stereo_width=0.6, bit_crush=8,
        ),
        harmonics=[(0.5, 0.4), (2.0, 0.2)],
    ),
}


# ═══════════════════════════════════════════════════════════════
#  游戏通用音效（sfxr 经典 8 类对标）
# ═══════════════════════════════════════════════════════════════
# 对标 sfxr 家族 (pickupCoin / laserShoot / explosion / powerUp /
# hitHurt / jump / blipSelect / random) 的经典游戏音效分类，
# 用 BloodMusic 合成能力（谐波/包络/滤波/失真）实现，音色现代化。
GAME_FX_PRESETS: Dict[str, SynthVoice] = {
    # 拾取金币 — 清脆短促的高频"叮"（sfxr pickupCoin）
    "pickup_coin": SynthVoice(
        freq=988.0, osc_type=OscType.SQUARE, duration=0.09,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE, pitch_mod=7,
        harmonics=[(2.0, 0.35), (3.0, 0.15)],
        effect_chain=EffectChain(lp_filter_hz=9000, reverb_mix=0.08),
    ),
    # 激光射击 — 频率骤降的锯齿波（sfxr laserShoot）
    "laser_shoot": SynthVoice(
        freq=1800.0, osc_type=OscType.SAW, duration=0.12,
        volume=0.55, env_shape=EnvShape.PERCUSSIVE, pitch_mod=-12,
        harmonics=[(0.5, 0.3)],
        effect_chain=EffectChain(lp_filter_hz=6000, hp_filter_hz=120,
                                  distortion=0.15, bit_crush=10),
    ),
    # 爆炸 — 低频噪声长衰减（sfxr explosion）
    "explosion": SynthVoice(
        freq=90.0, osc_type=OscType.NOISE_BROWN, duration=0.7,
        volume=0.7, env_shape=EnvShape.PERCUSSIVE, pitch_mod=-6,
        harmonics=[(0.5, 0.5)],
        effect_chain=EffectChain(lp_filter_hz=900, distortion=0.35,
                                  reverb_mix=0.2, reverb_decay=0.9),
    ),
    # 能力提升 — 上行滑音感（sfxr powerUp）
    "power_up": SynthVoice(
        freq=440.0, osc_type=OscType.TRIANGLE, duration=0.35,
        volume=0.55, env_shape=EnvShape.SWELL, pitch_mod=5,
        harmonics=[(2.0, 0.2)],
        effect_chain=EffectChain(reverb_mix=0.15, chorus_mix=0.15,
                                  chorus_rate=2.0),
    ),
    # 受击 — 短促锯齿骤降（sfxr hitHurt）
    "hit_hurt": SynthVoice(
        freq=280.0, osc_type=OscType.SAW, duration=0.16,
        volume=0.6, env_shape=EnvShape.PERCUSSIVE, pitch_mod=-8,
        effect_chain=EffectChain(lp_filter_hz=3500, distortion=0.3,
                                  bit_crush=8),
    ),
    # 跳跃 — 上行滑音（sfxr jump）
    "jump": SynthVoice(
        freq=330.0, osc_type=OscType.SQUARE, duration=0.14,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE, pitch_mod=9,
        harmonics=[(1.5, 0.15)],
        effect_chain=EffectChain(lp_filter_hz=5000),
    ),
    # UI 选择 — 极短 blip（sfxr blipSelect）
    "blip_select": SynthVoice(
        freq=1200.0, osc_type=OscType.SINE, duration=0.04,
        volume=0.4, env_shape=EnvShape.PERCUSSIVE,
    ),
    # 随机拾取 — 与金币区分的另一种拾取（sfxr random 风格）
    "random_pick": SynthVoice(
        freq=660.0, osc_type=OscType.TRIANGLE, duration=0.1,
        volume=0.5, env_shape=EnvShape.PLUCK, pitch_mod=-3,
        harmonics=[(2.0, 0.25)],
        effect_chain=EffectChain(reverb_mix=0.12, reverb_decay=0.3),
    ),
}
