# -*- coding: utf-8 -*-
"""scripts/tests 公共配置：把 scripts/ 与本目录加入 sys.path。

护栏脚本全部位于 scripts/（含 line_metrics.py，护栏经 `from line_metrics import` 引用），
测试文件 import 护栏时必须能解析；helpers.py 提供夹具级公共函数。
"""

import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_TESTS))
sys.path.insert(0, str(_TESTS.parent))