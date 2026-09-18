"""
interactive/service.py — B-lite 轻量服务化（mini-Context + 引擎服务插件）
=======================================================================

Phase B-lite（docs/REVIEW_phase_b_20260918.md P2）：把 RealtimeMusicEngine 暴露为
Context 服务，状态机/映射器/混音器成为**可运行时热替换单元**——这是 cordis
「服务可替换、依赖可重载」语义在 Python 引擎内部的落地。core/effects/music/sfx
保持纯函数库不动（评审结论：纯函数没有副作用可组合，插件化只有边界开销）。

两个东西：

1. ``Context`` —— 服务注册表 + 可逆副作用栈（provide / get / effect / install /
   unload / dispose / fork）。语义对齐 cordis（注册即回滚、逆序销毁、inject 装配期
   校验、fork 双作用域）。**形态借鉴 alloy/core/context.py**（siwpan，MIT，同为
   cordis 语义的 Python 实现）；本实现为 bloodmusic 内的精简版（去掉 fork_install
   外层去重与作用域枚举，够用即止），零第三方依赖。

2. ``MusicEnginePlugin`` —— 引擎服务插件：一次 install 提供
   ``music.engine`` / ``music.state_machine`` / ``music.mapper`` / ``music.mixer``
   四个服务；``replace_state_machine`` 支持运行时热替换（重绑引擎引用 + 服务注册，
   替换走 unload 语义）；dispose 时清缓存/回调，逆序回收。

用法::

    from bloodmusic.interactive import Context, music_engine_plugin

    ctx = Context()
    ctx.install(music_engine_plugin)          # 四个服务就位
    engine = ctx.get("music.engine")
    engine.start()

    # 运行时热替换状态机（换一套转换规则，引擎不重启）
    from bloodmusic.interactive import MusicStateMachine
    ctx.provide("music.state_machine", MusicStateMachine(), replace=True)

    # 多实例：每个游戏场景一个 fork，各自独立回收
    scene = ctx.fork("boss-scene")
    scene.install(music_engine_plugin)

    ctx.dispose()                              # 逆序回滚全部
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from .engine import EngineConfig, RealtimeMusicEngine
from .state_machine import MusicStateMachine

__all__ = [
    "Context",
    "MusicEnginePlugin",
    "music_engine_plugin",
    "replace_state_machine",
    "DuplicateServiceError",
    "MissingDependencyError",
]

_MISSING = object()

# 条目类型：(key, disposer)；key 为 None 表示匿名副作用（effect）
_Entry = Tuple[Optional[str], Optional[Callable[[], Any]]]


class DuplicateServiceError(RuntimeError):
    """同一上下文内重复提供同名服务。"""

    def __init__(self, key: str):
        super().__init__(f"服务已注册: '{key}'（重复 provide）。如需覆盖请使用 replace=True")


class MissingDependencyError(RuntimeError):
    """插件要求的依赖服务不存在。"""

    def __init__(self, key: Any, context: "Context" = None):
        hint = f"（已注册: {sorted(context.keys())}）" if context is not None else ""
        super().__init__(f"缺少依赖服务: {key} {hint}")


class Context:
    """服务注册表 + 可逆副作用栈（cordis 语义的 Python mini 实现）。

    - ``provide`` 注册服务（可附 disposer），注册动作本身压入回滚栈；
    - ``effect`` 注册匿名可逆副作用；
    - ``install`` 按 ``{name, inject, apply}`` 协议装配插件，inject 缺失装配期报错；
    - ``dispose`` 逆序回滚全部（后注册先销毁，与 cordis Fiber 语义一致），幂等，
      单个 disposer 抛异常不阻断其余回滚；
    - ``fork`` 创建子作用域：查找沿父链向上、注册只落本层、销毁只回滚自身。
    """

    def __init__(self, parent: Optional["Context"] = None):
        self._parent = parent
        self._services: Dict[str, Any] = {}
        self._entries: List[_Entry] = []
        self._disposed = False
        self._children: List["Context"] = []

    # ── 注册 ──

    def provide(self, key: str, service: Any, *,
                dispose: Optional[Callable[[], Any]] = None,
                replace: bool = False) -> Any:
        """注册服务；可附带 disposer（unload/dispose 时调用）。返回 service 便于链式赋值。"""
        self._ensure_live()
        if key in self._services and not replace:
            raise DuplicateServiceError(key)
        if key in self._services and replace:
            self.unload(key)
        self._services[key] = service
        self._entries.append((key, dispose))
        return service

    def effect(self, fn: Callable[[], Any]) -> None:
        """注册匿名可逆副作用：上下文销毁时逆序执行。"""
        self._ensure_live()
        if not callable(fn):
            raise TypeError("effect 需要可调用对象")
        self._entries.append((None, fn))

    # ── 查找 ──

    def has(self, key: str) -> bool:
        if key in self._services:
            return True
        return self._parent.has(key) if self._parent is not None else False

    def get(self, key: str, default: Any = _MISSING) -> Any:
        """按 key 查找服务：先本层、再父链；缺失且无 default 时抛 MissingDependencyError。"""
        if key in self._services:
            return self._services[key]
        if self._parent is not None:
            value = self._parent.get(key, _MISSING)
            if value is not _MISSING:
                return value
        if default is _MISSING:
            raise MissingDependencyError(key, self)
        return default

    def keys(self) -> List[str]:
        """本层注册的所有 key（不含父链）。"""
        return list(self._services.keys())

    # ── 插件 ──

    def install(self, plugin: Any, config: Any = None) -> "Context":
        """按插件协议装配：name（标识）+ inject（依赖 key 列表）+ apply(ctx, config)。

        apply 若返回可调用对象，视为该插件的统一 disposer，随上下文销毁执行。
        """
        self._ensure_live()
        name = getattr(plugin, "name", None) or plugin.__class__.__name__
        inject = list(getattr(plugin, "inject", None) or [])
        missing = [k for k in inject if not self.has(k)]
        if missing:
            raise MissingDependencyError(
                f"插件 '{name}' 缺少依赖: {missing}", self)
        result = plugin.apply(self, {} if config is None else config)
        if callable(result):
            self.effect(result)
        return self

    # ── 卸载 / 销毁 ──

    def unload(self, key: str) -> bool:
        """只回滚指定 key 的注册：执行其 disposer 并移除服务。未注册返回 False。"""
        if key not in self._services:
            return False
        for k, disp in reversed(self._entries):
            if k == key and disp is not None:
                disp()
        self._entries = [(k, d) for k, d in self._entries if k != key]
        del self._services[key]
        return True

    def dispose(self) -> None:
        """销毁本上下文：递归销毁子作用域，再按注册逆序回滚全部 effect/disposer。幂等。"""
        if self._disposed:
            return
        for child in list(self._children):
            child.dispose()
        for _, disp in reversed(self._entries):
            if disp is None:
                continue
            try:
                disp()
            except Exception:
                pass  # 容错：单个失败不阻断回滚
        self._entries.clear()
        self._services.clear()
        self._disposed = True
        if self._parent is not None and self in self._parent._children:
            self._parent._children.remove(self)

    def fork(self, name: Optional[str] = None) -> "Context":
        """创建子作用域：查找沿父链向上，注册/effect 只落本层，dispose 只回滚自身。"""
        self._ensure_live()
        child = Context(parent=self)
        self._children.append(child)
        return child

    # ── 内部 ──

    def _ensure_live(self) -> None:
        if self._disposed:
            raise RuntimeError("Context 已销毁，不能再注册服务")

    def __contains__(self, key: str) -> bool:
        return self.has(key)

    def __repr__(self) -> str:
        return (f"<Context keys={sorted(self.keys())} "
                f"parent={'yes' if self._parent else 'no'}>")


# ══════════════════════════════════════════════════════════════════
# 引擎服务插件
# ══════════════════════════════════════════════════════════════════

def _teardown_engine(engine: RealtimeMusicEngine) -> None:
    """引擎服务 disposer：清音频缓存与回调（同包内访问内部状态，可接受）。"""
    engine._layer_audio_cache.clear()
    engine._on_state_change.clear()
    engine._on_beat.clear()


class MusicEnginePlugin:
    """把 RealtimeMusicEngine 装配为 Context 服务。

    config（dict，均可选）::

        {
          "config": EngineConfig(...),   # 引擎配置；缺省 EngineConfig()
          "default_layers": True,        # 是否装默认 5 层模板
        }

    提供的服务：
      - ``music.engine``        RealtimeMusicEngine（dispose 清缓存/回调）
      - ``music.state_machine`` 引擎当前状态机（可 replace=True 热替换）
      - ``music.mapper``        参数映射器
      - ``music.mixer``         层混音器
    """

    name = "music-engine"
    inject: List[str] = []

    def apply(self, ctx: Context, config: Any = None) -> Callable[[], None]:
        cfg = config or {}
        engine_cfg = cfg.get("config")
        if engine_cfg is None:
            engine = RealtimeMusicEngine()
        elif isinstance(engine_cfg, EngineConfig):
            engine = RealtimeMusicEngine(engine_cfg)
        elif isinstance(engine_cfg, dict):
            engine = RealtimeMusicEngine(EngineConfig(**engine_cfg))
        else:
            raise TypeError(f"config.config 需为 EngineConfig 或 dict，得到 {type(engine_cfg).__name__}")

        if cfg.get("default_layers", True):
            engine.setup_default_layers()

        ctx.provide("music.engine", engine, dispose=lambda: _teardown_engine(engine))
        ctx.provide("music.state_machine", engine.state_machine)
        ctx.provide("music.mapper", engine.mapper)
        ctx.provide("music.mixer", engine.mixer)
        return lambda: _teardown_engine(engine)


#: 模块级单例（无状态，可复用）
music_engine_plugin = MusicEnginePlugin()


def replace_state_machine(ctx: Context, new_machine: MusicStateMachine) -> MusicStateMachine:
    """运行时热替换状态机：重绑引擎引用 + 以 replace 语义更新服务注册。

    引擎不重启、层不重建——换的只是「转换规则」这颗螺丝。旧状态机无资源
    需要释放，直接丢弃。返回新机器便于链式使用。
    """
    engine = ctx.get("music.engine")
    old = engine.state_machine
    # 新机器继承旧机器的当前状态（避免热替换瞬间状态跳变）
    if old.current_state is not None:
        new_machine.start(old.current_state)
    engine.state_machine = new_machine
    ctx.provide("music.state_machine", new_machine, replace=True)
    return new_machine
