# steel-design-checker

[![CI](https://github.com/yuluo554/steel-design-checker/actions/workflows/ci.yml/badge.svg)](https://github.com/yuluo554/steel-design-checker/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

钢结构连接与构件验算计算器 —— 规范驱动的离线桌面工具：5 个验算模块 + 设计说明文本核查 +
GB 55006-2021 符合性检查单 + 内置基准与 docx 交付物。

**它不是**：自动出图、荷载组合生成、节点构造优化，也不替代正式设计文件与施工图审查。

> **辅助验算工具，不替代正式设计文件与施工图审查。** 这句免责声明强制写进每一条计算结果、
> 每一份导出的 docx，以及终端输出的最后一行。

## 现在能做什么

| 能力 | 命令 | 当前状态 |
|---|---|---|
| 单模块验算（对接焊缝 / 角焊缝 / 普通螺栓 / 高强螺栓摩擦型 / 轴心受压整体稳定） | `sdc run --case 参数卡.json` | 引擎与 5 个模块已就绪；引用未核对数据时 **拒算并逐项说明缺哪条核对**（附录 D 已 verified，但 f 仍来自 located 的表 4.4.1 ⇒ 没有模块出数值，见下「纪律」） |
| 设计说明 → 参数卡 IR | `sdc parse --doc 说明.docx` | 支持 `.docx/.txt/.md`（标准库直读 OOXML，不引第三方 docx 库） |
| 文本核查三级判定（异常 / 可疑 / 通过） | `sdc check --ir X.ir.json` | 10 条规则，每条挂依据条款与原文段落 |
| GB 55006-2021 符合性检查单 | `sdc checklist` | 全 8 章 107 条，9 条挂自动初判，其余显式待人工确认 |
| docx 交付物 | `sdc report --case X.json --out 验算书.docx`；`check`/`checklist` 加 `--out` | 0 外链、两次导出字节一致、免责声明强制存在 |
| 一键基准 | `sdc bench --all` | 四基准合一 + 指标表（下表） |
| 数据推进看板 | `sdc selfcheck` | 三档 status 进度 + 未启用原因 + 「核对哪条条款解锁哪些规则」队列 |
| 桌面界面（五页签） | `sdc gui`，或双击 `dist/sdc-gui/sdc-gui.exe` | 验算台 / 设计说明核查 / 规范检查单 / 报告导出 / 知识库与状态；正文与终端逐字同源，无第二套判定 |

## 指标

下表由 `sdc bench --all --markdown` 生成，`tests/test_suite.py` 逐行与实测对账——
改了数据没重跑，这条测试会红。**「不可判」是诚实的分母 0，不是通过。**

| 指标 | 门槛 | 实测 | 结论 | 来源命令 |
|---|---|---|---|---|
| 算例通过率 | 100% | 分母 0，样本待补 | 不可判 | `sdc bench --cases` |
| 确定性回归 | 100%，违反即未达标 | 24 份 IR 两次一致 | 达标 | `sdc bench --sweep` |
| 解析 F1 | ≥ 0.95 | 1.0000 | 达标 | `sdc bench --parse` |
| 缺陷检出率 | ≥ 0.95 | 1.0000 | 达标 | `sdc bench --audit` |
| 误报 | 0（硬门） | 0 处 | 达标 | `sdc bench --audit` |
| 条款可溯源率 | 100% | 12 / 12 条 finding 带条款 | 达标 | `sdc selfcheck` |
| 待核对闸门 | 0 例（必须 blocked） | 0 例漏出数值 | 达标 | `sdc run / sdc selfcheck` |
| 0 外链 | 0（硬门） | 0 处（3 份交付物） | 达标 | `sdc report / check --out / checklist --out` |
| 可硬判 abnormal 的规则分母 | — | 0 条规则 | 不可判 | `sdc bench --audit` |

两个「不可判」各有各的原因，别混成一句：**算例通过率**卡在 `data/cases/` 仍是 0 例
（真值要书名+版次+例题号齐全，解除通道写在 `data/cases/README.md`）；
**可硬判 abnormal 分母**卡在 10 条核查规则的依据条款**全部只 `located`**。
M3 定档把附录 D 的 φ 表与 α 表升到了 verified（条款 5 / 表 2 / 符号 1），但那几张表
既不在任何规则的依据里、也不含强度设计值 f ⇒ 规则档位与模块门控都没动。
用编造来源换取绿灯，是本项目最不能犯的错。

## 纪律：未核对的数据不进计算

条款库三档 `status`：**只有 `verified` 能进计算路径**；`located`（条号与主题已定位、数值未核对）
与 `pending` 一样让模块 `blocked`，而且 blocked 的结果里**一个数值都没有**，只有逐项缺什么。

```console
$ py -3.8 -X utf8 -m sdc run --module fillet_weld --case data/examples/A2-fillet-weld.json
结论：blocked（拒算（数据未核对））
比值（作用效应/抗力）：不出数值（blocked）
[拒算依据] 引用了未核对的数据，按口径 K2/K15 不产生数值：
  - clause   GB50017-2017:11.2.2          status=located（条号/表号已定位，式体与数值未核对），不进计算
  …
```

数值通路的验证靠 `tests/fixtures/kb/` 的**合成 verified 夹具**（虚构数据，渠道 `合成夹具`）：
同一套引擎、同一套门控，夹具上出逐步计算，真实数据上拒算。夹具里的任何数值与式体都不许
复制进 `data/`（有测试守着）。

## 快速开始

运行只需 Python 3.8+ 标准库，不装任何包也能跑全部命令：

```bash
git clone https://github.com/yuluo554/steel-design-checker.git
cd steel-design-checker
set PYTHONPATH=src                    # Windows cmd；PowerShell 用 $env:PYTHONPATH="src"；Git Bash 用 export PYTHONPATH=src
py -3.8 -X utf8 -m sdc selfcheck                     # 数据完整性 + 推进看板
py -3.8 -X utf8 -m sdc parse --dir data/synth/docx --out-dir .tmp_parse/ir
py -3.8 -X utf8 -m sdc check --ir .tmp_parse/ir/SYNTH-0013.ir.json
py -3.8 -X utf8 -m sdc bench --all                   # 一键四基准 + 指标表
py -3.8 -X utf8 -m sdc report --case data/examples/A2-fillet-weld.json --out 验算书.docx
```

退出码：`0` 完成 / `1` 降级完成（拒算、有可疑项、指标未达标）/ `2` 输入不可用。

跑测试与界面走可编辑安装（三条前置是有原因的：3.8 自带的 pip 太老，无法可编辑安装
pyproject-only 项目；激活后要用 `python`，Windows 的 `py` 启动器会绕过 venv 装到系统 Python）：

```bash
py -3.8 -m venv .venv
.venv\Scripts\activate                                # Linux/macOS：source .venv/bin/activate
python -m pip install -U pip
python -m pip install -U setuptools wheel
python -m pip install -e ".[dev]"                     # pytest + pyyaml（CI YAML 守门用）
python -X utf8 -m pytest -q -rs                       # 25 个测试模块 334 项（装 .[dev,gui] 后 0 跳过）
```


## 桌面版（GUI + exe）

```bash
python -m pip install -e ".[gui]"              # PySide6（上限按实测 pin：3.8 上可解析的最高版本是 6.6.3.1）
py -3.8 -X utf8 -m sdc gui                  # 五页签界面（页签②的文档解析走子进程）
py -3.8 -X utf8 -m sdc gui --screenshot 帧.png   # 抓一帧（native QPA 才有中文字体）

python -m pip install -e ".[pkg]"              # PyInstaller
py -3.8 -m PyInstaller --noconfirm sdc.spec # 产出 dist/sdc-cli 与 dist/sdc-gui 两个 onedir 包
py -3.8 -X utf8 scripts/verify_dist.py      # 构建红线：白名单 + 逐份 sha256 对账 → DIST_AUDIT_OK
py -3.8 -X utf8 scripts/clean_env_check.py  # 中立目录 + 剥离 PATH 跑双 exe → CLEAN_ENV_OK
```

**两个包要一起发**：`sdc-gui` 的一键基准与页签②的文档解析都用同侧的 `sdc-cli.exe` 当子进程
（口径 K45）。只拷走 `sdc-gui/` 而不带 `sdc-cli/` 时，这两处会老实显示**不可用**——这是设计行为，
不是崩溃，但发 Release 时请把两个 zip 一起放。

界面上没有任何一套自己的判定：每个页签的正文就是命令面用的那个渲染函数的输出，
`tests/test_gui_contract.py` 把两边输出逐字对账（含 `bench --all` 的整张指标表）。
数据目录按「显式参数 > `SDC_DATA_DIR` > 包内 `_MEIPASS/data` > exe 同侧 `_internal/data` >
CWD 上溯」解析；打包版的一键基准用同侧的 `sdc-cli.exe` 当解析子进程，找不到时那一行
显示**不可用**而不是达标。

## 仓库结构

```
src/sdc/{kb,engine,parse,rules,report,synth,gui}/   分层：数据 → 引擎 → 解析 → 判定 → 交付物 → 界面
sdc.spec + scripts/{bundle_rules,verify_dist,clean_env_check,entry_cli,entry_gui}.py   打包与构建红线
scripts/{audit_release,ci_bench_gate,make_tech_report}.py   脱敏五步审计 / CI 基准门禁 / 技术报告生成
.github/workflows/ci.yml                            四矩阵（3.8 基线 + 3.12 防版本差，一个矩阵装 gui）
data/{clauses,tables,formulas,symbols,rules,checklist,cases,synth,selfcheck,examples}/
docs/技术报告.md + 技术报告.docx                    材料固化（docx 由 md 程序化生成，禁止手改）
plan/       需求解读、架构选型、模块详设、数据计划与里程碑、决策记录、条文查证、交接与发布留档
tests/      25 个测试模块（schema/门控/引擎/解析/核查/基准/报告/界面契约/打包与守门/CI 与脱敏守门）
```

项目计划与逐条口径见 [plan/00-README总览.md](plan/00-README总览.md)；
数据台账（每份数据的来源、许可、status）见 [data/README.md](data/README.md)。

## 版权与免责

条款库只登记「标准号 + 条号 + 要点转述 + 出处」，不整条转载规范正文；导出物不写渠道 URL、
不写绝对路径（0 外链断言连带把机器用户名与 home 路径也一并拦下）。
本工具的计算结论来自仓库里的公式与规则表，**不引入 LLM、不联网**，因此任何结论都可以
回溯到「哪一条款、哪一式、哪个表值」——也包括回溯到它错在哪。
