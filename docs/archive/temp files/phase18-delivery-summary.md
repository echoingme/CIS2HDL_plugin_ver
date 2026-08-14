# Phase XVIII 交付总结 — Cadence 16.6 实测问题闭环

> 交付总监：齐活林（Qi）｜ 2026-08-13
> 测试：**802 passed / 5 skipped**（基线 684→802，+118 新测试）

---

## TL;DR

用户 Cadence 16.6 实测发现的 **13 类问题（R1-R13）已全部实现修复**，其中 4 个 P0 报错根因（SPCOCN-1158/515/543 + ORIGIN/attributes "?"）在真实转换产物中**代码级验证清零**；P1 视觉布线类（避让/GND/网络名/长度/mock 标签/匹配/对齐）已实现默认关可回退；对比包 v9（4 核心版本）已生成供用户复测。

## 交付概览

| 项 | 值 |
|----|----|
| 交付状态 | ✅ R1-R13 全部实现；P0 代码级验证通过 |
| 测试 | **802 passed / 5 skipped**（+118） |
| 新增模块 | validate_symbol_css / audit_origin_refs / gnd_cluster_planner（3 新文件） |
| 修改文件 | mock_icon_lib / csa_writer / cross_ref_parser / mapping_csv_writer / wire_simplifier / overlap_resolver / net_name_connect / detour_router / overlap_detector / wire_layout / naming / config 等 12+ |
| 新增测试 | 26 个文件（symbol_css/temp_lib/spcn543/crossref/avoidance/gnd_parallel/wire_len/mock_label/net_name_endpoint/power_ic/passive_alignment/v9_compare 等） |
| 交付物 | `HG5015_tests/output_phaseXVIII_compare/`（v9 四版本 + README + metrics + test_spn） |

## 用户实测问题 → 修复映射（逐条清点）

### A 类：系统级报错（全部代码级验证清零）

| 用户实测问题 | 根因 | 修复 | 验证 |
|-------------|------|------|------|
| SPCOCN-1158 symbol.css line 12 parse error，芯片消失 | mock C 指令 justify 用 U/D；全库只有 R/L | justify 仅 R/L + X PIN_TEXT + 语法校验器 | **全量 temp_lib 0 语法错误** |
| SPCOCN-515 库缺失（手动添加 temp_lib 后仍找不到） | master.tag 内容错误（写 CDS_SYSTEM，真实是 symbol.css/chips.prt/verilog.v） | master.tag 分目录 golden + entity 四文件 + 结构断言 | **结构断言 []** |
| SPCOCN-543 $PN/SPN/SIG_NAME 被删（页页刷屏） | 旋转 R 行无 golden 先例；GND offset/SIG_NAME 不符；UN$ 网名 | sym_2 视图切换 + LASTPIN 命中强校验 + GND golden 对齐 + UN$ 稳定名 | **CSA 无 543；g4 不再报 deleted** |
| 双击 C423 报 ORIGIN.SYM.1.1 缺失 | CAPACITOR 引用系统库符号 | hdl_lib_only 匹配 + audit_origin_refs | **0 ORIGIN 引用** |
| attributes description/jedec/package/sn 全 "?" | CrossRef CSV 四属性未注入 | _inject_crossref_props（数据源 CrossRef） | **897 条 PACKAGE_TYPE 真值，0 条 "?"** |
| test_spn g4 报 GND_POWER\g deleted；新页全空白 | g4 模板 LASTPIN offset 未命中；模板缺页面头 | test_spn 模板修正（golden offset + 页面头） | 模板生成，待 Cadence 复测 |

### B 类：视觉与布线（已实现，默认关可回退）

| 用户实测问题 | 修复 | 状态 |
|-------------|------|:---:|
| mock 芯片标签竖排重叠、引脚在框内、无标识、字太大 | 引脚在框**外侧**（outline 内缩）+ 四边方向对齐 + 字号 16 + X PIN_TEXT/MOCK_TEXT | ✅ 已实现 |
| 电线穿元件、"线头"、贴边缘 | self_intersections 检出 + 三段式 stub（延伸→折线→调头）+ margin 50/冗余区 100/引脚 50 | ✅ 已实现 |
| GND 一页 1 个、各自单独接地、落元件上 | gnd_cluster_planner 簇内先并联再统一引出 + GND 避让 | ✅ 已实现（v9_gnd GND 95） |
| v6 电线悬空无网络名标签 | net_name_endpoints 悬空端补 SIG_NAME | ✅ 已实现 |
| 电线超长无限制 | split_long_wires 超长分段 + 断口标签 | ✅ 已实现 |
| 元件标签竖放重叠、未与元件方向统一 | mock 标签方向随边；被动元件微调（R11） | ✅ 已实现 |
| J4/J8/U16-20/PQ2016 匹配错误 | power_ic 6 脚 dc_dc 规则 + connector_pin_check + mock 接管 | ✅ 规则就绪 |
| I18/I15 等元件重叠 | resolve_passives（≤50 微调，芯片不动） | ✅ 已实现 |

## 主理人 QA 中发现并修复的新问题

| # | 问题 | 影响 | 修复 |
|---|------|------|------|
| QA-1 | mapping_csv_writer `_xref_attrs` 误缩进为嵌套函数 + `self.` 调用 | Mapping CSV 生成失败 | 移到模块级（outputs 247 恢复） |
| QA-2 | cross_ref_parser 只支持简化版 CSV；真实 OrCAD "Entire" 导出（tab 分隔）无法解析 | R4 属性注入在真实数据下失效 | _parse_entire/_detect_delimiter + <null> 过滤 + 5 测试 |

## 用户下一步建议

1. **拷贝复测**：把 `HG5015_tests/output_phaseXVIII_compare/` 整个文件夹拷贝到 Cadence 16.6 电脑
2. **打开 v9_default**：File → Open Design → v9_default/5015.cpm
3. **手动添加 temp_lib**：Project Setup → Libraries → Add → temp_lib（README 有详细指引）
4. **核对 README 复测清单**：重点 ①无 SPCOCN-1158/515/543/541 ②芯片图形显示 ③双击元件无 ORIGIN 报错、attributes 有真值 ④mock 引脚在框外、字号 16
5. **对比视觉版本**：v9_gnd_distribute（GND 就近）、v9_wire_simplify（电线化简）、v9_net_name（网络名标签）
6. **复测 test_spn**：新建页复制 g1-g4 模板，确认无报错（g4 不再报 GND_POWER\g deleted）
7. 复测通过后提交 git（Phase XII-XVIII 工作区全部改动）

## 诚实声明（待 Cadence 复测项）

- SPCOCN 报错归零为**代码级验证**（语法/结构/坐标断言全部通过），最终确认需 Cadence 16.6 打开 v9
- X "PIN_TEXT" / MOCK_TEXT X 指令渲染需 16.6 目视确认（P→X 切换）
- capacitor/resistor/inductor 的 180° 旋转保留 R 行（90°/270° 已改 sym_2 视图）——需 A/B 实测
- 避让/标签视觉项需目视确认
