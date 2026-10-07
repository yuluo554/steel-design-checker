# HANDOFF-M4（M3 文本核查 → M4 内置基准 + 报告导出 交接快照）

> 用法（新对话）：`读取 plan/HANDOFF-M4.md，继续完成任务`（本文件内一律相对路径）
> 落盘时间：2026-10-07　落盘者：M3 文本核查对话
> 上一棒：[HANDOFF-M3.md](HANDOFF-M3.md)（已执行完毕；§五 待办 1~4 与 6 已做，第 5 条 T5 落数据被本轮查证**主动暂缓**，见本文 §三）

## 一、M3 交付了什么（已验证的事实）

| 交付物 | 位置 | 状态 |
|---|---|---|
| docx/文本读取 | `src/sdc/parse/textio.py` | ✅ 标准库 `zipfile`+`ElementTree` 直读 OOXML（表行按 `\|` 拼接成段），`.txt/.md` 带 gb18030 回退与解压体积上限；**不引 python-docx**（引它只为读文本，却把打包面与依赖风险带进来） |
| 槽位抽取 | `src/sdc/parse/slots.py` | ✅ 9 槽位 + 类目隔离（`ONLY_IF_TEXT`）+ 取值域检查 + **白名单外丢弃但留痕**；词表复用 `engine.params`，解析侧与引擎侧不会各长一套枚举 |
| 参数卡 IR | `src/sdc/parse/ir.py` | ✅ 排序键、无时间戳、同文档同解析器版本 ⇒ 字节一致；`validate_ir` 拒手改（段落数与 `paragraph_count` 不符、未知槽位、`index` 与位置不符都拒收）；设计说明天然凑不出可运行卡 ⇒ 交 `card_slots` + `card_gaps`，不假装拼得出一张卡 |
| 三级判定引擎 | `src/sdc/rules/{gate,engine,render}.py` | ✅ 闸门矩阵单点决定等级（K30）；条件/断言是闭集且**判定层不 import `re`**（K26）；`scope: paragraph` 支持段落级作用域；同规则多处命中合成一条 finding（防重复检出打挂误报口径） |
| 规则表 | `data/rules/description_rules.json`（10 条） | ✅ 材料/焊接/螺栓/构造/防护 5 组齐；每条挂依据条款，`verified_by` 与首条依据同档；**未核对阈值一律 `null`** ⇒ 引擎记「不启用」 |
| 检查单引擎 | `src/sdc/checklist.py`、`data/checklist/gb55006.json`（107 条） | ✅ 按 **T4 拍板＝全 8 章要点化**：8 章 24 节 107 条，9 条挂自动初判，其余显式 `待人工确认`；`chapters_missing` 字段专门用来把"没覆盖的章"说出来 |
| GB 55006 条款库 | `data/clauses/gb55006.json` 30 → **107 条** | ✅ 全 8 章条号 + 一句话要点 + 义务词，**107/107 两个独立主机文字层逐字命中**（`.tmp_verify/m3/gb55006-full/_crosscheck.tsv`）；本标准"全部条文必须严格执行"（前言三主机逐字）⇒ 107 条全部 `mandatory: true` |
| `sdc parse` / `check` / `checklist` | `src/sdc/cli.py` | ✅ 单文档与批量两种模式；退出码 0/1/2 见 K29；`--json` 全部排序键无时间戳 |
| `sdc bench --parse` / `--audit` | `src/sdc/bench.py` | ✅ 字段级 P/R/F1 与非 pass 集合对账；**只吃落盘 IR**，缺 `--ir-dir` 直接 rc=2，绝不在评测进程里现拉正则 |
| 规则/检查单 schema | `src/sdc/kb/schema.py`、`kb/loader.py` | ✅ 新增 `rule`/`checklist` 两个 kind；条件与断言算子闭集校验；跨 kind 同 id 不再误判重复（检查单条目 id 天然等于条款 id） |
| verified 档夹具 | `tests/fixtures/rules_kb/`（+ README） | ✅ 3 条虚构条款 + 4 条虚构规则 + 2 份 .txt 文档；兑现"规则升 verified 后能出 abnormal"和"规则自称 verified 但依据 located ⇒ 仍被压到 suspicious"这两条真实数据永远跑不到的路 |
| 测试 | `tests/test_parse.py`(18) `test_rules.py`(18) `test_text_cli.py`(12) + 既有 14 个文件 | ✅ 17 个文件**按文件分批取 rc 全 0**；真实数据侧 `sdc selfcheck` 0 问题 rc=0 |

**可演示物（四条，缺一不可；`--data-dir` 是全局参数，必须写在子命令之前）**

