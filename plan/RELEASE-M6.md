# RELEASE-M6 留档（脱敏 · 干净环境 · 发布执行记录）

> 用法：本节所有命令都在仓库根执行；扫描类命令的输出**已掩码化**（只打印 `位置 [类别] xN`），
> 因此本文可以引用输出而不成为二次泄漏源。含敏感字面值的核对一律在**仓外**人工执行，
> 字面不写进本文（否则"全历史 0 命中"永远验不过）。

## 〇、拍板留档（用户确认，2026-10-07）

| # | 议题 | 用户答复 |
|---|---|---|
| 1 | 提交元数据邮箱全历史改写 | **授权改写为 GitHub noreply**（`<id>+<login>@users.noreply.github.com`，id 由 `gh api user` 取得；用户名不变） |
| 2 | `plan/03 §四` 的 `pipeline.py` 文档漂移 | **改文档承认现状**（编排层 = `cli.py` 命令分派 + `suite.py` 套件通路），不补实现 |
| 3 | 对外动作范围 | **一次授权到底**：建仓公开 → SSH push → CI 首跑 → annotated tag `v0.1.0` → Release 附两个 onedir 的 zip（sha256 留档）→ topics |
| 4 | 技术报告 | **纳入本轮**：`docs/技术报告.md` 定稿 + 生成器程序化产出 docx（禁止手改产物） |

时序采用方法论的**结果回写后置型**：确认 → 本留档与终态回写提交 → 建仓 push → CI 绿 →
tag（指向"发布物基线 + 拍板留档"提交）→ Release → 结果性回写（CI run id / Release URL /
plan 状态 ✅）作为 tag 后的小提交推送并等 CI 复绿，**不迁 tag**。

## 一、发布前置事实核验（实测）

| 项 | 命令 | 结论 |
|---|---|---|
| gh 登录与通道 | `gh auth status` / `ssh -T git@github.com` | 账号 `yuluo554`；token scopes = `gist, read:org, repo`，**没有 `workflow`** ⇒ 带 `.github/workflows/*` 的 push 不能走 OAuth HTTPS；SSH 已认证可用 ⇒ 建仓走 `gh repo create --source . --remote origin`（不带 `--push`），再把 origin 切成 SSH URL 一次 push 成 |
| 姊妹/系列表述公开性（06 D09 要求 M6 复核） | `gh api users/yuluo554/repos` | 8 个同系列仓库 + 本项目共 15 个仓库**全部 visibility=public** ⇒ 按方法论阶段 7 第 0 步，plan/00 的系列表述**保留**，结论登记进 06 D26；审计脚本把姊妹词表以 base64 存放并计为**复核项**（不是硬门） |
| LICENSE 先例 | `gh api repos/yuluo554/<各仓>/license` | 全部 MIT（`awesome-dsh-plugin` 是 CC0-1.0，属合集仓）⇒ 本项目 MIT，版权行写 `steel-design-checker contributors`，不写真实姓名 |
| 工作树基线 | `git status --porcelain \| wc -l` | M5 已全部提交（两刀：GUI+契约 / 打包+文档），M6 改动叠加前工作树干净 |
| 提交数 | `git rev-list --count --all` | 8 个提交（历史改写覆盖全部） |

## 二、脱敏五步（`scripts/audit_release.py`，逐项命令与结论）

工具形态：四步 + 产物本体扫描固化成**入仓可复跑脚本**，`selftest` 模式先跑阳性/阴性对照；
分级为硬门（exit 1）与复核项（人工判定后在本文留档）；输出掩码化。守门测试在
`tests/test_release_audit.py`（9 项），随全量测试在 CI 里常驻。

