# HANDOFF-M1（阶段 0 → M1 数据先行 交接快照）

> 用法（新对话）：`读取 plan/HANDOFF-M1.md，继续完成任务`（本文件内一律用相对路径，绝对路径只出现在会话启动命令里）
> 落盘时间：2026-10-06　落盘者：阶段 0 收尾对话

## 一、当前进度

**阶段 0（plan 文档）已完成**，全部在 `plan/`：

| 文件 | 内容 | 备注 |
|---|---|---|
| 00-README总览 | 索引 + 里程碑 + 当前进度表 | 决策表已迁到 06，本文件不留副本 |
| 01-题目详细定义 | 模拟赛题全文（定稿） | 边界与非目标在 §六 |
| 02-需求解读 | 痛点转译 P1-P7、FR（A 验算/B 条款/C 核查/D 交付 + E 扩展）、边界、风险 R1-R6 | FR 每条都写了验收方式 |
| 03-架构与技术选型 | 分层架构、条款-公式-符号表引擎契约、status 门控、确定性纪律、目录骨架、CLI 命令面、GUI/打包方案 | 选型表里的 PySide6 版本上限是**待复核**假设 |
| 04-模块详设 | Result 契约、5 模块参数卡槽位、条款/公式/符号/规则/检查单 schema、测试矩阵 | **所有条号是占位**，M1 核对后回填 |
| 05-数据计划与里程碑 | 四类数据资产、9 张数值表清单、算例真值库 schema、合成生成器设计、8 项评测门槛、M1-M6 + 每周可演示 | 示例 JSON 里的书名/例题号是占位，不入台账 |
| 06-决策记录 | D01-D13 已定 + T4 未拍板（不阻塞 M1）+ 口径变更日志 | 本轮已按用户拍板回写 T1/T2/T3/T5 与阶段 0 收束方式 |

**其他已落地物**：`.gitattributes`（`* text=auto eol=lf` + 二进制标记，对冲本机 `core.autocrlf=true`）、`data/README.md`（台账骨架，尚未登记任何数据）、`code/`（空目录，不入仓）。

**本轮拍板结论（M1 必须照此执行，勿重新讨论）**：
- **D10** 真值分层：来源不可确证的样例不进通过率分母（落 `data/selfcheck/`）
- **D11** φ 双源交叉核对，单源须标注，两源皆无则该模块 `blocked`
- **D12** 锁 Python 3.8 开发 + CI 3.8/3.12 双矩阵，代码必须 3.8 兼容写法
- **D13** 阶段 0 止于文档提交，M1 在新对话按本快照续接

**工作区状态**：`.gitattributes`、`plan/02~06`、`plan/HANDOFF-M1.md` 为本轮新增（提交见 git log），`code/` 空目录不入仓。

## 二、条文查证结果（本快照落盘时的状态）

⚠️ **待补**：本轮派出的查证子代理（GB 50017-2017 条号定位 + GB 55006-2021 章节清单）结论需在收到后写入本节，并据此回填 04 的条号槽位与 05 的数值表出处。

已核对（题目阶段，见 `data/README.md`）：
- GB 50017-2017 存在性、2018-07-01 实施、替代 GB 50017-2003 ✅
- GB 55006-2021 全文强制、2022-01-01 实施 ✅
- 强制性条文清单（4.3.2、4.4.1～4.4.6、18.3.3）：条号在案，**主题与原文关键句待逐条核对**

未核对（不得进入计算）：全部强度设计值表、φ 曲线/表、μ 与 P、构造限值、焊缝质量分级条文、各公式条号。

## 三、M1 待办（按顺序，每步可单独演示）

