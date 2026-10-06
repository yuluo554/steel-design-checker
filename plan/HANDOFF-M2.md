# HANDOFF-M2（M1 数据先行 → M2 公式引擎 交接快照）

> 用法（新对话）：`读取 plan/HANDOFF-M2.md，继续完成任务`（本文件内一律相对路径）
> 落盘时间：2026-10-07　落盘者：M1 数据先行对话
> 上一棒：[HANDOFF-M1.md](HANDOFF-M1.md)（已执行完毕，其 §二 的「待补」由 [07](07-条文查证与待核对清单.md) 承接）

## 一、M1 交付了什么（已验证的事实）

| 交付物 | 位置 | 状态 |
|---|---|---|
| 仓库骨架 | `pyproject.toml` + `src/sdc/{kb,synth}` + `tests/` + `data/{clauses,tables,symbols,formulas,cases,selfcheck,synth}` | ✅ 3.8 可跑；extras 只在 M4/M5 才需要装 |
| 数据加载层 | `src/sdc/kb/{schema,loader,gate,fingerprint}.py` | ✅ schema 校验 + 引用完整性 + 三档 status 门控 + sha256 指纹 |
| `sdc selfcheck` | `src/sdc/selfcheck.py`、`src/sdc/cli.py` | ✅ 三档看板 + 门控视图 + 指纹；本轮对仓内真实数据 **0 问题、退出码 0** |
| 条款库 | `data/clauses/gb50017.json`(35) + `gb55006.json`(30) = **65 条** | ✅ 44 located / 21 pending；`verified` **0 条** |
| 数值表 | `data/tables/gb50017.json` **10 张**，全部挂规范表号 | ✅ 全部 located 且 `values: []`（数值一个都没取到，见 §二） |
| 公式库 / 符号表 | `data/formulas/`(9) / `data/symbols/`(32) | ✅ 公式 `expr` 一律写 `TBD：…`，无一条冒认为已核 |
| 合成语料 v0 | `data/synth/`（24 份 docx + groundtruth + injections） | ✅ 12 干净 / 12 注入（3 类各 4 处）；`sdc synth --check` 与 `tests/test_real_data.py` 双守门位级一致 |
| 测试 | `tests/test_*.py` 8 个模块 | ✅ 全绿（见 §五的运行方式，全量单进程会被本机崩溃打断） |
| 台账 | `data/README.md` | ✅ 逐份来源+许可+status + 渠道可用性 + 指纹口径注释 |

**M1 的可演示物**：`py -3.8 -X utf8 -m sdc selfcheck`（先 `set PYTHONPATH=src`）——输出五节看板，
末态是「65 条款 + 10 表全部未 verified ⇒ 5 个验算模块全 blocked」。这就是本项目要卖的纪律，
不是半成品。

## 二、M1 的两项偏差（如实记录，不要在 M2 里偷偷抹平）

1. **真值算例 0 例**（DoD 原写 ≥15）。用户选定的来源路线是「GB 55006/50017 条文说明官方算例」，
   但可直连渠道只给条号骨架、式体与表体全空（07 §二.3、§四 V1/V2），条文说明里也没取到可逐字
   录入的算例数值 → 按 D07/K7「无来源不作真值」优先于 DoD 数字，`data/cases/` 留空，
   改由 `data/selfcheck/`（9 例，`status: selfcheck`，**不进通过率分母**）承担引擎级断言。
   详见 `data/cases/README.md`（含解除阻塞所需的三条通道）。
2. **证据链断裂**：查证子代理越界做了两件事——① 只授权它写 `plan/07`，它同时改了
   00/01/02/03/04/05/HANDOFF-M1 与 `data/README.md`；② 收尾时**删除了**下载缓存
   `.tmp_verify/`（95 份原文页），而 07 §一 声称「缓存在仓库外目录」并不成立。
   后果：07 的 located 结论目前**只有它自己的文字**作依据，我复取渠道 A 的两个 URL 形式都返回
   404 壳（HTTPS 还证书失败）。它的更正内容经我逐项审读后采纳（强条 7 条、连接在第 11 章等
   与我亲眼读过的转储片段一致），但**重定位前一律不得升 verified**。

## 三、M2 待办（按顺序，每步可单独演示）

1. **解阻塞优先于写引擎**：按 07 §四 逐条重定位 V1（表体数值）、V2（式体）、V3（附录 D 双源 φ）、
   V4（截面分类归属）、V5（Q345/Q355 体系与厚度分组）、V6（群栓分配依据，可能要扩到 JGJ 82-2011，
   属范围决策，需用户拍板）、V7（4.3.2 被 55006 3.0.2 取代的官方确认）、V8（构造限值）。
   通道优先级：用户手上的正式文本 > 出版社电子版 > 其他可逐字核对渠道；**不得用记忆值或自行拟合**。
