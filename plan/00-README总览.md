# steel-design-checker 项目计划总览

**项目**：钢结构连接与构件验算计算器（土木工程·钢结构领域，Windows 桌面程序，零识图路线）
**方法论**：ai-tool-project-sprint；与 structural-strengthening-checker 同模式（公式引擎+文本核查+强制规范检查单+算例真值基准）
**项目系列**：①construction-drawing-plan-checker（建造，已发布）②电力两票 ③病历质控 ④招投标评审 ⑤食品标签（Web形态）⑥发票台账 ⑦简历人才库 ⑧结构加固（桌面形态）→ ⑨本项目（钢结构，桌面形态）

## 文档索引

| 文档 | 内容 | 状态 |
|---|---|---|
| [01-题目详细定义.md](01-题目详细定义.md) | 模拟赛题全文 | ✅ 定稿 2026-10-06 |
| [02-需求解读.md](02-需求解读.md) | 痛点→能力转译、FR 清单（A 验算/B 条款/C 核查/D 交付）、边界与非目标、风险 R1-R6、待定决策 | ✅ 定稿 2026-10-06 |
| [03-架构与技术选型.md](03-架构与技术选型.md) | 分层架构、条款-公式-符号表引擎契约、CLI 单一事实源、确定性纪律、桌面与打包方案 | ✅ 定稿 2026-10-06 |
| [04-模块详设.md](04-模块详设.md) | Result 契约、5 模块参数卡 schema、条款/公式/符号/规则/检查单 schema、测试矩阵 | ✅ M1 已按 07 回填条号（连接在**第 11 章**，轴压在第 7 章） |
| [05-数据计划与里程碑.md](05-数据计划与里程碑.md) | 四类数据资产、数值表清单、算例真值库 schema、合成生成器、评测门槛、M1-M6 与每周可演示 | ✅ M1 回写：三档 status（D15）+ 9 张表的规范表号 |
| [06-决策记录.md](06-决策记录.md) | 决策 D01-D26 + 待定表（T3/T4/T5 全部已关闭）+ 口径变更日志（K1~K51） | ✅ M2 落定 D16（JGJ 82-2011 入范围）、D17（合成夹具渠道）、D18（引擎 5 条口径细化）；**T5（镜像图片版能否升 verified）待用户拍板** |
| [07-条文查证与待核对清单.md](07-条文查证与待核对清单.md) | 渠道清单、三标准条文树、逐主题条号定位、V1~V8 阻塞清单、**§六 M2 第二轮、**§七 M3 第三轮（双镜像作废 + φ 交叉核对未闭合 + 55006 全 8 章 107 条）** | ✅ 证据链已修复：缓存落 `.tmp_verify/m2/`（gitignore，收尾不删），每批带 manifest（URL+HTTP+sha1） |
| HANDOFF-M1.md | 阶段 0 → M1 交接快照 | ✅ 已执行完毕（M1 结果见 HANDOFF-M2） |
| HANDOFF-M2.md | M1 → M2（公式引擎）交接快照 | ✅ 已执行完毕（M2 结果见 HANDOFF-M3） |
| HANDOFF-M3.md | M2 → M3（文本核查）交接快照 | ✅ 已落盘 2026-10-07 |
| HANDOFF-M4.md | M3 文本核查 → M4（内置基准 + 报告导出）交接快照 | ✅ 已执行完毕（M4 结果见 HANDOFF-M5）；**M3 定档轮又回填了 §三/§四/§五**（附录 D 落地结果 + K37/K38 + 「0. 引擎支持分段」） |
| HANDOFF-M5.md | M4 内置基准 → M5（桌面交付）交接快照 | ✅ 已执行完毕（M5 结果见 HANDOFF-M6） |
| HANDOFF-M6.md | M5 桌面交付 → M6（脱敏发布 + 收尾固化）交接快照 | ✅ 已落盘 2026-10-07（本轮结束时按 DoD 逐项勾选，M6 结果见 RELEASE-M6.md） |
| [RELEASE-M6.md](RELEASE-M6.md) | **发布留档**：拍板四项 + 前置事实核验 + 脱敏五步命令与结论 + 复核项判定 + 干净环境/CI/Release 执行记录 + 偏差与复跑手册 | ✅ 完整留档 2026-10-07：§〇 拍板四项、§一 前置核验、§二 脱敏五步（含邮箱全历史改写与三扫）、§三 干净环境复核、§四 CI 三轮对账、§五 发布执行与发布后复核、§六 偏差、§七 复跑手册 |
| [../docs/技术报告.md](../docs/技术报告.md) | 材料固化：三大主题 + 交付形态 + 已知限制诚实清单（docx 由 `scripts/make_tech_report.py` 生成，K51） | ✅ 定稿 2026-10-07，`tests/test_tech_report.py` 7 项钉住字节一致与计数对账 |
| ../README.md（仓库根） | 面向外部的总说明：能做什么、指标表、纪律、快速开始 | ✅ M4 新建；指标表由 `sdc bench --all --markdown` 生成，`tests/test_suite.py` 逐行对账 |