```bash
set PYTHONPATH=src
# ① 解析：整批语料 → IR（正则只在这一层）
py -3.8 -X utf8 -m sdc parse --dir data/synth/docx --out-dir .tmp_parse/ir
# ② 核查：牌号前后矛盾的那份 ⇒ abnormal + 强条提示 + 未启用规则清单
py -3.8 -X utf8 -m sdc check --ir .tmp_parse/ir/SYNTH-0013.ir.json      # rc=1
py -3.8 -X utf8 -m sdc check --ir .tmp_parse/ir/SYNTH-0000.ir.json      # rc=0，且明说"不等于合规"
# ③ 配对评测
py -3.8 -X utf8 -m sdc bench --parse  --ir-dir .tmp_parse/ir            # rc=0，F1 1.0000
py -3.8 -X utf8 -m sdc bench --audit  --ir-dir .tmp_parse/ir            # rc=0，12/12 检出，误报 0
# ④ 检查单：接 IR 才有初判；不接 IR ⇒ 全部待人工确认且 rc=1（降级完成）
py -3.8 -X utf8 -m sdc checklist --ir .tmp_parse/ir/SYNTH-0012.ir.json  # rc=0
py -3.8 -X utf8 -m sdc checklist                                       # rc=1
```

## 二、M3 DoD 逐项结果（含偏差，未抹平）

| DoD（plan/05 §七 M3 行 + HANDOFF-M3 §五） | 结果 |
|---|---|
| 解析 F1 ≥0.95 | ✅ **1.0000**（24 份语料、206 个 (槽位,取值) 事实，FP 0 / FN 0）。真值里的 `grade_alt` 按别名折算成"同槽位第二个取值"（`bench.TRUTH_SLOT_ALIASES`），语料本体一字节没动 |
| 误报 0（硬门） | ✅ 12 份干净语料 + 12 份注入语料，`非注入项被判非 pass = 0 处` |
| 每条 finding 挂条款与原文位置 | ✅ `clause_ids` + `basis`（条款=档位）+ `paras` + `evidence[].text`（截断 160 字） |
| `sdc check --doc` 出异常清单 | ⚠️ 形态改为 **`parse` → `check --ir` 两条命令**（K26，HANDOFF-M3 §六.2 要求解析与判定分进程）。`--doc` 一步到位的做法被否，理由是本机正则崩溃点会连带打挂整套评测 |
| `sdc checklist` 出符合性清单 | ✅ 107 条全 8 章（T4 拍板）；自动初判只有 9 条——**这不是偷懒**：剩下 98 条写不出可靠的"文档侧写没写"判据，硬挂就是假判 |
| 规则按 04 §四 闸门表实现，located 的 limit/construct 只能 suspicious | ✅ 矩阵单点（`rules/gate.py`）+ 三条硬测试；同时把 04 原稿的"规则自带 `level_rules`"**否掉**（见 K30），并把"pending 的 limit 降级成 suspicious"改成"**不启用**"（理由见 K31） |
| 用 `data/synth/` 做配对评测（K4 语义） | ✅ primary 命中 + `also_expect` 计入非 pass 集合、连带结论不算误报 |
| T5 拍板后把 φ/分类/长细比落进 `data/tables/` | ❌ **本轮主动不做**：查证把前提查坏了（§三），已重拍为"先补第三路证据再定档" |
| 回写 plan/00、05、06、07；写 HANDOFF-M4 | ✅ 本文件；07 新增 §七，06 新增 D19/D20/D21 + 6 行口径变更日志，04 改 2 处，05 改 4 处，data/README 台账同步 |

**M3 期间查出来的三件"上一轮记错了"（都已在 07 §七 逐字留证）**

1. **两镜像站不是两个来源**：`cabr-fire` 与 `建标库` 的表体图片解码后**像素完全相同**（`ImageChops` maxdiff=0，覆盖 D.0.1~D.0.4、D.0.5 α、7.2.1-1/-2、7.4.6、7.4.7）。M2 记的"双镜像逐格一致"只等于**一次读图**；a 类格的误读正是这么漏掉的。
2. **附录 D a 类 λ/εk=15 是 0.989 不是 0.990**：原书 OCR 该格 0.989；把 M2 的两张原图同区域放大 8 倍重读也是 0.989；D.0.5 公式给 0.98934。⇒ M2 的 953 格转录只有这一格错，其余 952 格与 OCR 一致。
3. **φ↔公式"952/953 自洽"不成立**：按官方写法 `k=(1/π)√(235/206000)=0.0107510`，3 位小数同点同值只有 **793/953**（a45/b49/c43/d23 处，λ/εk≥33 成片偏差，低 λ 段基本吻合）；把常数微调到 0.0107563 才有 948/953。⇒ 病灶更像**式体或 α 的读法**（D.0.5-3 根号内表达式图片版与 OCR 版本就不一致），不是表体。重放命令：`py -3.8 .tmp_verify/m3/residual/crosscheck_phi.py`。

