"""知识库加载：目录扫描 → JSON 解析 → schema 校验 → 引用完整性检查。

一次收集全部问题（不在第一个错误就抛出），因为 `sdc selfcheck` 要输出完整的问题与 pending 看板。
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from .schema import SPEC, validate_record

KINDS = ("clause", "table", "formula", "symbol", "rule", "checklist", "case", "selfcheck")

# (kind, 相对文件路径, 记录)
Parsed = Tuple[str, str, Dict[str, Any]]


class KB(object):
    def __init__(
        self,
        data_dir: str,
        records: Dict[str, List[Dict[str, Any]]],
        problems: List[Dict[str, str]],
    ):
        self.data_dir = data_dir
        self.records = records
        self.problems = problems

    def id_of(self, kind: str, rec: Dict[str, Any]) -> str:
        return str(rec.get(SPEC[kind]["id_field"], ""))

    def by_id(self, kind: str) -> Dict[str, Dict[str, Any]]:
        return dict((self.id_of(kind, rec), rec) for rec in self.records.get(kind, []))

    def status_of(self, kind: str, item_id: str) -> Optional[str]:
        rec = self.by_id(kind).get(item_id)
        return rec.get("status") if rec else None

    def problems_of(self, ptype: str) -> List[Dict[str, str]]:
        return [p for p in self.problems if p.get("type") == ptype]

    @property
    def blocking_problems(self) -> List[Dict[str, str]]:
        """结构、引用、解析、重复 id 中任一问题都算数据不可用。"""
        return self.problems

    def has_problems(self) -> bool:
        return bool(self.problems)


def _iter_json_files(directory: str):
    if not os.path.isdir(directory):
        return
    for name in sorted(os.listdir(directory)):
        if name.endswith(".json"):
            yield name, os.path.join(directory, name)


def load_kb(data_dir: str) -> KB:
    records = dict((kind, []) for kind in KINDS)  # type: Dict[str, List[Dict[str, Any]]]
    problems = []  # type: List[Dict[str, str]]
    parsed = []  # type: List[Parsed]
    # id 唯一性按 kind 分别成立：检查单条目的 id 就应当等于它对应的条款 id（04 §五），
    # 跨 kind 同 id 不是冲突，`by_id(kind)` 本来也分 kind 查。
    origin = {}  # type: Dict[Tuple[str, str], str]

    for kind in KINDS:
        spec = SPEC[kind]
        directory = os.path.join(data_dir, spec["dir"])
        for name, path in _iter_json_files(directory):
            where = "%s/%s" % (spec["dir"], name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    payload = json.loads(handle.read())
            except ValueError as exc:
                problems.append({"file": where, "kind": kind, "id": "", "field": "",
                                 "type": "parse", "problem": "JSON 解析失败：%s" % exc})
                continue
            except OSError as exc:
                problems.append({"file": where, "kind": kind, "id": "", "field": "",
                                 "type": "parse", "problem": "文件读取失败：%s" % exc})
                continue
            for rec in (payload if isinstance(payload, list) else [payload]):
                records[kind].append(rec)
                parsed.append((kind, where, rec))
                if isinstance(rec, dict):
                    item_id = str(rec.get(spec["id_field"], ""))
                    if item_id:
                        # 只在同一 kind 内查重：检查单条目的 id 天然等于其条款 id（04 §五），
                        # 跨 kind 同 id 不是冲突（`by_id(kind)` 本来就分 kind 取）。
                        key = (kind, item_id)
                        if key in origin:
                            problems.append({
                                "file": where, "kind": kind, "id": item_id,
                                "field": spec["id_field"], "type": "duplicate",
                                "problem": "同类记录 id 重复（已见于 %s）" % origin[key],
                            })
                        else:
                            origin[key] = where

    known_ids = dict(
        (kind, set(r.get(SPEC[kind]["id_field"], "") for r in recs if isinstance(r, dict)))
        for kind, recs in records.items()
    )

    for kind, where, rec in parsed:
        problems.extend(validate_record(kind, rec, where, known_ids))

    return KB(data_dir, records, _dedup(problems))


def _dedup(problems: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    out = []
    for item in problems:
        key = tuple(sorted(item.items()))
        if key not in seen:
            seen.add(key)
            out.append(item)
    return sorted(out, key=lambda p: (p["file"], p["kind"], p["id"], p["field"], p["type"]))
