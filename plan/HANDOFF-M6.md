# HANDOFF-M6（M5 桌面交付 → M6 脱敏发布 + 收尾固化 交接快照）

> 用法（新对话）：`读取 plan/HANDOFF-M6.md，继续完成任务`（本文件内一律相对路径）
> 落盘时间：2026-10-07　落盘者：M5 桌面交付对话
> 上一棒：[HANDOFF-M5.md](HANDOFF-M5.md)（M4 内置基准 → M5；其 §五 待办 1~4 与 6 已完成，
> §五.0「引擎支持分段选式」**未开工**，§三.4「冻结环境 suite 通路」**已解决**）

## 一、M5 交付了什么（已验证的事实）

| 交付物 | 位置 | 状态 |
|---|---|---|
| 五页签 GUI | `src/sdc/gui/{app,widgets,labels,page_verify,page_check,page_checklist,page_export,page_status}.py` | ✅ ①验算台 ②设计说明核查 ③规范检查单 ④报告导出 ⑤知识库与状态；页签标题与顺序有测试钉住；`sdc gui` 与 `sdc-gui.exe` 两个入口 |
| GUI 与 CLI 同一批函数 | `src/sdc/cli.py` 的 `load_kb_or_error` / `run_card_command` / `run_case_command` / `check_command` / `checklist_command` / `bench_suite_command` / `export_command` | ✅ 命令的"算"部分从 `_cmd_*` 里提出来，CLI 与界面调的是同一个函数、同一批异常映射、同一个退出码（D08/K48）；`_cmd_*` 只负责打印 |
| 界面不越权的守门 | `tests/test_gui_pages.py` 的 ast 扫描 | ✅ GUI 不得 import `re`/`subprocess`/网络库/`sdc.parse`；不得出现 `QMessageBox`；不得调用 `lookup`/`evaluate`/`run_rules`/`build_ir` 等引擎内部件 |
| GUI↔CLI 契约 | `tests/test_gui_contract.py`（12 项） | ✅ 同一张卡两边 `Result` **对象相等**、正文面板与 `cli.main` 的 stdout **逐字相同**、退出码相同、`bench --all` 整段输出逐字相同、三类 docx **字节相同**；期望值全部现跑，不手写 |
| 拒算与降级在界面上的形态 | 页签①②⑤ | ✅ 真实数据 blocked ⇒ 步骤表 0 行、原文含"不出数值（blocked）"；夹具 KB ⇒ 出逐步计算；解析通路拿不到 ⇒ 直说"通路不可用"；`bench --all` 的「不可判／不可用」原样显示（有测试断言非 pass 行不得显示"达标"） |
| 打包态子进程通路 | `src/sdc/suite.py::cli_channel` | ✅ 源码态 `sys.executable -X utf8 -m sdc`；冻结态同目录/邻接 `sdc-cli.exe`，`SDC_CLI_EXE` 可显式指定；拿不到 ⇒ 返回 None ⇒ 指标记「不可用」。**HANDOFF-M5 §三.4 就此关闭**，且 GUI 页签②的解析也走这条通路（界面进程不跑正则） |
| 双 exe | `sdc.spec` + `scripts/entry_{cli,gui}.py` | ✅ `dist/sdc-cli`（13 MB，**不含 PySide6**，console=True，与 `python -m sdc` 同一个 `cli.main`）＋ `dist/sdc-gui`（108 MB，console=False）；`.gitignore` 加 `!sdc.spec` |
| 打包白名单单源 | `scripts/bundle_rules.py` | ✅ spec 与断言脚本共用；入包 9 个数据目录；**排除** `data/README.md`（台账含渠道 URL，K42）与 `data/cases/`（0 例，缺目录 ⇒ 算例通过率照旧「不可判」） |
| 构建红线断言 | `scripts/verify_dist.py` → `DIST_AUDIT_OK` | ✅ 四组：禁区成分（任何深度的 `.tmp_verify`/`plan`/`__pycache__` + 包根的 `tests/src/scripts` 与禁引库）／内嵌数据**含子目录**逐份 sha256 对账且不许多出文件／PySide6 只在 GUI 包／GUI 旁边找得到 CLI exe。任一违反 exit 1；`tests/test_packaging.py` 用伪造 dist 逐项验证扫描器不是空转 |
| 干净环境验证 | `scripts/clean_env_check.py` → `CLEAN_ENV_OK` | ✅ 复制到 `%TEMP%\sdc-clean-env`（不在仓库树内）、PATH 里没有任何 Python、`PYTHONPATH/PYTHONHOME/SDC_*` 全剥；CLI 六连 rc 逐条断言（0/1/0/1/0/1/1）+ `SDC_DATA_DIR` 覆盖生效 + GUI 存活探针 + `sdc-cli.exe gui` 老实报"桌面界面不可用"（rc=2）共 10 项 |
| 编码口径修正 | `cli._err()`（K47） | ✅ 干净环境验证抓回的真 bug：冻结 exe 的 stderr 跟随系统代码页（本机 GBK）而 stdout 已是 UTF-8 ⇒ 同一句话两种字节。23 处 `sys.stderr.write` 收进 `_err`，用 GBK 流当诱饵的回归测试钉住 |
| extras 上限 | `pyproject.toml` | ✅ `PySide6>=6.4,<6.7`（本机实测 6.6.3.1 是 3.8 上可解析的最高版本）、`pyinstaller>=6.0,<7`（实测 6.22.3 构建一次通过）；`report` 组保留声明但**不使用** python-docx（它会写真实时间与用户名，打挂 K42） |
| 测试 | 22 个文件 **310 项全绿，0 跳过**（新增 `test_gui_pages.py` 19、`test_gui_contract.py` 12、`test_packaging.py` 15） | ✅ `py -3.8 -X utf8 -m pytest -q -rs` 全绿且无 skip；`sdc selfcheck` 0 问题；`sdc bench --all` 仍 rc=1（两个不可判） |

