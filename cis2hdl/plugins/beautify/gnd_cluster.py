"""gnd_cluster 美化插件（FR4 / Phase XVII R3）。S2 占位：顺序记录 + enabled 感知 → False。"""

from __future__ import annotations

from .._stubs import make_beautify_stub
from ..spec import PluginSpec

PLUGIN = PluginSpec(
    name="gnd_cluster",
    stage="beautify",
    description="GND 聚类（默认；S5 真实现）",
    cls=make_beautify_stub("gnd_cluster"),
    module=__name__,
    param_section="gnd_distribution",
    param_fields=("enabled", "cluster_radius"),
    writes_keys=("routed_nets",),
    requires=("ir", "matches"),
)
