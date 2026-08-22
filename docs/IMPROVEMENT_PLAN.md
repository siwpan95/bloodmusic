# BloodMusic 改进规划

> 基于《深度评估报告》+ sfxr 家族优点采纳
> 原则：自用优先，合规暂缓；先修结构性与 bug，再纳 sfxr 优点，最后补工程增强
> 日期：2026-08-13

---

## 阶段一 · P0 结构性清理 + Bug 修复（立即）

### T1. 修复失败测试 `test_pool_imports_are_lazy`
- **现状**：`tests/test_album_generator_integration.py:282-291` 用字符串 `in` 匹配检查懒加载，误把 `album_generator.py` 里 docstring 中的示例代码当成"模块级 import 泄漏"
- **根因**：测试用纯文本匹配而非 AST 分析
- **方案**：改用 `ast.parse` 遍历，只检查真正的 `ast.Import`/`ast.ImportFrom` 节点是否出现在模块顶层（`ast.Module.body` 顶层，而非函数体 `ast.FunctionDef.body` 内），忽略字符串/文档节点
- **验收**：`pytest tests/test_album_generator_integration.py -k lazy` 通过，且仍能真正拦截"模块级泄漏"

### T2. 收敛范围 — 清理废弃/残留
- **删除**：根目录 `album_generator.py`（1,369 行，已标注 deprecated，被 `album_maker/` 子包替代）
- **清理**：`album_maker_quick/`（实为输出残留，含 10 个 `track_01_*` 测试目录 + `album.yaml.copy`，非代码模块）→ 内容移入 `.gitignore` 或直接删除测试输出
- **归一**：统一专辑生成入口为 `album_maker/`，在 `album_maker/__init__.py` 顶部注明"已替代根目录 album_generator.py"
- **验收**：根目录无废弃大文件；`album_maker_quick/` 不再混入仓库

### T3. 硬编码路径可配置化
- **现状**：`album_maker/track.py:29-36` 硬编码 `_AUDIO_PIPELINE_ROOT = Path(r"G:\tools\audio\audio_pipeline")` 和 `_REMIX_ROOT = Path(r"G:\tools\audio\remix")`
- **方案**：改为环境变量优先 + 相对回退：
  ```
  _AUDIO_PIPELINE_ROOT = Path(os.environ.get("BLOODMUSIC_AUDIO_PIPELINE", r"G:\tools\audio\audio_pipeline"))
  _REMIX_ROOT = Path(os.environ.get("BLOODMUSIC_REMIX", r"G:\tools\audio\remix"))
  ```
  并在路径不存在时 `logger.warning` 而非静默失败
- **验收**：跨机器可通过环境变量配置；路径缺失时有明确告警

---

## 阶段二 · P1 采纳 sfxr 家族优点

### sfxr 家族优点梳理（调研所得）
| 优点 | 来源 | 价值 | 采纳方式 |
|------|------|------|----------|
| 参数序列化为紧凑字符串 | jsfxr base58 | 整个音效压缩成几十字符，便于分享/版本控制/存储 | T4 |
| 变异(mutation)机制 | bfxr Randomize/Mutation | 在预设基础上微调生成变体，避免重复 | T5 |
| 锁定参数随机化 | bfxr lock 图标 | 随机化时保留指定参数 | T5 |
| 经典 8 类游戏预设 | sfxr pickupCoin/laserShoot/explosion/powerUp/hitHurt/jump/blipSelect | 游戏通用音效标配 | T6 |
| Mixer 叠加 | bfxr 最多 5 个效果叠加 | 已有 LayeredSFX，可增强接口 | T7 |
| 波形可视化反馈 | jfxr | 调参时看到波形变化 | T8 |

### T4. SFX 参数序列化（SynthVoice ↔ 紧凑字符串）
- **现状**：`SynthVoice`/`EffectChain` 是 dataclass，无序列化能力；预设是 Python 字面量
- **方案**：新增 `sfx/serialize.py`
  - `voice_to_dict(voice) → dict`：dataclass → 可 JSON 化字典（枚举转字符串）
  - `voice_to_json(voice) → str`：JSON 字符串
  - `voice_from_json(s) → SynthVoice`：反序列化（往返一致）
  - `voice_to_compact(voice) → str`：base64+压缩的紧凑串（仿 jsfxr 短 URL），用于分享
  - `voice_from_compact(s) → SynthVoice`
- **验收**：任一预设可序列化→反序列化→合成，结果与原预设位一致；紧凑串长度 < 300 字符

### T5. 变异(mutation)引擎 + 锁定随机化
- **方案**：新增 `sfx/mutate.py`
  - `mutate_voice(voice, amount=0.15, locked_fields=None) → SynthVoice`：对 freq/duration/volume/pitch_mod/distortion 等数值字段做 ±amount 比例随机扰动；`locked_fields` 指定不动的字段（仿 bfxr lock）
  - `randomize_voice(base=None, locked_fields=None) → SynthVoice`：在合理范围内完全随机（仿 sfxr Randomize）
  - `mutate_preset(name, n=5) → list[SynthVoice]`：基于某预设生成 n 个变体
- **验收**：从 `button_click` 变异出 5 个听感不同但风格相近的变体；锁定 freq 时变异后 freq 不变

### T6. 补齐 sfxr 经典 8 类游戏通用预设
- **现状**：BloodMusic 分类是 UI/CARD/COMBAT/SYSTEM，缺 sfxr 经典游戏分类
- **方案**：在 `sfx/presets.py` 新增 `GAME_FX_PRESETS` 字典，补齐 8 类：
  `pickup_coin` / `laser_shoot` / `explosion` / `power_up` / `hit_hurt` / `jump` / `blip_select` / `random_pick`
  每类用 BloodMusic 现有合成能力（FM/噪声/包络/滤波）实现，音色对标 sfxr 但利用本项目更强的效果链
