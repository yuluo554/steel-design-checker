# DEVELOPMENT — steel-design-checker 开发细节索引

> 本文件**只做索引与现状摘要**，不复制 `plan/` 下的内容（避免双份维护）。
> 里程碑与 K 口径清单的**唯一来源**在 [plan/05-数据计划与里程碑.md](plan/05-数据计划与里程碑.md)
> 与 [plan/06-决策记录.md](plan/06-决策记录.md)；逐条条文查证状态在
> [plan/07-条文查证与待核对清单.md](plan/07-条文查证与待核对清单.md)。
> 面向用户的功能说明、判定依据与已知限制在 [README.md](README.md)。

---

## 一、按需查哪份文档

| 想了解 | 看这里 |
| --- | --- |
| 题目定义、5 模块首期范围 | [plan/01-题目详细定义.md](plan/01-题目详细定义.md) |
| 需求解读（P1–P4 痛点 → 交付物） | [plan/02-需求解读.md](plan/02-需求解读.md) |
| 分层架构、JSON 知识库 schema、退出码契约 | [plan/03-架构与技术选型.md](plan/03-架构与技术选型.md) |
| 模块级详设（五个验算模块 + 核查 + 检查单 + 报告） | [plan/04-模块详设.md](plan/04-模块详设.md) |
| 数据计划与里程碑（K 口径清单） | [plan/05-数据计划与里程碑.md](plan/05-数据计划与里程碑.md) |
| 决策记录 D01–Dxx（改变既定口径必须在此登记） | [plan/06-决策记录.md](plan/06-决策记录.md) |
| 条文查证渠道、三档 status、待核对清单 V1–V8 | [plan/07-条文查证与待核对清单.md](plan/07-条文查证与待核对清单.md) |
| 阶段交接（M1→M6 逐棒唯一入口） | [plan/HANDOFF-M1.md](plan/HANDOFF-M1.md) … [plan/HANDOFF-M6.md](plan/HANDOFF-M6.md) |
| `v0.1.0` 发布留档（tag 时点事实 + tag 后追加事实） | [plan/RELEASE-M6.md](plan/RELEASE-M6.md) |
| 每份数据的来源 / 许可 / status | [data/README.md](data/README.md) |
| 技术报告（材料固化，docx 由 md 程序化生成、禁止手改） | [docs/技术报告.md](docs/技术报告.md) |

## 二、仓库结构（摘要，细节见 plan/03）

```
src/sdc/{kb,engine,parse,rules,report,synth,gui}/   分层：数据 → 引擎 → 解析 → 判定 → 交付物 → 界面
sdc.spec + scripts/{bundle_rules,verify_dist,clean_env_check,entry_cli,entry_gui}.py   打包与构建红线
scripts/{audit_release,ci_bench_gate,make_tech_report}.py   脱敏五步审计 / CI 基准门禁 / 技术报告生成
.github/workflows/ci.yml                            四矩阵（3.8 基线 + 3.12 防版本差，一个矩阵装 gui）
data/{clauses,tables,formulas,symbols,rules,checklist,cases,synth,selfcheck,examples}/
tests/                                              25 个测试模块（schema/门控/引擎/解析/核查/基准/报告/界面契约/打包与守门/CI 与脱敏守门）
```

- **CLI 是单一事实源**（口径 K D08）：GUI 每个页签的正文就是命令面同一渲染函数的输出，
  `tests/test_gui_contract.py` 把两边输出逐字对账（含 `bench --all` 的整张指标表）。
- 数据目录解析顺序：显式参数 > `SDC_DATA_DIR` > 包内 `_MEIPASS/data` > exe 同侧 `_internal/data` > CWD 上溯。

## 三、CI 矩阵

工作流 `.github/workflows/ci.yml`，`defaults.run.shell: bash`（Windows runner 默认 pwsh，
`$?` 与 `set -e` 语义不同）。四个矩阵：

| OS | Python | extras |
| --- | --- | --- |
| ubuntu-22.04 | 3.8（开发基线；24.04 不提供 3.8） | dev |
| ubuntu-latest | 3.12 | dev |
| windows-latest | 3.8 | dev,gui（唯一装 PySide6 的矩阵） |
| windows-latest | 3.12 | dev |

只装 gui 的那一个矩阵会让其余矩阵的 GUI 用例被 `importorskip` 声明式跳过（`-rs` 逐项可见），
所以 CI 打印收集总数并在 RELEASE-M6 里逐项归因。**CI 不落地任何 scratch 文件**：Windows runner 上
`> collect.txt` 会写成 CRLF，而 `tests/test_eol_guard.py` 扫工作树（CI 首跑就是被这条抓住的）。

CI 另有一条 `No CRLF committed to the index`（`git ls-files --eol | grep i/crlf`）：EOL 测试只能看见
**工作树**，看不见索引里到底存了什么，这条把「提交进仓库的 CRLF」挡在合并前。

