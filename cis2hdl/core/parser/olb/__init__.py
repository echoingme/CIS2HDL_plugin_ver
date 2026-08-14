"""OLB Parser — OrCAD Capture CIS 器件库 (.olb) 解析器。

OLB 文件与 DSN 文件同样使用 CFB (Compound File Binary) 格式。
此包提供 OLBOleReader（CFB 容器读取）和 OLBParser（结构体解析）。

参考:
    - docs/ORCAD_SOURCE_ANALYSIS.md §1.2
    - openOrCadParser: OlbParser.cpp
"""

from .olb_reader import OLBOleReader
from .olb_parser import OLBParser

__all__ = [
    "OLBOleReader",
    "OLBParser",
]