另两处更正：表 7.2.1 分界是 **t＜40 / t≥40**（t=40 落 7.2.1-**2**，原记 t≤40/t>40 作废）；V7 的"4.3.2 由 55006 3.0.2 承接"这半句**唯一渠道本轮 11 个载体都复现不出来** ⇒ `data/clauses` 两条记录都改成了"废止条号多源已证 / 映射未核实"两截表述。

## 三、定档已完成，还剩一件真待办

1. **附录 D 已定档落地**（06 D22/D23：用户拍板 D11 的「同点同值」容差取 **±0.001**）。
   第三路证据已回来（`.tmp_verify/m3/phi-third-source/`），结论与落库如下：
   - **升 verified**：条款 `D.0.1~D.0.5`（5 条）、表 `T-buckling-curve`（**953 格，二维：
     `section_class` × `lambda_over_eps_k`**）、新表 `T-buckling-alpha`（α₁~α₃ 六行）、符号 `phi`；
     渠道白名单新增「**电子版PDF文字层**」（出版社电子版 PDF 的**矢量文字层**，不是扫描图 OCR）。
   - **不入库**：a 类 λ/εk=250=0.130（只在 PDF 文字层，页面渲染图上被底线压住 ⇒ 单源隐藏/串版内容）；
     拟合常数 `k≈0.0107563`（V3b：官方生成常数**未取到**，D11/K14 禁止当规范事实）。
   - **`F-D.0.5-1` 故意保持 pending**（D23）：式体文字三源一致并已写进 `notes`，但现行 AST 白名单
     没有条件分支，两支公式（λn≤0.215 与否则式）都指派生目标 `phi` ⇒ 落 verified 后依赖一闭合，
     引擎在求解阶段必抛 `EngineError`。**要先把「分段 / 按条件选式」做进引擎才能升它**（§五 第 0 条）。
   - **仍未升**：表 4.4.1 / 4.4.5 / 4.4.6 / 11.4.2-1 / 11.4.2-2 / 7.4.6 / 7.4.7 / 7.2.1-1-2
     —— 只剩同一批底图这一路，按 T5③ 原意保持 located、`values: []`。
   - **净效果**：`sdc selfcheck` 的 verified 从 0 变成 clause 5 / table 2 / symbol 1；
     A5 阻塞项缩到 6 项（F-7.2.1-1、F-D.0.5-1、条款 7.2.1、符号 A/f/lambda），
     **没有任何模块开始出数值**（f 来自仍 located 的表 4.4.1）；`data/cases/` 仍 0 例 ⇒ 算例分母仍 0。
2. **`data/cases/` 真值仍 0 例**（M1 起就挂着）。分母为 0 时 `sdc bench` 必须继续显式输出
   「分母 0，样本待补」；解除通道见 `data/cases/README.md`（教材/手册例题需 书名+版次+例题号 齐全）。

> **两个会话在改同一个工作区**（重要）：本轮收尾时 M4 的对话已经动过
> `src/sdc/report/`、`src/sdc/suite.py`、`src/sdc/selfcheck.py`（推进看板）、`tests/test_report.py`、
> `tests/test_suite.py`、`tests/test_eol_guard.py`、`src/sdc/synth/docx.py`、`README.md`，
> 也碰过 `cli.py`/`bench.py`/`rules/engine.py`/`parse/`/`plan/05`。谁都不许假设对方没改：
> 提交前 `git status` 全量复核，**别在对方写入中途 commit**。
> 本轮定档已知会打挂他们那边的一处断言：`tests/test_selfcheck.py::test_repo_progress_counts_and_queue_shape`
> 里的 `progress["clause"]["verified"] == 0` —— 现在应是 **5**，`table verified` 是 **2**。
## 四、既定口径清单（改了会打挂基准，动手前先对照）

K1~K16 见 HANDOFF-M2 §四，K17~K25 见 HANDOFF-M3 §四，**全部未变**。M3 新增：

