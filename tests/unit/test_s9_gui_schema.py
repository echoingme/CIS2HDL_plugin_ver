"""S9 GUI 测试 — 参数 schema 推断（§3.3 控件映射）。

纯逻辑模块测试（无 PySide6）。
"""

from __future__ import annotations

from cis2hdl.gui.schema import (
    ENUM_CHOICES,
    build_plugin_schema,
    infer_field_type,
    jsonable,
)
from cis2hdl.plugins.spec import PluginSpec


def test_infer_field_type() -> None:
    assert infer_field_type("enabled", True) == "bool"
    assert infer_field_type("count", 3) == "int"
    assert infer_field_type("factor", 0.65) == "float"
    assert infer_field_type("name", "worklib") == "str"
    assert infer_field_type("mode", "p0") == "enum"  # ENUM_CHOICES 命中
    assert infer_field_type("items", [1, 2]) == "list"
    assert infer_field_type("weights", {"a": 1}) == "dict"


def test_enum_choices_known() -> None:
    assert ENUM_CHOICES["mode"] == ["p0", "detour", "edif_reuse"]


def test_jsonable_dataclass_and_tuple() -> None:
    assert jsonable((1, 2)) == [1, 2]
    assert jsonable(True) is True
    assert jsonable({"a": (1, 2)}) == {"a": [1, 2]}


def test_build_plugin_schema_beautify() -> None:
    from cis2hdl.core.pipeline_config import RoutingConfig  # noqa: F401 别名

    spec = PluginSpec(
        name="overlap_resolve", stage="beautify",
        description="防重叠", param_section="overlap",
        param_fields=("check", "resolve", "avoid_margin"),
    )
    schema = build_plugin_schema(spec, RoutingConfig().overlap)
    assert schema["name"] == "overlap_resolve"
    assert schema["param_section"] == "overlap"
    by_key = {f["key"]: f for f in schema["fields"]}
    assert by_key["check"]["type"] == "bool"
    assert by_key["resolve"]["type"] == "bool"
    assert by_key["avoid_margin"]["type"] == "int"
    assert by_key["avoid_margin"]["default"] == 50


def test_build_plugin_schema_enum() -> None:
    from cis2hdl.core.pipeline_config import RoutingConfig

    spec = PluginSpec(name="x", stage="beautify", param_section="",
                      param_fields=("mode",))
    schema = build_plugin_schema(spec, RoutingConfig())
    field = schema["fields"][0]
    assert field["type"] == "enum"
    assert field["choices"] == ["p0", "detour", "edif_reuse"]
    assert field["default"] == "p0"


def test_build_plugin_schema_match_dict() -> None:
    from cis2hdl.core.pipeline_config import MatchSection

    spec = PluginSpec(name="exact", stage="match", param_fields=("weights",))
    schema = build_plugin_schema(spec, MatchSection())
    assert schema["fields"][0]["type"] == "dict"


def test_build_plugin_schema_unknown_field_fallback() -> None:
    spec = PluginSpec(name="ghost", stage="beautify", param_section="overlap",
                      param_fields=("unknown_field",))
    schema = build_plugin_schema(spec, None)
    assert schema["fields"][0]["type"] == "str"
    assert schema["fields"][0]["default"] == ""