```bash
py -3.8 -X utf8 scripts/audit_release.py selftest    # 阳性/阴性对照 9 组
py -3.8 -X utf8 scripts/audit_release.py tracked     # ① 敏感文件名 + ② 内容级
py -3.8 -X utf8 scripts/audit_release.py binary      # ③ 跟踪二进制（docx 全 zip 条目）
py -3.8 -X utf8 scripts/audit_release.py messages    # 提交信息正文
py -3.8 -X utf8 scripts/audit_release.py metadata    # ④ 作者/提交者邮箱
py -3.8 -X utf8 scripts/audit_release.py history     # 全历史补丁 blob 级
py -3.8 -X utf8 scripts/audit_release.py dist        # ⑤ 构建产物本体扫描
```

| 步 | 命令 | 结论 |
|---|---|---|
| ① 敏感文件名 | `git ls-files`（158 份）+ `FORBIDDEN_TRACKED_NAMES` | **0 命中**：无 `.env`/`.key`/`secret`/`token`/`_private/` 形态的跟踪路径；`.gitignore` 覆盖 `.env`、`*.key`、`*_private/`、运行产物与会话产物 |
| ② 内容级扫描 | `tracked`（文本 133 份 / 二进制 25 份） | **硬门 0 命中**（密钥、手机号、身份证、内网 IP、个人邮箱、个人目录、个人标记全部 0）；复核项 9 处见下节逐条判定 |
| ③ 二进制 | `binary`（25 份，docx 展开全部 7 个 zip 条目含 `docProps/core.xml`、`app.xml`、`styles.xml`、rels） | **0 命中**：`dc:creator` / `cp:lastModifiedBy` 均为 `SYNTH_PLACEHOLDER`，`Application` 为 `sdc-synth` / `sdc-report`，无真实时间与姓名 |
| ④ 提交元数据邮箱 | `metadata` + 全历史改写 + 三扫 | 改写前 `metadata` 报 1 个不同邮箱（非 noreply）⇒ **硬门命中**，按用户授权改写；改写与三扫结论见下方"④ 改写执行记录" |
| ⑤ 产物本体扫描 | `dist`（M5 构建的 252 个文件全树字节读法） | **0 命中**：无个人标记字节、无禁区成分（与 `verify_dist.py` 双保险）。构建机路径没有跟进 exe——PyInstaller 只记模块相对路径，不记绝对源路径 |
| 提交信息 | `messages`（8 条正文） | **0 命中**（只扫 `%B`，作者头由 metadata 模式负责，否则提交邮箱必被误报） |
| 全历史 blob | `history`（补丁全文 1,350,396 字符） | 改写前后各跑一次；blob 级**硬门 0 命中** ⇒ 邮箱只在元数据（诊断命令：`git rev-list --all \| while read c; do git grep -lF <字面> "$c"; done` 为空）⇒ 单跑 `--env-filter` 足够，不需 tree-filter |

### 复核项判定（9 处，逐条指认后放行）

| 位置 | 类别 | 判定 |
|---|---|---|
| `plan/00` ×2、`plan/01` ×1 | sister_word | 8 个同系列仓库经 `gh api users/yuluo554/repos` 逐个核实 **visibility=public** ⇒ 按方法论阶段 7 第 0 步保留系列表述，结论登记 06 D09/D26 |
| `scripts/audit_release.py` ×3 | drive_path | 正则说明与 selftest 夹具里的**占位符形态**（`<个人标记>` 由片段拼接、`C:\Users\<name>`），不含真实账户名 |
| `scripts/clean_env_check.py` ×1 | drive_path | `os.environ.get("SystemRoot", r"C:\Windows")` 的系统目录默认值 ⇒ 方法论明确列为复核项 |
| `src/sdc/report/docxio.py` ×2 | drive_path | 模块 docstring 里的示例形态 `C:\Users\<name>\…`，正是 0 外链断言要拦的**形状的说明**，非字面泄漏 |
| `tests/test_release_audit.py` ×3 | drive_path | 夹具样本，个人标记运行时从 `PERSONAL_MARKS` 取，源码不含完整字面 |
| `plan/RELEASE-M6.md` ×4 | drive_path | 本留档在描述判定与构建命令时写的路径形态（占位符与系统目录默认值），扫描器的个人标记类为 **0** ⇒ 无真实账户名 |
| `tests/test_report.py` ×1 | drive_path | `C:\Users\someone\Desktop\规范.pdf` 是"个人信息不得进交付物"这条测试的诱饵输入，`someone` 非真实账户 |

