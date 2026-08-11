"""
bridge/errors.py —— 可分辨异常体系与统一错误码

命中需求: P0-1（基础设施）
关联发现: F1（mido 未安装）、Q3（只读硬规则）

设计约束:
    - 本模块属于 L1 模型层，**零 IO、零第三方依赖**；
    - `load_mido()` 内部才 import mido（R5 惰性导入），
      模块顶层绝不出现 `import mido`。
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "BridgeError",
    "MidoMissingError",
    "BridgeScanError",
    "BridgeImportError",
    "BridgeRenderError",
    "BridgeWriteDenied",
    "BridgeConfigError",
    "IssueCode",
    "MIDO_INSTALL_HINT",
    "load_mido",
]


# mido 缺失时的统一提示语（§9.2 要求 message 必含 "pip install mido>=1.3"）
MIDO_INSTALL_HINT: str = (
    "未检测到 mido 库，MIDI 读写功能不可用。"
    "请运行: pip install mido>=1.3,<2.0"
)


class BridgeError(Exception):
    """所有 bridge 异常的基类。

    Attributes:
        message: 人读的简体中文错误描述。
        context: 附加上下文（路径 / 参数等），便于写入结构化报告。
    """

    #: 该异常对应的统一错误码（见 IssueCode）
    code: str = "BRIDGE_ERROR"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message: str = message
        self.context: dict[str, Any] = dict(context)

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典（供 report.json 使用）。"""
        return {
            "type": type(self).__name__,
            "code": self.code,
            "message": self.message,
            "context": {k: str(v) for k, v in self.context.items()},
        }

    def __str__(self) -> str:  # pragma: no cover - 简单委托
        if not self.context:
            return self.message
        detail = ", ".join(f"{k}={v}" for k, v in self.context.items())
        return f"{self.message} ({detail})"


class MidoMissingError(BridgeError):
    """未安装 mido（或导入失败）。message 必含 pip 安装提示。"""

    code = "MIDO_MISSING"

    def __init__(self, message: str | None = None, **context: Any) -> None:
        super().__init__(message or MIDO_INSTALL_HINT, **context)


class BridgeScanError(BridgeError):
    """扫描根不存在 / 不可读。"""

    code = "SCAN_ROOT_MISSING"


class BridgeImportError(BridgeError):
    """单个 MIDI 文件解析失败（批量层会降级为 BridgeIssue 继续跑）。"""

    code = "IMPORT_FAILED"


class BridgeRenderError(BridgeError):
    """渲染或音频落盘失败。"""

    code = "RENDER_FAILED"


class BridgeWriteDenied(BridgeError):
    """触碰只读根（Q3 硬规则 R1）——**永不降级，必须抛**。"""

    code = "WRITE_DENIED"


class BridgeConfigError(BridgeError):
    """CLI / BridgeConfig 参数非法。"""

    code = "CONFIG_INVALID"


class IssueCode:
    """统一错误码常量表（对应 system_design.md §9.4）。

    使用常量而非裸字符串，避免各模块拼写漂移导致报告聚合失效。
    """

    MIDO_MISSING = "MIDO_MISSING"
    SCAN_ROOT_MISSING = "SCAN_ROOT_MISSING"
    IMPORT_FAILED = "IMPORT_FAILED"
    MULTIPLE_TEMPO = "MULTIPLE_TEMPO"
    UNCLOSED_NOTE = "UNCLOSED_NOTE"
    OVERLAP_TRUNCATED = "OVERLAP_TRUNCATED"
    NOTE_TOO_SHORT = "NOTE_TOO_SHORT"
    CHORD_PITCH_FOLDED = "CHORD_PITCH_FOLDED"
    PITCH_OUT_OF_RANGE = "PITCH_OUT_OF_RANGE"
    DRUM_GRID_UNSUPPORTED = "DRUM_GRID_UNSUPPORTED"
    DRUM_QUANTIZE_DRIFT = "DRUM_QUANTIZE_DRIFT"
    DRUM_STEP_COLLAPSED = "DRUM_STEP_COLLAPSED"
    UNMAPPED_DRUM_NOTE = "UNMAPPED_DRUM_NOTE"
    MULTI_DRUM_TRACK_TRUNCATED = "MULTI_DRUM_TRACK_TRUNCATED"
    RENDER_FAILED = "RENDER_FAILED"
    WRITE_DENIED = "WRITE_DENIED"
    # ── 以下为实现期补充（设计文档 §9.4 之外，均为 info 级，不影响验收）──
    DRUM_BAR_POLICY_UNSUPPORTED = "DRUM_BAR_POLICY_UNSUPPORTED"
    EMPTY_TRACK_SKIPPED = "EMPTY_TRACK_SKIPPED"
    NO_PATTERN_PRODUCED = "NO_PATTERN_PRODUCED"
    TINY_GAP_MERGED = "TINY_GAP_MERGED"
    DRY_RUN = "DRY_RUN"


def load_mido():
    """惰性加载 mido（R5：绝不在模块顶层 import mido）。

    Returns:
        已导入的 mido 模块对象。

    Raises:
        MidoMissingError: 未安装 mido 或导入失败。
    """
    try:
        import mido  # noqa: PLC0415 - 惰性导入是硬约束 R5
    except Exception as exc:  # ImportError 及其他导入期异常
        raise MidoMissingError(f"{MIDO_INSTALL_HINT}（原始错误: {exc}）") from exc
    return mido


def mido_available() -> bool:
    """探测 mido 是否可用（doctor 子命令用，不抛异常）。"""
    try:
        load_mido()
    except MidoMissingError:
        return False
    return True