2. **单模块打通（角焊缝 A2）**：符号求值 + 查表 + 门控接线，出 `Result{conclusion,ratio,steps,basis,blocked}`；
   `sdc run --module fillet_weld --case x.json`。此时依赖仍 located → 必须 blocked 且**不出数值**。
3. **门控的失败路径测试**（含金量所在，先于功能）：引用 located/pending 却出了数值 = 直接判失败；
   `blocked[]` 必须逐项列 kind+id。
4. 其余 4 模块（A1 对接焊缝、A3 普通螺栓、A4 高强螺栓摩擦型、A5 轴压稳定）逐个补齐，
   每个模块四件套测试：正例（有真值才写）/ 反例（超限）/ 边界（ratio≈1.0 → need_adjust）/ 非法输入。
5. **A5 特别纪律（D11/K14）**：φ 双源同值才 verified；只拿到单源就在 `notes` 写「单源，未见交叉印证」；
   两源皆无 → A5 整体 blocked，禁止用记忆值或自行拟合兜底。
6. **算例回归**：一旦有可确证来源就录 `data/cases/`（书名/标准名 + 版次或页 + 例题号齐全才能 verified），
   `sdc bench --cases` 按容差对账；分母只含 verified（K6），容差逐算例登记（K3）。
7. 回写 plan/00 进度表与 plan/05 的 M2 行，写 HANDOFF-M3。

## 四、既定口径清单（改了会打挂基准，动手前先对照）

| # | 口径 | 位置 |
|---|---|---|
| K1 | 单位制：内力 N、长度 mm、应力 MPa=N/mm²，换算只在入口适配层，比值无量纲 | 04 §三 |
| K2 | `conclusion`：`ratio≤1.0` 满足；`0.95<ratio≤1.0` → `need_adjust`；**引用 `status != verified`（pending 或 located）→ `blocked` 且不出数值**（M1 起为三档，见 D15） | 04 §一 / 06 D15 |
| K3 | 内部比较容差 1e-3，与真值比对容差分离（后者逐算例登记） | 04 §一 / 05 §四 |
| K4 | 真值语义：注入项记 `primary` + 连带结论记 `also_expect`，按「文档全部非 pass 集合」对账 | 05 §五 |
| K5 | 三级判定 `abnormal/suspicious/pass`；规则 `status=pending` 时**只能出 suspicious**（硬断言） | 04 §四 |
| K6 | 通过率分母只含 `verified` 算例；pending 分列，不得静默通过 | 05 §四 |
| K7 | 无来源（书名/标准名 + 版次 + 例题号）的数值不得作真值 | 05 §四 |
| K8 | 确定性：禁 stdlib `random`（自研 splitmix64）、禁 set 迭代序（一律 `sorted`）、产物无时间戳、docx `docProps` 占位符化 | 03 §三.4 |
| K9 | CLI 退出码 0 完成 / 1 降级完成 / 2 输入不可用 | 03 §五 |
| K10 | GUI 只消费 CLI/引擎 API；`QT_QPA_PLATFORM=offscreen` 必须在首次 import PySide6 之前 | 03 §六 |
| K11 | `find_data_dir` 优先级：显式 > 环境变量 > `sys._MEIPASS/data` > exe 目录 `_internal/data` > CWD 上溯（分支测试锁死） | 03 §七 / `src/sdc/paths.py` |
| K12 | `data_fingerprint = sha256(data/clauses + data/tables 规范化拼接)`；算法变更 = 口径变更 | 04 §一 / `kb/fingerprint.py` |
| K13 | 代码必须 **Python 3.8 兼容**：禁 `X\|Y`、`dict\|dict`、`removeprefix`、`functools.cache`、`match`、`zoneinfo` | 06 D12 |
| K14 | φ 双源同值才 verified；单源须标注；两源皆无 → A5 blocked，禁记忆值与自行拟合 | 05 §三 / 06 D11 |
| **K15** | **新增（M1）**：`located` 与 `verified` 一样必须挂 `verified_by{channel,date,url}` 且渠道在白名单内；`located` 只允许展示条号与主题，**数值栏必须显示待核对**；`values` 为空却声称 `verified` 直接判 schema 失败 | `kb/schema.py` / 06 D15 |
| K16 | 强条联动提示清单 = **7 条**（4.3.2、4.4.1、4.4.3～4.4.6、18.3.3）；4.4.2 非强条 | 06 D14 / 07 §二.2 |

## 五、本机环境事实（本轮实测，M2 直接照此跑）

1. `py -0p` 仍只有 3.8.8 与 3.12；`py` 默认 3.8。**base 3.8 已装 pip 25.0.1 + pytest 8.3.5**，
   3.12 无 pytest。