1. **仓库骨架**：`pyproject.toml`（extras：`dev`/`gui`/`report`/`pdf`/`pkg`，Python≥3.8，pin 写法见 §五坑 3）、`src/sdc/`（kb/engine/parse/rules/report/cli/gui）、`tests/`、`scripts/`、`data/{clauses,tables,symbols,cases,synth}/`
2. **数据加载层**：JSON schema 校验器（引用完整性：formula→clause、table→clause 不得悬空）+ `status` 门控 + `sdc selfcheck` 输出 pending 看板
3. **条款库第一批入库**：按 05 §三 的 9 张表逐张建条目（先建 `pending`，挂 `verified_by` 后升 `verified`）；形式 = 要点 + 出处（不整条转载正文）
4. **算例真值库第一批**：≥15 例，每例必须有书名+版次+例题号；来源不可确证的 → 放 `data/selfcheck/` 做自校验样例，不参与通过率
5. **合成生成器 v0**：段落模板 + 槽位真值 JSON + 3 类注入（焊缝等级缺标注 / 牌号前后矛盾 / 螺栓等级不匹配）；splitmix64 固定 seed；两次生成逐字节一致 + CR 守门测试
6. **测试**：schema 校验、门控（pending 必 blocked）、生成器位级一致、`.gitattributes` 生效（fixtures 出现 CR 即失败）
7. **台账登记**：`data/README.md` 每份数据来源+许可+status；`data_fingerprint` 计算口径写进注释
8. 回写 plan/00 进度表 + plan/05 里程碑 DoD ✅，写 HANDOFF-M2

## 四、既定口径清单（改了会打挂基准，动手前先对照）

| # | 口径 | 位置 |
|---|---|---|
| K1 | 单位制：内力 N、长度 mm、应力 MPa=N/mm²，换算只在入口适配层，比值无量纲 | 04 §三 |
| K2 | `conclusion` 判定：`ratio≤1.0` 满足；`0.95<ratio≤1.0` → `need_adjust`（不硬判不符合）；引用 pending → `blocked` 且**不出数值** | 04 §一 |
| K3 | 内部比较容差 1e-3（与真值比对容差分离，后者逐算例登记） | 04 §一 / 05 §四 |
| K4 | 真值语义：注入项记 `primary` + 连带结论记 `also_expect`，评测按"文档全部非 pass 集合"对账 | 05 §五 |
| K5 | 三级判定 `abnormal / suspicious / pass`；**规则 status=pending 时只能出 suspicious，不得出 abnormal**（硬断言） | 04 §四 |
| K6 | 通过率分母只含 `verified` 算例；pending 算例分列显示，不得静默通过 | 05 §四 |
| K7 | 无来源（书名+版次+例题号）的数值不得作真值（D07） | 05 §四 |
| K8 | 确定性：禁 stdlib `random`（自研 splitmix64）、禁 set 迭代序（`sorted`）、产物无时间戳、docx `docProps` 元数据占位符化 | 03 §三.4 |
| K9 | CLI 退出码 0 完成 / 1 降级完成 / 2 输入不可用；定稿后锁进 CLI 契约测试 | 03 §五 |
| K10 | GUI 只消费 CLI/引擎 API，不得出现第二套判定逻辑；`QT_QPA_PLATFORM=offscreen` 必须在首次 import PySide6 **之前**设置 | 03 §六 |
| K11 | `find_data_dir` 优先级：显式 > 环境变量 > `sys._MEIPASS/data` > exe 目录 `_internal/data` > CWD 上溯（分支测试锁死） | 03 §七 |
| K12 | 数据指纹 `data_fingerprint = sha256(data/clauses + data/tables 规范化拼接)`，算法变更=口径变更，需登记 §六 | 04 §一 |
| K13 | 代码必须 **Python 3.8 兼容**：禁 `X \| Y` 联合类型语法、`dict \| dict`、`str.removeprefix/removesuffix`、`functools.cache`、`match` 语句、`zoneinfo` 等 3.9+ 语法/API；CI 双矩阵是这道约束的守门（D12） | 06 D12 |
| K14 | φ 数值必须双源（附录离散表 + 原文拟合公式）交叉核对同值才 `verified`；单源入库要在 `notes` 写"单源，未见交叉印证"；两源皆无 → A5 模块 `blocked`，禁止用记忆值或自行拟合兜底（D11） | 05 §三 / 06 D11 |

## 五、本机环境事实（本轮实测，只写实测过的）

