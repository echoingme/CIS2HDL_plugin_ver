"""output 阶段插件包（FR5）。

S6：把 S2 粗粒度 default_writer/reports 占位替换为**细粒度输出插件**：

- 文件插件（``output.files``，7）：csa / con / xcon / csv / cpc / cpm /
  cds_lib —— 各写对应文件（writer 模块编排，不重写逻辑）。
- 报告插件（``output.reports``，4）：aesthetic / ioport / mapping /
  error —— mapping（mapping.csv+top3）、error（错误日志）真委托；
  aesthetic/ioport 为 no-op 门（报告由 csa 插件侧效应写出，门控抑制）。

``_SPECS`` 汇总顺序 = **发现顺序**（Manager 对 output 按发现序注册；
pluggy LIFO 执行 = 逆发现序）。为保证执行顺序 = yaml 顺序
（files: [csa, con, xcon, csv, cpc, cpm, cds_lib]；
reports: [aesthetic, ioport, mapping, error]），此处声明**逆 yaml 序**：
文件插件 ``[cds_lib, cpm, cpc, csv, xcon, con, csa]``、报告插件
``[error, mapping, ioport, aesthetic]``。
"""

from __future__ import annotations

from ..spec import PluginSpec
from . import (
    aesthetic,
    cds_lib,
    con,
    cpc,
    cpm,
    csa,
    csv,
    error,
    ioport,
    mapping,
    xcon,
)

#: 发现顺序 = 逆 yaml 序（LIFO 执行 = yaml 顺序；S2 逆序注册机制）。
_SPECS: list[PluginSpec] = [
    # 文件插件（逆 yaml：cds_lib ← cpm ← cpc ← csv ← xcon ← con ← csa）
    cds_lib.PLUGIN,
    cpm.PLUGIN,
    cpc.PLUGIN,
    csv.PLUGIN,
    xcon.PLUGIN,
    con.PLUGIN,
    csa.PLUGIN,
    # 报告插件（逆 yaml：error ← mapping ← ioport ← aesthetic）
    error.PLUGIN,
    mapping.PLUGIN,
    ioport.PLUGIN,
    aesthetic.PLUGIN,
]

__all__ = [
    "_SPECS",
    "aesthetic",
    "cds_lib",
    "con",
    "cpc",
    "cpm",
    "csa",
    "csv",
    "error",
    "ioport",
    "mapping",
    "xcon",
]
