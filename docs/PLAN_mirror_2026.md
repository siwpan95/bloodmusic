# 镜像架构重规划 —— bloodmusic（纯机生成混音）↔ musickit（纯采样混音）

> 版本：2026-08 · 依据：用户裁定（2026-08）
> 原则：**互为镜像、代码不共享**——musickit 只作功能结构参考；
> bloodmusic 用自身合成引擎独立实现所有对应功能，两项目各自演进。
> 状态：Phase 1 已落地（autowav 并入 + mirror 包骨架），Phase 2/3 待排期。

---

## 一、镜像总纲

| | **musickit** `G:/music/musickit` | **bloodmusic** `G:/tools/audio/bloodmusic` |
|---|---|---|
| 定位 | 纯采样混音（phonk/流派混音器） | 纯机生成混音（程序化合成 + 算法作曲） |
| 素材来源 | 120GB 真实采样库（13 池） | 合成引擎实时生成（零采样、零版权风险） |
| 素材形态 | 采样文件（stem/loop/one-shot） | 合成声源（stem/loop/one-shot，渲染即得） |
| 授权模型 | license_tier: free/pack/restricted/unknown | license_tier 恒为 selfgen（自生成，天然 release-safe） |
| 人声 | acapella 采样池（真人声） | autowav 共振峰人声（Klatt 元音吟唱/哼鸣） |
| 选音 | manifest 时长/哈希去重、loop 切片、atempo 对齐 | 合成时长可控、无重复问题、BPM 天然对齐 |
| 混音内核 | 自带 remix/core + ffmpeg | 自带 remix/core + ffmpeg（bloodmusic 内置，镜像同名） |
| 混音师 | burbidge_album 24 位签名链 | mirror/mixer_styles.py 24 位签名链（effects 实现） |

**镜像判据**：任一功能在 musickit 中如何由采样达成，bloodmusic 中就有同名的
机生成对应物；CLI 参数、产物结构（stems/成品/report）尽量同名同构。

---

## 二、完整镜像映射表

### 2.1 素材池层

| musickit | bloodmusic 对应物 | 说明 |
|---|---|---|
| 13 采样池目录 bass/drum/guita/cowbell/synth/acapella/animal/sfx/keys/strings/brass/woodwind/ethnic | mirror/pools.py 13 个**机生成声池**（同名） | 每池注册合成预设：drum→808/原声鼓合成、bass→减法/808、guita→KS/波导拨弦、cowbell→噪声+环形、synth→波表/FM、acapella→共振峰人声、animal→噪声叫声、sfx→riser/impact、keys→波表钢琴、strings→FM/KS 弦乐、brass→FM 铜管、woodwind→KS 木管、ethnic→FM 拨弦 |
| instrument_taxonomy.json（242 乐器词 → 37 类 → 13 池，mixer_role） | mirror/taxonomy.py（同词表 → 同类目 → 同 13 池，mixer_role 一致） | 同一份词表语义；bloodmusic 侧解析为合成引擎+预设，而非文件子目录 |
| 各池 manifest.json + manifest_index.json（file/duration_s/sha256/subcategory/license_tier/content_kind） | mirror/manifest.py（同字段） | content_kind 同为 stem/loop/one_shot；license_tier 恒 selfgen；sha256 为生成物哈希 |

### 2.2 风格与编排层

| musickit | bloodmusic 对应物 |
|---|---|
| music/styles/ 65 流派 JSON（mood/bpm/乐器词） | mirror/styles.py 65 风格注册表（63 个 slug 与 musickit 同名 + 2 个机生成侧补充，乐器词→合成引擎/声池） |
| music/music_prompt_generator.py（提示词生成） | mirror/styles.py::generate_prompt |
| music/prompt_driven_remix.py（提示词→混音桥接） | mirror/cli.py --remix（提示词→生成源→混音） |
| remix/templates/structures.json（classic_drop 等曲式） | mirror/structure.py（同名曲式模板） |
| 选音规则：骨架层保底 ≥1 小节 loop、点缀层 ≤1、BPM atempo 对齐、内容去重 | mirror/selection.py（骨架层保底 ≥1 合成 loop、点缀层 ≤1、BPM 天然对齐、生成物天然无重复） |

### 2.3 混音与母带层

| musickit | bloodmusic 对应物 |
|---|---|
| remix/main.py --remix --count --seed --bars --bpm --structure --out --format --release-safe --mixer-style | mirror/cli.py（参数同名；--release-safe 恒真但保留开关；--format wav/flac/ogg） |
| burbidge_album/mixer_styles.py 24 位混音师签名链（bus_chain/master_chain/resolve_style） | mirror/mixer_styles.py（同名 24 slug，用 bloodmusic effects 的 EQ/压缩/饱和/混响/宽度实现） |
| burbidge_album/build_album.py 固定 stems × N 混音师专辑 | mirror/album.py（Phase 2：固定生成 stems × N 混音师） |
| remix/tools/mixer_radio.py / mixer_stream.py 电台 | mirror/radio.py（Phase 3：本地机生成电台，复用 playback/） |
| 输出目录 + report.json（prompt/seed/sources/mixer_style） | mirror/report.py（同字段） |