## 决策记录

已迁至 [06-决策记录.md](06-决策记录.md)（D01-D26；待定表 T3/T4/T5 已全部关闭，无「⬜ 缓议」进终态），本文件不再维护副本，避免双处漂移。

## 里程碑

已细化至 [05-数据计划与里程碑.md](05-数据计划与里程碑.md) §七（含 DoD 与每周可演示清单）：

- **M1 数据先行**：条款库骨架 + 数值表入库（status 纪律跑通）+ 算例真值库第一批 + 合成生成器 v0 + 台账 ✅
- **M2 公式引擎**：5 个验算模块实现，算例回归（容差判定）✅ 完成 2026-10-07（数据未核对 ⇒ 全模块拒算，这是设计行为）
- **M3 文本核查**：设计说明参数卡解析 + 限值规则引擎 + GB 55006-2021 检查单 ✅ 完成 2026-10-07（其后 T5 定档轮把附录 D 升 verified，但没有任何模块出数值——f 仍来自 located 的表 4.4.1）
- **M4 内置基准**：一键四基准 + 指标表写进 README + docx 交付物（0 外链／两次导出字节一致／免责声明强制存在）✅ 完成 2026-10-07（两个指标仍「不可判」：算例分母 0、可硬判 abnormal 规则 0 条）
- **M5 桌面交付**：PySide6 界面 + PyInstaller onedir 双 exe + 打包断言 ✅ 完成 2026-10-07（GUI 与 CLI 同一批函数、逐字对账；`DIST_AUDIT_OK` + `CLEAN_ENV_OK`；冻结态子进程通路 K45 解决）
- **M6 脱敏发布 GitHub + Release（exe）+ 收尾固化** 🚧 进行中（CI 矩阵/脱敏五步/技术报告已落地，发布执行见 plan/RELEASE-M6.md）

## 当前进度

