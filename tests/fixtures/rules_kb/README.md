# rules_kb：核查规则与检查单的 verified 档夹具（M3）

和 `tests/fixtures/kb/` 同一个道理（决策 D17、口径 K25）：

- 真实 `data/` 里，任何核查规则的**依据条款**都只到 `located`（表体数值与式体尚未与正式文本
  核对），按 plan/04 §四 的闸门表，presence/limit/construct 规则最高只能判 `suspicious`；
- 于是"规则升 verified 后能出 `abnormal`"这半张矩阵在真实数据上永远跑不到；
- 本夹具用**虚构**条款（`FX-C-*`，渠道 `合成夹具`）+ 虚构规则（`FX-R-*`）把这条路跑通，
  并额外放一条「规则自称 verified、依据只 located」的陷阱用例（`FX-R-HF-CAPPED`），
  证明有效档位取 min 而不是取规则自己的声明。

夹具里的数值（焊脚 5/6mm、等级下限"二级"）都是编的，**不构成任何规范结论**；
`data/` 里出现 `FX-` id 或 `合成夹具` 渠道即测试失败（`tests/test_engine_fixtures.py`）。
