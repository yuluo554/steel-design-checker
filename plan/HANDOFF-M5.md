# HANDOFF-M5（M4 内置基准 + 报告导出 → M5 桌面交付 交接快照）

> 用法（新对话）：`读取 plan/HANDOFF-M5.md，继续完成任务`（本文件内一律相对路径）
> 落盘时间：2026-10-07　落盘者：M4 内置基准对话
> 上一棒：[HANDOFF-M4.md](HANDOFF-M4.md)（M3 文本核查 → M4；其 §三 已被 M3 定档轮回填为"定档已完成"，§四 增 K37/K38，§五 增"0. 引擎支持分段"）

## 一、M4 交付了什么（已验证的事实）

| 交付物 | 位置 | 状态 |
|---|---|---|
| 一键基准 | `src/sdc/suite.py`、`sdc bench --all` | ✅ 四基准合一出**一张指标表**（9 行：达标 7 / 不可判 2 / 未达标 0，rc=1）；`--sweep` 只做确定性回归（rc=0）、`--markdown` 打印 README 引用的同一张表、`--json` 机器读且两次逐字节一致 |
| 确定性回归 | `suite.parse_corpus_twice` / `reports_twice` / `exports_twice` | ✅ 整批 24 份 IR **两个独立进程**各跑一遍逐文件比字节；`check`/`checklist` 的 JSON 两次输出一致；三类 docx 两次渲染一致；9 项引擎自校验样例（含单位不变性）；合成语料位级一致 |
| 解析步骤的子进程通路 | `suite.run_cli` | ✅ `sys.executable -X utf8 -m sdc …`，`--data-dir` 显式传下去；子进程起不来只让对应指标记「不可用」，不打挂整套（口径 K39） |
| 待核对闸门探针 | `suite.count_leaks` / `gate_probe` | ✅ 把 `data/examples/` 每张卡跑一遍，用**引擎自己的门控视图**判"依赖未核对却出了数值"；本轮 0 例。反证测试在手：伪造一个 blocked 模块带 ratio/steps 的结果 ⇒ 探针必须点名 |
| docx 交付物三件套 | `src/sdc/report/{body,docxio}.py` | ✅ `sdc report --case X --out 验算书.docx`、`sdc check --ir X --out 核查清单.docx`、`sdc checklist --out 检查单.docx`。**正文 = 终端渲染器的同一批行 + 报告头**（口径 K41，不另起第二套渲染）；落盘前**自检 fail closed**：0 外链不成立或缺免责声明就**拒绝写文件** |
| 0 外链的机器定义 | `report/docxio.find_external_refs` | ✅ 四条：部件必须等于白名单（7 个）；`.rels` 的 **`Target`** 不得是 URL/绝对路径、`TargetMode` 不得 External；无 `<w:hyperlink`；**正文文字**（`w:t`）无 URL scheme 与盘符路径。命名空间声明与关系 `Type` 标识符**不算**外链——把它们算进去会在任何合法 docx 上误报（M4 第一版就是这么误报的，已改）|
| 交付物身份纪律 | `report/body._name()`、`docxio.find_personal_info` | ✅ 只写文件名与渠道名，**不写渠道 URL、不写绝对路径**（K42）；docProps 的 creator/lastModifiedBy 是占位符 `REPORT_PLACEHOLDER`；测试用本机用户名/home/git 署名做反向断言 |
| docx 写入器 | `src/sdc/synth/docx.py` | ✅ 加 `application`/`creator` 两个参数（默认值不变 ⇒ `data/synth/` 冻结字节仍一致，`sdc synth --check` 通过）；报告传 `sdc-report`/`REPORT_PLACEHOLDER`。**没有引入 python-docx**——它会写真实时间与用户名，直接打挂字节一致与身份纪律 |
| selfcheck 两档看板 | `src/sdc/selfcheck.py` | ✅ `[6] 推进看板`：各 kind 的 located→verified 进度 + 未启用原因**四分类**；`[7] 核对队列`：按"核对完这条能解锁几项判定"降序排的工单（本轮 116 条条款挡着 126 项判定，文本只打前 15 条并指向 `--json`） |
| 未启用原因的第四类 | `REASON_LABEL["slot_unsupported"]` | ✅ 把"解析层还没有这个槽位"从"等核对"里**分出来**——这类未启用补多少正式文本都没用，得先补抽取（口径 K44） |
| 免责声明单源 | `bench.render_*` | ✅ 三处硬编码副本删除，全部回到 `engine/core.DISCLAIMER`（K23 落进代码），并有"整个 src/ 里这条文案只出现在 core.py"的守门测试 |
| 根 README | `README.md` | ✅ 能做什么 / 指标表 / 纪律 / 快速开始 / 结构。指标表由 `sdc bench --all --markdown` 生成，`tests/test_suite.py::test_readme_metrics_table_matches_a_live_run` **逐行与实跑对账**：改了数据不重跑 README 就是红的 |
| 测试 | `tests/test_report.py`(19) `test_suite.py`(15) + `test_selfcheck.py`(17) `test_text_cli.py`(13) + 既有 | ✅ **19 个文件按文件分批取 rc 全 0**；`sdc selfcheck` 0 问题 rc=0；`sdc bench --all` rc=1（两个不可判） |