| 阶段 | 状态 |
|---|---|
| 阶段 0（plan 文档 00-06） | ✅ 完成 2026-10-06；决策 T1/T2/T3/T5 已拍板（→ D10-D13）；T4 随 D19 关闭（M3 拍板全 8 章），待定表至此清零 |
| 条文查证（GB 50017-2017 / GB 55006-2021 / JGJ 82-2011 条号定位） | ✅ 条号骨架完成；M2 第二轮（07 §六）**推翻**了「在线渠道拿不到数值本体」的结论——表体与式体是**图片**，已下载并双源逐格转录（附录 D φ 953 格双源一致 + D.0.5 公式反算 952/953 吻合）；V6 群栓分配定位到 JGJ 82-2011 第 5 章且限定 H 型钢梁拼接；V7 废止条号多源已证、映射仍单源。缓存 `.tmp_verify/m2/` 保留可重放 |
| M1 数据先行 | ✅ 完成 2026-10-07：仓库骨架 + 数据加载层（schema/引用完整性/三档门控/指纹）+ `sdc selfcheck` + 条款库 65 条 + 数值表 10 张 + 公式 9 条 + 符号 32 项 + 合成语料 24 份（位级一致）+ 8 个测试模块全绿。偏差：真值算例 0 例（来源不可确证，D07 优先于 DoD 数字），见 `data/cases/README.md` |
| M2 公式引擎 | ✅ 完成 2026-10-07：`src/sdc/engine/`（式体 AST 求值 + 单位入口层 + 参数卡校验 + 查表 + 编排）+ `sdc run` + `sdc bench`；5 模块在真实数据上**全部拒算且不出数值**，数值通路由 `tests/fixtures/kb/` 合成 verified 夹具覆盖；门控失败路径含「located 却带 values」的陷阱测试与反向构造条款门控。测试：M1 的 8 个模块 + M2 新增 6 个模块，按文件分批全绿。偏差与待拍板见 HANDOFF-M3 |
| M3 文本核查 | ✅ 完成 2026-10-07：`src/sdc/parse/`（docx/txt→槽位→IR，正则只在解析层）+ `src/sdc/rules/`（闸门矩阵 + 判定引擎，不 import `re`）+ `src/sdc/checklist.py` + `sdc parse/check/checklist` 与 `bench --parse/--audit`。指标：**F1 1.0000**（TP206/FP0/FN0）、**注入 12/12 检出、误报 0**、finding 全带条款与段落位置；数据侧新增 `rules/` 10 条、`checklist/` 107 条、55006 条款 30→107（全 8 章双主机文字层）。**T5 前提被查坏**（双镜像实为同一底图；φ↔公式官方常数下仅 793/953）⇒ 重拍为补第三路证据再定档，本轮 verified 仍 0。细目见 [HANDOFF-M4.md](HANDOFF-M4.md)。**其后 M3 定档轮已完成**（第三路＝出版社电子版 PDF 矢量文字层，±0.001 下 953/953 ⇒ 附录 D 一套升 verified，见 D22/D23）；另：本行原写「判定引擎不 import `re`」的字面表述在 M4 实测中被更正（D24①/K39），成立的是"不读文档、不对文档执行正则 + 解析判定分进程" |
| M4 内置基准 | ✅ 完成 2026-10-07：**一键基准** `sdc bench --all`（四基准合一 + 指标表，另加 `--sweep`／`--markdown`／`--json`，达标 7 / 不可判 2 / 未达标 0，rc=1）+ **docx 交付物**（`sdc report --case --out`、`check`/`checklist --out`；三类正文与终端渲染同源，落盘前自检 fail closed：0 外链、两次导出字节一致、免责声明必存、无真实身份信息）+ **selfcheck 两档看板**（`[6]` 未启用原因四分类、`[7]` 按解锁数排序的核对队列）+ 根 `README.md` 指标表（与实跑逐行对账）。口径新增 K39~K44（D24），并更正 K26 的字面表述。测试 19 个文件按文件分批全绿（新增 `test_report.py` 19 项、`test_suite.py` 15 项）。偏差：两个「不可判」不是达标——`data/cases/` 仍 0 例 ⇒ 通过率分母 0；10 条核查规则的依据全 located ⇒ 可硬判 abnormal 分母 0。细目见 [HANDOFF-M5.md](HANDOFF-M5.md) |
| M5 桌面交付 | ✅ 完成 2026-10-07：**五页签 GUI**（`src/sdc/gui/`：①验算台 ②设计说明核查 ③规范检查单 ④报告导出 ⑤知识库与状态）+ **GUI↔CLI 契约测试**（12 项逐字对账，含 `bench --all` 全文与三类 docx 字节相同）+ **onedir 双 exe**（`sdc.spec`：`dist/sdc-cli` 13 MB 不含 Qt、`dist/sdc-gui` 108 MB）+ **构建红线**（`scripts/bundle_rules.py` 白名单单源、`scripts/verify_dist.py` → `DIST_AUDIT_OK`，40 份内嵌数据逐份对账含子目录）+ **干净环境验证**（`scripts/clean_env_check.py` → `CLEAN_ENV_OK`：%TEMP% 中立目录、PATH 无 Python、CLI 六连 + GUI 存活探针 + `sdc-cli gui` 老实降级）。口径新增 K45~K48（D25）：冻结态子进程通路（解 HANDOFF-M5 §三.4）、打包白名单与断言单源、stdout/stderr 同编码、界面与命令面同源。测试 22 个文件 310 项全绿（新增 `test_gui_pages.py` 19、`test_gui_contract.py` 12、`test_packaging.py` 15）。偏差：①GUI 页签②仍只吃 `.docx/.txt/.md`（PDF 未支持，与 M3 同）；②docx 版式仍是最小 OOXML（无 Word 表格/标题样式，M4 留的 spike 未做）；③`data/cases/` 仍 0 例 ⇒ 指标表两个「不可判」照旧；④CI 矩阵（D12）尚未建 workflow，列 M6。细目见 [HANDOFF-M6.md](HANDOFF-M6.md) |
| M6 发布收尾 | ✅ 完成 2026-10-07：**CI 从零建**（`.github/workflows/ci.yml` 四矩阵 + `defaults.run.shell: bash` + step 名加引号；`scripts/ci_bench_gate.py` 基准门禁；`tests/test_ci_workflow.py` 8 项含"dev 必须声明 pyyaml"防静默少跑）+ **脱敏五步固化成工具**（`scripts/audit_release.py`：selftest/tracked/binary/messages/metadata/history/dist，掩码输出与硬门/复核分级；tracked 133 份文本、binary 25 份 docx 全 zip 条目、history 1,350,396 字符补丁、dist 252 个产物文件——**硬门全 0**；④ 提交邮箱按用户授权改写为 noreply）+ **MIT LICENSE** + **技术报告**（`docs/技术报告.md` 三大主题 + 程序化生成 docx，重生成逐字节一致）+ **§三.7 文档漂移处置**（plan/03 承认"编排层 = cli.py 命令分派 + suite.py 通路"，不补 pipeline.py）。测试 25 个文件 334 项全绿（新增 `test_ci_workflow` 8、`test_release_audit` 9、`test_tech_report` 7）。发布执行全部留档在 [RELEASE-M6.md](RELEASE-M6.md)：干净 clone + 全新 venv 跑出与开发机一致的 334 项 0 跳过并通过 DIST_AUDIT_OK + CLEAN_ENV_OK + 产物本体扫描；GitHub 公开、tag v0.1.0（指向 CI 全绿提交）、Release 附两个 onedir zip 与 sha256、14 个 topics；CI 三轮对账（前两轮的红分别是仓库 EOL 守门抓住 CI 自己的 scratch、以及 `${PIPESTATUS[0]}` 在管道前展开让门禁收到陈旧退出码，都由门槛自己抓出、未放宽）；两个「不可判」与 0 例真值**没有**为了绿灯被抹平（K43/K49） |