### 2.4 作曲与人声层（本次并入的 wav_music_gen）

| musickit | bloodmusic 对应物 |
|---|---|
| acapella 采样池（真人声切片） | autowav/vocal_formant.py（Klatt 共振峰人声：8 元音 + 哼鸣 + 拼音韵母映射） |
| （无——采样不作曲） | autowav/（14 调式、13 和弦进行、马尔可夫旋律、对位、曲式 ABA/AABA/ABAC、鼓机、MIDI 导入导出桥） |
| — | autowav/backend.py（symbolic 默认 / acestep 可选懒加载，Hybrid 种子路线） |

---

## 三、合并后 bloodmusic 目标结构

```
bloodmusic/
├── autowav/            # [并入] 算法作曲 + 共振峰人声（纯 stdlib，零依赖）
│   ├── autowav.py / theory.py / melody.py / synthesis.py / effects.py / form.py
│   ├── vocal_formant.py / vocal_render_np.py / batch_vocals.py / demo_vocal.py
│   ├── midi_io.py / backend.py / backends_acestep.py / produce.py / gui.py
│   └── output/         # 已生成示例（50 段人声批次 + 演示曲，自生成资产）
├── mirror/             # [新增] 镜像层：musickit 功能结构的机生成对应物
│   ├── taxonomy.py     # 242 词 → 13 机生成声池（镜像 instrument_taxonomy.json）
│   ├── pools.py        # 13 机生成声池（同名池、合成预设、渲染即得）
│   ├── manifest.py     # 生成资产清单/总索引（镜像 manifest_index.json 字段）
│   ├── styles.py       # 65 风格注册表 + 提示词生成（镜像 music/styles/）
│   ├── structure.py    # 曲式模板（镜像 remix/templates/structures.json）
│   ├── selection.py    # 选源规则（镜像 remix 选音规则）
│   ├── mixer_styles.py # 24 混音师签名链（镜像 burbidge_album/mixer_styles.py）
│   ├── renderer.py     # 提示词→选源→编排→混音→母带（镜像 remix/main.py）
│   ├── report.py       # 报告（镜像 remix 报告字段）
│   ├── cli.py          # --remix CLI（镜像 remix/main.py 参数）
│   └── __main__.py
├── core/ music/ effects/ sfx/           # 既有合成引擎（机生成翼的底层）
├── album_maker/ pipeline/ bridge/       # 既有专辑/流水线（合成路径）
├── remix/                               # bloodmusic 自带混音内核（与 musickit 的 remix 镜像同名、独立实现）
└── docs/PLAN_mirror_2026.md             # 本文档
```

---

## 四、实施阶段

### Phase 1（本轮落地）
- [x] wav_music_gen 并入 autowav/（包化 + python -m bloodmusic.autowav 完整 CLI）
- [x] mirror/ 全模块实现：taxonomy/pools/manifest/styles/structure/selection/mixer_styles/renderer/report/cli（65 风格 / 13 池 / 24 混音师 / 5 曲式）
- [x] 冒烟：python -m bloodmusic.mirror --remix 产出纯生成 WAV + report

### Phase 2（待排期）
- [ ] 65 风格完整数据（每风格乐器词→引擎/预设细调，对齐 musickit styles/*.json 语义）
- [ ] 13 池全部声色细化（现为代表性预设，扩为每池多子类，镜像 subcategory 维度）
- [ ] mirror/album.py 固定风格专辑（镜像 burbidge_album：同一生成 stems × 24 混音师）
- [ ] maker_gui 集成 mirror 页签（镜像 musickit remix/gui/main_window.py）

### Phase 3（待排期）
- [ ] mirror/radio.py 本地机生成电台 + 流服务（镜像 mixer_radio/mixer_stream）
- [ ] 批量质量评分筛选（镜像 musickit 的去重/审计工具链，改作用于生成物）
- [ ] 与 musickit 的对照评测：同风格同参数，采样翼 vs 机生成翼 AB 听感报告

---

## 五、不变量（与 musickit 的镜像边界）

1. **代码零共享**：bloodmusic 不 import musickit 任何模块，反之亦然。
2. **数据零互拷**：采样库留在 musickit，生成物留在 bloodmusic，两仓互不引用。
3. **同名同构**：模块名/池名/CLI 参数/报告字段刻意对齐，便于双项目对照与迁移经验。
4. **纯度守恒**：bloodmusic 的一切音频均自生成（上一轮净化成果不回退）；
   采样需求永远指向 musickit，本仓不再引入任何外部采样。
