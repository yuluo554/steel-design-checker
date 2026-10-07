# HANDOFF-M3（M2 公式引擎 → M3 文本核查 交接快照）

> 用法（新对话）：`读取 plan/HANDOFF-M3.md，继续完成任务`（本文件内一律相对路径）
> 落盘时间：2026-10-07　落盘者：M2 公式引擎对话
> 上一棒：[HANDOFF-M2.md](HANDOFF-M2.md)（已执行完毕，其 §七 DoD 的逐项结果见本文 §二）

## 一、M2 交付了什么（已验证的事实）

| 交付物 | 位置 | 状态 |
|---|---|---|
| 式体求值器 | `src/sdc/engine/expr.py` | ✅ AST 白名单遍历，禁 `eval`/属性/下标/链式比较；派生式 `x = …` 与验算式 `<=`/`>=` 两类，比值恒取「作用效应/抗力」 |
| 单位入口层 | `src/sdc/engine/units.py` | ✅ 内部一律 N、mm、MPa；力/力矩/长度/面积/惯性矩/应力量纲族齐全，未知单位直接判输入不可用；查表结果也在此换算 |
| 参数卡校验 | `src/sdc/engine/params.py` | ✅ 5 模块必填/可选槽位、输入词表、`group` 排列对象、承压型显式拒绝（扩展项 E）、**数据侧量禁止入参**（β_f/μ/P/φ/各强度设计值出现即 rc=2） |
| 查表 | `src/sdc/engine/tables.py` | ✅ `values` 形态 `{"axes":{槽位:值},"outputs":{符号:值}}`；group 精确匹配、linear 单数值轴显式线性插值、**超表界禁止外推**；只认 `verified`，且绕过编排层直接调用也拒 |
| 编排 | `src/sdc/engine/core.py` | ✅ 门控 → 派生式与查表**同一个不动点循环**求解（φ 表这类「轴值来自派生式」的情况才能通）→ 验算式 → 构造限值 → 结论 |
| `sdc run` | `src/sdc/cli.py`、`data/examples/` | ✅ 真实数据 ⇒ `blocked` + 逐项 `kind/id/status/reason`，**Result 里一个数值都没有**；夹具 verified ⇒ 逐步计算 + 依据条款 + 强条提示 + 免责声明。rc 0/1/2 |
| `sdc bench` | `src/sdc/bench.py` | ✅ 分母只含 verified 算例；无 verified 时显式输出「分母 0，样本待补」；blocked 算例记 `blocked_skip` 不静默通过；自校验样例单列不进分母 |
| JGJ 82-2011 入范围 | `data/{clauses,tables,formulas,symbols}/jgj82-2011.json` | ✅ 条款 19（18 located + 1 真空 pending）、表 2、公式 5、符号 4；全部 `located/pending`，verified 仍 0 |
| 门控补漏 | `src/sdc/kb/gate.py` | ✅ 构造/限值条款通过 `clause.formulas` **反向进入模块依赖集**（M1 的真实漏洞：构造依据只是 located 也能出数值） |
| schema 收紧 | `src/sdc/kb/schema.py` | ✅ verified 算例必须挂 `tolerance`；渠道白名单增 `合成夹具`（仅 tests 可用）；`selfcheck` 记录新增 `expect_input_error` |
| 合成 verified 夹具 | `tests/fixtures/kb/`（+ README.md） | ✅ 5 模块全 verified 的**虚构**数据集，用来兑现数值通路；数值刻意避开渠道转述值（β_f=1.20 不是 1.22、k=0.9 不是 0.85、φ 表 60 处 0.86 不是 0.85） |
| 测试 | `tests/test_engine_{expr,gate,modules,fixtures}.py`、`test_bench.py`、`test_run_cli.py`（+ M1 的 8 个） | ✅ 按文件分批全绿；真实数据侧 `sdc selfcheck` 0 问题 rc=0 |

**可演示物（两条，缺一不可）**

