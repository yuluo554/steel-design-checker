"""核查报告文本渲染（`sdc check` 默认输出）。

排序、无时间戳，同一 IR + 同一数据目录 ⇒ 字节一致（口径 K8）。
"""

from typing import Any, Dict

_MARK = {"abnormal": "异常", "suspicious": "可疑"}


def render_report(report: Dict[str, Any]) -> str:
    out = ["=" * 72, "sdc check（设计说明文本核查）", "=" * 72]
    doc = report["doc"]
    out.append("文档：%s（%s，%d 段，sha256=%s）" % (
        doc.get("name", ""), doc.get("format", ""), doc.get("paragraph_count", 0),
        str(doc.get("sha256", ""))[:12]))
    out.append("规则库：%d 条；data_fingerprint：%s" % (
        report["rules_total"], report["meta"]["data_fingerprint"][:12]))
    out.append("文档级结论：%s（异常 %d / 可疑 %d）" % (
        report["conclusion"], report["counts"]["abnormal"], report["counts"]["suspicious"]))
    out.append("")

    if not report["findings"]:
        out.append("未发现非 pass 项。注意：这不等于合规——依据未核对的规则未启用，见下表。")
    for finding in report["findings"]:
        out.append("[%s] %s %s" % (_MARK.get(finding["level"], finding["level"]),
                                   finding["rule_id"], finding["name"]))
        out.append("    判定：%s（依据档位 %s，%s）" % (
            finding["outcome"], finding["status"], ", ".join(finding["basis"]) or "无依据登记"))
        if finding["detail"]:
            out.append("    事实：%s" % finding["detail"])
        if finding["clause_ids"]:
            out.append("    条款：%s" % ", ".join(finding["clause_ids"]))
        for item in finding["evidence"]:
            where = "第 %d 段" % item["para"] if item["para"] is not None else "全文"
            out.append("    原文（%s）：%s" % (where, item["text"]))
        if finding["also_expect"]:
            out.append("    连带：%s" % "；".join(finding["also_expect"]))
        if finding["suggestion"]:
            out.append("    建议：%s" % finding["suggestion"])
        out.append("")

    if report.get("mandatory_clause_ids"):
        out.append("命中强制性条文（50017 的 7 条清单见 06 D14；GB 55006-2021 全文强制）：")
        for clause_id in report["mandatory_clause_ids"]:
            out.append("  ！ %s —— 请同步核对强条要求与检验记录" % clause_id)
        out.append("")

    if report["not_activated"]:
        out.append("未启用的规则（类目未命中 / 阈值未核对 / 闸门表不出结论）：")
        for item in report["not_activated"]:
            out.append("  - %s：%s" % (item["rule_id"], item["reason"]))
        out.append("")

    out.append("免责声明：%s" % report["disclaimer"])
    return "\n".join(out)
