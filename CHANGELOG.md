# Changelog

本项目的版本分两层：

- **代码版本**（本文件）：修 bug、加功能、改交付形态
- **规则集版本**：条款库 / 数值表 / 公式 / 符号 / 核查规则所依据的标准及其生效日期

> 判定结果发生变化（或放弃解释器支持一类破坏性环境变更）时，**主版本号 +1**，
> 并在发布说明中提示「历史报告需重跑」。

## [0.1.1] - 2026-10-22

> **0.1.0 之后的 7 个提交此前没有发版**，本版把它们一次性落了 tag：报告头依据版本、
> 规则集复核元数据、GUI 抓帧时序修复都在 `main` 上，但 Release 的两个 exe 还停在 `v0.1.0`
> 时点。本版从 `main` 重打两个 exe —— 版本号就是区分两者的唯一办法。

### 新增

- **报告头写入依据版本**：三类交付物（验算书 / 核查文本 / 检查单）头部新增
  `依据规范：GB 50017-2017、GB 55006-2021、JGJ 82-2011` + 本次/下次复核日；
  与「引擎版本」同一行组出现。**不写生成时间** —— 交付物要求无身份信息且两次导出逐字节一致（K42）。
- **规则集复核元数据** `data/review/ruleset-review.json` 的 `meta.review`：复核日 / 周期 /
  下次到期 / 复核人 / `standards[]`（含 `currency` 与 `authority_url`）/ 每个知识文件的
  `standard` 与 `used_by` / `declared_not_used`（声明本版本不依赖的 extras）。
- **守门测试** `tests/test_clause_review.py`：6 个用例（元数据齐全 / 日期与周期 / `authority_url` /
  覆盖每个知识文件且标准已登记 / `not_used_by` 与真实模块依赖面吻合 / 报告头可见依据与引擎版本）。
- **`sdc bench --allow-indeterminate`**：把「不可判」（分母 0，这条现在量不了）从退出码 1 里
  摘出来，只有「未达标」才 exit 1。默认不带旗标时行为与 0.1.0 完全一致（仍 exit 1）；
  「不可用」永远是 2。指标表里那几行仍逐项写「不可判」，**不会**被渲染成达标。

### 变更

- `pyproject.toml`：`[project.urls]` 增加 `Changelog`；classifiers 补齐
  Development Status / Intended Audience / Topic。
- README「判定依据」表增加「本次复核（下次复核）」与「是否现行」两列，与
  `meta.review` 一致。
- **删掉 `report` 与 `pdf` 两个 extra**：两者代码里 0 使用（`grep` 证实）。
  `report` 的 python-docx 会写真实时间与用户名、打挂 K42，`pdf` 对应的 PDF 输入从未实现；
  `pip install sdc[report]` 只会白拉一整套 lxml。`declared_not_used` 里的说明保留。
- **CI 基准门禁带 `--allow-indeterminate`**：`scripts/ci_bench_gate.py` 接受同名旗标并据此
  对账退出码；「未达标 / 不可用」照旧红，负控见 `tests/test_ci_workflow.py`。
- **CI 新增 `No CRLF committed to the index`**：`test_eol_guard.py` 只看工作树，
  这条用 `git ls-files --eol` 把「提交进索引的 CRLF」也挡住。
- `tests/test_eol_guard.py` 的 `SKIP_DIRS` 加 `update`，与 `.gitignore` 对齐
  （二次迭代交接物落盘曾把这条门打红过）。

### 修复

- **删掉 `src/sdc/engine/expr.py` 里 `ast.Num` 的兼容兜底**（3 行）。`ast.parse` 从 3.8 起只产
  `ast.Constant`，前面那段已完整覆盖；而 `getattr(ast, "Num", None)` 本身在 3.12+ 触发
  `DeprecationWarning`，把 pytest 告警从 **1735 条压到 0 条**。**不是修 bug** ——
  原来的写法有 `is not None` 保护，3.14 移除 `ast.Num` 也不会崩。
- **GUI 抓帧时序修复**、**报告头写入依据规范**（`sdc.gui.app` / `sdc.report.body`）：
  这两个在 0.1.0 tag 之后就已提交，本版随重打的 exe 首次进入发布物。

### 规则集

- **无变更**。当前依据：
  - GB 50017-2017《钢结构设计标准》（2018-07-01 实施）—— 现行；4.3.2 等强条自 2022-01-01 起废止
  - GB 55006-2021《钢结构通用规范》（2022-01-01 实施）—— 现行；住建部公告 2021 年第 69 号已直连核实
  - JGJ 82-2011《钢结构高强度螺栓连接技术规程》（2011-10-01 实施）—— 现行；6 条强条随 GB 55006-2021 废止
- `data_fingerprint` 仍为 `235a0c14…`：`data/clauses` 与 `data/tables` 一字节未动，
  没有一条数据升 `verified`（`data/review/` 不在指纹计入目录内）。

### 是否需要重跑历史报告

**否。** 判定结论未变（5 个模块对真实数据仍全部 `blocked`），交付物差异仍只是报告头那几行依据。

## [0.1.0] - 2026-10-07

首个发布版本：5 个连接与稳定验算模块 + 设计说明文本核查 + GB 55006-2021 全 8 章 107 条检查单 +
docx 交付物 + PySide6 五页签界面；双 exe（`sdc-cli` / `sdc-gui`）与源码跑法。

### 规则集

- GB 50017-2017 / GB 55006-2021 / JGJ 82-2011（条款 161 条 + 数值表 13 张 + 公式 14 条 + 符号 36 项 +
  规则 10 条 + 检查单 107 条，均挂渠道档；真实数据上一律 `blocked`，不猜数值）
- 数据指纹 `235a0c14…`；条款库只登记「标准号 + 条号 + 要点转述 + 出处」，不转载正文