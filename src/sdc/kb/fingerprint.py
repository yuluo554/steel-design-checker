"""数据指纹（口径 K12）。

`data_fingerprint = sha256(data/clauses + data/tables 规范化拼接)`。
规范化 = 按相对路径排序 + JSON 重新序列化（键排序、紧凑分隔符、UTF-8），
所以缩进与键顺序的排版改动不会改变指纹，而任一数值或条号改动一定会改变指纹。
算法或计入目录的变更属口径变更，需在 plan/06 登记。
"""

import hashlib
import json
import os
from typing import Iterable, Tuple

SIGNED_DIRS = ("clauses", "tables")


def _files(data_dir: str, subdirs: Iterable[str]) -> Iterable[Tuple[str, str]]:
    for sub in sorted(subdirs):
        directory = os.path.join(data_dir, sub)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if name.endswith(".json"):
                # 相对路径用正斜杠：反斜杠进指纹会让 Windows 与 Linux 算出不同值
                yield "%s/%s" % (sub, name), os.path.join(directory, name)


def _normalize(raw: bytes) -> bytes:
    try:
        obj = json.loads(raw.decode("utf-8"))
    except ValueError:
        # 解析失败的文件按原始字节计入：仍然可复现，问题由 schema 校验另行报出
        return raw
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def data_fingerprint(data_dir: str, subdirs: Iterable[str] = SIGNED_DIRS) -> str:
    digest = hashlib.sha256()
    for rel, path in _files(data_dir, subdirs):
        with open(path, "rb") as handle:
            raw = handle.read()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_normalize(raw))
        digest.update(b"\0")
    return digest.hexdigest()