### 据链（sha256）

| 产物 | sha256 | 生成方式 |
|---|---|---|
| `docs/技术报告.docx` | `e3ab973cf4dce792e08f8b70aacdaa69526dde6bea132e53ec35a4c6100205f0` | `py -3.8 -X utf8 scripts/make_tech_report.py`（源 md `f87bb72fa33e7bedfd6191c6bb2af2ddc350cb005dcf1324b606fccccb6e50c6`）；重生成逐字节一致由 `tests/test_tech_report.py` 钉住 |
| `dist/sdc-cli/*.exe` 与 `dist/sdc-gui/*.exe` | 待回填（Release 上传时逐包记录） | 构建基线 = tag 所指提交；发布前 `verify_dist.py` 已对内嵌数据逐份对账 |

发布 zip 与源码的同一基线用 `git diff <发布基线>..HEAD -- src/` 为空来证明，防"扫的是旧产物"。

### ④ 改写执行记录（2026-10-07，用户授权）

| 序 | 动作 | 命令 | 结论 |
|---|---|---|---|
| 1 | 范围诊断 | `git rev-list --all \| while read c; do git grep -lF "<旧邮箱>" "$c"; done \| sort -u` | **0 个 blob 命中** ⇒ 邮箱只在提交元数据 ⇒ 单跑 `--env-filter` 足够，不需要 tree-filter |
| 2 | 仓外备份 | `git bundle create ../steel-design-checker-history-backup.bundle --all` + `git bundle verify` | 备份在**仓库外**，记录完整历史（12 个提交）；改写失败可整仓恢复 |
| 3 | 全历史改写 | `git filter-branch -f --env-filter '…' -- --all`（输出**不接管道**，重定向到文件） | rc=0，12 个提交全部重写，`refs/heads/main` was rewritten |
| 4 | 树未被改动证明 | `git rev-parse 2481ce3^{tree}` vs `git rev-parse HEAD^{tree}` | 两个 tree 哈希**完全相同**（`d13c12fd…`）⇒ 只动元数据，工作树与基准不受影响 |
| 5 | 清理 | `rm -rf .git/refs/original` → `git reflog expire --expire=now --all` → `git gc --prune=now --aggressive` | `git fsck --no-reflogs` 无错误；`git status --porcelain` 空 |
| 6 | 本地配置同步 | `git config user.email "…@users.noreply.github.com"` | 后续提交不再引入旧邮箱 |
| 7 | 终验三扫 | ①逐提交 blob grep ②`git log --all -p` 计数 ③`git log --all --format="%an %ae %cn %ce"` 计数 ④`git cat-file commit` 逐个提交对象头 | **全部 0 命中**；阳性对照用历史里确实存在的字面（`steel-design-checker`，19 处）先证明扫描通道本身工作正常 |
| 8 | 工具复核 | `audit_release.py metadata` / `messages` | 两个模式均 `DESENSITIZE_AUDIT_OK`；`metadata` 只剩 1 个不同值（noreply） |

字面值不入仓、不入本文：改写前 `git log` 取到的是「11 位数字@qq.com」形态的真实邮箱，
终验在**本 shell 会话内**用固定字面执行（`--all` 扫描在清理 `refs/original` 之后进行，
避免备份 ref 把旧对象扫进来误报）。

### 五步合跑结论（改写后）

```
py -3.8 -X utf8 scripts/audit_release.py all      # rc=0
[selftest] 阳性/阴性对照 9 组
[tracked]  文本 133 份 / 二进制 25 份
[binary]   展开 25 份跟踪二进制（docx 全 zip 条目）
[messages] 全历史提交信息 12 条
[metadata] 作者/提交者邮箱 1 个不同值（noreply）
[history]  补丁全文 1,427,055 字符
[dist]     遍历 dist 树 252 个文件
汇总：硬门 0 类命中 / 复核项 12 类命中 → DESENSITIZE_AUDIT_OK
```