| # | 口径 | 位置 |
|---|---|---|
| K26 | **解析层与判定层分进程**：正则只在 `sdc parse` 用，`sdc rules`/`checklist`/`bench --parse/--audit` 一律不 import `re`，两层只通过落盘 IR 交接 | `parse/` vs `rules/`、`bench.run_audit_eval` |
| K27 | docx 用标准库直读（`.docx/.txt/.md`），**不引第三方 docx 库**；PDF 属扩展项，未支持就明确报错 | `parse/textio.py` |
| K28 | 类目隔离有**两层**：槽位级 `ONLY_IF_TEXT`（段落不含该主题用词，抽取式不参与）+ 规则级 `gate_keywords`（文档没这个主题 ⇒ 规则"未启用"，不算漏检也不算误报） | `parse/slots.py`、`rules/engine._rule_gate_hit` |
| K29 | 文本侧命令退出码：`parse` 0/1/2（部分文档不可读=1，全部不可读=2）；`check` 0=无非 pass 项、1=有可疑或异常（等级差异看报告不看码）、2=文档/IR/数据不可用；`checklist` 的 1 另含"没接 IR"与"章节未覆盖齐"；`bench --parse/--audit` 缺 `--ir-dir`=2 | `cli.py` |
| K30 | **规则文件不得自带等级**（无 `level_rules` 字段）：等级由 `rules/gate.py` 的矩阵按 `check_type × 有效档位` 单点决定，有效档位 = `min(规则 status, 各依据条款 status)`；`ambiguous` 一律 suspicious | `rules/gate.py`、`kb/schema.py::SPEC["rule"]` |
| K31 | 未核对的阈值一律 `null`（`assert.min`/`assert.bound`），判定层记「**规则不启用**」而不是降级成 suspicious；反向地，`status=verified` 的规则必须给出非空阈值。schema 双向卡死 | `kb/schema.py::_check_rule`、`rules/engine.judge_assert` |
| K32 | `presence` = 列出的槽位**全部**要写明；`cross_param` = 备选信息**至少给一项**；规则可声明 `scope: paragraph`（主受力段没写连接形式，不能被别处的"摩擦面"补上依据）；同规则多处命中合成**一条** finding | `rules/engine.judge_assert`、`run_rules` |
| K33 | 抽取"白名单外丢弃但留痕"：不在输入词表/数值域的取值不进 `card_slots`，但进 `dropped`；同义写法只做**完全等值**归一（`喷砂后涂富锌漆` ≠ `涂富锌漆后喷砂`，绝不归一）；`mu` 等数据侧量永不进卡（K19 的解析侧延伸） | `parse/slots.normalize_to_card_slots` |
| K34 | 评测对账：语料真值按 **(槽位, 取值) 事实集** 比，`grade_alt` 经 `TRUTH_SLOT_ALIASES` 折算成同槽位第二取值；"作用域限定的等级表述"（"其余焊缝不低于三级"）不抽进主槽位，否则会凭空造出前后矛盾 | `bench.py`、`parse/slots.PATTERNS` |
| K35 | 检查单条目 id **等于**条款 id，跨 kind 同 id 不算重复（查重按 kind 分别成立） | `kb/loader.load_kb` |
| K36 | GB 55006 无"强条/非强条"之分（全文强制），107 条一律 `mandatory: true`；`requirement_type` 由**义务词**判档（必须/严禁/应/不应/不得→must，宜→should，可/无→may）。50017 的 7 条强条清单（D14）**只适用于 50017** | `data/clauses/gb55006.json`、`checklist.render_text` |
| K37 | D11 的「表 ↔ 公式同点同值」容差 = **±0.001**（06 D22）。3 位小数取整一致只有 792/953，±0.001 下 953/953（最大 0.00086，单向系统偏移，成因=表体生成 λₙ 标度与官方 k 差约 0.05%，官方常数未取到 → V3b）；**禁止**把拟合常数当规范事实入库 | `data/tables/gb50017.json`、06 D22 |
| K38 | `interpolation=linear` 支持「**分组轴 + 数值轴**」：数值轴 = 出现在数值环境里的声明轴，其余声明轴必须由参数卡给分组值；**缺分组轴就返回 None（编排层记未查表）**，绝不把 a/b/c/d 四类的行混在一起插值；词表外的分类值不给兜底 ⇒ 抛 `EngineError`；超表界仍拒绝不外推 （K18 的扩展，M3 落地附录 D 时发现单数值轴表达不了二维表）| `engine/tables.py::_linear_lookup`、`tests/test_real_data.py::test_promoted_phi_table_is_usable_but_a5_still_blocked` |

## 五、M4 待办（按顺序，每步可单独演示）

