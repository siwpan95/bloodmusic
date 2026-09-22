"""run_all.py — 串联所有自动化流水线（纯本地、项目内）。

依次执行：
  1. content_pipeline  (C1/C2/C5/C8 内容生成 + 质量巡检)
  2. qa_pipeline       (T1/T2/T3 回归 + ruff；T4 基准需 BM_BENCH=1)

退出码: 0=全通过, 1=有失败。各子流水线自带报告写入 automations/output/reports/。
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import log  # noqa: E402


def main() -> int:
    log("========== run_all 启动 ==========")
    rc = 0
    try:
        import content_pipeline
        r1 = content_pipeline.main()
        rc = rc or r1
    except Exception as exc:  # pragma: no cover
        log(f"[content] 异常: {exc}")
        rc = 1
    try:
        import qa_pipeline
        r2 = qa_pipeline.main()
        rc = rc or r2
    except Exception as exc:  # pragma: no cover
        log(f"[qa] 异常: {exc}")
        rc = 1
    log(f"========== run_all 结束，退出码 {rc} ==========")
    return rc


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