**可演示物（四条，缺一不可；`--data-dir` 是全局参数，必须写在子命令之前）**

```bash
set PYTHONPATH=src
# ① 一键四基准：一张指标表 + 确定性明细 + 闸门探针；退出码 1 来自"不可判"而不是"未达标"
py -3.8 -X utf8 -m sdc bench --all                 # rc=1
py -3.8 -X utf8 -m sdc bench --all --markdown      # README 那张表
py -3.8 -X utf8 -m sdc bench --sweep               # rc=0：只做确定性回归
# ② docx 交付物：blocked 也照样出文件（逐项待核对 + 免责声明），退出码仍是 1
py -3.8 -X utf8 -m sdc report --case data/examples/A2-fillet-weld.json --out .tmp_parse/reports/验算书.docx
py -3.8 -X utf8 -m sdc --data-dir tests/fixtures/kb report --case data/examples/A2-fillet-weld.json --out .tmp_parse/reports/验算书-夹具.docx   # rc=0，带逐步计算
# ③ 核查清单与检查单导出（正文与终端同源）
py -3.8 -X utf8 -m sdc parse --dir data/synth/docx --out-dir .tmp_parse/ir
py -3.8 -X utf8 -m sdc check --ir .tmp_parse/ir/SYNTH-0013.ir.json --out .tmp_parse/reports/核查清单.docx   # rc=1
py -3.8 -X utf8 -m sdc checklist --ir .tmp_parse/ir/SYNTH-0012.ir.json --out .tmp_parse/reports/检查单.docx # rc=0
# ④ 推进看板与核对队列
py -3.8 -X utf8 -m sdc selfcheck                   # [6]/[7] 两段
```

导出的三份 docx 能被自家解析层读回（`read_document` 段落数与正文逐段一致），这条也在测试里。

## 二、M4 DoD 逐项结果（含偏差，未抹平）

