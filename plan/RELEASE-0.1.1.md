# RELEASE-0.1.1：发布台账（2026-10-22）

> 上一份台账是 `plan/RELEASE-M6.md`（v0.1.0，2026-10-07）。**本文件只记 0.1.1**，
> 不重写历史。**v0.1.0 的 tag 与 Release 原样保留**，本版是新增不是替换。
>
> 两节结构：§一 记 **tag 时点**能写在源码里的事实；§二 记 **tag 之后**才知道的事实
> （附件 sha256 / CI run 号 / 真下载复验）——这些值不可能出现在 tag 树自身里，
> 所以按本仓口径不写进 zip、只留在 Release 说明与本文件。

---

## 一、tag 时点事实（这些值已随 tag 进入源码树）

### 起因：0.1.0 之后 7 个提交从未发版

```
$ git rev-list --count v0.1.0..HEAD      # 修前
7
$ git log --oneline v0.1.0..HEAD
6d27a98 feat: 报告头写入依据规范 + 规则集 meta.review + CHANGELOG + GUI 抓帧时序修复（阶段三 任务 3/5，P1-1）
16ce5da docs: restructure README as product page; move dev details to DEVELOPMENT.md (#2)
e12f20a chore: add issue templates for bug and rule-error reports (#1)
41684eb M6 发布门（十三）：CI 对账定格在六轮，台账设终点
23a5ae4 M6 发布门（十二）：流程瑕疵留档——退出码取自管道的第三次踩坑
f5f3eaa M6 发布门（十一）：CI 第四轮复绿入台账，发布收尾定格
afbe1bd M6 发布门（十）：收官回写——CI 三轮对账、发布记录与发布后复核
```

7 个里有 3 个是**代码**改动（`src/sdc/gui/app.py`「GUI 抓帧时序修复」、
`src/sdc/report/body.py`「报告头写入依据规范」、`scripts/bundle_rules.py`）+ 新增
`tests/test_clause_review.py`（129 行）。Release 上那两个 exe 停在 `v0.1.0` 时点，
**不含**这些修复；而 `main` 的版本号仍是 `0.1.0`，用户靠版本号区分不了。

### 本版改了什么

| # | 改动 | 对应缺陷 |
|---|---|---|
| 1 | 版本 `0.1.0 → 0.1.1`（`pyproject.toml` + `src/sdc/__init__.py`）；`CHANGELOG` 的 `[Unreleased]` 落成 `## [0.1.1] - 2026-10-22` | D1 |
| 2 | **从当前 HEAD 重打两个 exe**（不复用旧 `dist/`），重算 `SHA256SUMS.txt` | D1 |
| 3 | `sdc bench --allow-indeterminate`：分母 0 的「不可判」不计失败，只有「未达标」exit 1 | D3（DEC2=A） |
| 4 | 删 `pyproject.toml` 的 `report` / `pdf` 两个 extra（代码里 0 使用） | D4 |
| 5 | 删 `src/sdc/engine/expr.py` 的 `ast.Num` 冗余兜底 → pytest warnings **1735 → 0** | D2 |
| 6 | `.gitignore` 加 `update/`；`tests/test_eol_guard.py` 的 `SKIP_DIRS` 加 `update` | 批次 0.2 / C.1 |
| 7 | CI 加 `No CRLF committed to the index`（`git ls-files --eol \| grep i/crlf`） | 批次 C.2 |
| 8 | CI 基准门禁带 `--allow-indeterminate`，`scripts/ci_bench_gate.py` 按旗标对账退出码 | D3 联动 |

### 决策记录（用户 2026-10-22 拍板）

- **DEC1 = A**：发 `v0.1.1` 并**重打两个 exe**（不是只发源码，也不移动 `v0.1.0` tag）。
  理由：本仓卖点就是免安装 exe，只发源码会让首屏「桌面版 + CLI」落空；
  移动已公开引用的 tag 属改写历史，违反本仓发布纪律。
- **DEC2 = A**：给 `bench` 加 `--allow-indeterminate`，把「不可判」从 exit 1 里摘出来。
  代价是加一个参数 + 改 CI；收益是「以后补齐算例时这个门能自动生效」这件事保住了。
  **默认不带旗标时行为与 0.1.0 完全一致（仍 exit 1）**，因此这是纯增量。

### 基线（改前实测，2026-10-22）

