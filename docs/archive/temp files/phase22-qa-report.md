# Phase XXII 最终独立 QA 报告

> QA：严过关（software-qa-engineer）｜ 日期：2026-08-14
> 验证基线：commit `b8ef8d0`（Phase XXII QA fixes）+ `b7c28b0`（T01-T05 实现）
> 方法：**全部独立执行**（全量 pytest + 源码只读复核 + 探针重跑转换取证），不轻信工程师报告
> 输入：`phase22-prd.md`（D1-D8）/ `phase22-system-design.md`（T01-T05 断言）/ `handoff-20260813-190605.md` §7c

---

## 一、总判定

| 项 | 结论 |
|----|------|
| 全量测试 | ✅ **876 passed / 6 skipped**（基线 ≥875/6 达成） |
| D1 | ✅ PASS |
| D2 | ⚠️ **FAIL（严格验收口径）**：`[WIRE_THROUGH_BODY] total=524`（非豁免真违规 524 条，**非文档所述 26 条**） |
| D3 | ✅ PASS |
| D4 | ✅ PASS |
| D5 | ✅ PASS |
| D6 | ✅ PASS |
| D7 | ✅ PASS |
| D8 | ✅ PASS |
| Q1-Q8 落地核查 | ✅ PASS（8/8） |
| 回归语义（542/310/1158/IC3/off-grid） | ✅ PASS（6/6） |
| **智能路由判定** | **需工程师修复（D2 报告口径/文档 + 真违规收敛）** |

**一句话**：交付包结构/字节级/回归全部达标，**但 D2 的 `[WIRE_THROUGH_BODY]` 真违规数是 524（非豁免），与 README/提交信息宣称的 "26 non-exempt" 不符（报告字段语义被误读）**，且未达到 PRD D2 验收 `total=0`。此为唯一阻塞项，需工程师处置后复测。

---

## 二、验证项明细

### 1. 全量测试 ✅ PASS

```bash
python3 -m pytest tests/ -q -p no:cacheprovider
# ============ 876 passed, 6 skipped, 7 warnings in 123.28s ============
```

- D1-D8 专项单测：`test_wire_layout_p0_stub / test_wire_through_body_exempt / test_net_name_endpoint / test_parallel_short_all / test_ioport_clustering / test_xcon_single_source / test_text_layout / test_lastpin_miss_fix` **51 passed in 3.56s**。
- e2e `test_phase_xvi.py`：**8 passed**（aes 模式 `[LASTPIN_MISS] total=0` 断言通过）。

### 2. 交付包 output_phaseXXIV_compare 验收（D1-D8）

#### D1 三段式 stub — ✅ PASS
- `tests/unit/test_wire_layout_p0_stub.py` 7 用例全过（含条件三段式：通畅 stub 1 段直连、受阻才引出）。
- v9_default WIRE 段数实测 **6708**（`grep -c "WIRE 16"` 全 24 页），与 metrics_summary 一致；off-grid(25)=0。
- 独立探针重跑默认转换：`WTB` 语义与报告一致（见 D2）。

#### D2 避让默认开 — ⚠️ FAIL（严格口径）
- 单测 `test_wire_through_body_exempt.py` 全过（自身引脚引出豁免逻辑正确）。
- **报告语义复核（关键）**：`aesthetic_report.py:332-335`
  ```python
  total = sum(1 for e in self.wire_through_bodies if not e[4])  # 非豁免数
  exempt = len(self.wire_through_bodies) - total
  ```
  → 报告行 `[WIRE_THROUGH_BODY] total=524 exempt=498` 中 **`total` 就是"非豁免真违规"数 = 524**，而非"总检出数"。
- **独立探针（monkeypatch 全程记录）**：默认 p0 转换 WTB 总检出 1023，`NON_EXEMPT=524`、`EXEMPT=499`（与交付 498 差 1，因探针未注入 entire.csv，可忽略）。
- **524 条逐条复核**：重放 `_wire_through_body_exempt` 判定，**524 条全部为 GENUINE_CROSS**（段端点≠该 body 自身引脚坐标，非豁免误判），即：
  - 按网类：电源网 186（GND\g=102、0V9_COMM\g=23、0V9_WIFI\g=17、VDD3V3_0\g=11、12V0\g=8…）、信号网 338；
  - 按体尺寸：小体（≤200，多为电源符号）131、大体（>10000，真实元件）393；
  - 按段长：≤150 短段 139、150-500 中段 102、**>500 长段 283（trunk 穿体）**；
  - 按页集中：P5=18、P6=6、P7=27、P8=41、P9=44、P13=11、P16=18、P17=75、P19=10、P20=7、P21=179、P22=78。
