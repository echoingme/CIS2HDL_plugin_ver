# CIS2HDL 项目记忆

> 注：本文件与 `.workbuddy/memory/MEMORY.md` 同内容，工作记忆目录（`.workbuddy/memory/`）为原始版本。

## 项目元数据
- 版本: **1.1.0** (匹配系统 v2.0)
- 测试: **268 passed, 23 skipped**（291 collected，零回归）
- 阶段: Phase I-IX ✅ | Phase X ✅ | **匹配系统 v2.0 重构 ✅**
- 目标: OrCAD CIS → Cadence DEHDL 原理图格式转换
- 匹配率: **889/889 全匹配**（声称匹配率 92.4%，quality=72%；口径: 92.4%=(889-67 NEEDS_REVIEW)/889）
- 输出: 24 CSA (20原理图+4信息页), PAINT WIRE 生成器已移除（Cadence 16.6 不支持，原"7页16段"记载为临时接线状态）, No_Pin=0
- OpenOrCadParser: 无RTL格式概念; TitleBlock=StructGraphicInst子类; Preamble=0xFFE45C39

## 关键决策
1. **纯 Python 实现** — 不依赖 C++ OpenOrCadParser，避免编译依赖
2. **CrossRef CSV 为主数据源** — refdes/value/坐标/页面 100%，DSN 仅用于网络拓扑
3. **DSN 价值评估结论** — PlacedInstance 解析已废弃（RTL 格式乱码），不再恢复
4. **基类-注册模式** — Parser/Writer/Matcher/Validator 通过 ABC + Registry 扩展
5. **.csa 优先于 .sch.\*** — DEHDL 原生 MACRO_DRAWING 格式
6. **CFB 回退路径** — OleReader.count_page_candidates() + DSNParser._read_all_pages()
7. **PST 网表作为辅助数据源** — pstchip/pstxprt/pstxnet 提供精确 JEDEC_TYPE/VALUE/网络连接，可选加载
8. **FORCEADD body_name 必须用 cell 名** — DEHDL 中 FORCEADD 引用 library cell 名（如 capacitor），primitive 名（如 CAPACITOR_0402）应通过 PART_NAME 属性指定。参考实现 `generate_hdl_sch.py` 确认此规则

## Phase X: Cadence SPB 16.6 实测 (2026-08-06) ✅
- **实测环境**: Cadence Allegro SPB 16.6, 项目 5015.cpm
- **修复总计**: 8 项 (X-1~X-8), 修改 2 文件
- **P0-1**: FORCEADD body_name 用了 primitive 名 → 改为 cell 名 + 分离 PART_NAME
- **P0-2**: LASTPIN SIG_NAME 全部删除 → 移除代码块
- **P1**: ADD_COMMENT 标准化 + 乱码过滤 + PAGE_NUMBER 页标题
- **P2**: **PAINT WIRE 连线渲染** — dsn_parser wire_net_map 修复 + csa_writer 生成 PAINT WIRE 命令 (7 页 16 段, DSN Wire 坐标→DEHDL 映射)（注: 该生成器已于 2026-08-07 随 v1.1.0 彻底移除，Cadence 16.6 不支持；"7页16段"为当时的临时接线状态）
- **线宽**: 原理图阶段默认细线 (1px)，线宽控制仅在 PCB 布线阶段相关
- **测试**: 134 passed, 23 skipped, 0 failed
- **文档**: ROADMAP §十一, CHANGELOG v0.9.0, MEMORY 更新
- **待办**: Cadence SPB 16.6 二次实测

## Phase IX (v0.8.0 — 2026-08-05)
- pstchip.dat 解析器: 7615行→PART_NAME/JEDEC_TYPE/VALUE/pins
- pstxnet.dat 解析器: 823 refdes × 1818 pin connections
- pstxprt→pstchip 查找桥: build_pstchip_lookup()
- PST 管线集成: Stage 2.3(解析) + Stage 2.5b(注入extra_data) + Stage 5.5b(pin补充)
- JEDEC_TYPE 精确匹配: ExactMatcher fallback (conf=0.95)
- 278页→20页 BUG 修复: file_inventory 页面名模式过滤
- Value match warning 修复: 显示 ptf 行 value 而非 ComponentDef.value
- DZ_前缀→zener 映射: prefix_filter + component_catalog
- 新建: pstchip_parser.py, pstxnet_netlist_parser.py
- 修改: pstxnet_parser.py, conversion_engine.py, value_matcher.py, exact.py, file_inventory.py, prefix_filter.py, component_catalog.py