1. `py -0p` 实测只有两个解释器：**3.8-64**（`…\AppData\Local\Programs\Python\Python38`，版本 `3.8.8 (MSC v.1928 64bit)`，`py` 默认就是它）与 **3.12-64**。→ D12 的 3.8 基线本机可用，无需额外安装。
2. **`git config core.autocrlf = true`（仓库级与全局均 true）** → 全新 clone 会把 LF 写成 CRLF，字节冻结基准必挂。已用 `.gitattributes`（`* text=auto eol=lf`）对冲；M1 必须配"fixtures 出现 CR 即失败"守门测试，且发布前要跑一次**本机全新 clone 验证**。
3. 现有 `plan/*.md`、`data/README.md`、`.gitignore` 实测全为 LF（无历史 CRLF 债）。
4. PATH 上的 `python` 解析到 `…\AppData\Local\Microsoft\WindowsApps\python`（商店占位符，`python -V` 无有效输出），`where python` 还列出 `…\AppData\Local\Python\bin\python.exe` 与 `Python312\python.exe` → **本项目命令一律 `py -3.8 -X utf8`（或激活后的 venv `python -m …`）**，脚本内不假设 `python` 指向哪个解释器。
5. 尚未实测（M1/M5 需要时先 spike 再写死）：pip 是否被系统代理污染、PySide6 在本机 3.8 上可解析的最高版本、PyInstaller 对 3.12 的 modulegraph 稳定性。

## 六、关键命令速查（M1 起步用，路径按当前仓库）

```bash
# 建 venv（3.8 基线；若 ensurepip 崩 → --without-pip + 手动 ensurepip）
py -3.8 -X utf8 -m venv .venv
.venv/Scripts/python.exe -m pip install -U pip setuptools wheel   # venv 内用 python -m pip，别用 py
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -m pip install -e .[dev]

# 跑测试（禁写 pyc；失败先清 __pycache__ 再重跑一轮，随机崩溃不等于真 bug）
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -m pytest -q

# 自检看板（M1 交付物）
.venv/Scripts/python.exe -m sdc selfcheck

# 合成语料重新生成（固定 seed，必须位级一致）
.venv/Scripts/python.exe -m sdc synth --seed 20261006
```

（pip 若被系统代理污染：`NO_PROXY="*" no_proxy="*" ... -i https://pypi.tuna.tsinghua.edu.cn/simple`；此为方法论记录的本机家族坑，**本项目尚未实测**，遇到再按此处理。）

## 七、M1 DoD（逐项打勾，未达成写偏差说明）

- [ ] `data/clauses/` ≥ 60 条，每条含 `id/standard/clause_no/kind/status/verified_by/gist`，未核对项 status=pending 且**未被任何计算路径引用**
- [ ] 9 张数值表条目建好，`verified` 的每张挂渠道+日期+URL；查不到的登记进"待核验清单"
- [ ] 算例真值库 ≥ 15 例，逐例有书名+版次+例题号；无来源样例已降级且不计入通过率
- [ ] 合成生成器 v0：≥ 20 份 docx + 真值 JSON + 注入清单，两次运行**逐字节一致**（守门测试绿）
- [ ] `sdc selfcheck` 能输出 pending 看板 + 引用完整性检查 + 指纹
- [ ] 测试全绿：schema、门控（pending→blocked）、生成器位级一致、CR 守门
- [ ] `data/README.md` 台账登记全部数据资产（来源+许可+status）
- [ ] plan/00 进度表与 plan/05 M1 行回写 ✅；04 条号槽位按查证结果回填
- [ ] 写 HANDOFF-M2 并落盘

## 八、禁止事项（本阶段）

- 不得把未核对的条号/数值写进 `data/` 的 `verified` 项，或以确定语气写进文档结论（04/05 的占位符必须保持"待回填"标注）
- 不引入 LLM / 网络依赖；不引 numpy/scipy/faiss
- 不得为了"模块数好看"绕过 status 门控（门控被绕过 = 项目含金量归零）
- 不动 `.gitattributes` 的 `eol=lf`（口径 K8 的一部分）
- 对外动作（push/建仓/tag）未获用户确认不得执行
