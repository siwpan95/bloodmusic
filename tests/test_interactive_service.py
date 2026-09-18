"""tests/test_interactive_service.py — B-lite 服务化验收（Phase B-lite / 评审 P2）。

覆盖（全部实跑）：
  1. Context 基本语义：provide/get/has/重复注册报错/replace
  2. effect + dispose 逆序回滚（后注册先销毁）
  3. dispose 容错：单个 disposer 抛异常不阻断其余回滚
  4. install 协议：inject 缺失装配期报错；apply 返回 disposer 被回收
  5. 引擎插件：四服务就位、默认层已建、引擎真实可跑（update+process_frame）
  6. 状态机热替换：replace_state_machine 重绑引擎引用、服务注册同步、状态继承
  7. fork 多实例：两个场景各自引擎互不干扰、独立回收
  8. dispose 后引擎缓存/回调被清（disposer 实际生效）
"""

import numpy as np
import pytest

from bloodmusic.interactive import (
    Context,
    MusicState,
    MusicStateMachine,
    RealtimeMusicEngine,
    music_engine_plugin,
    replace_state_machine,
)
from bloodmusic.interactive.service import DuplicateServiceError, MissingDependencyError


# ── 1. Context 基本语义 ──


class TestContextBasics:
    def test_provide_get_has(self):
        ctx = Context()
        obj = object()
        assert ctx.provide("a", obj) is obj
        assert ctx.get("a") is obj
        assert ctx.has("a") and "a" in ctx
        assert not ctx.has("b")

    def test_get_missing_raises_with_registered_hint(self):
        ctx = Context()
        ctx.provide("a", 1)
        with pytest.raises(MissingDependencyError, match="a"):
            ctx.get("a" if False else "nope")

    def test_get_default(self):
        ctx = Context()
        assert ctx.get("nope", default=42) == 42

    def test_duplicate_provide_raises(self):
        ctx = Context()
        ctx.provide("a", 1)
        with pytest.raises(DuplicateServiceError):
            ctx.provide("a", 2)

    def test_replace_unloads_old(self):
        disposed = []
        ctx = Context()
        ctx.provide("a", 1, dispose=lambda: disposed.append("old"))
        ctx.provide("a", 2, replace=True, dispose=lambda: disposed.append("new"))
        assert ctx.get("a") == 2
        ctx.dispose()
        assert disposed == ["old", "new"]  # 旧的在 replace 时卸载，新的在 dispose 时卸载


# ── 2/3. effect 逆序 + 容错 ──


class TestEffectDisposal:
    def test_dispose_reverse_order(self):
        order = []
        ctx = Context()
        ctx.effect(lambda: order.append(1))
        ctx.effect(lambda: order.append(2))
        ctx.effect(lambda: order.append(3))
        ctx.dispose()
        assert order == [3, 2, 1]

    def test_dispose_tolerates_failing_disposer(self):
        order = []

        def boom():
            raise RuntimeError("disposer 崩了")

        ctx = Context()
        ctx.effect(lambda: order.append("before"))
        ctx.effect(boom)
        ctx.effect(lambda: order.append("after"))
        ctx.dispose()
        assert order == ["after", "before"]  # 崩的那个被吞，其余照常回滚

    def test_dispose_idempotent(self):
        n = [0]
        ctx = Context()
        ctx.effect(lambda: n.__setitem__(0, n[0] + 1))
        ctx.dispose()
        ctx.dispose()
        assert n[0] == 1

    def test_dead_context_rejects_registration(self):
        ctx = Context()
        ctx.dispose()
        with pytest.raises(RuntimeError, match="已销毁"):
            ctx.provide("a", 1)


# ── 4. install 协议 ──


class TestInstallProtocol:
    def test_missing_inject_raises_at_install(self):
        class NeedDep:
            name = "need-dep"
            inject = ["music.engine"]

            def apply(self, ctx, config):
                raise AssertionError("不应执行到 apply")

        ctx = Context()
        with pytest.raises(MissingDependencyError, match="music.engine"):
            ctx.install(NeedDep())

    def test_apply_disposer_collected(self):
        class Simple:
            name = "simple"
            inject = []

            def apply(self, ctx, config):
                ctx.provide("x", 1)
                return lambda: order.append("disposed")

        order = []
        ctx = Context()
        ctx.install(Simple())
        assert ctx.get("x") == 1
        ctx.dispose()
        assert order == ["disposed"]


