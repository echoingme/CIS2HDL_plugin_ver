"""S10 — 重建对比包（config 驱动，output_phaseXXVI_compare）。

背景（S10 兼容窗口结束）：旧 CLI 行为参数（--gnd-distribute /
--wire-simplify / --use-net-name / --rotate-passives 等共 20 个）已移除，
旧脚本 make_compare_v9.py 的 ``VERSIONS`` 依赖 CLI flags 无法再复用。
本脚本改用 **pipeline.yaml 变体**驱动 4 个核心版本——与用户 S10 后的
配置方式完全一致（改 yaml 或 --profile），并保留 make_compare_v9 的
量化统计 / README / test_spn 模板逻辑。

版本矩阵（4 核心，Cadence 16.6 复测用）：
  s10_default          默认修复版（p0）——等价 default profile
  s10_gnd_distribute   GND 分布 + 聚类 + 密度补点（pipeline.yaml
                       beautify.params.gnd_distribution.enabled +
                       .distribute_density）
  s10_wire_simplify    电线化简 + 超长分段（wire_simplify.enabled）
  s10_net_name         网络名跨页 + 末端标签（ioport.use_net_name）

输出：HG5015_tests/output_phaseXXVI_compare/（S10 新目录；用户防
Windows 重名约定——每轮发布递增目录名。Phase XXIII 已用
output_phaseXXV_compare，故本轮递增为 output_phaseXXVI_compare）。

用法：python scripts/make_compare_s10.py
"""

from __future__ import annotations

import copy
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from make_compare_v9 import (
    _count_gnd,
    _count_ioport,
    _count_wire,
    _read_wire_through_body,
    _write_test_spn_templates,
)

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "tests" / "fixtures" / "HG5015test" / "HG5015-BE36_V10.EDF"
HDL_LIB = ROOT / "tests" / "fixtures" / "hdl_lib"
OUT = ROOT / "HG5015_tests" / "output_phaseXXVI_compare"
#: 每版本 pipeline.yaml 变体（生成物，随包保留便于复现）
PIPE_DIR = ROOT / "HG5015_tests" / "_phaseXXVI_pipelines"
# 注意：每次发布用新目录名（用户 Windows 上有旧拷贝，重名导致混淆/误拷）。
PY = sys.executable

#: 完整版 Cross Reference CSV（用户 HG5015test 目录，OrCAD "Entire" 格式，
#: 59 列含 DESCRIPTION/JEDEC_TYPE/PACKAGE_TYPE/SN_NUM，914 条元件）。
#: 转换引擎按 ``<EDF 同名>.CSV`` 读取，故复制为同名后使用（不污染 fixture）。
CSV_SOURCE = ROOT / "tests" / "fixtures" / "HG5015test" / "entire.csv"
WORK_DIR = Path("/tmp") / "cis2hdl_s10_input"

#: 版本矩阵：(目录名, pipeline.yaml 覆盖（深合并）, 说明)
#: 覆盖字段与 S10 迁移对照表一致（旧 CLI 参数 → pipeline.yaml 字段）。
VERSIONS: list[tuple[str, dict, str]] = [
    ("s10_default", {}, "默认修复版（p0，R1-R4 + 视觉/布局 + trunk 避让）"),
    (
        "s10_gnd_distribute",
        {"beautify": {"params": {"gnd_distribution": {
            "enabled": True, "distribute_density": True,
        }}}},
        "GND 分布 + 簇内并联 + 密度补点（beautify.params.gnd_distribution）",
    ),
    (
        "s10_wire_simplify",
        {"beautify": {"params": {"wire_simplify": {"enabled": True}}}},
        "电线化简 + 超长分段（beautify.params.wire_simplify.enabled）",
    ),
    (
        "s10_net_name",
        {"beautify": {"params": {"ioport": {"use_net_name": True}}}},
        "网络名跨页 + 末端标签（beautify.params.ioport.use_net_name）",
    ),
]


def _deep_merge(base: dict, override: dict) -> dict:
    """递归深合并：override 覆盖 base 对应字段（dict 递归，其余直接替换）。"""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _write_variant(name: str, override: dict) -> Path:
    """基于仓库 pipeline.yaml 生成版本变体配置并写盘。"""
    base = yaml.safe_load((ROOT / "pipeline.yaml").read_text(encoding="utf-8"))
    variant = _deep_merge(base, override)
    variant["profile"] = "default"  # 显式锚定 default profile（FR9 语义）
    target = PIPE_DIR / f"{name}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(variant, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return target