- **与文档/提交信息矛盾**：
  - README §六 已知限制："WIRE_THROUGH_BODY non-exempt 26 条"（❌ 实际 524）；
  - commit b8ef8d0："remaining 26 non-exempt are dense-page fallbacks"（❌ 误读报告：把 `total` 当总检出数，用 524-498=26）。
  - PRD D2 验收：`[WIRE_THROUGH_BODY] total=0`（p0 默认）→ 未达成（total=524）。
- **说明**：524 中约 186 条为电源符号挂轨穿体（GND/12V0 符号位于干线上，电气上正常、Cadence 可接受），其余 338 条信号网穿体（其中 234 条穿大体元件）为真实密集页回退。是否接受需工程师给出证据化豁免/收敛方案，**不能以 "26" 口径交付**。

#### D3 net_name_endpoints 接线 — ✅ PASS
- `csa_writer.py:2241-2276` use_net_name 分支单一调用 `net_name_endpoints` + 去重（`_extra_nets` 跳过泛化循环）。
- `test_net_name_endpoint.py` 全过（含 D3 扩展：跨页悬空端全补、同网不双标签）。
- 交付 v9_net_name：CSA 中 **IOPORT=0**（`grep -c IOPORT *.csa` = 0）；SIG_NAME 590 个唯一网名 / 1280 条标签；`ioport_audit_report ioport_total=522`（审计口径，独立于 CSA 发射）。

#### D4 并联全信号 — ✅ PASS
- `wire_simplifier.plan_parallel_short`（L400）已接线：csa_writer L1942-2006 路由前规划 + route_map 注入 `PARALLEL_HUB_*`（仅路由层）+ 路由后短接段并入（L2017-2040）。
- `test_parallel_short_all.py` 全过；`wire_simplify.enabled` 保持 false（Q4）。
- **独立探针**：默认转换中 `plan_parallel_short` 被调用 **454 次，253 次产出 ≥1 簇**（如 24 引脚网聚 6 簇 → 47 短接段；4 引脚网聚 1 簇 → 7 短接段）→ 并联确实在真实转换中生效。
- 注：`PARALLEL_HUB` 为合成路由点，**不应**出现在 CSA（hub 不发射 LASTPIN），QA 复核确认 CSA 无该 refdes 属预期。

#### D5 IO port 聚类 — ✅ PASS
- `_build_ioport_cluster_order` / `_ioport_position_cfg` 实现（csa_writer L3691/L3734），edge_layout 开启时按同网页内引脚 y 均值重排槽位。
- `test_ioport_clustering.py` 全过（距离均值下降 / 无重叠 / 确定性 / 关闭时原序）。
- 门控 `ioport.edge_layout=false`（默认关）与 routing.yaml 一致；e2e aes（edge_layout=true）8 用例通过。

#### D6 xcon 合并 — ✅ PASS
- 全仓 `grep -rn "def _build_xcon_content"` **仅 1 处**：`xcon_writer.py:109`（output_manager 已删除自建实现）。
- `test_xcon_single_source.py` 全过（write_xcon 无 override → ValueError）。
- **字节级比对**（独立脚本，归一化 modificationTime）：XXIII vs XXIV 四版本各 10 个 .xcon，**9 个逐字节一致，仅 worklib 5015.xcon 的 modificationTime 不同**（时间戳差异符合预期）→ xcon 内容字节级不变达成。

#### D7 标签方向 — ✅ PASS
- `text_layout.py` TextItem.orient / TextLayoutResult.label_orient 实现；csa_writer `_emit_conn_instance_block` 按 orient 输出 `R n`。
- `test_text_layout.py` 全过（旋转 180° → VALUE 块 `R 2`；disabled 保持 `R 1` 字节不变）。
- 门控 `text_layout.enabled=false`（默认关，--text-layout 开启）与 routing.yaml 一致；v9 四版本均未开 text_layout（符合交付矩阵）。

#### D8 LASTPIN miss — ✅ PASS
- `test_lastpin_miss_fix.py` 全过（微移豁免 / expected 同源 / 未微移仍严格校验）。
- 交付四版本 aesthetic_report 首行均 `[LASTPIN_MISS] none`（default/gnd_distribute/net_name 实测）；e2e aes 断言 `total=0` 通过。

### 3. 既有回归语义（A1-A8 + 542/310/1158）— ✅ PASS（6/6）

