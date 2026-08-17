"""CIS2HDL GUI v2 — 工程工作台（S9）。

设计依据：``docs/gui-design.md``（完整版）。与旧 GUI（v1 面板）共存：
v1 面板保留不动（S10 决定去留）；v2 提供新的"工程工作台"交互。

纯逻辑层（controller/schema/yaml_bridge，**无 PySide6 依赖**，可单测）位于
``cis2hdl/gui/`` 根；PySide6 UI 组件位于本包。
"""

from ..controller import PipelineController
from ..schema import build_plugin_schema
from ..yaml_bridge import (
    FormState,
    YamlValidationError,
    cfg_from_form_state,
    cfg_to_yaml_text,
    form_state_from_cfg,
    yaml_text_to_cfg,
)
from .app import HAS_PYSIDE6, run_gui

__all__ = [
    "PipelineController",
    "FormState",
    "YamlValidationError",
    "cfg_from_form_state",
    "cfg_to_yaml_text",
    "form_state_from_cfg",
    "yaml_text_to_cfg",
    "build_plugin_schema",
    "run_gui",
    "HAS_PYSIDE6",
]