```bash
set PYTHONPATH=src
# 注意：`--data-dir` 是**全局参数**，必须写在子命令之前（写在后面 argparse 直接报 unrecognized）
# ① 纪律：引用未核对数据 ⇒ 拒算，且逐项说清缺什么
py -3.8 -X utf8 -m sdc run --module fillet_weld --case data/examples/A2-fillet-weld.json          # rc=1
# ② 能力：同一引擎换 verified 夹具就出逐步计算
py -3.8 -X utf8 -m sdc --data-dir tests/fixtures/kb run --case data/examples/A2-fillet-weld.json   # rc=0
py -3.8 -X utf8 -m sdc --data-dir tests/fixtures/kb bench                                           # rc=0，7/7
py -3.8 -X utf8 -m sdc bench                                                                        # rc=1，分母 0
```

## 二、M2 DoD 逐项结果（含偏差，未抹平）

| DoD（HANDOFF-M2 §七） | 结果 |
|---|---|
| V1~V8 至少 V1/V2/V3 有明确结论 | ⚠️ **结论与预期相反**：不是「仍不可得」，而是**已到手但档次不够**。表体/式体在渠道里是图片，已下载并双源逐格转录（附录 D φ 953 格两站一致 + D.0.5 公式反算 952/953 吻合）。是否可升 verified = 待用户拍板 T5。详见 07 §六 |
| 5 模块 `sdc run` 可用：已核对出逐步计算，未核对必须 blocked 且无数值 | ✅ 两条路都有：真实数据全 blocked（含「不出数值」的硬测试），已核对路径在夹具上出 steps/basis/warnings/limits |
| 门控失败路径测试齐 | ✅ 含三个陷阱用例：located 表带着 values、located 公式带着式体、未核对构造条款带着限值；另有绕过 `run_case` 直接调查表的用例 |
| 每模块四件套（正/反/边界/非法） | ✅ 5×4 全在夹具上；期望比值人工独立算出（见 `_helpers.py` 注释），不是引擎回填 |
| `sdc bench --cases` 跑通；无来源则显式「分母 0，样本待补」 | ✅ 两种输出都实测过 |
| `data/README.md` 与 plan/07 的 located→verified 升级逐项登记 | ⚠️ 本轮**没有任何升级**，但渠道、日期、URL、缓存 sha1 已逐项登记，升级动作留给 T5 拍板后一次性做 |
| 测试分批全绿；`sdc selfcheck` 0 问题 | ✅ |
| 回写 plan/00、05 M2 行；写 HANDOFF-M3 | ✅ 本文件 |

**M2 期间的两处返工（如实记）**

1. M1 留下的 `data/selfcheck/engine_samples.json` 不合 M2 参数卡 schema（力写在顶层、缺必填槽位），
   bench 一跑就 9 个 input_error。已按 schema 重写 inputs 并保留断言语义，其中一条断言改了口径：
   「`surface_treatment` 未核对前拒绝枚举校验通过」→ 现为「输入词表只拦拼写，词表放行≠数值可用，
   模块仍必须 blocked」。理由：把处理状态名当规范事实来拒绝，会让参数卡无法构造，
   而真正的纪律（不给数值）在门控那一层。
2. `plan/07 §一` 与 `data/README.md` 曾称「证据缓存在仓库外目录」——不成立。本轮改为
   缓存固定落 `.tmp_verify/m2/`（gitignore，收尾不删），并把「缓存在仓外」的表述作废。

## 三、唯一悬而未决的用户决策：T5（渠道档次）

`data/` 现状：条款 84（62 located / 22 pending）、表 12、公式 14、符号 36，**verified = 0**。
到手但没入库的东西（全部在 `.tmp_verify/m2/`，逐格转录见 `v3v4/tables_text.md`）：