| DoD（plan/05 §七 M4 行 + HANDOFF-M4 §五） | 结果 |
|---|---|
| 四基准合一 + 汇总表写进 README | ✅ `sdc bench --all`；README §指标 就是那张表，且与实跑逐行对账 |
| 全指标达标 | ⚠️ **没有全达标，也不该这么说**：达标 7 项、**不可判 2 项**——① 算例通过率卡在 `data/cases/` 仍 0 例；② 可硬判 abnormal 的规则分母 0 条（10 条规则的依据**全部只 located**，M3 定档升的是附录 D，那 5 条条款不在任何规则的依据里）。rc=1 是这个意思 |
| docx 0 外链、两次导出字节一致、免责声明强制存在 | ✅ 三条都成立，且**命令面自己把关**（自检不过就不写文件），不是只写在测试里；另有两条反证测试证明扫描不是空转 |
| 报告导出（验算书 / 核查清单 / 检查单） | ✅ 三类都通；形态上 `--out` 挂在 `check`/`checklist` 上、`report` 只管验算书（与 plan/03 §五 命令面一致）。**只有段落没有 Word 表格/标题样式**——写入器是最小 OOXML，加样式要么扩 XML 要么引第三方库（后者破坏字节一致与元数据占位），M5 若要做"像样的验算书版式"先 spike |
| `sdc selfcheck` 增补两档看板 | ✅ `[6]/[7]`；未启用原因四分类里 `slot_unsupported` 是本轮新想清楚的一件事 |
| T5 若定档则处理 `data/tables/` | ✅ **M3 定档轮已做完**（D22/D23：±0.001、附录 D 升 verified、拟合常数与单源隐藏格不入库）。M4 侧的连带后果：数据指纹变了 ⇒ README/plan-05 的实测数字全部重跑过一遍（`a39187e2…` → `235a0c14…`，可溯源率分母 178 → 180） |
| 插值口径登记成新口径条目 | ⚠️ **没做，且不该由 M4 做**：M3 定档没把 φ 表的「离散表 + 线性内插」写成独立口径条目（现在的口径是 K18 + K38 的二维轴 + 超界不外推）。**留给 M5/M6 补一条**——它是引擎行为，不是报告行为 |
| 回写 plan/00、05、06、07、data/README；写 HANDOFF-M5 | ✅ 本文件。00 加 M4 行与 README 索引；05 §六 重写（四态 + 逐项实测）、§七 M4 行；06 加 **D24**（K39~K44）与 4 行变更日志、**T5 关闭**；data/README 两处过期表述改正 |

**M4 期间查出来的三件"上一轮记错了 / 记歪了"**

1. **K26 的字面表述「判定层一律不 import `re`」不成立**。探针（`.tmp_verify/m4/k26-import-graph/probe.py` + `result.tsv`）：`sdc.bench`、`sdc.rules.engine`、`sdc.checklist`、`sdc.selfcheck`、`sdc.suite`、`sdc.report` 在 **import 阶段**就有 `slots.PATTERNS_compiled=True`、模式数 9（它们复用 `parse.slots` 的 `canonical_value`/`SLOT_NAMES`）；连 `sdc.engine.core` 也把 `re`/`sre_parse` 带进来（stdlib 传递导入，做不到"不 import"）。成立的是「判定层不读文档、不对文档执行抽取式匹配」+ **解析与判定分进程**——这正是本轮把一键基准的解析步骤放子进程的理由（D24①/K39）。相关注释与文档已按此改正，并加了一条命令面测试：`tests/test_text_cli.py::test_judgment_commands_never_read_or_parse_a_document`（把 `read_document`/`build_ir` 换成抛异常后跑 `check`/`checklist`/`bench --parse`/`--audit`/`selfcheck`，全部照常完成）。
2. **`data/README.md` 与 README/plan-05 的"verified 仍 0 / 数值一个都没进 data"在定档后全部过期**。已按实测数字改写：条款 161（verified 5）、表 13（verified 2）、符号 36（verified 1）、公式 14（verified 0，`F-D.0.5-1` 故意 pending）、规则 10 与检查单 107 全 located。
3. **CRLF 守门基线就是红的**：`tests/test_eol_guard.py` 在 M4 基线复跑时失败，原因是 `.tmp_parse/o.txt`（M3 会话留下的带 CRLF 临时输出）落在守门范围内——`SKIP_DIRS` 有 `.tmp_verify/` 却没有同样被 gitignore 的 `.tmp_parse/`。补进名单，并把这条理由写进注释。

另：`plan/06` 里 **D22 被引用三处（HANDOFF-M4 §三/§四、plan/07 §七.6）却没有那一行**——M4 按这三处的既有表述把它补成正式决策行（±0.001 容差 + 落库与不入库清单），并把 T5 那行从"⚠️ 落地暂缓、查证中"改成"✅ 已随 D22/D23 关闭"。如果这不是 M3 定档轮的本意，请回退这两处。

## 三、悬而未决（M5 开工前要注意，但都不阻塞 M5 主线）

