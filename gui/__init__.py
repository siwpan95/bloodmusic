"""GUI 模块 —— Tkinter 工作站界面（可选）"""

# GUI 是可选依赖, 需要 tkinter
try:
    from .workstation import GameAudioWorkstationGUI
    _HAS_GUI = True
except ImportError:
    _HAS_GUI = False
    GameAudioWorkstationGUI = None  # type: ignore