- 附录 D 表 D.0.1~D.0.4 的 φ（953 格，两站点图片逐格一致，且与 D.0.5 公式自洽到 ±0.0005）
- 表 D.0.5 的 α1~α3 + D.0.5 公式全文
- 表 7.2.1-1/7.2.1-2 截面分类、表 7.4.6/7.4.7 容许长细比（双源逐格一致）
- 表 4.4.1/4.4.5/4.4.6（cabr-fire 图片 + xycost 文字转录，后者二手）
- 表 11.4.2-1（μ）/11.4.2-2（P）：只有单渠道图片，无文字层

三个选项（06 T5）：**①** 双镜像一致即可升 verified；**②** 必须正式文本（纸质/正版 PDF），镜像只配 located；
**③（推荐）分级**——附录 D 这种「双源一致 + 原文公式反算自洽」的升 verified，单一镜像来源的（4.4.1/4.4.5/4.4.6/11.4.2）保持 located。

拍板后 M3 开工前 30 分钟就能把 φ/分类/长细比落进 `data/tables/` 并让 A5 真正出数值；
不拍板则 M3/M4 继续「全 blocked」形态跑基准，通过率分母恒为 0。

已知残差（升 verified 前必须处理）：a 类 λ/εk=15 单格两图读 0.990、公式算 0.98933；
生成常数 k 取 0.0107510（E=206000）只有 797/953 吻合，微调至 0.0107563 才 952/953（等价 E≈205800 或 π=3.14）；
表 7.2.1 的厚度分界图中作 **t＜40 / t≥40**，与 07 §二.3 记的 **t≤40 / t>40** 冲突。
（另：子代理 `v3v4/fit_k.py` 的常数反算只是校验手段，按 D11/K14 **禁止**把拟合值写进 `data/`。）

## 四、既定口径清单（改了会打挂基准，动手前先对照）

K1~K16 见 HANDOFF-M2 §四，**全部未变**。M2 新增：

| # | 口径 | 位置 |
|---|---|---|
| K17 | 式体必须机器可解析形式；派生式 `x = …`（左端单符号），验算式只允许 `<=`/`>=`；**比值恒为作用效应/抗力**（`>=` 时左右互换）；链式比较/严格不等/未知函数/下标/属性一律判数据不合法 | `engine/expr.py` / 06 D18① |
| K18 | 数值表 `values` 形态 `{"axes":{槽位名:值},"outputs":{符号名:值}}`；`linear` 单数值轴 `{"x":…,"outputs":…}`，超界失败不外推；表的 `unit` 声明本体单位，换算只在入口层 | `engine/tables.py` / 06 D18② |
| K19 | 数据侧量（β_f、μ、P、φ、各强度设计值）**禁止**由参数卡传入；卡里出现即 rc=2 | `engine/params.py::FORBIDDEN_SLOTS` / 06 D18④ |
| K20 | `status=verified` 的算例必须登记 `tolerance`，`expected` 里的数值字段没有对应容差 ⇒ 判失败，不给默认容差 | `kb/schema.py`、`bench.py` / 06 D18⑤ |
| K21 | 模块依赖集 = 公式(applies_to) → 条款 → 符号 → 条款.tables，**加上** `clause.formulas` 反向命中的条款（构造依据也进门控） | `kb/gate.py::module_requirements` / 06 D18③ |
| K22 | 结论判定顺序：`ratio > 1+1e-3` 或任一 `limits` 不过 ⇒ `unsatisfied`；`ratio > 0.95` ⇒ `need_adjust`；否则 `satisfied`。ratio=1.0 属 need_adjust，容差内（≤1.001）不判超限 | `engine/core.py`（K2/K3 的机器化，未改语义） |
| K23 | Result 新增 `notes`（留痕位）与 `basis[].mandatory`；免责声明文案单源于 `engine/core.py::DISCLAIMER` | 04 §一 的 M2 增补 |
| K24 | 焊缝质量等级输入词表统一为 **`一级/二级/三级`**（04 原写 `一/二/三`） | `engine/params.py` |
| K25 | 引擎数值通路的测试基准 = `tests/fixtures/kb/`（合成 verified，渠道 `合成夹具`）；`data/` 里出现该渠道或 `FX-`/`F-FX-` id 即测试失败 | `tests/test_engine_fixtures.py` / 06 D17 |