1. **`F-D.0.5-1` 的"分段/按条件选式"是引擎欠账**（D23）。两支式体（λn≤0.215 与否则式）都指派生目标 `phi`，现行 AST 白名单无条件分支 ⇒ 式体文字已写进 `notes`，但记录保持 pending，一旦升 verified 而引擎还不会选式，依赖一闭合就抛 `EngineError`（等于给 A5 埋雷）。HANDOFF-M4 §五 第 0 条就是这件事。**注意它与 M5 的关系**：不做它，A5 永远 blocked；做它属于引擎改动，会动 `tests/test_engine_*`，与 GUI/打包并行做容易互相打挂。
2. **`data/cases/` 真值仍 0 例**（M1 起就挂着）。`sdc bench --all` 的算例分母是 0，输出必须继续显式说"分母 0，样本待补"，不许用夹具或自造值充数。解除通道见 `data/cases/README.md`（教材/手册例题要书名+版次+例题号齐全）。
3. **单一底图那批表**（4.4.1/4.4.5/4.4.6/11.4.2-1/-2/7.4.6/7.4.7/7.2.1-1-2）按 T5③ 原意保持 located、`values: []`；要继续推进就得再找独立渠道，M4 没有动这件事。
4. **一键基准在冻结环境下会退化**：`suite.run_cli` 走 `sys.executable -m sdc`，PyInstaller onedir 里这条不成立 ⇒ GUI/exe 形态下"确定性回归"那一行会变成「不可用」（M4 已验证它会诚实降级而不是崩）。M5 要么给 exe 补一条"用 CLI exe 自身当子进程"的通路，要么在打包版里把这一行明确标成"桌面版不提供"。**别让它静默显示达标。**

## 四、既定口径清单（改了会打挂基准，动手前先对照）

K1~K16 见 HANDOFF-M2 §四，K17~K25 见 HANDOFF-M3 §四，K26~K36 见 HANDOFF-M4 §四，**全部未变**。
**K37/K38 是 M3 定档轮的**（±0.001 容差；`linear` 支持"分组轴 + 数值轴"、缺分组轴返回 None 绝不跨类插值）。M4 新增：

| # | 口径 | 位置 |
|---|---|---|
| K39 | **一键基准的解析步骤走子进程**（`sys.executable -X utf8 -m sdc parse …`，`--data-dir` 显式传）：套件进程不定义/不编译/不执行项目正则；子进程起不来或超时只让对应指标记「不可用」，不打挂整套。同时把 K26 的字面表述更正为"判定层不读文档、不对文档执行抽取式匹配"——实测证明"不 import `re`"做不到也没必要 | `suite.run_cli`、`tests/test_text_cli.py::test_judgment_commands_never_read_or_parse_a_document`、`.tmp_verify/m4/k26-import-graph/` |
| K40 | **0 外链的机器定义**：部件必须等于白名单；`.rels` 只查 **`Target`**（URL/绝对路径/`TargetMode=External`），`Type` 的关系类型标识符与 XML 命名空间 URI **不算外链**；`word/document.xml` 无 `<w:hyperlink`；**正文文字**（`w:t`）无 `http:`/`https:`/`ftp:`/`mailto:`/`file:`/`www.` 与盘符路径 | `report/docxio.find_external_refs` |
| K41 | **报告与终端渲染同源**：docx 正文 = `render_result`/`render_report`/`checklist.render_text` 的同一批行 + 报告头；M5 的 GUI 不得再写第三套渲染或第二套判定 | `report/body.py`、`tests/test_report.py::test_docx_body_contains_every_terminal_line` |
| K42 | **交付物不写绝对路径、不写渠道 URL**，docProps 的 creator/lastModifiedBy 用占位符；URL 的归属地是取证台账（`data/README.md`、`.tmp_verify/`）。测试用本机用户名/home/git 署名做反向断言 | `report/body._name`、`report/docxio.find_personal_info`、`metadata_values` |
| K43 | **指标表四态与退出码**：达标／未达标／**不可判**（分母 0 这类量不了的，绝不写成通过）／不可用（前置数据或子进程缺失）。`--all`：全达标 0、有未达标或不可判 1、有任何不可用 2；`--sweep` 的码只看确定性回归；`--all`/`--sweep` 与 `--ir-dir`、模式标志之间互斥 | `suite._exit_code`/`sweep_exit_code`、`cli.py` bench 分派 |
| K44 | **selfcheck 看板口径**：未启用原因四分类，优先级 `slot_unsupported` > `threshold_unverified` > `matrix_silent` > `active`（"解析层还没有这个槽位"与"等正式文本"是两件事，混在一起会让人白跑一趟渠道）；核对队列按"解锁项数"降序，文本只打前 15 条并指向 `--json`；已启用但依据未 verified 的规则**仍进队列**（依据升 verified 才判得出 abnormal） | `selfcheck._rule_board`/`_verify_queue`/`_progress` |

