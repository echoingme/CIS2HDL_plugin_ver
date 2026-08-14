"""ProfileManager — 自定义 profile 的增删改查 + 查重 + 导入导出（§3.8 落实）。

设计依据：``docs/S1-config-design.md`` §5（架构师高见远交付）。

目录布局（K7：内置与自定义同目录 + ``builtin`` 标志）::

    cis2hdl_plugin_ver/
    ├── pipeline.yaml                    # 主配置（权威；profile: 记录当前生效名）
    └── profiles/
        ├── default.yaml                 # 内置只读（builtin: true，禁止覆盖/删除）
        ├── max-beauty.yaml              # 内置只读
        ├── fast.yaml                    # 内置只读
        ├── match-only.yaml              # 内置只读
        └── my-power-design.yaml         # 用户自定义（原子写）

profile 文件格式（§5.2）：``schema_version`` + ``profile`` 块
（name/description/created/builtin/plugins/params）。
S1 最小扩展：``profile.output``（files/reports）用于表达
"output.reports=[mapping]" 类设置（见 profiles/match-only.yaml 注释）。

查重规则（§5.4）：
  - 插件组合等价：``set(a) == set(b)`` 逐阶段（**顺序无关**）
  - 参数等价：``deep_eq_params``（dataclass→asdict 递归；list **顺序敏感**；
    float 精确 ``==``，S1 决策 6）
  - 组合同、参数异：允许保存，``create()`` 记录 ``self.last_note``
  - 名称冲突：trim + ``casefold()`` 比较；同名 → 非 overwrite 拒绝

导入校验（§5.5）：结构 / 插件白名单（BUILTIN_PLUGIN_NAMES，S2 起由
PluginManager 提供）/ 参数类型（warning 不阻断）/ 路径安全（防御性）/
schema_version ≤ 1。
"""

from __future__ import annotations

import dataclasses
import datetime
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .pipeline_config import (
    PipelineConfig,
    OutputSection,
    RoutingConfig,
    apply_params,
    atomic_write_text,
    deep_eq_params,
    routing_params_deep_diff,
    routing_to_params,
)

logger = logging.getLogger(__name__)

__all__ = [
    "STAGES",
    "BUILTIN_PLUGIN_NAMES",
    "ProfileInfo",
    "ProfileDiff",
    "ProfileError",
    "ProfileReadOnlyError",
    "DuplicateProfileError",
    "ProfileManager",
]

#: 插件组合比较的 5 个阶段（顺序 = 查重比较顺序）。
STAGES: tuple[str, ...] = ("input", "match", "beautify", "output", "test")

#: S1 插件白名单常量表（§5.5）；S2 起改由 PluginManager.list_plugins() 提供。
BUILTIN_PLUGIN_NAMES: dict[str, set[str]] = {
    "input": {"edif", "dsn", "cross_ref", "pstxnet", "pstchip"},
    "match": {"exact", "fuzzy", "passive", "fallback", "power_ic"},
    "beautify": {
        "overlap_resolve", "gnd_cluster", "parallel_short", "wire_simplify",
        "three_stage_stub", "text_layout",
    },
    "output": {
        "csa", "con", "xcon", "csv", "cpc", "cpm", "cds_lib",
        "aesthetic", "ioport", "mapping", "error", "benchmark", "net_name",
    },
    "test": {"unit", "e2e", "qa_package"},
}

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_NAME_MAX_LEN = 64

#: 路径/命令类 key 防御性检查关键词（§5.5 ④）。
_PATH_SAFETY_KEYWORDS = ("file", "path", "dir", "command", "exec")
_PATH_LIKE_SUFFIXES = (".yaml", ".yml", ".json", ".csv", ".edf", ".dsn", ".olb")


class ProfileError(ValueError):
    """profile 操作失败（查重/校验/只读等；CLI 退出码 2/3）。"""


class ProfileReadOnlyError(ProfileError):
    """内置只读 profile 禁止操作（CLI 退出码 3）。"""


class DuplicateProfileError(ProfileError):
    """查重失败：插件组合 + 参数与已有 profile 全等（CLI 退出码 2）。

    ``duplicate_of`` 指明重复来源。
    """

    def __init__(self, message: str, duplicate_of: str | None = None) -> None:
        super().__init__(message)
        self.duplicate_of = duplicate_of


