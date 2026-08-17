"""参数 schema 推断 — PluginSpec + 配置默认值 → GUI 表单 schema（S9 §3.3）。

设计依据：``docs/gui-design.md`` §3.3（参数 schema → 表单控件映射）。
纯逻辑模块（**不依赖 PySide6**），可单测；UI 层按 ``type`` 字段生成控件：

=============  =============
schema type    控件
=============  =============
bool           QCheckBox
int            QSpinBox
float          QDoubleSpinBox
str            QLineEdit
enum           QComboBox（choices 限定）
list           QListWidget + 增删
dict           QTreeWidget（折叠）
=============  =============

类型推断基于**实际默认值**（``isinstance``），因此无论参数源是
RoutingConfig 子节、MatchSection dict 还是 TestSection 均一致。
``enum`` 特判：str 默认值且字段名在 :data:`ENUM_CHOICES` 中。
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ENUM_CHOICES",
    "infer_field_type",
    "jsonable",
    "build_plugin_schema",
]

#: 已知枚举字段的合法取值（gui-design §3.3 示例 routing.mode p0/detour/edif_reuse）。
#: 依据字段名映射 —— 新增枚举字段在此登记（合理默认，可扩展）。
ENUM_CHOICES: dict[str, list[str]] = {
    "mode": ["p0", "detour", "edif_reuse"],
    "net_order": ["short_first", "long_first"],
    "un_name_policy": ["rename", "keep", "omit"],
    "mock_text_cmd": ["T", "P", "X"],
}


def infer_field_type(key: str, value: Any) -> str:
    """根据字段默认值推断 schema type（bool 必须先于 int 判断）。"""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "enum" if key in ENUM_CHOICES else "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return "str"


def jsonable(value: Any) -> Any:
    """递归转换为 JSON 可序列化值（dataclass → dict；tuple → list）。"""
    import dataclasses

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    return str(value)


def build_plugin_schema(spec: Any, base: Any) -> dict:
    """从 PluginSpec + 参数源对象构造表单 schema。

    Args:
        spec: :class:`cis2hdl.plugins.spec.PluginSpec`（name/stage/description/
            param_section/param_fields）。
        base: 参数源对象（RoutingConfig 子节 / RoutingConfig 顶层 /
            MatchSection / TestSection / InputSection / OutputSection）；
            ``None`` = 无参数。

    Returns:
        ``{"name", "stage", "description", "param_section", "fields"}``；
        ``fields`` 每项 ``{"key", "type", "default", "label", "choices"}``。
        未知字段（base 无属性）退化为 ``str`` 空值（防御，不阻断表单生成）。
    """
    fields: list[dict[str, Any]] = []
    for field_name in spec.param_fields or ():
        if base is None or not hasattr(base, field_name):
            fields.append({
                "key": str(field_name),
                "type": "str",
                "default": "",
                "label": str(field_name),
                "choices": None,
            })
            continue
        value = getattr(base, field_name)
        ftype = infer_field_type(field_name, value)
        fields.append({
            "key": str(field_name),
            "type": ftype,
            "default": jsonable(value),
            "label": str(field_name),
            "choices": list(ENUM_CHOICES[field_name]) if (
                ftype == "enum" and field_name in ENUM_CHOICES
            ) else None,
        })
    return {
        "name": spec.name,
        "stage": spec.stage,
        "description": spec.description or "",
        "param_section": spec.param_section or "",
        "fields": fields,
    }