- **验收**：8 类预设可播放，听感对应经典游戏场景；导出测试通过

### T7. LayeredSFX Mixer 接口增强
- **现状**：`sfx/layered.py` 有 `LayeredSFX`（ImpactLayer/BodyLayer/TailLayer），但叠加接口较固定
- **方案**：新增 `mix_voices(voices: list[SynthVoice], weights=None) → np.ndarray`，支持任意 N 个 SynthVoice 加权叠加（仿 bfxr Mixer 的 5 路叠加，但不限数量）
- **验收**：3 个 SynthVoice 加权混合输出正确，归一化无削波

### T8. GUI 波形可视化
- **现状**：`gui/workstation.py`（213 行）仅列表+导出，无波形显示
- **方案**：嵌入 matplotlib FigureCanvasTkAgg，预览 SFX 时绘制波形（时域 + 包络轮廓）；选预设即显示其波形
- **依赖**：matplotlib（GUI 可选依赖，缺失时降级不显示波形）
- **验收**：选任一 SFX 预设，右侧面板显示其波形图

---

## 阶段三 · P2 工程增强

### T9. 实时性能基准
- **方案**：新增 `benchmarks/bench_engine.py`，测量 `RealtimeMusicEngine.process_frame()` 在不同层密度(2/4/6层)、不同 buffer_size(128/256/512)下的单帧耗时，输出表格
- **目标**：明确"能否满足 60fps（16.6ms/帧）"，给出可用的层密度上限
- **验收**：产出基准报告，标注实时可行配置

### T10. GUI 实时参数滑块
- **方案**：在 GUI 增加 SynthVoice 参数滑块（freq/duration/volume/pitch_mod/distortion/reverb_mix），滑动即重合成即播放（节流 200ms）
- **验收**：拖动滑块可实时听变化

### T11. 统一署名 + pyproject 元数据
- **现状**：LICENSE=siwpan / README="全哥创建" / pyproject 无 author
- **方案**：统一 author 字段，pyproject 补 `[project.authors]`，README 与 LICENSE 对齐
- **验收**：三处署名一致

---

## 执行顺序与依赖

```
阶段一（P0，无依赖，可并行）
  T1 修测试 ──┐
  T2 清范围 ──┼─→ 阶段一完成
  T3 路径配置 ┘

阶段二（P1，T4 为基础）
  T4 序列化 ─→ T5 变异（依赖 T4 的 dict 表示）
            ─→ T8 GUI波形（可并行）
  T6 经典预设（独立）
  T7 Mixer（独立）

阶段三（P2）
  T9 性能基准（独立）
  T10 GUI滑块（依赖 T8 的 GUI 基础）
  T11 署名（独立）
```

**关键路径**：T1/T2/T3（阶段一）→ T4（序列化）→ T5（变异）→ T8（GUI波形）→ T10（GUI滑块）

---

## 风险与回退
- T2 删除 album_generator.py 前先 `git mv` 到 `archive/` 保留历史，确认无引用再删
- T4 序列化需保证浮点往返精度（用 repr 而非 str）
- T8/T10 GUI 改动较大，先在分支验证，matplotlib 缺失须优雅降级


---

## 2026-08-21 核对状态

> 本计划（2026-08-13）全部 11 项任务核对结果。

| 任务 | 状态 | 说明 |
|---|---|---|
| T1 修复 lazy 测试 | ✅ 完成 | 改用 ast.parse 分析；pytest -k lazy 实测 1 passed |
| T2 收敛范围 | ✅ 完成 | album_generator.py → archive/；album_maker_quick 已清理；album_maker/__init__.py 已注明替代 |
| T3 硬编码路径配置化 | ✅ 完成 | 环境变量 BLOODMUSIC_AUDIO_PIPELINE / BLOODMUSIC_REMIX + 缺省回退 + 缺失告警 |
| T4 SFX 序列化 | ✅ 完成 | sfx/serialize.py（dict/JSON/compact 往返一致） |
| T5 变异引擎 + 锁定 | ✅ 完成 | sfx/mutate.py（mutate/randomize/mutate_preset，含 locked_fields） |
| T6 经典 8 类游戏预设 | ✅ 完成 | sfx/presets.py GAME_FX_PRESETS（test_game_fx 6 passed） |
| T7 LayeredSFX Mixer | ✅ 完成 | mix_voices N 路加权叠加 |
| T8 GUI 波形可视化 | ✅ 完成 | workstation 内嵌 matplotlib 波形 |
| T9 实时性能基准 | ✅ 完成 | benchmarks/report.md：2-6 层 1.13~1.49ms/帧，60fps 可行（预算 16.6ms） |
| T10 GUI 实时参数滑块 | ✅ 完成 | 滑块 + 200ms 节流重合成 |
| T11 统一署名 | ✅ 完成 | pyproject authors=siwpan，README/LICENSE 对齐 |

**2026-08-21 追加收尾（本计划外新立项）**：
- [x] 真实游戏引擎接入验证：games/zhuangtaiji（pygame）+ bloodmusic.interactive.RealtimeMusicEngine 端到端
- [x] 钢琴卷帘/音序器 UI：gui/piano_roll.py + 工作站集成
- [x] 镜像架构 Phase 1/2（docs/PLAN_mirror_2026.md）与人声档 B（autowav/vocal_tts.py）