基准那一步从 0.1.1 起用 `sdc bench --all --json --allow-indeterminate`（DEC2=A）：分母 0 的
「不可判」按 0 放行，「未达标 / 不可用」照旧红；门禁脚本要拿到同一个旗标才能对账退出码。

**可选 extras 只有 `dev` / `gui` / `pkg`**（0.1.1 移除了 `report` / `pdf`：代码里 0 使用，
装了只会白拉 python-docx + lxml / pypdf）。

本机等价命令（本机 venv 引导 pip 会崩，见 HANDOFF-M1 §五；测试用 `pythonpath = ["src"]` 免安装）：

```bash
py -3.8 -X utf8 -m pytest -q -rs
py -3.8 -X utf8 -m sdc bench --all
```

测试总数**随 extras 变化**，复验时必须说清装法（2026-10-22 实测，全新 venv）：

| 装法 | 0.1.0 基线 | 0.1.1 实测 |
| --- | --- | --- |
| `pip install -e .` + `pytest`（核心） | `301 passed, 3 skipped` | **`304 passed, 3 skipped`** |
| `pip install -e ".[dev]"` | `309 passed, 2 skipped` | **`313 passed, 2 skipped`** |
| `.[dev]` + `PySide6>=6.4,<6.7` | `340 passed, 1735 warnings` | **`344 passed`, 0 warnings** |

增量来源（+3 / +4 / +4）：`test_suite.py` 两条（旗标只放行 `unmeasurable`；
放行后仍逐项列「不可判」）+ `test_run_cli.py` 一条（命令面四态）——
这三条不依赖 pyyaml；`test_ci_workflow.py` 那条门禁负控要靠 `[dev]` 的 pyyaml，
所以核心档只 +3。

## 四、条款库三档与拒算门控（口径见 plan/05、plan/07）

- `status` 三档：`verified` / `located` / `pending`。**只有 verified 进计算路径**；
  另两档让模块 `blocked`，且 blocked 结果**不含任何数值**，只逐项列出缺哪条核对。
- 数值通路验证靠 `tests/fixtures/kb/` 的合成 verified 夹具（虚构数据、渠道标注"合成夹具"）；
  夹具数值不许复制进 `data/`（有测试守着）。
- `data_fingerprint`（K12）= sha256(规范化拼接 `data/clauses` + `data/tables`)：
  排版改动不影响指纹，任一数值或条号改动必然改变指纹。实现在 `src/sdc/kb/fingerprint.py`。
- 申请新数据入计算路径的前提：先核对原文 → 升 `status` → 重算指纹 → 跑 `sdc bench --all`。

## 五、打包红线与发布对账

```bash
python -m pip install -e ".[pkg]"
py -3.8 -m PyInstaller --noconfirm sdc.spec          # 产出 dist/sdc-cli 与 dist/sdc-gui 两个 onedir 包
py -3.8 -X utf8 scripts/verify_dist.py               # 白名单 + 逐份 sha256 对账 → DIST_AUDIT_OK
py -3.8 -X utf8 scripts/clean_env_check.py           # 中立目录 + 剥离 PATH 跑双 exe → CLEAN_ENV_OK
```

**两个包要一起发**：`sdc-gui` 的一键基准与页签②的文档解析都用同侧的 `sdc-cli.exe` 当子进程
（口径 K45）；只拷走 `sdc-gui/` 时这两处老实显示**不可用**（设计行为，不是崩溃）。

| 项 | 值 |
| --- | --- |
| 版本 | `v0.1.1`（包版本 `0.1.1`，`pyproject.toml` / `src/sdc/__init__.py`） |
| 发布留档 | [plan/RELEASE-M6.md](plan/RELEASE-M6.md)（v0.1.0）、[plan/RELEASE-0.1.1.md](plan/RELEASE-0.1.1.md)（v0.1.1） |
| 构建红线 | `scripts/verify_dist.py`（DIST_AUDIT_OK）+ `scripts/clean_env_check.py`（CLEAN_ENV_OK） |
| 脱敏审计 | `scripts/audit_release.py`（五步审计：无 URL、无绝对路径、无用户名） |

## 六、界面与 exe 的本机注意

- 抓帧要在 native QPA 上跑（offscreen 拿不到中文字体）；`--screenshot` 走 `gui.capture()`。
- `QPixmap.save(BytesIO)` 在 PySide6 6.6 不可用 ⇒ 存进 `QBuffer` 再落盘（`gui/app.py:capture`）。
- `PySide6` 在 Python 3.8 上的可解析上限是 6.6.3.1（6.7+ 元数据要求 ≥3.9），`pyproject` 两端都钉。
- 导出的 docx 走「0 外链」硬门，因此报告里**不含任何 URL**；需要出处时读仓库条款库。