@dataclass
class ProfileInfo:
    """``list_profiles`` 返回项。"""

    name: str
    builtin: bool
    """True = 内置只读。"""
    description: str
    path: Path


@dataclass
class ProfileDiff:
    """两 profile 的差异（查重核心，§3.8.2）。

    ``diff()`` 返回**首个差异阶段**的差异；``equivalent=True`` 表示全部阶段
    插件组合+参数全等。完整逐阶段差异用 ``diff_all()``（GUI 展示用）。
    """

    stage: str
    """差异所在阶段（beautify 等）；equivalent=True 时为 ""。"""
    added: list[str]
    """新组合多出的插件。"""
    removed: list[str]
    """新组合缺少的插件。"""
    param_diffs: dict[str, dict]
    """``{plugin: {key: (旧值, 新值)}}``；仅含差异参数。"""
    equivalent: bool
    """True = 插件组合+参数全等（判重）。"""


class ProfileManager:
    """自定义 profile 的增删改查 + 查重 + 导入导出（§3.8 落实）。"""

    def __init__(
        self,
        profiles_dir: Path | None = None,
        builtin_names: tuple[str, ...] = ("default", "max-beauty", "fast", "match-only"),
    ) -> None:
        """``profiles_dir`` 不存在时创建（幂等）。"""
        if profiles_dir is None:
            profiles_dir = Path(__file__).resolve().parents[2] / "profiles"
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.builtin_names = tuple(builtin_names)
        self.last_note: str = ""
        """最近一次 ``create()`` 的提示（组合同、参数异时写入）。"""

    # ── 查询 ──────────────────────────────────────────────────────────

    def list_profiles(self) -> list[ProfileInfo]:
        """扫描 ``profiles/*.yaml``，按 builtin 优先 + 名称排序。

        解析失败条目打 warning 跳过（不阻断整体扫描）。
        """
        infos: list[ProfileInfo] = []
        for p in sorted(self.profiles_dir.glob("*.yaml")):
            try:
                data = self._load_profile_file(p)
                prof = data.get("profile", {})
                name = str(prof.get("name") or p.stem)
                infos.append(ProfileInfo(
                    name=name,
                    builtin=bool(prof.get("builtin", False)),
                    description=str(prof.get("description", "")),
                    path=p,
                ))
            except Exception as exc:  # noqa: BLE001 — 单条损坏不阻断
                logger.warning("profile 解析失败，跳过: %s (%s)", p, exc)
        infos.sort(key=lambda i: (not i.builtin, i.name.casefold()))
        return infos

    def get(self, name: str) -> PipelineConfig:
        """解析为完整配置（合并内置 default 增量）：

        ① 校验名称存在
        ② 取默认 PipelineConfig（= pipeline.yaml 默认行为）
        ③ 用 profile 文件 plugins 替换各阶段插件列表（5 阶段）
        ④ 用 profile 文件 params 深合并（增量覆盖）
        ⑤ 应用 ``profile.output`` 扩展（S1）
        ⑥ 返回完整 PipelineConfig（profile 字段置 name）
        """
        path = self._resolve_profile_path(name)
        if path is None:
            available = ", ".join(i.name for i in self.list_profiles()) or "(无)"
            raise ProfileError(f"profile 不存在: {name!r}（可用: {available}）")
        data = self._load_profile_file(path)
        prof = data.get("profile", {})

        cfg = PipelineConfig()
        cfg.profile = str(prof.get("name") or path.stem)

        plugins = prof.get("plugins")
        if isinstance(plugins, dict):
            for stage in STAGES:
                if stage in plugins:
                    self._set_stage_plugins(cfg, stage, plugins[stage])

        params = prof.get("params")
        if isinstance(params, dict) and params:
            self._merge_params(cfg.beautify.params, params)

        out = prof.get("output")
        if isinstance(out, dict):
            if "files" in out:
                cfg.output.files = [str(x) for x in out["files"]]
            if "reports" in out:
                cfg.output.reports = [str(x) for x in out["reports"]]

        return cfg

    # ── 写操作 ────────────────────────────────────────────────────────

    def create(self, name: str, cfg: PipelineConfig, overwrite: bool = False) -> None:
        """① 名称校验；② 查重；③ 名称冲突；④ 原子写；⑤ 内置只读拒绝。

        查重语义（§5.4）：
          - duplicate（组合+参数全等）→ ``DuplicateProfileError``
          - 组合同、参数异 → 允许保存，``self.last_note`` 记录提示
        """
        canonical = self._validate_name(name)

        if canonical.casefold() in {b.casefold() for b in self.builtin_names}:
            raise ProfileReadOnlyError(f"内置只读 profile 不可覆盖/创建: {canonical!r}")

        dup = self._check_duplicate(cfg)
        if dup is not None and dup.casefold() != canonical.casefold():
            raise DuplicateProfileError(
                f"profile 重复：插件组合+参数与已有 profile {dup!r} 全等（查重 §5.4）",
                duplicate_of=dup,
            )

        existing = self._resolve_profile_path(canonical)
        if existing is not None and not overwrite:
            raise FileExistsError(
                f"profile 名称冲突: {canonical!r} 已存在（用 overwrite=True 覆盖）"
            )

        self.last_note = ""
        same_combos = self._find_same_combos(cfg, exclude=canonical)
        if same_combos:
            self.last_note = f"插件组合与 {same_combos!r} 相同但参数不同"

        data = self._build_profile_dict(canonical, cfg)
        text = yaml.safe_dump(
            data, allow_unicode=True, sort_keys=False, default_flow_style=None,
        )
        out = self.profiles_dir / f"{canonical}.yaml"
        self._atomic_write(out, text)

    def delete(self, name: str) -> None:
        """删除自定义 profile；内置（builtin: true）→ 拒绝；不存在 → FileNotFoundError。"""
        path = self._resolve_profile_path(name)
        if path is None:
            raise FileNotFoundError(f"profile 不存在: {name!r}")
        data = self._load_profile_file(path)
        if bool(data.get("profile", {}).get("builtin", False)):
            raise ProfileReadOnlyError(f"内置只读 profile 不可删除: {name!r}")
        path.unlink()

    def export(self, name: str, out_path: Path | None = None) -> Path:
        """导出为可分发的 .yaml（builtin: true 条目转 false，去掉 created）。

        ``out_path`` 缺省 = ``profiles/export_<name>_<ts>.yaml``。
        返回写出路径（原子写）。
        """
        path = self._resolve_profile_path(name)
        if path is None:
            raise ProfileError(f"profile 不存在: {name!r}")
        data = self._load_profile_file(path)
        prof = dict(data.get("profile", {}))
        prof.pop("created", None)
        prof["builtin"] = False
        exported = {"schema_version": data.get("schema_version", 1), "profile": prof}

        if out_path is None:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = self.profiles_dir / f"export_{name}_{ts}.yaml"
        out_path = Path(out_path)
        text = yaml.safe_dump(
            exported, allow_unicode=True, sort_keys=False, default_flow_style=None,
        )
        self._atomic_write(out_path, text)
        return out_path

    def import_file(self, path: Path, rename_to: str | None = None) -> str:
        """导入 profile 文件（校验链 §5.5），返回实际写入的 profile 名。

        ① 结构校验（必填 profile.name + profile.plugins，≥1 阶段非空）
        ② 插件白名单（未知 → 失败并列出）
        ③ 参数类型校验（warning 不阻断）
        ④ 路径安全校验（防御性）
        ⑤ schema_version ≤ 1（>1 拒绝）
        ⑥ 名称冲突 → rename_to 指定则改名，否则报错拒绝
        ⑦ 原子写
        """
        src = Path(path)
        with src.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        if not isinstance(raw, dict):
            raise ProfileError(f"导入文件顶层必须是 mapping: {src}")
        cleaned = self._validate_import(raw)

        prof = cleaned["profile"]
        name = self._validate_name(rename_to) if rename_to else self._validate_name(
            str(prof["name"])
        )

        if name.casefold() in {b.casefold() for b in self.builtin_names}:
            raise ProfileReadOnlyError(f"内置只读 profile 名称不可导入: {name!r}")

        existing = self._resolve_profile_path(name)
        if existing is not None:
            if rename_to:
                raise FileExistsError(
                    f"rename 目标冲突: {name!r} 已存在（请换一个 --rename 名称）"
                )
            raise FileExistsError(f"profile 已存在: {name!r}（用 --rename 改名导入）")

        prof["name"] = name
        data = {"schema_version": cleaned.get("schema_version", 1), "profile": prof}
        text = yaml.safe_dump(
            data, allow_unicode=True, sort_keys=False, default_flow_style=None,
        )
        out = self.profiles_dir / f"{name}.yaml"
        self._atomic_write(out, text)
        return name

    # ── 差异/查重 ─────────────────────────────────────────────────────

    def diff(self, a: PipelineConfig, b: PipelineConfig) -> ProfileDiff:
        """查重核心（§3.8.2）：

        ① 逐阶段 set 比较 plugins（顺序无关）——首现差异即返回该阶段
        ② 全部相同 → 参数深度比较：
           - 全等 → equivalent=True
           - 不等 → param_diffs 列出 {plugin: {key: (旧, 新)}}
        """
        combos_a = a.plugin_combos()
        combos_b = b.plugin_combos()
        for stage in STAGES:
            sa, sb = combos_a[stage], combos_b[stage]
            if sa != sb:
                return ProfileDiff(
                    stage=stage,
                    added=sorted(sb - sa),
                    removed=sorted(sa - sb),
                    param_diffs={},
                    equivalent=False,
                )
        if deep_eq_params(a.beautify.params, b.beautify.params):
            return ProfileDiff(stage="", added=[], removed=[], param_diffs={}, equivalent=True)
        return ProfileDiff(
            stage="beautify",
            added=[],
            removed=[],
            param_diffs=routing_params_deep_diff(a.beautify.params, b.beautify.params),
            equivalent=False,
        )

    def diff_all(self, a: PipelineConfig, b: PipelineConfig) -> list[ProfileDiff]:
        """完整逐阶段差异（GUI 差异视图用）；equivalent 汇总。"""
        combos_a = a.plugin_combos()
        combos_b = b.plugin_combos()
        results: list[ProfileDiff] = []
        for stage in STAGES:
            sa, sb = combos_a[stage], combos_b[stage]
            if sa != sb:
                results.append(ProfileDiff(
                    stage=stage,
                    added=sorted(sb - sa),
                    removed=sorted(sa - sb),
                    param_diffs={},
                    equivalent=False,
                ))
            else:
                results.append(ProfileDiff(
                    stage=stage, added=[], removed=[], param_diffs={}, equivalent=True,
                ))
        params_eq = deep_eq_params(a.beautify.params, b.beautify.params)
        results.append(ProfileDiff(
            stage="beautify.params",
            added=[],
            removed=[],
            param_diffs={} if params_eq else routing_params_deep_diff(
                a.beautify.params, b.beautify.params,
            ),
            equivalent=params_eq,
        ))
        return results

    # ── 内部 ──────────────────────────────────────────────────────────

    def _check_duplicate(self, cfg: PipelineConfig) -> str | None:
        """返回 duplicate_of 名（组合+参数全等）或 None（不判重）。"""
        for info in self.list_profiles():
            try:
                existing = self.get(info.name)
            except Exception:  # noqa: BLE001 — 损坏 profile 跳过
                continue
            if cfg.deep_eq(existing):
                return info.name
        return None

    def _find_same_combos(self, cfg: PipelineConfig, exclude: str) -> str | None:
        """返回插件组合相同但参数不同的已有 profile 名（提示用）。"""
        target = cfg.plugin_combos()
        for info in self.list_profiles():
            if info.name.casefold() == exclude.casefold():
                continue
            try:
                existing = self.get(info.name)
            except Exception:  # noqa: BLE001
                continue
            if existing.plugin_combos() == target:
                return info.name
        return None

    def _validate_name(self, name: str) -> str:
        """trim 规范 + 非法字符校验，返回规范名（冲突检测用 casefold）。"""
        canonical = (name or "").strip()
        if not canonical:
            raise ProfileError("profile 名称不能为空")
        if len(canonical) > _NAME_MAX_LEN:
            raise ProfileError(f"profile 名称长度不能超过 {_NAME_MAX_LEN}")
        if not _NAME_RE.match(canonical):
            raise ProfileError(
                "profile 名称只能包含字母/数字/._-，且以字母或数字开头"
            )
        return canonical

    def _validate_import(self, data: dict) -> dict:
        """结构/白名单/类型/路径安全/schema_version 校验，返回清洗后 dict。"""
        schema_version = data.get("schema_version", 1)
        if not isinstance(schema_version, int) or schema_version > 1:
            raise ProfileError(
                f"不支持的 schema_version={schema_version!r}（当前支持 ≤1，请升级）"
            )

        prof = data.get("profile")
        if not isinstance(prof, dict):
            raise ProfileError("profile 块缺失或不是 mapping")
        name = prof.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ProfileError("profile.name 必须是非空字符串")
        self._validate_name(name)

        plugins = prof.get("plugins")
        if not isinstance(plugins, dict):
            raise ProfileError("profile.plugins 必须是 mapping")
        if not any(
            isinstance(plugins.get(s), list) and plugins[s] for s in STAGES
        ):
            raise ProfileError("profile.plugins 至少 1 个阶段非空")

        cleaned_plugins: dict[str, list[str]] = {}
        unknown: dict[str, list[str]] = {}
        for stage in STAGES:
            stage_plugins = plugins.get(stage)
            if stage_plugins is None:
                continue
            if not isinstance(stage_plugins, list):
                raise ProfileError(f"profile.plugins.{stage} 必须是 list")
            cleaned_plugins[stage] = [str(x) for x in stage_plugins]
            bad = [x for x in cleaned_plugins[stage]
                   if x not in BUILTIN_PLUGIN_NAMES.get(stage, set())]
            if bad:
                unknown[stage] = bad
        if unknown:
            detail = "; ".join(f"{s}: {', '.join(v)}" for s, v in unknown.items())
            raise ProfileError(f"未知插件（白名单外）: {detail}")

        params = prof.get("params", {})
        if not isinstance(params, dict):
            raise ProfileError("profile.params 必须是 mapping")
        self._warn_param_type_mismatches(params)
        self._warn_path_safety(params)

        cleaned = {
            "schema_version": schema_version,
            "profile": {
                "name": name,
                "description": str(prof.get("description", "")),
                "builtin": False,
                "plugins": cleaned_plugins,
                "params": params,
            },
        }
        out = prof.get("output")
        if isinstance(out, dict):
            cleaned["profile"]["output"] = out
        return cleaned

    def _warn_param_type_mismatches(self, params: dict) -> None:
        """参数类型与 RoutingConfig 默认字段类型比对（类型错误 → warning 不阻断）。"""
        try:
            defaults = RoutingConfig()
        except Exception:  # noqa: BLE001
            return
        flat: dict[str, Any] = {}
        for key, value in params.items():
            if key == "routing" and isinstance(value, dict):
                flat.update(value)
            elif hasattr(defaults, key) and isinstance(value, dict):
                sub = getattr(defaults, key)
                for k, v in value.items():
                    if hasattr(sub, k):
                        flat[f"{key}.{k}"] = v
            elif hasattr(defaults, key):
                flat[key] = value
        for key, value in flat.items():
            expected = self._expected_type(key, defaults)
            if expected is None:
                continue
            if expected is bool and not isinstance(value, bool):
                logger.warning("profile 参数类型可疑: %s=%r（期望 bool）", key, value)
            elif expected is int and not isinstance(value, bool) and not isinstance(value, int):
                logger.warning("profile 参数类型可疑: %s=%r（期望 int）", key, value)
            elif expected is float and not isinstance(value, (int, float)):
                logger.warning("profile 参数类型可疑: %s=%r（期望 float）", key, value)
            elif expected is str and not isinstance(value, str):
                logger.warning("profile 参数类型可疑: %s=%r（期望 str）", key, value)

    @staticmethod
    def _expected_type(key: str, defaults: RoutingConfig) -> type | None:
        """根据 ``routing.key`` 或 ``subsection.field`` 返回期望类型。"""
        import dataclasses

        if "." in key:
            sec, fld = key.split(".", 1)
            obj = getattr(defaults, sec, None)
            if obj is None:
                return None
            for f in dataclasses.fields(obj):
                if f.name == fld:
                    return f.type if isinstance(f.type, type) else None
            return None
        for f in dataclasses.fields(RoutingConfig):
            if f.name == key:
                return f.type if isinstance(f.type, type) else None
        return None

    def _warn_path_safety(self, params: dict, prefix: str = "") -> None:
        """路径/命令类 key 防御性检查（§5.5 ④；仅 warning，导入只读不执行）。"""
        for key, value in params.items():
            full = f"{prefix}.{key}" if prefix else str(key)
            low = full.casefold()
            suspicious = any(kw in low for kw in _PATH_SAFETY_KEYWORDS)
            if isinstance(value, dict):
                self._warn_path_safety(value, prefix=full)
            elif suspicious and isinstance(value, str) and (
                "/" in value or "\\" in value or value.casefold().endswith(_PATH_LIKE_SUFFIXES)
            ):
                logger.warning(
                    "profile 参数含路径/命令形态字段（防御性提示，仅读取不执行）: "
                    "%s=%r", full, value,
                )

    def _atomic_write(self, path: Path, text: str) -> None:
        """临时文件 + os.replace（原子写；权限 0644）。"""
        atomic_write_text(path, text)

    def _resolve_profile_path(self, name: str) -> Path | None:
        """按规范名找 ``profiles/<name>.yaml``（不区分大小写扫描）。"""
        target = (name or "").casefold()
        for p in sorted(self.profiles_dir.glob("*.yaml")):
            if p.stem.casefold() == target:
                return p
        return None

    def _load_profile_file(self, path: Path) -> dict:
        """safe_load + 结构检查 + builtin 标志。"""
        p = Path(path)
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict) or not isinstance(data.get("profile"), dict):
            raise ValueError(f"profile 文件结构非法: {p}")
        return data

    def _set_stage_plugins(self, cfg: PipelineConfig, stage: str, plugins: Any) -> None:
        """按阶段替换插件列表（output→files；test→suites）。"""
        values = [str(x) for x in (plugins or [])]
        if stage == "input":
            cfg.input.plugins = values
        elif stage == "match":
            cfg.match.plugins = values
        elif stage == "beautify":
            cfg.beautify.plugins = values
        elif stage == "output":
            cfg.output.files = values
        elif stage == "test":
            cfg.test.suites = values
        else:  # pragma: no cover — 防御
            raise ProfileError(f"未知阶段: {stage!r}")

    def _merge_params(self, rc: RoutingConfig, params: dict) -> None:
        """profile params 深合并（增量覆盖）到 RoutingConfig 上。

        委托 ``pipeline_config.apply_params``（单一实现，避免重复逻辑）：
        - ``routing`` 子 dict / 顶层标量 → 覆盖顶层标量
        - 子节 dict → ``dataclasses.replace`` 部分覆盖（深合并）
        """
        merged = apply_params(rc, params)
        # apply_params 返回新对象；就地同步回入参（保持调用方语义）
        for f in dataclasses.fields(rc):
            setattr(rc, f.name, getattr(merged, f.name))

    @staticmethod
    def _build_profile_dict(name: str, cfg: PipelineConfig) -> dict:
        """从 PipelineConfig 构造 profile 文件 dict（plugins 全量快照 + params 增量）。"""
        combos = cfg.plugin_combos()
        order = {
            "input": cfg.input.plugins,
            "match": cfg.match.plugins,
            "beautify": cfg.beautify.plugins,
            "output": cfg.output.files,
            "test": cfg.test.suites,
        }
        profile: dict[str, Any] = {
            "name": name,
            "description": "",
            "created": datetime.date.today().isoformat(),
            "builtin": False,
            "plugins": {stage: list(order[stage]) for stage in STAGES},
            "params": ProfileManager._params_incremental(cfg.beautify.params),
        }
        if cfg.output.files != OutputSection().files or cfg.output.reports != OutputSection().reports:
            profile["output"] = {
                "files": list(cfg.output.files),
                "reports": list(cfg.output.reports),
            }
        return {"schema_version": 1, "profile": profile}

    @staticmethod
    def _params_incremental(rc: RoutingConfig) -> dict:
        """只存与默认值不同的参数（增量；深合并到 default 之上，§5.2）。"""
        base = routing_to_params(RoutingConfig())
        cur = routing_to_params(rc)
        diff: dict[str, Any] = {}
        for group, sub in cur.items():
            if isinstance(sub, dict):
                base_sub = base.get(group, {})
                sub_diff = {
                    k: v for k, v in sub.items()
                    if k not in base_sub or not deep_eq_params(base_sub[k], v)
                }
                if sub_diff:
                    diff[group] = sub_diff
            elif base.get(group) != sub:
                diff[group] = sub
        return diff
