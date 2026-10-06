"""合成语料生成器 v0：位级一致、注入语义、docx 无时间戳无外链。"""

import io
import io
import json
import os
import zipfile

from sdc import cli
from sdc.synth.generator import (CLEAN_COUNT, DOC_COUNT, INJECTION_TYPES,
                                 compare_corpus, corpus_payloads, generate_corpus)
from sdc.synth.rng import SplitMix64

SEED = 20261006


def _docs_by_injection(payloads):
    docs = json.loads(payloads["groundtruth.json"].decode("utf-8"))["documents"]
    return dict((d["doc_id"], d) for d in docs), docs


def test_same_seed_same_bytes():
    assert corpus_payloads(SEED) == corpus_payloads(SEED)


def test_different_seed_different_bytes():
    assert corpus_payloads(SEED) != corpus_payloads(SEED + 1)


def test_corpus_shape():
    payloads = corpus_payloads(SEED)
    manifest = json.loads(payloads["injections.json"].decode("utf-8"))
    assert manifest["doc_count"] == DOC_COUNT
    assert manifest["clean_count"] == CLEAN_COUNT
    assert manifest["injected_count"] == DOC_COUNT - CLEAN_COUNT
    counts = manifest["injection_counts"]
    assert sorted(counts) == sorted(INJECTION_TYPES)
    assert sum(counts.values()) == DOC_COUNT - CLEAN_COUNT


def test_docx_count_matches_groundtruth():
    payloads = corpus_payloads(SEED)
    _by_id, docs = _docs_by_injection(payloads)
    docx_files = sorted(k for k in payloads if k.endswith(".docx"))
    assert len(docx_files) == DOC_COUNT
    assert set(docx_files) == set(d["file"] for d in docs)


def test_weld_class_missing_omits_the_slot():
    by_id, docs = _docs_by_injection(corpus_payloads(SEED))
    hit = [d for d in docs if any(i["type"] == "weld_class_missing" for i in d["injections"])]
    assert hit
    for doc in hit:
        assert "weld_class" not in doc["slots"]
        assert doc["expected_non_pass"]


def test_grade_contradiction_writes_two_different_grades():
    _by_id, docs = _docs_by_injection(corpus_payloads(SEED))
    hit = [d for d in docs
           if any(i["type"] == "steel_grade_contradiction" for i in d["injections"])]
    assert hit
    for doc in hit:
        assert doc["slots"]["grade"] != doc["slots"]["grade_alt"]


def test_bolt_grade_mismatch_uses_low_grade():
    _by_id, docs = _docs_by_injection(corpus_payloads(SEED))
    hit = [d for d in docs if any(i["type"] == "bolt_grade_mismatch" for i in d["injections"])]
    assert hit
    for doc in hit:
        assert doc["slots"]["bolt_grade"] == "4.6"


def test_clean_docs_have_no_injections_and_all_core_slots():
    _by_id, docs = _docs_by_injection(corpus_payloads(SEED))
    for doc in docs:
        if not doc["clean"]:
            assert doc["injections"] and doc["expected_non_pass"]
            continue
        assert doc["injections"] == [] and doc["expected_non_pass"] == []
        for slot in ("grade", "weld_class", "bolt_grade", "surface", "mu", "fire_hour"):
            assert slot in doc["slots"], (doc["doc_id"], slot)


def test_docx_entries_have_no_timestamps_and_no_external_targets():
    payloads = corpus_payloads(SEED)
    for rel, payload in payloads.items():
        if not rel.endswith(".docx"):
            continue
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.namelist().count("word/document.xml") == 1
            stamps = set(i.date_time for i in archive.infolist())
            assert stamps == {(1980, 1, 1, 0, 0, 0)}, rel
            for name in archive.namelist():
                text = archive.read(name).decode("utf-8")
                assert 'TargetMode="External"' not in text, (rel, name)
                if name == "docProps/core.xml":
                    assert "SYNTH_PLACEHOLDER" in text
                    assert "1970-01-01T00:00:00Z" in text


def test_splitmix64_is_pure_and_diverges_by_seed():
    a = [SplitMix64(7).next_u64() for _ in range(3)]
    b = [SplitMix64(7).next_u64() for _ in range(3)]
    c = [SplitMix64(8).next_u64() for _ in range(3)]
    assert a == b and a != c


def test_generate_then_compare_is_clean(tmp_path):
    data_dir = os.path.join(str(tmp_path), "data")
    os.makedirs(os.path.join(data_dir, "clauses"))
    generate_corpus(os.path.join(data_dir, "synth"), SEED)
    assert compare_corpus(data_dir, SEED) == []


def test_hand_edit_is_caught(tmp_path):
    data_dir = os.path.join(str(tmp_path), "data")
    os.makedirs(os.path.join(data_dir, "clauses"))
    generate_corpus(os.path.join(data_dir, "synth"), SEED)
    target = os.path.join(data_dir, "synth", "docx", "SYNTH-0000.docx")
    with open(target, "ab") as handle:
        handle.write(b"x")
    problems = compare_corpus(data_dir, SEED)
    assert any("SYNTH-0000.docx" in p for p in problems)


def test_foreign_file_in_corpus_is_caught(tmp_path):
    data_dir = os.path.join(str(tmp_path), "data")
    os.makedirs(os.path.join(data_dir, "clauses"))
    generate_corpus(os.path.join(data_dir, "synth"), SEED)
    with open(os.path.join(data_dir, "synth", "手工加的一份.json"), "w", encoding="utf-8") as h:
        h.write("{}")
    problems = compare_corpus(data_dir, SEED)
    assert any("未登记文件" in p for p in problems)


def test_cli_synth_check_exit_codes(tmp_path, capsys):
    data_dir = os.path.join(str(tmp_path), "data")
    os.makedirs(os.path.join(data_dir, "clauses"))
    assert cli.main(["--data-dir", data_dir, "synth"]) == 0
    assert cli.main(["--data-dir", data_dir, "synth", "--check"]) == 0
    target = os.path.join(data_dir, "synth", "groundtruth.json")
    with open(target, "ab") as handle:
        handle.write(b"\n")
    assert cli.main(["--data-dir", data_dir, "synth", "--check"]) == 1