def main() -> int:
    if not INPUT.exists():
        print(f"输入缺失: {INPUT}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    PIPE_DIR.mkdir(parents=True, exist_ok=True)
    metrics: list[tuple[str, str, int, int, int, tuple | None]] = []

    for name, override, desc in VERSIONS:
        target = OUT / name
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        pipe_file = _write_variant(name, override)
        # 用完整版 CSV（entire.csv）作为转换输入：复制到临时工作目录并
        # 命名为与 EDF 同名，转换引擎 ``<EDF>.with_suffix('.CSV')`` 即命中。
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        work_edf = WORK_DIR / INPUT.name
        work_csv = WORK_DIR / INPUT.with_suffix(".CSV").name
        shutil.copy(INPUT, work_edf)
        shutil.copy(CSV_SOURCE, work_csv)
        # S10：仅用保留的路径类参数 + --pipeline 变体（不再传旧行为参数）
        cmd = [
            PY, "-m", "cis2hdl", "convert", str(work_edf),
            "--pipeline", str(pipe_file),
            "--output", str(target),
            "--hdl-lib", str(HDL_LIB),
        ]
        print(f"── {name}: {' '.join(cmd)}")
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        if proc.returncode != 0:
            print(f"  ✗ 转换失败: {proc.stderr[-500:]}")
            return 1
        worklib = target / "worklib" / "5015" / "sch_1"
        if not worklib.exists():
            print(f"  ✗ 缺 worklib: {target}")
            return 1
        wire = _count_wire(worklib)
        gnd = _count_gnd(worklib)
        ioport = _count_ioport(worklib)
        wtb = _read_wire_through_body(target)
        metrics.append((name, desc, wire, gnd, ioport, wtb))
        print(
            f"  ✓ WIRE={wire} GND={gnd} IOPORT={ioport} "
            f"WTB={wtb}"
        )

    _write_metrics(OUT, metrics)
    _write_readme(OUT, metrics)
    print(f"✓ metrics_summary.md 已生成（{OUT / 'metrics_summary.md'}）")
    print(f"✓ README.md 已生成（{OUT / 'README.md'}）")
    _write_test_spn_templates(OUT)
    return 0


def _write_metrics(out: Path, metrics) -> None:
    """写 metrics_summary.md（S10 版：config 驱动口径）。"""
    lines = [
        "# S10 对比分析包 — 各版本量化指标汇总",
        "",
        "> 生成：S10（Cadence 16.6 复测用）｜ HG5015-BE36_V10 主链",
        "> 说明：S10 起旧 CLI 行为参数已移除，4 个版本由 pipeline.yaml 变体",
        "> （HG5015_tests/_phaseXXVI_pipelines/）驱动，与用户 S10 后的配置方式",
        "> 一致（改 yaml 或 --profile）。全部包含 R1-R4 修复 + 视觉/布局优化",
        "> + trunk 避让增强。",
        "",
        "## 一、指标总表（4 版本）",
        "",
        "| 版本 | 说明 | WIRE 段数 | GND 符号 | IOPORT | WIRE_THROUGH_BODY violations |",
        "|------|------|:---:|:---:|:---:|:---:|",
    ]
    for name, desc, wire, gnd, ioport, wtb in metrics:
        wtb_txt = "—"
        if wtb is not None:
            d, e, v, tb, nt = wtb
            wtb_txt = f"{v} (trunk_blocked={tb}, non_trunk={nt})"
        lines.append(
            f"| **{name}** | {desc} | {wire} | {gnd} | {ioport} | {wtb_txt} |"
        )
    lines += [
        "",
        "## 二、S10 与 Phase XXIII 对比包差异",
        "",
        "| 项 | Phase XXIII（output_phaseXXV_compare） | S10（本包） |",
        "|----|----------------------|------------------------|",
        "| 驱动方式 | make_compare_v9.py + 旧 CLI flags（--gnd-distribute 等） | make_compare_s10.py + pipeline.yaml 变体 |",
        "| 版本名 | v9_default / v9_gnd_distribute / v9_wire_simplify / v9_net_name | s10_default / s10_gnd_distribute / s10_wire_simplify / s10_net_name |",
        "| 引擎模式 | 默认（legacy） | 默认（legacy）——FR9 字节等价基座不变 |",
        "| 功能开关 | 仅 v9_gnd_distribute 开启 gnd_distribute_density | 同左（经 pipeline.yaml 字段） |",
        "",
        "> 注：SPCOCN 报错归零为**代码级验证**（语法/结构/坐标断言）；最终确认需用户",
        "> Cadence 16.6 打开复测。violations 为 [WIRE_THROUGH_BODY] 真违规口径",
        "> （trunk_blocked = 密集页 trunk 无解回退直穿，README 已知限制）。",
        "",
    ]
    (OUT / "metrics_summary.md").write_text("\n".join(lines), encoding="utf-8")


def _write_readme(out: Path, metrics) -> None:
    """写 README.md（S10 版：包结构 + config 驱动说明）。"""
    wtb_txt = "见 metrics_summary"
    for _name, _desc, _wire, _gnd, _ioport, wtb in metrics:
        if _name == "s10_default" and wtb is not None:
            d, e, v, tb, nt = wtb
            wtb_txt = (
                f"detected={d} exempt={e} violations={v} "
                f"(trunk_blocked={tb}, non_trunk={nt})"
            )
    lines = [
        "# CIS2HDL S10 对比分析包（Cadence 16.6 复测用）",
        "",
        "> 生成：S10（插件化重构交付收尾）｜ 软件交付团队",
        "> **本包用于 Cadence 16.6 复测 S10 收尾后输出**。所有素材已在本机准备",
        "> 完毕，Cadence 电脑上只需打开与对比。",
        "",
        "---",
        "",
        "## 一、包结构",
        "",
        "```",
        "output_phaseXXVI_compare/",
        "├── s10_default/           # 默认修复版（p0，三段式 stub + 并联 + trunk 避让）",
        "├── s10_gnd_distribute/    # GND 分布 + 簇内并联 + 密度补点",
        "├── s10_wire_simplify/     # 电线化简 + 超长分段",
        "├── s10_net_name/          # 网络名跨页 + 末端标签",
        "├── test_spn_g1~g4.csa     # SPN 机制复测模板",
        "├── README.md              # 本文档",
        "└── metrics_summary.md     # 各版本量化指标 + S10 差异说明",
        "```",
        "",
        "每个 s* 目录是**完整可打开的 Cadence 工程**（worklib/5015/sch_1/ + cds.lib + hdl_lib + temp_lib）。",
        "变体 pipeline.yaml 存于 `HG5015_tests/_phaseXXVI_pipelines/`（可复现）。",
        "",
        "---",
        "",
        "## 二、在 Cadence 16.6 打开工程（3 步）",
        "",
        "1. 把 `output_phaseXXVI_compare` **整个文件夹**拷贝到 Cadence 电脑（保持目录结构不变）",
        "2. 打开 Design Entry HDL：File → Open Design → 选择 `s10_default/5015.cpm`",
        "3. **⚠️ 重要：手动添加 temp_lib 库**（Phase XVII 遗留：Project Setup 需手动引用 temp_lib）：",
        "   - Project Manager → **Project → Project Setup**",
        "   - **Libraries** 标签页 → **Add** → 选择 `s10_default/temp_lib` 目录",
        "   - 确认 Libraries 列表包含：`5015_lib`、`hdl_lib`、`temp_lib`",
        "   - Apply → OK",
        "",
        "> 说明：`cds.lib` 已包含 `DEFINE temp_lib temp_lib` 行，但 Cadence Project Setup 仍",
        "> 需手动引用（工具侧无法控制 Cadence UI）。添加后 temp_lib 的 mock 图标（U6 系列等）",
        "> 才能正常加载。",
        "",
        "---",
        "",
        "## 三、S10 说明：版本由 pipeline.yaml 驱动（旧 CLI 参数已移除）",
        "",
        "S10 起旧 CLI 行为参数（--gnd-distribute / --wire-simplify / --use-net-name /",
        "--rotate-passives 等共 20 个）已移除。本包 4 个版本由 pipeline.yaml 变体",
        "驱动，字段与迁移对照表一致：",
        "",
        "| 版本 | pipeline.yaml 字段 | 旧 CLI（S10 前） |",
        "|------|-------------------|------------------|",
        "| s10_default | 无覆盖（default profile） | 无 |",
        "| s10_gnd_distribute | `beautify.params.gnd_distribution.enabled: true` + `.distribute_density: true` | --gnd-distribute |",
        "| s10_wire_simplify | `beautify.params.wire_simplify.enabled: true` | --wire-simplify |",
        "| s10_net_name | `beautify.params.ioport.use_net_name: true` | --use-net-name |",
        "",
        "复现命令示例（s10_gnd_distribute）：",
        "",
        "```bash",
        "python -m cis2hdl convert <input>.EDF \\",
        "  --pipeline HG5015_tests/_phaseXXVI_pipelines/s10_gnd_distribute.yaml \\",
        "  --output out_s10_gnd/ --hdl-lib tests/fixtures/hdl_lib",
        "```",
        "",
        f"> s10_default [WIRE_THROUGH_BODY] **{wtb_txt}**（trunk 避让增强保持，",
        "> 基线 506 → 收敛；剩余 violations 为电源网长 stub 穿大体）。",
        "",
        "---",
        "",
        "## 四、S10 转换行为等价说明",
        "",
        "- **默认（p0）转换**：default profile 与 legacy 路径字节级等价（FR9 最终",
        "  验收，tests/e2e 全绿）。",
        "- 三项功能开关现为 pipeline.yaml 字段（S10 迁移），默认关/开语义不变。",
        "",
    ]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