## 匹配系统 v2.0 重构 (2026-08-07) ✅
- **架构**: Phase1 类型假设排序 + Phase2A 被动元件确定性规则 + Phase2B 主动元件类型内评分
- **核心修复**: 零跨类型错误（C11不再→resistor, D21不再→resistor, M1不再→rtxm169, C21/C282不再→inductor, R2/R42不再→capacitor）
- **Phase1 TypeHypothesisGenerator**: refdes前缀→有序类型列表（不锁死），PST+值特征+学习矩阵调整先验
- **Phase2A PassiveMatcher**: C/R/L/D 5级确定性规则 (值+尺寸双精确→值精确→尺寸兜底→前缀兜底)，conf=1.0/0.95/0.80/0.70/0.60/0.40
- **Phase2B ActiveMatcher**: IC/connector等 5维类型内评分 (footprint:0.30, value:0.15, jedec:0.20, pin:0.20, part:0.15)
- **conf**: final_conf = phase1_prior × phase2_within（不用max虚高），STOP_SEARCH=0.75, NEEDS_REVIEW=0.40
- **新建**: type_hypothesis.py(300行), passive_matcher.py(670行), active_matcher.py(516行), candidate_pool.py(244行), type_gate.yaml(86行), test_matcher_v2.py(112 个测试函数)（原记 178/209/169/120/133 为初版数字，已按实际更新）
- **修改**: match.py(MatchStrategy+8,MatchResult+5), pipeline.py(run_batch完全重写), scoring.py(MultiScorer移除), prefix_filter.py(+PASSIVE_TYPES), fallback.py(恢复v0.8.2风格), match_config.py(+type_gate), value_matcher.py(+match_typed), mapping_csv_writer.py(+双边对比+Top3), report_gen.py(+匹配维度标注)
- **删除**: MultiScorer类 + run_batch全库打分逻辑
- **不变**: exact.py, fuzzy.py, feature.py, base.py, registry.py, component.py, component_db.py, conversion_engine.py
- **设计**: docs/system_design.md (838行), docs/MATCHING_ANALYSIS_2026-08-06.md (436行)
- **SOP**: PM(许清楚)→PRD, Architect(高见远)→设计+5任务, Engineer(寇豆码)→T01-05(IS_PASS:YES), QA(严过关)→R1(254/2bug)→R2(255/0)
- **遗留**: gui/candidate_selector.py 已迁移至 ActiveMatcher 权重编辑（不再引用 MultiScorer）；Cadence SPB 16.6 二次实测待做

## 遗留事项
- ~~Cadence SPB 16.6 实测验证~~ → **Phase X 进行中**
- **weights.yaml 潜在缺陷**: GUI 权重编辑写入 weights.yaml，但 ActiveMatcher 使用硬编码权重（两处不同步，需审计统一）
- 无 CrossRef CSV 时的 legacy DSN 回退
- INDUCTOR/DIODE/CONNECTOR 无尺寸变体精准匹配
- J*/D* 匹配一致性审计 (部分已通过 DZ_ 映射改善)

## 已知限制
- pstxnet 补充注入仅 14 pin (EDIF 已覆盖 880/889 实例)
- 278→20 修复在 file_inventory(diagnostic)生效，mapping CSV 的统计暂未联动
- 信息页 CSA 仍为占位符格式 (TitleBlock 文本解析待完善)
- FORCEADD body_name 与 primitive 名混淆 → Phase X 修复中

## 环境
- Python 3.13.12 (managed)
- 测试: `pytest tests/unit/ tests/integration/ tests/e2e/ -q`
- 转换: `python -m cis2hdl convert <dsn> --output <dir> --hdl-lib <dir>`
- HDL 参考库: `docs_for_reference/CIStoHDL_standard/hdl_lib/`
- CSA 参考输出: `docs_for_reference/CIStoHDL_standard/worklib/out_hdl/sch_1/page1.csa`
