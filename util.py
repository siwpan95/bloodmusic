# -*- coding: utf-8 -*-
"""
util.py —— 共享工具函数
========================

历史重复实现收敛点：
  - album_maker/track.py::_safe_stem
  - bridge/renderer.py::_safe_stem
  - mirror/renderer.py::_safe_stem
三者行为一致（白名单字符 + 兜底名），统一为 safe_filename()。
"""

from __future__ import annotations


def safe_filename(name: str, fallback: str = "pattern") -> str:
    """把任意名称规范成安全文件名（防路径穿越）。

    仅保留字母/数字/_/-，其余字符替换为下划线；
    全非法时返回 fallback（非空字符串）。
    """
    safe = [c if (c.isalnum() or c in "_-") else "_" for c in str(name)]
    return "".join(safe).strip("_") or fallback