| 项 | 值 |
|---|---|
| 起点 HEAD | `6d27a98ecdcb26c8e4efebee1563daa8e50b1be1`（2026-10-19） |
| 起点 tag | `v0.1.0` = `570a0a32ebffc754ac177e410fb24592693c0df6`（annotated），**落后 7 提交** |
| 起点版本 | `pyproject.toml` = `0.1.0`；包名 `sdc` |
| 起点测试（三档） | `301 passed, 3 skipped`（`-e .`）/ `309 passed, 2 skipped`（`.[dev]`）/ **`340 passed, 1735 warnings`**（`.[dev]` + PySide6） |
| 起点 `selfcheck` | exit 0，「合计 116 条条款在挡着 126 项判定」 |
| 起点 `bench` | exit 1（分母 0，「不可判」）；9 个自校验样例全 `[OK]` |
| 数据指纹 | `235a0c1453adf7e715ca2594c0df64b31e1b0b2ffa0413fc52f732d7daeeccf4` |

**测试数随 extras 变**（这是本轮的基线口径修正）：0.1.0 的诊断稿只写 340 又同时声称
「本机未装 PySide6」，两者不可能同时成立。复验时必须报装法。

### 改后实测（tag 前，本机）

| 项 | 值 | 命令 |
|---|---|---|
| 版本 | `sdc 0.1.1` | `python -m sdc --version` |
| 全档测试 | **344 passed, 0 warnings**, exit 0 | 新建 venv：`-e ".[dev]"` + `PySide6>=6.4,<6.7` |
| 开发档测试 | **313 passed, 2 skipped**, exit 0 | 新建 venv：`-e ".[dev]"` |
| 核心档测试 | **304 passed, 3 skipped**, exit 0 | 新建 venv：`-e .` + `pytest` |
| 测试增量 | 301→304 / 309→313 / 340→344（+3 / +4 / +4；全档 warnings 1735→0） | 三档各建独立 venv |
| `selfcheck` | exit 0，「合计 116 条条款在挡着 126 项判定」（**未变**） | `sdc selfcheck` |
| `bench`（严格） | exit **1**（分母 0） | `sdc bench` |
| `bench --allow-indeterminate` | exit **0**，输出仍写「分母 0，样本待补」+ 说明本次是放行档 | `sdc bench --allow-indeterminate` |
| `bench --all`（严格） | exit **1**（达标 7 / 不可判 2） | `sdc bench --all` |
| `bench --all --allow-indeterminate` | exit **0**（同上，不可判仍逐项列出） | `sdc bench --all --allow-indeterminate` |
| `bench --parse --allow-indeterminate` | exit **2**（该旗标只作用于分母 0，不对缺 IR 放宽） | — |
| 数据指纹 | `235a0c14…`（**未变**） | `sdc.kb.fingerprint.data_fingerprint("data")` |
| 受控文件 | 167 → 168（新增本文件） | `git ls-files \| wc -l` |

### 构建（从当前 HEAD 树，不在仓库里建 .venv）

```bash
# 3.8.8 构建环境建在 %TEMP%，与 v0.1.0 同解释器线
%TEMP%\sdc-build38\Scripts\python.exe -m pip install "pyinstaller>=6.0,<7" "PySide6>=6.4,<6.7"
%TEMP%\sdc-build38\Scripts\python.exe -m pip install -e ".[dev,pkg]"
rm -rf build dist
PYTHONDONTWRITEBYTECODE=1 %TEMP%\sdc-build38\Scripts\python.exe -m PyInstaller --noconfirm sdc.spec
```

| 项 | 值 |
|---|---|
| 解释器 | Python **3.8.8**（与 v0.1.0 同线；`installer` 与 `PySide6` 版本都一致） |
| PyInstaller | **6.22.3**（与 v0.1.0 构建时同版本） |
| PySide6 | **6.6.3.1**（3.8 上可解析的最高版本，`pyproject` 两端 pin） |
| 产物规模 | `dist/sdc-cli` 55 个文件 / 13 MB；`dist/sdc-gui` 197 个文件 / 108 MB |
| 与 v0.1.0 对比 | 文件数**逐个相同**（55 / 197），体积同级 |

三条构建红线（全过）：

```
scripts/verify_dist.py         → DIST_AUDIT_OK（禁区成分 0；内嵌数据 40 份逐份 sha256 对账）
scripts/clean_env_check.py     → CLEAN_ENV_OK（中立 CWD + 剥离 PATH 跑双 exe）
scripts/audit_release.py dist  → DESENSITIZE_AUDIT_OK（硬门 0 / 复核项 0）
```

