"""NetNameConnect — M5 跨页网网络名连接（Phase XVII，用户 D2）。

用户 D2：**IOPORT→网络名，同步去除，con 层也可以去除**（CSA + con 都改
网络名表达）。本模块提供跨页网判定 + IOPORT 跳过计划 + 网络名标签补发射：

* ``cross_page_bare_names`` —— 设计级网在 >1 页出现的 bare 名集合
  （数据源 = DesignConnectivity 模型，数据源铁律）；
* ``ioport_skip_plan``     —— ``ioport.use_net_name=true`` 时全部 IOPORT
  符号不生成（跨页连接由同名 SIG_NAME 网络名表达）；
* ``net_name_labels``      —— 跨页网若本页无 source-pin 标签，补一条
  线上 SIG_NAME（``_sig_name_on_wire`` 同格式）；
* ``net_name_endpoints``   —— **Phase XXII D3 主接线点（Q3 单一调用点）**：
  路由完成后对跨页网 WIRE 悬空端补 SIG_NAME；非跨页补全由 csa_writer
  泛化 has_label 循环承担（去重：同网不双标签）。``net_name_labels``
  保留（向后兼容 + 单测引用），但 csa_writer use_net_name 分支不再调用。

con/xcon/cpm 评估：con 层本就没有 IOPORT 概念（跨页连接 = 设计级网
scope=2 + alias），天然是"网络名"表达；``use_net_name`` 只关 CSA 的
IOPORT 符号发射，不碰 con/xcon/cpm 结构（避免冗余开关）。

配置开关：``ioport.use_net_name``（默认 false，保留 IOPORT 符号；
true 时改为网络名表达）。
"""

from __future__ import annotations

import logging
from typing import Iterable

logger = logging.getLogger(__name__)


def cross_page_bare_names(conn) -> set[str]:
    """设计级网中出现在 >1 页的 bare 名集合。

    Args:
        conn: DesignConnectivity（NetRecord.pages 为页号列表）。

    Returns:
        ``{"NET_A", "12V0", ...}`` —— 跨页网 bare 名（小写）。
    """
    names: set[str] = set()
    for net in getattr(conn, "nets", []) or []:
        pages = getattr(net, "pages", None)
        if pages is None:
            continue
        if len(pages) > 1 and getattr(net, "bare_name", ""):
            names.add(str(net.bare_name).lower())
    return names


def ioport_skip_plan(
    off_pages: Iterable[dict],
    use_net_name: bool,
) -> list[dict]:
    """决定哪些 off_page 条目不生成 IOPORT 符号。

    Args:
        off_pages: 页级 off_page 列表（``{"name", "net_name"}``）。
        use_net_name: ``ioport.use_net_name``（用户 D2）。

    Returns:
        应**跳过**的 off_page 条目列表（``use_net_name=true`` 时全部）。
    """
    off = list(off_pages or [])
    if not use_net_name:
        return []
    return off


def net_name_labels(
    net_pin_map: dict[str, list],
    source_pin_keys: set[str],
    cross_page: set[str],
    use_net_name: bool,
) -> list[tuple[tuple[int, int], str]]:
    """跨页网缺失 source-pin 标签时，补线上 SIG_NAME。

    Args:
        net_pin_map: 网显示名 → 引脚列表。
        source_pin_keys: ``refdes.pin`` source-pin 键集合。
        cross_page: ``cross_page_bare_names`` 输出（小写 bare 名）。
        use_net_name: 用户 D2 开关。

    Returns:
        ``[(coord, net_display)]`` —— 需要 ``_sig_name_on_wire`` 的条目。
    """
    if not use_net_name:
        return []
    out: list[tuple[tuple[int, int], str]] = []
    for net_display, pins in (net_pin_map or {}).items():
        bare = str(net_display).lower().replace("\\g", "")
        if bare not in cross_page:
            continue
        has_label = any(
            (str(p.get("refdes", "")), str(p.get("pin", ""))) in source_pin_keys
            for p in pins if isinstance(p, dict)
        )
        if has_label or not pins:
            continue
        coord = tuple(pins[0]["coord"])
        out.append((coord, net_display))
    return out


def ioport_net_mapping(off_pages: Iterable[dict]) -> dict[str, str]:
    """off_page 条目 → 网络名映射（``{"OFFPAGE_0": "NET_A"}``）。

    供审计/报告：IOPORT 符号与网络名的对应关系。

    Args:
        off_pages: 页级 off_page 列表。

    Returns:
        ``{name: net_name}``。
    """
    mapping: dict[str, str] = {}
    for op in off_pages or []:
        name = str(op.get("name", "") or "")
        net_name = str(op.get("net_name", "") or name)
        if name:
            mapping[name] = net_name
    return mapping


def net_name_endpoints(
    net_pin_map: dict[str, list],
    wire_segments: dict[str, list[tuple[int, int, int, int]]],
    cross_page: set[str],
    use_net_name: bool,
) -> list[tuple[tuple[int, int], str]]:
    """网络名标签落到**电线末端/悬空端**（Phase XVIII R7）。

    用户实测 B5：use_net_name 版本中，跨页网电线延伸到原 IOPORT 位置
    后**悬空**且无网络名标签，信号去向不可知。本函数对每个跨页网，
    找出其 WIRE 段中**不与任何引脚重合**的开放端点（悬空端），在该处
    补 SIG_NAME 网络名标签。

    Args:
        net_pin_map: 网显示名 → 引脚列表（引脚坐标集）。
        wire_segments: 网显示名 → WIRE 段列表（(x1,y1,x2,y2)）。
        cross_page: 跨页网 bare 名集合（小写）。
        use_net_name: ``ioport.use_net_name``（仅该模式需要）。

    Returns:
        ``[(coord, net_display)]`` —— 悬空端坐标 + 网络名。
    """
    if not use_net_name:
        return []
    out: list[tuple[tuple[int, int], str]] = []
    for net_display, segs in (wire_segments or {}).items():
        bare = str(net_display).lower().replace("\\g", "")
        if bare not in cross_page:
            continue
        pins = net_pin_map.get(net_display, []) or []
        pin_coords = {
            (int(p["coord"][0]), int(p["coord"][1]))
            for p in pins if isinstance(p, dict) and p.get("coord")
        }
        # 收集悬空端点：段端点不与任何引脚重合。
        dangling: list[tuple[int, int]] = []
        for s in segs:
            for ep in ((s[0], s[1]), (s[2], s[3])):
                if ep not in pin_coords and ep not in dangling:
                    dangling.append(ep)
        if not dangling:
            continue
        # 取第一个悬空端（距引脚最远者优先，更可能是"尽头"）。
        def _far(ep: tuple[int, int]) -> float:
            if not pin_coords:
                return 0.0
            return max(
                ((ep[0] - px) ** 2 + (ep[1] - py) ** 2) ** 0.5
                for (px, py) in pin_coords
            )

        dangling.sort(key=_far, reverse=True)
        out.append((dangling[0], net_display))
    return out