**可演示物（四条，缺一不可）**

```bash
export PYTHONPATH=src            # 注意：Git Bash 里 `set PYTHONPATH=src` 无效（那是 cmd 语法）
# ① 界面：五页签 + 抓帧（native QPA 才有中文字体）
py -3.8 -X utf8 -m sdc gui
py -3.8 -X utf8 -m sdc gui --screenshot .tmp_verify/m5/gui-tab1.png
# ② 界面逐页签真跑（offscreen，含"真实数据拒算 / 夹具出数值 / 解析走子进程 / 人工答复回灌"）
py -3.8 -X utf8 .tmp_verify/m5/gui_smoke.py            # 末行 GUI_SMOKE_OK
# ③ 构建 + 两条红线
py -3.8 -m PyInstaller --noconfirm sdc.spec
py -3.8 -X utf8 scripts/verify_dist.py                 # DIST_AUDIT_OK
py -3.8 -X utf8 scripts/clean_env_check.py             # CLEAN_ENV_OK
# ④ 冻结态一键基准的原始输出（§三.4 闭环的证据）
py -3.8 -X utf8 .tmp_verify/m5/capture_frozen_bench.py # 确定性回归＝达标，数据目录在 _internal/data
```

## 二、M5 DoD 逐项结果（含偏差，未抹平）