打包后的 exe 实跑（**这是「产物与代码一致」的直接证据**，不只是 sha256 对得上）：

```
dist/sdc-cli/sdc-cli.exe --version                     → sdc 0.1.1        rc=0
dist/sdc-cli/sdc-cli.exe selfcheck                     →                  rc=0
dist/sdc-cli/sdc-cli.exe bench --allow-indeterminate    →                  rc=0
dist/sdc-cli/sdc-cli.exe bench                          →                  rc=1
```

### 附件（tag 时点打包，值见 §二）

`dist/` 与 `build/` 都在 `.gitignore` 内，产物不进仓库；zip 按 v0.1.0 的布局打
（顶层 `<包名>/` 目录、deflate、含目录条目）。

---

## 二、tag 之后追加的事实（这些值不可能出现在 tag 树里）

**口径（本仓已踩过一次）**：台账若被打进附件，就不能写自己的 sha256——那是循环依赖。
故本节的数值同时写进 **Release 说明**与 **tag 消息**，本文件只记不变量与结论。

### 附件与据链

| 资产 | 字节 | sha256 |
|---|---|---|
| `sdc-cli-windows-x64.zip` | 5,866,621 | `6f60c78410c01a86765dd6494a60a560d6bc06898e1fb23d8350dc32654a1dfe` |
| `sdc-gui-windows-x64.zip` | 44,052,547 | `dafca2fd64ee5faf5f791e39cbf7a5d053360c4c39da7b1075ec0e5ed24feb4f` |
| `SHA256SUMS.txt` | 180 | （见 Release） |

**三方对撞**：本地实算 = `SHA256SUMS.txt` = Release API `digest`，逐位一致（复验命令见下）。

### 新 tag 与 CI

| 项 | 值 |
|---|---|
| tag | `v0.1.1`（annotated），指向 `39338d7b41880e221e3a5c048aebbe02336a013f` = CI 绿的那个提交 |
| `git rev-list --count v0.1.1..HEAD`（**tag 时刻**） | **0** |
| `git rev-list --count v0.1.1..HEAD`（**收尾提交后**） | **1** —— 见下「tag 后补录」 |
| `v0.1.0` 的 tag 与 Release | **未动**（`570a0a32…` 与 3 个旧附件原样） |
| CI（tag 时刻） | run **`39703164118`** @ 2026-10-22 → **success**（4/4 job） |
| CI（收尾提交） | run **`39703952199`** @ 2026-10-22 → **success**（4/4 job） |
| `git rev-list --count v0.1.0..HEAD` | **9** = 原 7 + 发布提交 + 收尾提交（旧版仍滞后，说明探针有效） |

### tag 后补录（本仓既定形态，D26④）

tag 之后有一个**纯文档**提交 `f2c4f42`（`docs: v0.1.1 收尾 —— 状态位与口径账本同步`），
改的是 `README.md` 与 `plan/00|05|06`，把里程碑 🚧→✅、补 D27 与 K43 粒度修正行。

**这是一致性风险，所以给出「发布物仍与代码一致」的直接证据**：

```
$ git diff --stat v0.1.1..HEAD -- src/ data/ pyproject.toml sdc.spec \
      scripts/entry_cli.py scripts/entry_gui.py scripts/bundle_rules.py
（空输出）
```

即 **构建输入零改动** ⇒ tag 上的两个 exe 与当前代码的运行时面完全相同，
收尾提交不可能改变任何产物字节。

**为什么不把 tag 挪到 `f2c4f42`**：D26④ 的原文就是「CI run id 与 Release URL 用
**tag 后小提交补录，不迁 tag**」。v0.1.0 时的台账 §五 也是这么做的（发布后回填）。
迁 tag 会让「被 CI 验过的那个提交」与 tag 指向脱钩，反而更难追溯；
而 `v0.1.1..HEAD` 这个数字本身不区分「文档补录」与「代码滞后」，
所以本仓的口径是**用 `-- src/ data/` 的 diff 判代码是否滞后，而不是只看计数**。

### 附件复验（真下载，2026-10-22）

