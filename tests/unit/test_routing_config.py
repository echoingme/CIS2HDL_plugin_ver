"""Phase XIV T1 — routing.yaml 配置加载/覆盖/默认值（D5）。

Covers:
  * RoutingConfig 默认值（全部新功能默认关）
  * Config.load_from_file 从 routing.yaml 加载
  * 段级覆盖（text_layout / overlap / power_ic / aesthetic）
"""

from __future__ import annotations

from pathlib import Path

import pytest

_CONFIG = Path(__file__).resolve().parents[2] / "cis2hdl" / "config" / "routing.yaml"


class TestRoutingConfigDefaults:
    def test_defaults_all_off(self):
        from cis2hdl.core.config import RoutingConfig

        cfg = RoutingConfig()
        assert cfg.mode == "p0"
        assert cfg.text_layout.enabled is False
        assert cfg.overlap.check is False
        assert cfg.power_ic.enabled is False
        assert cfg.aesthetic.enabled is False
        assert cfg.manual_matches == ""
        assert cfg.export_unmatched == ""
        assert cfg.fallback_to_p0 is True
        assert cfg.cross_page_opt is False

    def test_defaults_align_flags_on(self):
        from cis2hdl.core.config import RoutingConfig

        cfg = RoutingConfig()
        assert cfg.text_layout.align_net_names is True
        assert cfg.text_layout.align_ports is True
        assert cfg.text_layout.diff_pair_pn is True


class TestRoutingConfigLoad:
    def test_config_file_exists(self):
        assert _CONFIG.exists(), f"routing.yaml missing: {_CONFIG}"

    def test_load_from_file(self):
        from cis2hdl.core.config import Config

        cfg = Config()
        cfg.load_from_file(_CONFIG)
        assert cfg.routing.mode == "p0"
        assert cfg.routing.text_layout.enabled is False
        assert cfg.routing.overlap.check is False
        assert cfg.routing.power_ic.enabled is False

    def test_load_missing_file_raises(self):
        from cis2hdl.core.config import Config

        cfg = Config()
        with pytest.raises(FileNotFoundError):
            cfg.load_from_file(Path("/nonexistent/routing.yaml"))

    def test_from_dict_overrides(self):
        from cis2hdl.core.config import RoutingConfig

        cfg = RoutingConfig.from_dict({
            "mode": "detour",
            "text_layout": {"enabled": True, "align_net_names": False},
            "overlap": {"check": True, "min_area": 1000},
            "power_ic": {"enabled": True},
            "manual_matches": "mm.yaml",
        })
        assert cfg.mode == "detour"
        assert cfg.text_layout.enabled is True
        assert cfg.text_layout.align_net_names is False
        assert cfg.overlap.check is True
        assert cfg.overlap.min_area == 1000
        assert cfg.power_ic.enabled is True
        assert cfg.manual_matches == "mm.yaml"

    def test_from_dict_ignores_unknown(self):
        from cis2hdl.core.config import RoutingConfig

        cfg = RoutingConfig.from_dict({"bogus_key": 123, "mode": "edif_reuse"})
        assert cfg.mode == "edif_reuse"


class TestRoutingConfigPhaseXVI:
    def test_mirror_defaults(self):
        """mirror.normalize 默认 true（正确性修复）；report 默认 true。"""
        from cis2hdl.core.config import RoutingConfig

        cfg = RoutingConfig()
        assert cfg.mirror.normalize is True
        assert cfg.mirror.report is True

    def test_ioport_audit_defaults_off(self):
        """ioport.audit 默认 false；skip_orphan/manual_names 默认。"""
        from cis2hdl.core.config import RoutingConfig

        cfg = RoutingConfig()
        assert cfg.ioport.audit is False
        assert cfg.ioport.skip_orphan is False
        assert cfg.ioport.manual_names == {}

    def test_mirror_from_dict(self):
        from cis2hdl.core.config import RoutingConfig

        cfg = RoutingConfig.from_dict({"mirror": {"normalize": False}})
        assert cfg.mirror.normalize is False
        assert cfg.mirror.report is True

    def test_ioport_from_dict_new_fields(self):
        from cis2hdl.core.config import RoutingConfig

        cfg = RoutingConfig.from_dict({
            "ioport": {
                "audit": True,
                "skip_orphan": True,
                "manual_names": {"WPS": "wps"},
            },
        })
        assert cfg.ioport.audit is True
        assert cfg.ioport.skip_orphan is True
        assert cfg.ioport.manual_names == {"WPS": "wps"}

    def test_load_from_file_phase_xvi_sections(self):
        """routing.yaml 的 mirror/ioport.audit 段可加载。"""
        from cis2hdl.core.config import Config

        cfg = Config()
        cfg.load_from_file(_CONFIG)
        assert cfg.routing.mirror.normalize is True
        assert cfg.routing.mirror.report is True
        assert cfg.routing.ioport.audit is False
        assert cfg.routing.ioport.skip_orphan is False
        assert cfg.routing.ioport.manual_names == {}