| DoD（plan/05 §七 M5 行 + HANDOFF-M5 §五） | 结果 |
|---|---|
| PySide6 五页签 GUI，只调公开 API | ✅ 页签⑤把 `selfcheck` 的 `[3]门控`/`[6]推进看板`/`[7]核对队列` 与 `bench --all` 指标表原样显示；页签④导出失败会说明为什么没写出来 |
| CLI 契约测试（GUI 与 CLI 同一套行为） | ✅ 12 项逐字对账；`data_fingerprint` 与免责文案同源（`test_report.py` 的"src 里只有一处定义"守门仍生效，GUI 没写第二句） |
| onedir 双 exe + spec 白名单 + 构建后遍历断言 | ✅ 见 §一；`find_data_dir` 五分支测试 M2 就有（`tests/test_paths.py`），本轮补的是"冻结态真的命中内嵌数据"的实跑证据 |
| §三.4 冻结通路：解决或明确标注 | ✅ **解决**（`cli_channel()`），并有测试 + 实跑证据双份 |
| 干净环境验证 | ✅ `CLEAN_ENV_OK`；顺带抓出 K47 那条编码不一致（真 bug，已修 + 加回归） |
| 回写 plan/00、03、05、06；写 HANDOFF-M6 | ✅ 本文件；03 §六/§七 改成"已落地形态 + 实测表"，05 §七 M5 行、06 加 **D25（K45~K48）** 与 4 行变更日志，README 加「桌面版（GUI + exe）」节 |
| HANDOFF-M5 §五.0：引擎支持"分段/按条件选式"再升 `F-D.0.5-1` | ⚠️ **没做**（本轮按 §五 的顺序走主线）。后果不变：A5 永远 blocked，`sdc run --module column_buckling` 出不了数值；且它属于引擎改动，会动 `tests/test_engine_*` |
| 解析侧已知缺口（`spacing`/`edge`/`end_distance`、螺栓数量类槽位） | ⚠️ 未动。`sdc selfcheck` 会把这些规则报成 `slot_unsupported`（K44 的第四类），与核对无关 |
| docx 版式（Word 表格/标题样式） | ⚠️ 未做（M4 留的 spike 没跑）。三类交付物仍只有段落 |
| PDF 输入 | ⚠️ 未支持，页签②与 `sdc parse` 同口径（`.docx/.txt/.md`） |
| GIF/截图 | ⚠️ 只有 PNG 一帧（`.tmp_verify/m5/gui-tab1.png`）；没做 GIF。抓帧脚本没进产品面（`--screenshot` 单帧进产品面，多帧 GIF 没做） |

**M5 期间查出来的三件事**

1. **冻结 exe 的 stderr 不跟 stdout 同编码**（K47）。`_emit` 早就把 stdout 钉成 UTF-8，但
   `sys.stderr.write` 在 PyInstaller 打包后按系统代码页（本机 GBK）落字节 —— 同一句拒算说明
   在 `python -X utf8 -m sdc` 与 `sdc-cli.exe` 里是两种字节。修法：`cli._err()` 与 `_emit` 同口径。
2. **`env -i` 剥太狠会让 PyInstaller 的 bootloader 起不来**（`Fatal Python error:
   _Py_HashRandomization_Init: failed to get random numbers`）。"剥离 PATH"的正确形态是
   保留 `SystemRoot/WINDIR/COMSPEC/PATHEXT/TEMP/TMP/USERPROFILE/APPDATA/LOCALAPPDATA/HOME`
   并把 PATH 缩到 `System32` + 包目录，同时断言 PATH 里没有 `python.exe/py.exe` —— 已经写进
   `scripts/clean_env_check.py:stripped_env`，别再手搓。
3. **构建红线的对账必须递归**。第一版 `reconcile_data` 用 `os.listdir` 只比顶层文件，
   于是 `data/synth/docx/` 的 24 份语料**根本没参与对账**，而审计照样打印 `DIST_AUDIT_OK`
   （16 份 vs 40 份）。改成整目录相对路径对账 + 一条"改一个子目录字节必须被抓出来"的测试。

## 三、悬而未决（M6 开工前要注意）

1. **`data/cases/` 真值仍 0 例**（M1 起就挂着）。指标表的「算例通过率」照旧是**不可判**，
   解除通道在 `data/cases/README.md`（教材/手册例题要书名+版次+例题号齐全）。
   **不许**为了绿灯编来源。