```
gh release download v0.1.1 --dir dl --clobber      → 3 件齐、字节数对上
sha256sum sdc-cli-windows-x64.zip sdc-gui-windows-x64.zip
  6f60c78410c01a86765dd6494a60a560d6bc06898e1fb23d8350dc32654a1dfe  sdc-cli-windows-x64.zip
  dafca2fd64ee5faf5f791e39cbf7a5d053360c4c39da7b1075ec0e5ed24feb4f  sdc-gui-windows-x64.zip
cat SHA256SUMS.txt                                 → 同上两行（逐位一致）
gh release view --json assets --jq '.digest'        → 同上两值 + SHA256SUMS.txt 的 ebd3703e…
sha256sum -c SHA256SUMS.txt                         → 2/2 OK
```

解包实跑（**这是「发布物与代码一致」的直接证据**）：

```
cli/sdc-cli/sdc-cli.exe --version                    → sdc 0.1.1   rc=0
cli/sdc-cli/sdc-cli.exe selfcheck                    →             rc=0（合计 116 条挡 126 项）
cli/sdc-cli/sdc-cli.exe bench                        →             rc=1（分母 0）
cli/sdc-cli/sdc-cli.exe bench --allow-indeterminate  →             rc=0
```

### 复跑手册

```bash
# 1) tag 滞后：计数会含 tag 后的纯文档补录，所以**代码是否滞后看 diff 而不是只看数字**
git rev-list --count v0.1.1..HEAD                 # tag 时刻 0；收尾提交后 1（纯文档）
git diff --stat v0.1.1..HEAD -- src/ data/ pyproject.toml sdc.spec \
    scripts/entry_cli.py scripts/entry_gui.py scripts/bundle_rules.py
                                                  # 期望：(空输出) = 构建输入零改动
git rev-list --count v0.1.0..HEAD                 # 期望 9（原 7 + 发布 + 收尾）＝旧版仍滞后

# 2) 附件三方对撞
gh release download v0.1.1 --repo yuluo554/steel-design-checker --dir dl --clobber
cd dl && sha256sum sdc-cli-windows-x64.zip sdc-gui-windows-x64.zip && cat SHA256SUMS.txt
gh release view v0.1.1 --repo yuluo554/steel-design-checker --json assets \
  --jq '.assets[]|"\(.name) \(.size) \(.digest)"'

# 3) 产物实跑（版本必须是 0.1.1 —— 0.1.0 是旧构建的标志）
python -c "import zipfile; zipfile.ZipFile('sdc-cli-windows-x64.zip').extractall('cli')"
cd cli/sdc-cli && ./sdc-cli.exe --version && ./sdc-cli.exe selfcheck

# 4) 全档测试（装法必须报清楚，否则数字对不上）
python -m pip install -e ".[dev]" && python -m pip install "PySide6>=6.4,<6.7"
python -X utf8 -m pytest tests > log.txt 2>&1; echo $?    # 期望 344 passed，0 warnings
```

### 已知未覆盖

- **GUI 实机目检**：本机无图形环境，只做了 GUI zip 的解包与 `clean_env_check` 的
  `gui-alive`（rc=0）。需人启动 `sdc-gui.exe` 过五个页签。
- **3.8 实跑测试**：本机有 3.8.8 且构建就是用它，但 `pytest tests` 未在 3.8 上跑
  （本轮测试用 3.12 + PySide6）。CI 的 3.8×2 矩阵会覆盖。
- **`data/` 下 100+ 条款文件是否都被规则引用**：未逐个核（0.1.0 诊断时也留为未验证）。

### 与 0.1.0 的差异（如实）

| 项 | 0.1.0 | 0.1.1 |
|---|---|---|
| 判定结论 | 5 个模块对真实数据全 `blocked` | **相同**（未改任何条款/表值/公式/阈值） |
| 数据指纹 | `235a0c14…` | **相同** |
| 条款挡板 | 116 条挡 126 项 | **相同** |
| `sdc bench`（严格） | exit 1 | exit 1（**行为未变**） |
| `sdc bench --allow-indeterminate` | 参数不存在（exit 2） | exit 0，「不可判」放行、「未达标」仍红 |
| pytest warnings | 1735 | **0** |
| extras | dev / gui / report / pdf / pkg | dev / gui / pkg（`report` `pdf` 已删） |
| exe 内含代码 | tag 时点（不含 GUI 抓帧时序修复、不含报告头依据） | 当前 HEAD（含） |

**是否需要重跑历史报告**：否。判定结论未变，交付物差异仅为报告头那几行依据。