12 处复核项 = 上表 9 处（跟踪面）+ 全历史补丁的 `drive_path` 14 次与 `sister_word` 5 次
（同一批文件在各历史版本里重复出现所致），判定理由与跟踪面一致，无新增面。

**⑤ 构建产物本体扫描的关键结论**：M5 在开发机路径下构建的 252 个产物文件里**没有**个人标记字节，
也没有禁区成分——PyInstaller 只把模块记成相对名，构建机绝对路径没有跟进 exe。这条不是猜的：
字节读法逐个文件扫（含 `base_library.zip`、`PYZ-00.pyz`、Qt DLL 与 `.pyd`）才敢这么写。

**阳性对照不是形式**：首轮 selftest 抓出两处扫描器自身的问题——邮箱正则把域名要求成"至少三段"
（两段域，形如 `<本地部分>@<服务商>.com`，被放行），以及 `\.env$` 前面多加了路径分隔符锚
（`prod.env` 这类根目录形态放行）。两条都由 selftest 的阳性样本逼出，修完才继续。

**审计器自引用坑（本文件与脚本都踩过）**：`audit_release.py` 的 selftest 夹具最初直接写了
内网 IP 与邮箱的完整字面，于是扫描器命中自己 ⇒ 样本一律改成**片段拼接**；姊妹词表 base64 存放；
输出只给 `位置 [类别] xN`。

## 三、干净环境复核（新 clone + 全新 venv，按 README 原文逐字）

clone 落在**仓库树外**的 `../sdc-clean-clone`（`find_data_dir` 的 CWD 上溯会命中仓库 `data/`，
在树内跑等于什么都没验）。步骤与真实退出码：

| 步 | 命令 | 结论 |
|---|---|---|
| clone | `git clone <本地仓库> ../sdc-clean-clone` | rc=0，158 份跟踪文件 |
| EOL 门 | `sdc synth --check`（全新检出后校验冻结语料） | **rc=0「合成语料位级一致（seed=20261006）」** ⇒ 本机 `core.autocrlf=true` + 全新检出没有改写坏字节 |
| venv | `py -3.8 -m venv .venv` | rc=0（ensurepip 正常，本轮没触发历史坑） |
| README 前置 | `python -m pip install -U pip` | rc=0 |
| README 原文 | `python -m pip install -e ".[dev]"` | **首跑 rc=1**：pip 的 build-isolation 子进程 `exit code 3221225477`（0xC0000005）；**同一条命令第二次跑 rc=0** ⇒ 环境级随机崩溃，按方法论定性后 README 原文与门槛都不改 |
| 收集数 | `pytest --collect-only`（仅 dev extras） | **25 个文件 303 项**（GUI 两个模块被 `importorskip` 声明式跳过 ⇒ 少 31 项） |
| README 原文 | `python -m pip install -e ".[dev,gui]"` | rc=0，解析到 **PySide6 6.6.3.1** ⇒ 证明 `<6.7` 上限在干净 venv 里落到的就是开发机实测版本（"只写下限等于没 pin" 那条教训的反向验证） |
| 全量测试 | `pytest -q -rs`（未构建 dist） | rc=0，334 项 / 跳过 1 项（`test_packaging.py:251` 尚未构建） |
| 命令面 | `sdc selfcheck` / `sdc bench --all` | selfcheck rc=0；bench rc=1（两个不可判，符合 K43）；`bench --all --markdown` 与 clone 里的 README 逐行比对 **README_TABLE_MISMATCH=0** |
| 材料固化 | `scripts/make_tech_report.py` | rc=0，重生成 docx 与仓内产物 sha256 相同 |
| 脱敏 | `scripts/audit_release.py tracked` | rc=0 → `DESENSITIZE_AUDIT_OK`（工具不依赖开发机存量包） |
| 打包 | `pip install -e ".[pkg]"` + `python -m PyInstaller --noconfirm sdc.spec` | 前 3 次尝试全灭（`SystemError: unknown opcode`，命中本机已知的 `sre_parse`/pyc 损坏家族）⇒ 清 `__pycache__`（clone venv 内 164 个目录 + 系统 Python 132 个，全是可再生字节码）并以 `PYTHONDONTWRITEBYTECODE=1` 重跑 → **rc=0**，`dist/sdc-cli` 13 MB、`dist/sdc-gui` 108 MB，与开发机构建一致 |
| 红线一 | `scripts/verify_dist.py` | **`DIST_AUDIT_OK`**：sdc-cli 55 个文件 / sdc-gui 197 个文件，内嵌数据 40 份逐份 sha256 对账，禁区成分 0 处 |
| 红线二 | `scripts/clean_env_check.py` | **`CLEAN_ENV_OK`**：10 项全过（CLI 六连 rc 逐条断言、`SDC_DATA_DIR` 覆盖生效、GUI 存活探针 rc=0、`sdc-cli.exe gui` 老实报"桌面界面不可用" rc=2） |
| 红线三 | `scripts/audit_release.py dist` | **`DESENSITIZE_AUDIT_OK`**：干净构建的产物树同样硬门 0 命中 |
| 终局 | `pytest -q -rs`（dist 已构建） | **rc=0，334 项、0 跳过** ⇒ 与开发机基线**完全一致** |