2. **可硬判 abnormal 的规则分母仍是 0 条**（10 条核查规则的依据全部只 `located`）。
3. **单一底图那批表**（4.4.1/4.4.5/4.4.6/11.4.2-1/-2/7.4.6/7.4.7/7.2.1-1-2）按 T5③ 原意
   保持 located、`values: []`；`sdc run` 在真实数据上仍然一个数值都不出。
4. **CI 矩阵从未建过**：仓库里没有 `.github/workflows/`，而 D12 承诺 3.8/3.12 双矩阵、
   M6 DoD 写着"CI 矩阵全绿是发布门"。M6 要新建 workflow，并注意：GUI 测试需要
   `.[dev,gui]`（否则 22 个文件里有 3 个会**声明式跳过** —— 收集数对账要按 skill 的
   "dev 与 CI 计数逐项归因"做）；step 名里带「冒号+空格」必须加引号（否则整份 workflow
   非法、GitHub 一个 job 都不建）。
5. **`dist/` 里的产物要过"构建产物本体扫描"**（M6 第 5 步）：exe/onedir 里可能带构建机
   路径与个人标记；`dist/` 被 gitignore，所以仓库内容级扫描**看不见它**。发布 zip 的
   sha256 要留档。
6. **只拷走 `sdc-gui/` 目录**（不带邻接的 `sdc-cli/`）时，界面的一键基准与页签②解析会
   显示「不可用」——这是设计行为（诚实降级），但 Release 说明里要写清楚"两个包一起发"。
7. **`plan/03 §四` 目录结构里写了 `pipeline.py`（轻量状态机）而代码里从未有它**。M5 不需要；
   M6 收尾要么改文档承认"编排层就是 `cli.py` 的命令分派"，要么补实现 —— 别让文档与树长期不一致。

## 四、既定口径清单（改了会打挂基准，动手前先对照）

K1~K16 见 HANDOFF-M2 §四，K17~K25 见 HANDOFF-M3 §四，K26~K36 见 HANDOFF-M4 §四，
K37/K38 见 HANDOFF-M4 §四（M3 定档轮），K39~K44 见 HANDOFF-M5 §四，**全部未变**。M5 新增：

| # | 口径 | 位置 |
|---|---|---|
| K45 | **CLI 子进程通路单源**：`suite.cli_channel()` 返回 `(argv 前缀, cwd)` —— 源码态 `[sys.executable, -X, utf8, -m, sdc]` + `src/`，冻结态同目录/邻接的 `sdc-cli.exe`（`SDC_CLI_EXE` 显式指定优先），两条都不成立返回 `(None, exe 目录)`，调用方把对应指标记「不可用」并原样说明。GUI 的文档解析也走这条通路 ⇒ 界面进程不执行项目正则 | `suite.cli_channel`/`run_cli`、`gui/page_check.py`、`tests/test_packaging.py` |
| K46 | **打包白名单与构建红线单源**：`scripts/bundle_rules.py` 定义入包数据目录（9 个）与禁区成分，`sdc.spec` 与 `scripts/verify_dist.py` 都读它；`data/README.md` 与 `data/cases/` 不入包；构建后四组断言（禁区成分／内嵌数据**含子目录**逐份 sha256 对账且不许多出文件／PySide6 只在 GUI 包／GUI 旁边有 CLI exe），任一违反 exit 1 | `scripts/{bundle_rules,verify_dist}.py`、`sdc.spec`、`tests/test_packaging.py` |
| K47 | **stdout 与 stderr 同编码**：两条流都钉成 UTF-8（`_emit`/`_err`）。冻结 exe 的 stderr 默认跟随系统代码页，不处理就会让同一句话在源码态与打包态落成两种字节 | `cli._emit`/`_err`、`tests/test_run_cli.py::test_error_channel_uses_the_same_encoding_as_stdout` |
| K48 | **界面与命令面同源**：GUI 只调 `sdc.cli` 的公开命令函数与 `engine`/`rules`/`checklist`/`report`/`suite`/`selfcheck` 的公开 API；文本面板 = 命令面渲染器输出；通知走 `NotifyMixin`（可注入回调 + `messages`），界面源码禁 `QMessageBox`；契约测试期望值一律现跑，不手写 | `src/sdc/gui/`、`tests/test_gui_{pages,contract}.py` |