| 项 | 验证 | 结果 |
|----|------|:---:|
| SPCOCN-542 mock 9 P 属性 | 抽查 T5_PH/U12_PH/J18_PH symbol.css：P 声明含 `CDS_LMAN_SYM_OUTLINE/$LOCATION/VALUE/PART_NAME/JEDEC_TYPE/PATH/PACKAGE_TYPE/DESCRIPTION/SN_NUM/MOCK_TEXT` 全 10 条（9 默认属性+MOCK_TEXT） | ✅ |
| SPCOCN-310 引脚重叠=0 | 全 temp_lib 100 cell C 指令坐标 Counter：**0 重复坐标** | ✅ |
| SPCOCN-1158 C/X 字号/类型 | 全 temp_lib：C 字号 **29**（≥29 合法）、X 字号 **29**、X 类型 **仅 PIN_TEXT**（1202 条） | ✅ |
| IC3 引脚名 | IC3_PH symbol.css：GND/OUTPUT/TAP/INPUT（Phase XXI D 不回归） | ✅ |
| WIRE off-grid(25)=0 | 交付 v9_default 全 24 页 6708 条 WIRE 端点逐坐标 %25：**0 off-grid** | ✅ |
| 转换错误日志 | v9_default errors.txt：**0 ERROR** / 140 WARNING（134 MATCH 低置信度 + 6 INFO_LOSS Missing_Value，均为良性诊断） | ✅ |

### 4. Q1-Q8 落地核查 — ✅ PASS（8/8）

| 裁决 | 落地 | 复核 |
|------|------|:---:|
| Q1 三段式默认开 | `routing.three_stage_stub: true`（routing.yaml）+ WIRE 基线 6708 | ✅ |
| Q2 能力下沉共用 | DetourRouter 删重复、WireLayoutEngine 基类持有 `_three_stage_stub` 等（git diff b7c28b0..b8ef8d0 验证） | ✅ |
| Q3 net_name_endpoints 单一调用点 | csa_writer use_net_name 分支仅调 `net_name_endpoints` + 去重 | ✅ |
| Q4 仅接线 parallel_short | `wire_simplify.enabled: false`、`parallel_short: true`、`parallel_short_dist: 500` | ✅ |
| Q5 位移后 snap50 | D8 修复包含 `_snap_body_coords`（代码复核）+ aes LASTPIN=0 | ✅ |
| Q6 xcon 单一内容源 | `_build_xcon_content` 全仓 1 处（xcon_writer） | ✅ |
| Q7 text_layout 默认关 | `text_layout.enabled: false`（--text-layout 开） | ✅ |
| Q8 全量 ≥840 + 目录递增 | 876 passed；目录 = `output_phaseXXIV_compare`（make_compare_v9.py OUT 常量 + test_v9_compare_package.py 指向） | ✅ |

---

## 三、遗留问题 / Known Issues（Round 2 后仍存在）

### 1. 【需工程师处置】D2 `[WIRE_THROUGH_BODY]` 报告口径与真违规数（P1）
- **现象**：交付报告 `total=524 exempt=498`；`total` 即非豁免真违规 = **524**。README/commit 宣称 "non-exempt 26" **为误读**（把 total 当总检出数）。
- **影响**：D2 严格验收 `total=0` 未达成；文档口径错误会导致交付质量被低估/高估。
- **建议**：
  1. 更正 README/metrics_summary/commit 中的 "26 non-exempt" → 实际 524（或给出子分类口径）；
  2. 对 524 条分类处置：电源符号挂轨穿体（~186）给出证据化豁免；信号网穿大体（~234）评估是否需加强 trunk 避让或接受为密集页已知限制；
  3. 至少补充一条 e2e 断言锁定报告语义（`total`=非豁免数），防止后续误读。
- **证据文件**：`cis2hdl/core/writer/aesthetic_report.py:332-335`；`HG5015_tests/output_phaseXXIV_compare/v9_default/aesthetic_report.txt:182`；README.md:49/98/121；`temp/qa_phase22_wtb_probe_records.json`（524 条逐条记录）。

### 2. 【低风险】MATCH 低置信度 134 + INFO_LOSS 6（既有，非本轮引入）
- 匹配失败/模糊 132 个器件（confidence<0.5）+ 6 个 Missing_Value，均为诊断性警告，不影响本轮验收，建议用户 Cadence 复测时按 README 指引人工确认。

---

## 四、QA 结论

- **通过项**：全量测试 876/6；D1、D3-D8 全部达标；回归语义 6/6；Q1-Q8 落地 8/8；交付包结构/字节级/xcon 单一源正确。
- **需修复项**：**D2 真违规数 524 与文档 "26" 不符 + 严格验收 total=0 未达成** → 路由至**工程师**（软件工程师 Alex）：
  - 文件：`cis2hdl/core/writer/aesthetic_report.py`（报告语义如无问题则仅文档侧）、`HG5015_tests/output_phaseXXIV_compare/README.md`、`metrics_summary.md`、commit 信息；
  - 修复方向：更正口径 / 证据化豁免 / 加强避让（三者至少取一），并补 e2e 断言防误读。
- **建议**：工程师修复后回归全量 pytest + 默认转换 WTB 复核，再交付用户 Cadence 16.6 复测。