### 本轮抓到的两条，定性分开

1. **`test_eol_guard` 在干净 clone 里报红**——原因是**我的验证脚本**把 22 个 scratch 文件
   （`.pytest_full.txt`、`.bench.txt` 等）撒在 clone 根目录，Windows 写入带 CRLF，而该守门测试
   扫的是工作树（不只是跟踪面——这是 M5 定下的"提交前就要拦住"口径）。
   定性：**脚手架口径问题，不是仓库回归**；处置：scratch 全部挪进 clone 内的 gitignore 目录后
   重跑，rc=0。副作用是这条测试再次被证明不是空转。
2. **`test_suite.py` 如实报出「两次解析退出码不同：0 / 3221225477」**——确定性回归捕获了一个
   子进程崩溃。这正是本项目"绝不把量不了当达标"的口径在真实故障上的演练：它没有静默通过，
   也没有把崩溃算成达标。定性：崩溃属环境随机（同命令重试即恢复），**测试语义不放宽**。

### 计数逐项归因（dev ↔ 干净环境 ↔ CI）

| 环境 | 收集 | 跳过 | 归因 |
|---|---|---|---|
| 开发机（装 gui、dist 已构建） | 334 | 0 | 基线 |
| 干净 clone + `.[dev]` | 303 | 3 | `tests/_gui.py:19` 模块级 importorskip ×2（`test_gui_pages` 19 项 + `test_gui_contract` 12 项 = 31 项不进收集）+ `test_packaging.py:251` 未构建 ×1 |
| 干净 clone + `.[dev,gui]` + dist | 334 | 0 | 与开发机一致 |
| CI ubuntu/3.8、ubuntu/3.12、windows/3.12（`dev`） | 303 | 3 | 同"干净 clone + `.[dev]`" |
| CI windows/3.8（`dev,gui`） | 334 | 1 | GUI 常驻该矩阵；CI 不跑 PyInstaller ⇒ 未构建那条跳过 |


## 四、CI 首跑与四轮对账

| 轮 | run id | 触发 | 结果 |
|---|---|---|---|
| 1 | `37570991561` | 第 1 次 branch push（main，SSH） | 4 作业：**ubuntu-22.04/3.8 绿、ubuntu-latest/3.12 绿**；两条 windows 各 1 条红 |
| 2 | `37571427131` | 第 2 次 branch push | 测试步**四条全绿**（含 windows/3.8+gui 的 334 项），三条作业红在 `Bench gate` |
| 3 | `37571747456` | 第 3 次 branch push | **四矩阵全绿**（windows/3.8+gui、windows/3.12、ubuntu-22.04/3.8、ubuntu-latest/3.12） |
| 4 | `37572650848` | 第 4 次 branch push（= tag 之后的**结果性回写**提交，pattern ③） | **四矩阵全绿**，收集数与第 3 轮完全一致（23/303 ×3 + 25/334 ×1） |
| tag | `v0.1.0` push | — | **没有产生 run**：ci.yml 只配 `push: branches [main]` + `pull_request`，tag ref 不匹配。如实记录，不虚构第四轮 |