## 五、M5 待办（按顺序，每步可单独演示）

0. 若要先解 A5：引擎支持"分段/按条件选式"（§三.1），然后再升 `F-D.0.5-1`；这条做完 `sdc run --module column_buckling` 才有可能出数值——但仍缺 `f`（表 4.4.1 located），**别指望它顺带变绿**。
1. **PySide6 五页签 GUI**（plan/03 §六）：①验算台 ②设计说明核查 ③规范检查单 ④报告导出 ⑤知识库与状态。**只准调 `sdc.engine`/`sdc.rules`/`sdc.checklist`/`sdc.report`/`sdc.suite` 的公开 API**（K41/D08）——GUI 里不许出现第二套判定、第二套渲染、第二套查表。
   - 页签⑤直接把 `sdc selfcheck` 的 `[3] 门控`/`[6] 推进看板`/`[7] 核对队列` 显示出来：把纪律做成看得见的功能。
   - 页签④调 `report.export_docx`，落盘前自检失败要在界面上说清**为什么没写出来**（不要吞掉 `ReportError`）。
   - 测试口径：`QT_QPA_PLATFORM=offscreen` **必须在首次 import PySide6 之前**设置；消息框/文件对话框 monkeypatch；抓帧用 native QPA + `widget.grab()`（offscreen 拿不到中文字体）。
2. **CLI 契约测试**：GUI 与 CLI 同一套行为——同一参数卡两边结论、`data_fingerprint`、免责文案逐字相同（现有 `sdc run/check/checklist/report/bench` 的输出已是基准，别新写期望值）。
3. **PyInstaller onedir 双 exe**（GUI `console=False` + CLI `console=True`）：spec `datas` **白名单**只收运行必需数据 + 构建后遍历断言 dist 树无禁区成分、内嵌数据与仓库逐份对账（任一违反 exit 1）；`find_data_dir` 五分支测试（显式 > 环境变量 > `sys._MEIPASS/data` > exe 目录 `_internal/data` > CWD 上溯）。
   - 坑位预置：`*.spec` 被 .gitignore 的 `*.spec` 吞掉（加 `!sdc.spec` 例外）；spec 内相对路径解析到 SPECPATH；PyInstaller 无 `--workers`；本机 PyInstaller 对新 Python 模块的解析 bug 史——**构建失败先换解释器通道，别硬重试**。
   - §三.4 的 suite 冻结通路问题在这一步一起解决或明确标注。
4. **干净环境验证**：中立目录 + 剥离 PATH 跑 CLI 六连（`selfcheck / run / parse→check / checklist / report / bench --all`）+ GUI 存活探针；**不在仓库树内跑**（CWD 上溯会命中仓库 `data/`，"内嵌"验了个寂寞）。
5. 解析侧已知缺口（M4 未做，`selfcheck` 现在会自己报出来）：`spacing`/`edge`/`end_distance`（螺栓间距边距端距）与螺栓数量类槽位没抽 ⇒ 相关构造规则一加入就落进 `slot_unsupported`；跨段回指（"其余要求同前述"）不解析（设计上不猜）。
6. 回写 plan/00 进度表与 plan/05 的 M5 行，写 HANDOFF-M6。

## 六、本机环境事实（M4 新增，M5 直接照此跑）