## 五、M6 待办（按顺序，每步可单独演示）

1. **CI workflow 从零建**（§三.4）：`.github/workflows/ci.yml`，windows/3.8 + ubuntu/3.8 +
   ubuntu/3.12 矩阵；GUI 矩阵装 `.[dev,gui]`，非 GUI 矩阵按声明式跳过对账收集数；
   加一条"workflow 可被 YAML 解析且每个 job 有 runs-on/steps"的守门测试（dev 装 pyyaml）。
2. **脱敏四步 + 第 5 步产物本体扫描**，逐项把命令与结论留档到 `plan/RELEASE-M6.md`：
   ①`git ls-files` 敏感文件名；②内容级扫描全部跟踪文本（密钥/手机号/身份证/个人路径/
   内网 IP/邮箱），注意 HANDOFF 系列本身的用法行（本轮已全部写相对路径）；③二进制单独扫
   （`data/synth/*.docx` 的全部 zip 条目含 `docProps`；`dist/` 不在跟踪范围，走第 5 步）；
   ④提交元数据邮箱 `git log --format="%ae %ce" --all | sort -u`；⑤**构建产物本体扫描**：
   全 `dist` 树用 Python 字节读法扫个人标记与构建机路径（别跑邮箱正则，上游 LICENSE/SBOM
   会刷屏），并复核产物树无禁区成分（与 `verify_dist.py` 双保险）。
   扫描模式**别用 `/` 起始形式**（MSYS 静默转写 → 假 0 命中），先跑阳性对照。
3. **干净环境复核**：新目录 `git clone` + 全新 venv，按 README **原文逐字**跑（含
   `pip install -U pip` 前置、`.[dev,gui,pkg]` 安装、GUI offscreen 测试、构建 + 两条红线）；
   对照 dev 与干净环境的 pytest **收集数**（310 项，0 跳过）。
4. **对外动作（需用户逐项确认，未确认不得执行）**：建仓/公开性、push、tag `v0.1.0`、
   Release 附两个 exe（或打包 zip + sha256 留档）、topics。Release notes 写清：
   指标表数值（含两个「不可判」的实话）、演示命令、extras 说明、两个包要一起发（K45）、
   免责声明。
5. **材料固化（可选）**：`docs/技术报告.md`（当前 `docs/` 是空目录）——三大主题现成：
   条款-公式-符号表引擎与 status 门控、条文核对与三档定档（±0.001 的来龙去脉）、
   合成语料与内置基准；docx 版由 md 程序化生成（md 先定稿）。
6. **回写与清零**：plan/00 进度表 M6 行、plan/05 §七 M6 行、plan/06（脱敏与发布决策留档）、
   README 状态行转正（挂 Release 链接 + CI 徽章）、`plan/06` 待定表复核（T3/T4/T5 已全关，
   确认无"⬜ 缓议"进终态）、§三.7 的 `pipeline.py` 文档漂移处置。

## 六、本机环境事实（M5 新增，M6 直接照此跑）

1. HANDOFF-M2 §五、M3 §六、M4 §六、M5 全部仍成立：`py -3.8` + `PYTHONPATH=src`；
   测试**按文件分批取 rc、别接管道**；`-X utf8` 用于中文输出。
2. **Git Bash 里 `set PYTHONPATH=src` 不生效**（那是 cmd 内建），要 `PYTHONPATH=src py -3.8 …`
   或 `export`。历史 HANDOFF 里的 `set PYTHONPATH=src` 是给 cmd 用户看的。