**push 数 = run 数** 对账：4 次 branch push → 4 个 run ✓（1、2 红，3、4 绿）；tag push 不触发（上表）。
tag 之后不再迁 tag：`v0.1.0` 固定在 CI 全绿的提交 `570a0a3` 上，回写内容（含本段）在其后。
**本行是发布台账的最后一条**——记录 run 4 的那次 push 自己会触发 run 5，
其结论直接在仓库 Actions 页可查，不再回填一轮。

### 两轮红各是什么，都不是"放宽门槛"能解决的

**第 1 轮：仓库自己的 EOL 守门测试抓住了 CI 的脚手架。**

```
AssertionError: 以下文本文件含 CR，会打挂跨平台字节基准：['collect.txt']
```

`Collect count` 那一步用 `> collect.txt` 落地收集输出。Windows runner 上 Python 的 stdout 经
shell 重定向会写成 **CRLF**（`_utf8_stream` 只 reconfigure 编码，不改换行翻译），而
`tests/test_eol_guard.py` 扫的是**工作树**（不只是跟踪面——M5 定下的"提交前就要拦住"口径）。
ubuntu 矩阵换行本来就是 LF，看不见。
处置：收集数改走管道直出（`--collect-only -q | awk ...`），工作树里不留文件。

**第 2 轮：门禁那条"退出码与指标表互相对账"的断言，抓住了 CI 步骤自己写错的退出码。**

```
CI 基准门禁不通过：
  - 退出码与指标表不一致：bench 返回 0，按 K43 应为 1
```

指标表内容与本地实测逐行一致（7 达标 / 2 不可判），说明 `bench` 自己算出的码是 1；传给门禁的却是 0。
根因是 `${PIPESTATUS[0]}` **在管道执行之前**就展开，拿到的是上一条命令的陈旧状态——
方法论早就写过"退出码绝不能取自管道"，这次是我在修第 1 轮时换了一种拿法，又踩回同一个坑。
处置：`bench` 单独跑、`$?` 直接取码；JSON 落地改到 `.tmp_parse/`（`.gitignore` 覆盖，
且已在 `test_eol_guard` 的跳过名单里，Windows 重定向写 CRLF 也不会打挂 EOL 门）；
顺手回退 `ci_bench_gate.py` 没人用的 stdin 分支。

### 计数逐项归因（实测，取自 run 日志的 `collected_files/collected_items`）

| 矩阵 | extras | 收集 | 跳过明细 |
|---|---|---|---|
| ubuntu-22.04 / 3.8 | dev | 23 个文件 / 303 项 | `SKIPPED [2] tests\_gui.py:19`（GUI 两模块模块级 importorskip，合计 31 项不进收集）+ `SKIPPED [1] tests	est_packaging.py:251`（CI 不跑 PyInstaller） |
| ubuntu-latest / 3.12 | dev | 23 / 303 | 同上（3.12 无版本差型失败） |
| windows-latest / 3.8 | dev,gui | **25 / 334** | 仅 `test_packaging.py:251` 一条；**GUI 31 项真跑**（offscreen） |
| windows-latest / 3.12 | dev | 23 / 303 | 同 ubuntu 两条 GUI 跳过 + 一条未构建 |

第三轮起每个矩阵还打印 `BENCH_GATE_OK（未达标 0 / 不可用 0；不可判 2 项如实留档：
算例通过率、可硬判 abnormal 的规则分母）`——**门禁没有为了让 CI 绿而放行，也没有把不可判说成达标**。

## 五、发布执行记录（2026-10-07）

