"""python -m bloodmusic.autowav —— 复刻原 autowav.py 的命令行入口。

把原脚本以 __main__ 方式运行，保持 --random / --batch / --duration 等参数不变。
"""

import os
import runpy
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

runpy.run_path(os.path.join(_DIR, "autowav.py"), run_name="__main__")
