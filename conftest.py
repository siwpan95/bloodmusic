"""
pytest 全局配置 — slow 测试默认跳过。

渲染/端到端类测试（@pytest.mark.slow）在部分环境（嵌入式 Python、
无 torch 子进程 DLL 注入等）下会导致 pytest 主进程异常终止，
因此默认不执行。需要时显式运行:

    pytest --runslow
"""
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="run slow (long-render / end-to-end) tests as well",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip_slow = pytest.mark.skip(reason="slow test — run with --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