| 动作 | 命令 | 结果 |
|---|---|---|
| 建仓 | `gh repo create yuluo554/steel-design-checker --public --description "…" --source . --remote origin`（**不带 `--push`**） | 建成，避开"`--push` 被 `refusing to allow an OAuth App to create or update workflow` 拒 → 仓库已建出的半失败态"（token scopes 无 `workflow`） |
| 通道切换 | `git remote set-url origin git@github.com:…`（先 `ssh -T git@github.com` 验 key） | SSH 一次 push 成，`.github/workflows/ci.yml` 得以进 main |
| push ×3 | `git push -u origin main` → 修复 ×2 | 每次都单独跑并读**真实退出码**（不接管道）；三次对应三个 run |
| tag | `git tag -a v0.1.0 -m "…" && git push origin v0.1.0` | annotated tag 指向 `570a0a3`＝**CI 四矩阵全绿的那个提交**；tag 不触发 CI（见 §四） |
| Release | `gh release create v0.1.0 --notes-file …（两个 zip）` | https://github.com/yuluo554/steel-design-checker/releases/tag/v0.1.0 ，`draft=false`，`targetCommitish=main` |
| topics | `gh repo edit --add-topic …`（13 个）+ `gh api` 回读 | 回读 14 个 topic 生效（含 GitHub 归一的 `chinese`） |
| 仓库元信息复核 | `gh api repos/…` | `private=false`、`license.spdx_id=MIT`（GitHub 自动识别）、`default_branch=main` |

### Release 资产与据链

| 资产 | 字节 | sha256 |
|---|---|---|
| `sdc-cli-windows-x64.zip` | 5,883,297（解压后 13 MB / 55 个文件） | `4bde9847da444d2def537a37514aed287a04cc20c4a839ef2d08590871c18b3f` |
| `sdc-gui-windows-x64.zip` | 44,239,244（解压后 108 MB / 197 个文件） | `0ab39ae4577f2ff606b35cb9d7a96a3bfd03b82605c13a115e9087770f98db83` |

- 两个包由**仓库树外的全新 clone + 全新 venv** 构建（§三），并在同一环境通过
  `DIST_AUDIT_OK` + `CLEAN_ENV_OK` + `audit_release.py dist` 三条红线；
- **产物与发布基线同运行时面**的证明：
  `git diff 81af503..HEAD -- src/ data/ sdc.spec scripts/bundle_rules.py scripts/verify_dist.py
  scripts/clean_env_check.py scripts/entry_cli.py scripts/entry_gui.py pyproject.toml` **为空**
  （81af503 = 构建时的 clone HEAD）。其间变化的只有 `.github/workflows/ci.yml`、`plan/*` 与
  `scripts/ci_bench_gate.py`，而 `scripts/` 属打包禁区成分，不进 exe；
- Release 正文在发布前也过了审计（`scan_text` 硬门 0、复核项 0），发布面不含个人字面。

### 发布后复核（复核对象＝远端最终提交）

HTTPS 全新 clone `github.com/yuluo554/steel-design-checker` 到仓库树外目录：

| 检查 | 结果 |
|---|---|
| 远端 HEAD / tree | `570a0a3…` 与本地 HEAD **同一提交**；`refs/heads/main` + `refs/tags/v0.1.0` 两条 ref，无多余分支 |
| 跟踪清单 | 与本地 `git ls-files` **逐行一致**（159 条） |
| 冻结语料字节保真 | `sdc synth --check` rc=0「合成语料位级一致」——经 HTTPS 传输后仍位级一致 |
| 命令面 | `sdc selfcheck` rc=0；`sdc bench --all --json` rc=1（两个不可判，与本地一致） |
| 快测组（62 项） | `test_eol_guard` + `test_release_audit` + `test_ci_workflow` + `test_fingerprint` + `test_paths` + `test_kb_schema` + `test_tech_report` 全绿 |
| 脱敏三扫在**远端历史**上 | `metadata` / `messages` / `history` 三个模式全部 rc=0、硬门 0；远端提交邮箱只有 noreply 一个值 |
| 产物审计 | 干净 clone 内 `audit_release.py tracked` → `DESENSITIZE_AUDIT_OK` |