## 五、M3 待办（按顺序，每步可单独演示）

1. `sdc parse --doc x.docx`：docx → 纯文本 → 槽位抽取（正则 + 槽位 + 范围校验，白名单外丢弃）→ 参数卡 IR。
   类目隔离（`only_if_text` 关键词）从第一行代码就在，别等误报出现再补。
2. `sdc check --doc x.docx`：规则引擎三级判定（`abnormal/suspicious/pass`），`data/rules/description_rules.json`
   按 04 §四 的闸门表实现——**依据 status=located 的 limit/construct 规则只能出 suspicious**（K5 硬断言）。
   规则表要挂依据条款，而 `data/rules/` 目录还不存在（M1 只做了条款/表/公式/符号）。
3. 用 `data/synth/` 的 24 份语料做配对评测：字段级 P/R/F1 + 检出率/误报率按 K4 对账（注入项 `primary`、
   连带结论 `also_expect`，分母只含 verified 规则）。
4. GB 55006 检查单引擎（`sdc checklist`）：条目分母 ≈18 条核心（07 §二.5）；**T4 全章 vs 四章未拍板**，M3 前问一次。
   强条联动清单按 7 条（K16），并处理「50017 强条已被 55006 废止」这条关系（V7：条号已多源、映射仍单源）。
5. 若 T5 拍板升 verified：把 φ/分类/长细比/表 4.4.x 落进 `data/tables/`，`sdc bench` 才有非 0 分母；
   同时补 `data/cases/`（真值算例仍 0 例，`data/cases/README.md` 写了三条解除阻塞通道）。
6. 回写 plan/00 进度表与 plan/05 的 M3 行，写 HANDOFF-M4。

## 六、本机环境事实（M2 新增，M3 直接照此跑）

1. HANDOFF-M2 §五 全部仍然成立：`py -3.8` + `PYTHONPATH=src`，测试**按文件分批取 rc**，别接管道。
2. 新增：`ast.parse`（引擎式体解析）在本机稳定，未发现崩溃；但 `re` 走 `sre_parse` 是已知崩溃点，
   **引擎层刻意不用正则**。M3 的解析层必须用正则，届时把「解析」与「判定」分成两个进程/两次运行，
   别让一次崩溃连带打挂整套基准。
3. 长任务的随机中断（工具执行被 interrupted）在本轮出现过；对策同 `crash-loop-rescue`：
   每步产物先落盘再收尾，断跑后从文件状态续接。
4. 子代理纪律**本轮有效**：三个查证 agent 各只允许写 `.tmp_verify/m2/<批次>/`，收尾 `git status`
   逐文件核对，确认仓库文件零越界、缓存未删。M3 继续照此派活（M1 的教训见 HANDOFF-M2 §二.2）。

## 七、禁止事项（M3 阶段）

- 不得为了「通过率有数字」编造教材书名/例题号/规范数值；分母为 0 是诚实结果，编来源是事故
- 不得把 `located` 当 `verified` 用，或在引擎里绕过门控取 `values`；T5 未拍板前 `data/` 一律保持 located
- 不得用记忆值、近似式或自行拟合补 φ 曲线、强度设计值、μ、P、构造限值（D11/K14）
- 不得把 `tests/fixtures/kb/` 的任何数值或式体复制进 `data/`（K25 有测试，但复制本身就是事故）
- 不引入 LLM / 网络依赖 / numpy / scipy / faiss；不引第三方 docx 库到合成链路
- 不动 `.gitattributes` 的 `eol=lf`；不手改 `data/synth/`（改模板 → 固定 seed 重生成）
- 不删 `.tmp_verify/`（唯一可重放的证据链）；派子代理时限定可写文件并在收尾逐项 `git diff` 审读
- 对外动作（push / 建仓 / tag / Release）未获用户确认不得执行
