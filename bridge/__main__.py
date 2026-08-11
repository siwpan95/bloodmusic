"""
bloodmusic.bridge.__main__ —— `python -m bloodmusic.bridge` 入口

只做一件事：把控制权交给 `cli.main()` 并用其返回值作为进程退出码。

Example:
    $ python -m bloodmusic.bridge scan
    $ python -m bloodmusic.bridge render --root G:/midi --format wav
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