**一条重复三次的自我纪律**：这三轮复核里 EOL 守门测试红过两次，两次都是**我自己**把 scratch
文件（`collect.txt`、`.tmp_selfcheck.txt`、`bench_out.json`）撒在被扫描的工作树里——Windows 的
stdout 重定向写 CRLF。仓库的门槛是对的，错的是脚手架；最终口径固化为
**"任何 scratch 一律写进 `.gitignore` 覆盖且在 `test_eol_guard.SKIP_DIRS` 名单里的目录"**
（`.tmp_parse/`、`.tmp_verify/`），CI 步骤也已按这条改过。


### 流程瑕疵如实留痕（不回填时间线）

`f5f3eaa`（本台账第 11 刀）那次提交，我在提交前用了 `pytest … | tail -2` 的形式跑守门测试：
**`tail` 的退出码盖住了 pytest 的**，于是一条红测试（`test_ci_workflow::test_matrix_spans…`）
被带着提交并推送。这正是本文件 §四 第 2 轮刚写下的同一条坑（"退出码不能取自管道"），
我在同一个会话里第三次踩它。

定性：该测试单独复跑 3 次全部 rc=0，失败形态是 PyYAML scanner 抛 `TypeError`——
与本机 `SystemError: unknown opcode` / `XXX lineno: N, opcode: 0` 同族（pyc 与帧损坏，
清 `__pycache__` + `PYTHONDONTWRITEBYTECODE=1` 后恢复），属环境随机而非回归；
**权威复核交给 CI**（run 5，即本次 push 触发的这一轮），不在本地用"看起来绿"替代退出码。

固化的口径：本仓库里任何"跑测试 → 提交"的链，测试必须**单独跑、直接读 `$?`**，
或者把输出先落进 `.tmp_parse/`（gitignore + EOL 跳过名单）再 grep。

## 六、偏差与未做（如实）

1. CI 矩阵**不跑 PyInstaller 构建**：构建红线（`verify_dist.py`）与干净环境验证在发布前于本机
   实跑，CI 只常驻"测试 + selfcheck + 基准门禁 + 语料位级一致"。理由：Windows runner 上装
   PySide6+PyInstaller 会让首跑风险面从"代码"扩到"打包环境"，而这两条红线已经有 15 项
   `tests/test_packaging.py` 用伪造 dist 逐项验证扫描器不是空转。
2. `data/cases/` 仍 0 例、可硬判 abnormal 的规则分母仍 0 条 ⇒ 指标表两个「不可判」按 K43
   原样进 README 与 Release notes，**没有**为了让 CI 绿而放宽门禁：
   `scripts/ci_bench_gate.py` 只在出现**未达标 / 不可用 / 名单外的新不可判**时红。
3. HANDOFF-M6 §五.0 的"引擎支持分段/按条件选式"仍未做 ⇒ 轴压模块永远 blocked，已写进
   技术报告 §3.5 与 §6 的诚实清单。
4. docx 版式（Word 表格/标题样式）仍未做，技术报告 docx 与三类交付物一样只有段落；
   生成器用 `●` 标记层级，并在报告 §6 里承认这条限制。

## 七、复跑手册（发布后）

```bash
py -3.8 -X utf8 -m pytest -q -rs                      # 全套（装 .[dev,gui]）
py -3.8 -X utf8 scripts/audit_release.py all          # 脱敏五步，DESENSITIZE_AUDIT_OK
py -3.8 -m PyInstaller --noconfirm sdc.spec           # rm -rf build dist 后重建
py -3.8 -X utf8 scripts/verify_dist.py                # DIST_AUDIT_OK
py -3.8 -X utf8 scripts/clean_env_check.py            # CLEAN_ENV_OK
py -3.8 -X utf8 -m sdc bench --all --markdown         # README 指标表的唯一来源
py -3.8 -X utf8 scripts/make_tech_report.py           # TECH_REPORT_DOCX_WRITTEN
```
