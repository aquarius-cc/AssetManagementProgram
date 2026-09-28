# -*- coding: utf-8 -*-
"""API 字段/枚举层生成器 (package)

模块划分（均 ≤ 500 行，遵守根级 DR-5）：

* ``codesource``   —— 真值来源（Django choices + schema 基线）
* ``docparser``    —— 文档区域定位与外科式拼回
* ``annotations``  —— 注释层（唯一人工输入）
* ``render``       —— 表格渲染与对账
"""

__all__ = ["annotations", "codesource", "docparser", "render"]