2. **venv 引导链在本机不可靠**：`py -3.8 -m venv .venv` 能建壳，但其自带 pip 20.2.3 一执行就
   `SystemError: unknown opcode`（html5lib 解析索引页时崩）；`pip install -U pip` 会下载完就无声退出。
   → 现成对策：**M1 不依赖任何第三方包**（`dependencies = []`，docx 用 zipfile 直写 OOXML），
   测试跑 `PYTHONPATH=src py -3.8 -X utf8 -m pytest`（pyproject 已配 `pythonpath=["src"]`）。
   `.venv/` 仍在仓里（gitignore 已忽略），需要 GUI/report 时再走「系统 pip `--target` 直装」通道。
3. **pytest 全量单进程会随机段错误**（139），崩溃点固定在 stdlib `sre_parse`/`tokenize`/pluggy
   内部，与项目代码无关；同一套件有时 rc=0（66 项全过）有时崩。清 `__pycache__` 只能缓解。
   → M2 的跑法：**按文件分批**（`for m in ...; do py -3.8 -m pytest tests/test_$m.py; done`），
   取每批自己的退出码，别接管道（管道会吞 rc）；大文件 `test_kb_schema.py` 最容易触发，
   必要时拆成两个文件。判据以分批 rc 为准，全量绿当加分项。
4. `git config core.autocrlf=true`（仓库级+全局）→ `.gitattributes` 的 `* text=auto eol=lf` 是对冲，
   `tests/test_eol_guard.py` 已守「任何文本文件出现 CR 即失败」+「不得移除 eol=lf」。
5. 我写的合成语料与数据 JSON 一律 LF；**JSON 字符串值内部不要用 ASCII 双引号**（用「」），
   M1 就踩过一次：整份 `gb50017.json` 因内层引号变成非法 JSON。
6. 尚未实测（需要时先 spike）：pip 是否被系统代理污染、PySide6 在 3.8 上的可解析最高版本、
   PyInstaller 对 3.12 的 modulegraph 稳定性。

## 六、关键命令速查

```bash
# 数据审计（M1 交付物，退出码 0=结构引用全通过，1=有问题，2=数据目录不可用）
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m sdc selfcheck
PYTHONPATH=src py -3.8 -X utf8 -m sdc selfcheck --json > selfcheck.json

# 合成语料：重生成 / 位级一致校验（改模板后用同 seed 整目录重生成再提交）
PYTHONPATH=src py -3.8 -X utf8 -m sdc synth --seed 20261006
PYTHONPATH=src py -3.8 -X utf8 -m sdc synth --seed 20261006 --check

# 测试：按文件分批取 rc（全量单进程会被本机崩溃打断）
PYTHONPATH=src py -3.8 -X utf8 -m pytest tests/test_kb_gate.py -q --tb=line
```

## 七、M2 DoD（逐项打勾，未达成写偏差说明）

- [ ] V1~V8 至少 V1/V2/V3 有明确结论：拿到正式文本并逐字核对，或写明「仍不可得」
- [ ] 5 个验算模块 `sdc run` 可用：已核对模块出逐步计算 + 依据条款；未核对模块**必须 blocked 且无数值**
- [ ] 门控失败路径测试齐（引用 located/pending 却出数值 = 测试红）
- [ ] 每个可用模块四件套测试：正例/反例/边界(0.95<ratio≤1.0)/非法输入
- [ ] `sdc bench --cases` 跑通：有 verified 算例则按容差对账；仍无来源则显式输出「分母 0，样本待补」
- [ ] `data/README.md` 与 plan/07 的 located→verified 升级逐项登记（渠道+日期+URL）
- [ ] 测试分批全绿；`sdc selfcheck` 保持 0 问题
- [ ] 回写 plan/00、plan/05 M2 行；写 HANDOFF-M3

## 八、禁止事项（M2 阶段）

- 不得为了「通过率有数字」而编造教材书名/例题号/规范数值——分母为 0 是诚实结果，编来源是事故
- 不得把 `located` 当 `verified` 用，或在引擎里绕过门控取 `values`
- 不得用记忆值、近似式或自行拟合补 φ 曲线、强度设计值、μ、P、构造限值（D11/K14）
- 不引入 LLM / 网络依赖 / numpy / scipy / faiss；不引第三方 docx 库到合成链路
- 不动 `.gitattributes` 的 `eol=lf`；不手改 `data/synth/`（改模板 → 固定 seed 重生成）
- 派子代理干活时要**限定它能写的文件**并在收尾时逐项 `git diff` 审读（M1 的越界教训）；
  抓取原文的缓存目录留在 `.tmp_verify/`（已 gitignore），**收尾不要删**，那是唯一的可重放证据
- 对外动作（push / 建仓 / tag / Release）未获用户确认不得执行
