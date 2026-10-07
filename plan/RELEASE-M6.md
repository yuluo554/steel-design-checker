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

### ④ 改写执行记录

待回填：备份 bundle → `git filter-branch --env-filter` → 清 `refs/original` + reflog + gc →
三扫（逐提交 blob grep / `git log --all -p` / 提交信息）→ `git config user.email` 同步。
字面值不入仓，终验在仓外用固定字面执行。

**阳性对照不是形式**：首轮 selftest 抓出两处扫描器自身的问题——邮箱正则把域名要求成"至少三段"
（两段域，形如 `<本地部分>@<服务商>.com`，被放行），以及 `\.env$` 前面多加了路径分隔符锚
（`prod.env` 这类根目录形态放行）。两条都由 selftest 的阳性样本逼出，修完才继续。

**审计器自引用坑（本文件与脚本都踩过）**：`audit_release.py` 的 selftest 夹具最初直接写了
内网 IP 与邮箱的完整字面，于是扫描器命中自己 ⇒ 样本一律改成**片段拼接**；姊妹词表 base64 存放；
输出只给 `位置 [类别] xN`。

## 三、干净环境复核

待回填：新目录 `git clone` + 全新 venv，按 README **原文逐字**跑；dev 与干净环境收集数对照
与逐项归因（声明式跳过一条条指认）。

## 四、CI 首跑

待回填：`gh run list` 对账 push 数 = run 数；四矩阵 passed/skipped 逐项归因。

## 五、发布执行记录

待回填：建仓、push、tag、Release（两个 zip + sha256）、topics。

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