0. **引擎支持分段/按条件选式**（D23 欠下的账）：`F-D.0.5-1` 的两支公式现在无法表达，因此附录 D 的**公式那一源**只是文字级 verified、进不了计算路径。做完这条才能真正让 A5 在拿到表 4.4.1 之后跑起来；顺带把「按 `section_class` 选 φ 表分支」跑通一条端到端夹具用例。
1. **四基准合一**：`sdc bench` 一条命令跑 算例通过率 / 确定性回归（含 IR 与报告的两次字节一致）/ 解析 F1 /
   核查检出率与误报，输出一张指标表并写进 README（门槛见 plan/05 §六）。当前四个入口已分开，缺"一键 + 汇总表"。
2. **报告导出**（docx）：验算书（`Result` → 逐步计算 + 依据 + 免责声明）与核查清单/检查单（`check`、
   `checklist` 的报告 → 条目 + 判定 + 出处）。硬断言：**0 外链、两次导出字节一致、免责声明必存、无真实个人信息**
   （复用 `synth/docx.py` 的固定 ZipInfo 写法；导出侧同样不许引入 python-docx，除非 M4 里先做打包 spike 证明可控）。
3. `sdc selfcheck` 增补两档看板：规则/检查单的 located→verified 进度、**未启用规则清单**（现在只在 `check`
   报告里，selfcheck 应该按模块聚合给"还差哪条核对"的可执行队列）。
4. 若 T5 定档完成：按 §三 的两种结局处理 `data/tables/`，并把插值口径登记成新口径条目；
   `data/cases/` 若拿到可确证来源的教材算例，`sdc bench` 的算例分母才第一次非 0。
5. 解析侧已知缺口（M4 或 M5 补，按需）：`spacing`/`edge`/`end_distance`（螺栓间距边距端距）与
   螺栓数量类槽位没抽 ⇒ 相关构造规则只能"未启用"；跨段回指（"其余要求同前述"）不解析（设计上不猜）。
6. 回写 plan/00 进度表与 plan/05 的 M4 行，写 HANDOFF-M5。

## 六、本机环境事实（M3 新增，M4 直接照此跑）

1. HANDOFF-M2 §五 与 M3 §六 全部仍成立：`py -3.8` + `PYTHONPATH=src`；测试**按文件分批取 rc、别接管道**
   （接了管道 `$?` 是 `tail`/`head` 的，会假绿——本轮踩过）。
2. **判定层不含正则**已落进代码（K26），`sdc check/checklist/bench --parse/--audit` 全程不 import `re`；
   `sdc parse` 是唯一碰正则的入口，崩了也只丢 IR，重跑那一份文档即可。
3. 新坑：`py -3.8 - <<'PY'` 这种 **heredoc 传中文脚本会被判"Non-UTF-8 code"**（文件本身是合法 UTF-8，
   是 stdin 源码检测的问题）。对策：中文脚本一律用文件跑，并在首行加
   `# -*- coding: utf-8 -*-`（本轮三次命中，写成脚本后 `py -3.8 file.py` 全部正常）。
4. PIL 10.4 在系统 `py -3.8` 里可用（像素级比对用它做的），**只用于 `.tmp_verify/` 里的校验脚本**，
   不进 `src/`、不进依赖清单（D05 零第三方依赖不变）。
5. 子代理纪律本轮再次有效：两批查证各自只允许写 `.tmp_verify/m3/<批次>/`，收尾 `git status` 逐文件核对，
   仓库文件零越界、缓存未删。M4 继续照此派活；第二路证据的定点样本要**给具体格号**，
   "整表一致"这种笼统结论已被证明会掩盖单格误读。

## 七、禁止事项（M4 阶段）

- 不得为了"通过率/分母有数字"编造教材书名、例题号、规范数值；分母 0 是诚实结果，编来源是事故
- 不得把镜像图片转录的表体值在**交叉核对未闭合**时写进 `data/tables/`（T5 未定档 = 一律 located、`values: []`）
- 不得把 `tests/fixtures/**` 的任何数值、式体、规则复制进 `data/`（K25 有测试，复制本身就是事故）
- 不得在规则文件里加等级字段，也不得把未核对的阈值写成数字（K30/K31）；schema 会拒，别绕
- 不得把正则引进判定层，也不得让 `bench` 现场解析文档（K26）；不得为了少一条命令把 parse 和 check 合并
- 不引入 LLM / 网络依赖 / numpy / scipy / faiss；导出侧不新增第三方依赖（要引先做 spike 并记 06）
- 不动 `.gitattributes` 的 `eol=lf`；不手改 `data/synth/`（改模板 → 固定 seed 重生成）；不删 `.tmp_verify/`
- 不删 `.tmp_parse/`（已 gitignore 的 IR 工作目录）以外随意新增仓内临时目录
- 对外动作（push / 建仓 / tag / Release）未获用户确认不得执行；提交前先 `git status` 逐文件审读改动