# ── 5. 引擎插件 ──


class TestMusicEnginePlugin:
    def test_install_provides_four_services(self):
        ctx = Context()
        ctx.install(music_engine_plugin)
        engine = ctx.get("music.engine")
        assert isinstance(engine, RealtimeMusicEngine)
        assert ctx.get("music.state_machine") is engine.state_machine
        assert ctx.get("music.mapper") is engine.mapper
        assert ctx.get("music.mixer") is engine.mixer

    def test_engine_actually_runs(self):
        ctx = Context()
        ctx.install(music_engine_plugin)
        engine = ctx.get("music.engine")
        engine.start(MusicState.EXPLORE)
        engine.update({"hp_ratio": 1.0, "enemy_count": 0, "speed": 0.5, "intensity": 0.2}, 0.016)
        frame = engine.process_frame()
        assert isinstance(frame, np.ndarray) and frame.size > 0

    def test_config_dict_and_default_layers_off(self):
        ctx = Context()
        ctx.install(music_engine_plugin, {"config": {"sample_rate": 22050}, "default_layers": False})
        engine = ctx.get("music.engine")
        assert engine.config.sample_rate == 22050
        assert len(engine.mixer._layers) == 0  # default_layers=False → 不装默认层

    def test_bad_config_type_raises(self):
        ctx = Context()
        with pytest.raises(TypeError, match="EngineConfig"):
            ctx.install(music_engine_plugin, {"config": 123})

    def test_dispose_clears_engine_caches_and_callbacks(self):
        ctx = Context()
        ctx.install(music_engine_plugin)
        engine = ctx.get("music.engine")
        engine._layer_audio_cache["k"] = np.zeros(8)
        engine.on_state_change(lambda s: None)
        ctx.dispose()
        assert engine._layer_audio_cache == {}
        assert engine._on_state_change == []


# ── 6. 状态机热替换 ──


class TestStateMachineHotSwap:
    def test_replace_rebinds_engine_and_service(self):
        ctx = Context()
        ctx.install(music_engine_plugin)
        engine = ctx.get("music.engine")
        old = engine.state_machine
        engine.start(MusicState.EXPLORE)

        new = MusicStateMachine()
        returned = replace_state_machine(ctx, new)
        assert returned is new
        assert engine.state_machine is new
        assert ctx.get("music.state_machine") is new
        assert engine.state_machine is not old
        assert engine.current_state == MusicState.EXPLORE  # 状态继承，无跳变
        # 引擎继续可用
        engine.update({"hp_ratio": 1.0, "enemy_count": 0, "speed": 0.3, "intensity": 0.1}, 0.016)
        assert engine.process_frame().size > 0

    def test_replace_without_started_engine(self):
        ctx = Context()
        ctx.install(music_engine_plugin)
        new = MusicStateMachine()
        replace_state_machine(ctx, new)
        assert ctx.get("music.engine").state_machine is new
        assert new.current_state is None  # 旧机器未 start → 不强推状态


# ── 7. fork 多实例 ──


class TestForkScopes:
    def test_fork_isolation_and_independent_disposal(self):
        root = Context()
        root.install(music_engine_plugin)
        root_engine = root.get("music.engine")

        scene_a = root.fork("scene-a")
        scene_a.install(music_engine_plugin)
        scene_b = root.fork("scene-b")
        scene_b.install(music_engine_plugin)

        engine_a = scene_a.get("music.engine")
        engine_b = scene_b.get("music.engine")
        assert engine_a is not engine_b and engine_a is not root_engine

        # fork 内同名服务可遮蔽父层（shadow），父层不受影响
        assert scene_a.get("music.engine") is engine_a
        assert root.get("music.engine") is root_engine

        # 独立回收：销毁 scene_a 不影响 root / scene_b
        scene_a.dispose()
        assert root.has("music.engine")
        assert scene_b.has("music.engine")
        assert engine_a._layer_audio_cache == {}  # scene_a 的 disposer 已跑

    def test_fork_lookup_walks_parent_chain(self):
        root = Context()
        root.install(music_engine_plugin)
        child = root.fork("child")
        assert child.get("music.engine") is root.get("music.engine")  # 沿父链找到
        assert "music.engine" not in child.keys()  # 但注册仍在父层