3. **PyInstaller 6.22.3 + Python 3.8.8 一次构建通过**（约 2 分钟，无 modulegraph 崩溃复现）；
   产物 `dist/sdc-cli` 13 MB、`dist/sdc-gui` 108 MB。构建前 `rm -rf build dist` 更干净。
4. **冻结 exe 的 std 流编码不对称**（K47，见 §二.1）；`env -i` 的坑见 §二.2。
5. **GUI 测试跑法**：`QT_QPA_PLATFORM=offscreen` 由 `tests/_gui.py` 在 import PySide6 之前写死；
   310 项里 GUI 两个文件占 31 项（`test_gui_pages.py` 19 + `test_gui_contract.py` 12），
   `test_packaging.py` 另占 15 项；全套单进程跑完约 3 分钟量级（`test_gui_contract.py` 里那条
   `bench --all` 契约最慢，它跑两遍整批解析）。
6. 套件 scratch 目录：GUI 用 `%TEMP%\sdc-gui{,-suite}`，干净环境验证用
   `%TEMP%\sdc-clean-env`；`sdc bench --all` 在仓库树里仍写 `.tmp_parse/suite/`。
   新增 scratch 步骤要照 M4 的 `_reset_ir_dir` 口径（只删自己写的文件）。
7. 子代理纪律：M5 没派子代理（全部主对话内完成）。M6 若要派，仍按 HANDOFF-M1 的教训——
   **限定可写文件清单**，收尾 `git status` 逐文件 `git diff` 审读，中间证据不许它删。

## 七、禁止事项（M6 阶段）

- 不得为了"通过率/分母有数字"编造教材书名、例题号、规范数值；分母 0 与「不可判」是诚实结果
- 不得把「不可判」「不可用」渲染成达标或绿勾 —— CLI、docx、GUI 三处同一条口径（K43/K48）
- 不得在 `data/` 里写未核对的数值；`values: []` 的表保持空，除非有新的独立渠道证据 + 交叉核对闭合
- 不得把 `tests/fixtures/**` 的任何数值、式体、规则复制进 `data/`（K25 有测试）
- 不得给 GUI 写第二套判定/渲染/查表（K48）；不得在规则文件里加等级字段（K30/K31）
- 不得让 `bench` 或界面进程在本进程内解析文档（K39/K45）；文档解析只在 `sdc parse` 与子进程里发生
- 不得引入 LLM / 网络依赖 / numpy / scipy / faiss / python-docx；`verify_dist` 会把这些抓出来
- 不得放宽 `scripts/verify_dist.py` 或 `scripts/clean_env_check.py` 的断言来"让它过"；
  违反项要么修，要么在 `plan/RELEASE-M6.md` 里如实记为偏差
- 不动 `.gitattributes` 的 `eol=lf`；不手改 `data/synth/`（改模板 → 固定 seed 重生成）；
  不删 `.tmp_verify/` 与 `.tmp_parse/`
- 改了 `data/` 就要重跑 `sdc bench --all --markdown` 并同步 README（`test_readme_metrics_table_matches_a_live_run` 记着这件事）；
  改了 `data/` 或白名单还要重跑 `scripts/verify_dist.py`（内嵌数据对账会跟着变）
- 对外动作（push / 建仓 / tag / Release / 历史重写 / 可见性）未获用户确认不得执行；
  提交前先 `git status` 逐文件审读改动
- ⚠️ **本工作树的提交状态**：M5 的全部改动（`src/sdc/cli.py`、`src/sdc/suite.py`、
  `src/sdc/gui/`、`scripts/`、`sdc.spec`、`tests/{_gui,test_gui_pages,test_gui_contract,test_packaging,test_run_cli}.py`、
  `pyproject.toml`、`.gitignore`、README 与 plan/00/03/05/06 + 本文件）**尚未提交**。
  接手第一件事：确认切分方案（建议两刀：①GUI+契约+cli/suite 口径 ②打包+干净环境+文档回写），
  默认只本地 commit，不 push。`dist/`、`build/` 已在 gitignore 内，不要提交产物。