1. HANDOFF-M2 §五、M3 §六、M4 §六 全部仍成立：`py -3.8` + `PYTHONPATH=src`；测试**按文件分批取 rc、别接管道**。
2. **`sdc bench --all` 的墙钟成本 ≈ 一次批量解析 ×2 + 4 次子进程**（每个 ~0.2 s，总共几秒）。跑整套测试时 `test_suite.py` 是相对慢的那个文件，别误判成卡死。
3. 新坑（M4 真踩到）：**套件工作目录不清空会造成假绿**。上一轮 `.tmp_parse/suite/ir-a` 留下的旧 IR 会让"这一轮 `parse --dir` 其实失败了（目录不存在，rc=2）"看起来像成功——因为比对读的是目录内容而不是退出码。对策已落进 `suite._reset_ir_dir`（只删套件自己写的 `*.ir.json`，不递归、不碰别的文件）。M5 若新增别的 scratch 步骤，照这条办。
4. 新坑：`find_external_refs` 第一版把 `.rels` 的 **`Type` 属性**（`http://schemas.openxmlformats.org/…`）当外链，任何合法 docx 都会误报。**OOXML 里以 `http://` 开头的标识符有两类是格式本身**（部件命名空间、关系类型），扫描必须只看 `Target` 与 `w:t` 正文。同理"绝对路径"检测不能用 `re`，用一个字母 + `:` + `/`或`\` 的小循环（报告层不碰正则）。
5. `py -3.8 -X utf8 - <<'PY'` 这种 heredoc **可以**带中文（`-X utf8` 解决了 stdin 源码检测），但不带时会被判 "Non-UTF-8 code"（M3 §六.3）。仍然优先写成 `.tmp_*` 下的脚本文件再跑，好处是留下可重放的证据。
6. 子代理纪律：M4 没派子代理（全部主对话内完成）。M5 若要派，仍按 HANDOFF-M1 的教训——**限定可写文件清单**，收尾 `git status` 逐文件 `git diff` 审读，中间证据不许它删。

## 七、禁止事项（M5 阶段）

- 不得为了"通过率/分母有数字"编造教材书名、例题号、规范数值；分母 0 是诚实结果，编来源是事故
- 不得把指标表的「不可判」渲染成达标或绿勾（`--all` 的 rc=1 就是这个意思）；GUI 里也一样
- 不得在 `data/` 里写未核对的数值；`values: []` 的表保持空，除非有新的独立渠道证据 + 交叉核对闭合
- 不得把 `tests/fixtures/**` 的任何数值、式体、规则复制进 `data/`（K25 有测试）
- 不得给 GUI 写第二套判定/渲染/查表（D08/K41）；不得在规则文件里加等级字段，不得把未核对阈值写成数字（K30/K31）
- 不得让 `bench` 在本进程内解析文档（K39）；文档解析只在 `sdc parse` 与套件的子进程里发生
- 不得引入 LLM / 网络依赖 / numpy / scipy / faiss；导出侧不新增第三方依赖（python-docx 会写真实时间与用户名，直接打挂 K42 与字节一致；要引先做 spike 并记 plan/06）
- 不动 `.gitattributes` 的 `eol=lf`；不手改 `data/synth/`（改模板 → 固定 seed 重生成）；不删 `.tmp_verify/` 与 `.tmp_parse/`
- 改了 `data/` 就要重跑 `sdc bench --all --markdown` 并同步 README——`test_readme_metrics_table_matches_a_live_run` 会替你记着这件事
- 对外动作（push / 建仓 / tag / Release）未获用户确认不得执行；提交前先 `git status` 逐文件审读改动
- ⚠️ **本工作树的提交状态**：`git log` 只到 M1（`948bb59`），**M2/M3/M3-定档/M4 的改动至今全部未提交**（M3 定档轮明确说"这会儿提交会把 M4 半成品一起快照进去"，M4 同样不擅自提交）。接手第一件事就是决定怎么切分提交——`git status` 里有 25 个跟踪文件被改 + `src/sdc/{engine,parse,rules,report}/`、`tests/test_{report,suite}.py`、`README.md`、`data/{rules,checklist,examples}/` 等未跟踪目录。
