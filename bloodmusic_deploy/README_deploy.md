# BloodMusic 本地依赖部署说明

本目录是为 `X:\audio-generation-master` 准备的「依赖内置于项目根目录」部署包。
已在 Python 3.14 (Windows) 下完整验证：6 个依赖库 + PortAudio 均可从项目根目录
的 `lib/` 加载，项目可正常运行（`python -m bloodmusic --help`、合成、WAV 导出、
`python main.py --check` 均通过）。

> 说明：本机（X: 盘）对自动部署流程是只读的，因此无法由脚本直接写入项目目录。
> 请把本包里的 `lib\` 与 `deploy.py` 复制到 `X:\audio-generation-master\` 下，
> 然后**在你能写入 X: 的环境里**运行 `python deploy.py`。以下命令均在该环境下执行。

## 包含内容
- `lib/`          内置依赖：numpy, scipy, sounddevice, soundfile, PyYAML, mido
                  （含传递依赖 cffi / packaging / pycparser / typing_extensions）
                  以及声卡后端动态库 `portaudio.dll` / `libportaudio-2.dll`
- `deploy.py`     一键部署脚本（注入本地依赖引导 + 建立 bloodmusic 包名联结）

## 部署步骤（在 X:\audio-generation-master 根目录下操作）

1. 把本目录里的 `lib\`、`deploy.py` 复制到
   `X:\audio-generation-master\` 下（使 `X:\audio-generation-master\lib\` 存在）。

2. 打开终端，进入项目根目录并运行：
   ```
   cd X:\audio-generation-master
   python deploy.py
   ```
   脚本会做三件事（均幂等，可重复运行）：
   - 在 `__init__.py` 顶部注入「本地依赖引导」：导入包时把 `lib/` 加入
     `sys.path` 与 `PATH`，并预加载 PortAudio 动态库。
   - 在 `main.py` 的路径注入块后注入同一段引导，保证
     `python main.py --check` / `--demo` 等也能从 `lib/` 找到依赖。
   - 在项目根目录建立指向自身的目录联结(junction)
     `X:\audio-generation-master\bloodmusic -> X:\audio-generation-master`，
     让 `python -m bloodmusic` 能正确解析包名（项目目录名为
     audio-generation-master，包名是 bloodmusic）。**该步骤不依赖 pip，
     也不需要管理员权限**（junction 与普通符号链接不同，无需 Developer Mode）。

3. 验证：
   ```
   python -m bloodmusic --help
   python main.py --check
   python main.py
   ```

## 原理
- 依赖全部位于 `项目根目录/lib/`，无需联网 `pip install`。
- `__init__.py` 与 `main.py` 顶部的引导代码在导入/启动时把 `lib/` 加入
  `sys.path`，并把 `lib/` 加入 `PATH`，因此 `sounddevice` 能找到 `portaudio.dll`；
  同时脚本会先 `ctypes.CDLL("portaudio.dll")` 预加载，确保声卡后端就绪。
- `bloodmusic` 自指向联结让 `python -m bloodmusic` / `python main.py`
  （内部 `from bloodmusic...` 导入）都能正确解析包名。

## 关于 tkinter
`python main.py --check` 中的 `tkinter` 是 Python **标准库**模块，并非本包内置的
第三方依赖。若该项显示 `[MISS]`，是因为当前 Python 发行版未包含 tkinter
（如某些精简构建）。请使用完整版 Python（官方安装包勾选 tcl/tk 即可），
本部署包无需也无法为 tkinter 提供「本地依赖」——它不是我们需要 vendoring 的库。
其余 numpy/scipy/soundfile/sounddevice 四项均由本包从 `lib/` 提供。

## 恢复（撤销部署）
- 删除根目录下的 `bloodmusic` 联结（目录联结，可直接删除，不影响项目文件）。
- 删除 `__init__.py` 与 `main.py` 顶部的「本地依赖引导」代码块
  （含 `# 本地依赖引导 (local dependency bootstrap)` 注释）。
- 删除 `lib/` 目录。
- 以上三步均为本地文件改动，**未对 Python 环境做任何全局修改**，
  无需 `pip uninstall`。
