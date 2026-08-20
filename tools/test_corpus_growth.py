"""Тесты tools/corpus_growth.py -- Phase 5 W3 (t-508).

Структура: DoD-ключи 1-10 спеки docs/tasks/2026-08-19_w3-corpus-growth-
spec.md, 23 края S7 поимённо, три лимита по два теста на границе/за,
адверсариальная батарея CLI, негативный контроль счётчика (гигиена
п.6). Синтетика живёт в tmp_path -- живые артефакты репозитория не
портятся (командная гигиена п.7(г)); два теста намеренно используют
РЕАЛЬНЫЙ tools/corpus_manifest.json read-only для интеграционной
сверки с деревом репозитория.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_growth as cg  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

def _write_manifest(root: Path, artifacts, thresholds_version: int = 0, name: str = "manifest.json") -> Path:
    p = root / name
    p.write_bytes(json.dumps(
        {"thresholds_version": thresholds_version, "artifacts": artifacts},
        ensure_ascii=False,
    ).encode("utf-8"))
    return p


def _write_raw_manifest(root: Path, raw: str, name: str = "manifest.json") -> Path:
    p = root / name
    p.write_bytes(raw.encode("utf-8"))
    return p


def _write_file(root: Path, relpath: str, content: bytes) -> Path:
    full = root / relpath
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(content)
    return full


def _art(path, unit="юнит", record_re=r"^R\d+", owner="corpus", bpr_max=None):
    return {"path": path, "unit": unit, "record_re": record_re, "owner": owner, "bpr_max": bpr_max}


def _three_records() -> bytes:
    return "R1 aaa\nR2 bbb\nR3 ccc\n".encode("utf-8")


def _run(argv):
    """main() возвращает exit code; печать перехватывается вызывающим
    тестом через capsys (main пишет через print())."""
    return cg.main(argv)


def _sandbox(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    registry = tmp_path / "logs" / "sidecar.jsonl"
    return root, registry


# ---------------------------------------------------------------------------
# Ключ 1: манифест 19 артефактов, record_re дословно из таблицы S1-S2
# (12 исходных + 3 тела чеков 26/18/13 -- Phase 5 W4-2, 2026-08-19;
#  + 4 тела карты «правило -> сторож» RC-01/04/06/07 -- 2026-08-20)
# ---------------------------------------------------------------------------

EXPECTED_TABLE = {
    "PROCESS/checks/CHK-26.md": (r"^# Тело чека 26\b", "corpus"),
    "PROCESS/checks/CHK-18.md": (r"^# Тело чека 18\b", "corpus"),
    "PROCESS/checks/CHK-13.md": (r"^## 13\(", "corpus"),
    "docs/DECISIONS_FULL.md": (r"^## D-\d{4}\b", "corpus"),
    "docs/FINDINGS.md": (r"^## F-\d+\b", "corpus"),
    "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md": (r"^\d+\. \*\*", "corpus"),
    "docs/POLICY_FULL.md": (r"^## ", "corpus"),
    "docs/SIBLING_MAP.md": (r"^(## Ось \d+|### Класс:)", "corpus"),
    "docs/RULE_COVERAGE.md": (r"^\| + exclude разделители/шапки", "corpus"),
    "DECISIONS.md": (r"^- D-\d{4}", "corpus"),
    "docs/OPERATIONAL_NOTES.md": (r"^## §\d+\.", "corpus"),
    "docs/RETRO_PATTERNS.md": (r"^## ", "corpus"),
    "docs/DECISIONS_ARCHIVE.md": (r"^## D-\d{4}\b", "corpus-archive"),
    "docs/FINDINGS_ARCHIVE.md": (r"^## F-\d+\b", "corpus-archive"),
    "CLAUDE.md": (r"^R\d+[a-z]?\.", "boot-mirror"),
    "docs/rule_coverage/RC-01.md": (r"^## rc\d+-", "corpus"),
    "docs/rule_coverage/RC-04.md": (r"^## rc\d+-", "corpus"),
    "docs/rule_coverage/RC-06.md": (r"^## rc\d+-", "corpus"),
    "docs/rule_coverage/RC-07.md": (r"^## rc\d+-", "corpus"),
}


def test_key1_manifest_has_19_artifacts_verbatim_record_re():
    thresholds_version, raw_artifacts, _ = cg.read_manifest(
        REPO_ROOT / "tools" / "corpus_manifest.json")
    assert thresholds_version == 2
    assert len(raw_artifacts) == 19
    seen = {a["path"] for a in raw_artifacts}
    assert seen == set(EXPECTED_TABLE.keys())
    for a in raw_artifacts:
        expected_re, expected_owner = EXPECTED_TABLE[a["path"]]
        assert a["record_re"] == expected_re, a["path"]
        assert a["owner"] == expected_owner, a["path"]
        # Мир ПОСЛЕ посадки порогов (Lead 2026-08-19, посадка чека 34):
        # corpus-артефакты несут int-порог (замер x1.15), boot-mirror
        # — только null (порог запрещён формой).
        if a["owner"] == "boot-mirror":
            assert a["bpr_max"] is None, f"boot-mirror с порогом: {a['path']}"
        else:
            assert isinstance(a["bpr_max"], int) and a["bpr_max"] > 0, (
                f"corpus-артефакт без назначенного порога: {a['path']}"
            )


def test_key1_delivered_manifest_passes_form_validation_cleanly():
    _, raw_artifacts, _ = cg.read_manifest(REPO_ROOT / "tools" / "corpus_manifest.json")
    valid, defects = cg.validate_entries(raw_artifacts)
    assert defects == []
    assert len(valid) == 19


# ---------------------------------------------------------------------------
# Ключ 2/9/10 + интеграция на реальном дереве
# ---------------------------------------------------------------------------

def test_key2_report_sections_and_fixture_control(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "КОНТРОЛЬ ИСТОЧНИКОВ" in out
    assert "фикстура): 3/3" in out
    assert "АРТЕФАКТЫ" in out
    assert "ДЕФЕКТЫ" in out
    assert "ВЫБЫЛИ" in out
    assert "ИТОГ: сумма байт corpus=" in out
    assert "порогов 0/1" in out
    assert "WARN=0 BREACH=0" in out


def test_key10_real_tree_measures_all_19_artifacts(tmp_path, capsys):
    registry = tmp_path / "sidecar.jsonl"
    rc = _run(["--manifest", str(REPO_ROOT / "tools" / "corpus_manifest.json"),
               "--registry", str(registry), "--root", str(REPO_ROOT)])
    out = capsys.readouterr().out
    assert rc == 0
    for path in EXPECTED_TABLE:
        assert path in out
    assert "фикстура): 3/3" in out


# ---------------------------------------------------------------------------
# Ключ 3: дельта-правило независимо от порогов
# ---------------------------------------------------------------------------

def test_key3_growth_deep_rule_prints_without_thresholds(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", "R1\nR2\n".encode("utf-8"))
    manifest = _write_manifest(root, [_art("a.md", bpr_max=None)])
    _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    capsys.readouterr()
    # второй прогон: те же 2 записи, но байт стало больше -- Δbpr>0 при Δrecords<=0
    _write_file(root, "a.md", "R1 padded with extra bytes here\nR2 also padded a lot more\n".encode("utf-8"))
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "РОСТ ВГЛУБЬ: a.md" in out
    assert "порог" not in out.split("РОСТ ВГЛУБЬ")[1].split("\n")[0]  # строка дельта-правила без порога


# ---------------------------------------------------------------------------
# Ключ 4: сайдкар S4, повторный прогон добавляет строку, --no-write нет
# ---------------------------------------------------------------------------

def test_key4_no_write_flag_does_not_exist():
    with pytest.raises(SystemExit) as exc:
        cg.parse_args(["--no-write"])
    assert exc.value.code == 2  # argparse: неизвестный аргумент


def test_key4_repeat_run_appends_sidecar_line(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    capsys.readouterr()
    assert sum(1 for _ in open(registry, encoding="utf-8")) == 1
    _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    capsys.readouterr()
    assert sum(1 for _ in open(registry, encoding="utf-8")) == 2


# ---------------------------------------------------------------------------
# Ключ 6: --check exit 1 ровно на дефектах формы, exit 0 при BREACH
# ---------------------------------------------------------------------------

def test_key6_check_exit1_on_form_defect(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    manifest = _write_manifest(root, [_art("missing.md")])  # MISSING -> ДЕФЕКТ у --check
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--check"])
    capsys.readouterr()
    assert rc == 1


def test_key6_check_exit0_on_healthy(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--check"])
    capsys.readouterr()
    assert rc == 0


def test_key6_check_does_not_write_sidecar(tmp_path, capsys):
    """O2 (критик t-538, узел найден контрольным прогоном критика --
    --check дописал строку в боевой сайдкар): --check измеряет форму,
    НЕ пишет сайдкар вовсе -- пин на tmp-путях, боевой logs/*.jsonl не
    трогается (командная гигиена п.7г)."""
    root, registry = _sandbox(tmp_path)
    assert not registry.exists()
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--check"])
    capsys.readouterr()
    assert rc == 0
    assert not registry.exists(), "--check не должен создавать/писать сайдкар"


def test_key6_check_repeated_still_never_writes(tmp_path, capsys):
    """Позитивная половина пары: несколько --check подряд -- сайдкар
    по-прежнему не создаётся ни разу (не только на первом прогоне)."""
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    for _ in range(3):
        rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--check"])
        capsys.readouterr()
        assert rc == 0
    assert not registry.exists()


def test_key6_plain_run_writes_exactly_one_line_in_tmp(tmp_path, capsys):
    """Позитивная половина O2: прогон БЕЗ --check по-прежнему пишет
    ровно одну строку сайдкара (перенос записи не тронул поведение
    обычного прогона байтом сверх переноса)."""
    root, registry = _sandbox(tmp_path)
    assert not registry.exists()
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    capsys.readouterr()
    assert rc == 0
    assert registry.exists()
    assert sum(1 for _ in open(registry, encoding="utf-8")) == 1


def test_key6_check_exit0_on_breach_edge20(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", ("R1 " + "x" * 500 + "\n").encode("utf-8"))  # 1 запись, много байт
    manifest = _write_manifest(root, [_art("a.md", bpr_max=10)])  # заведомо BREACH
    rc_plain = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc_plain == 0
    assert "BREACH" in out
    rc_check = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--check"])
    capsys.readouterr()
    assert rc_check == 0  # измеритель не гейт -- BREACH сам по себе не дефект формы


# ---------------------------------------------------------------------------
# S7: 23 края поимённо
# ---------------------------------------------------------------------------

def test_edge01_missing_artifact(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    manifest = _write_manifest(root, [_art("nope.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0  # exit 0 в замере
    assert "MISSING" in out
    assert "сумма байт corpus=0" in out  # MISSING в сумму не входит
    rc_check = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--check"])
    capsys.readouterr()
    assert rc_check == 1  # ДЕФЕКТ в --check


def test_edge02_empty_file_is_not_a_defect(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", b"")
    manifest = _write_manifest(root, [_art("a.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--check"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ПУСТ" in out
    assert "records=0" in out
    assert "bpr=—" in out


def test_edge03_nonempty_zero_records_is_defect(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", b"nothing matches here at all\n")
    manifest = _write_manifest(root, [_art("a.md", record_re=r"^R\d+")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ДЕФЕКТ" in out
    assert "регекс протух" in out
    rc_check = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--check"])
    capsys.readouterr()
    assert rc_check == 1


def test_edge04_non_utf8_bytes_exact_decode_warn(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    raw = "R1 текст\nR2 текст\n".encode("cp1251")  # не валидный UTF-8 полностью
    _write_file(root, "a.md", raw)
    manifest = _write_manifest(root, [_art("a.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert f"bytes={len(raw)}" in out
    assert "WARN: не-UTF8 в a.md" in out


def test_edge05_crlf_bytes_as_on_disk_records_on_normalized(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    raw = b"R1 aaa\r\nR2 bbb\r\nR3 ccc\r\n"
    _write_file(root, "a.md", raw)
    manifest = _write_manifest(root, [_art("a.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert f"bytes={len(raw)}" in out
    assert "records=3" in out


def test_edge06_first_run_bazy_net(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    assert not registry.exists()
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "БАЗЫ НЕТ" in out
    assert "| новый |" in out
    assert registry.exists()  # сайдкар создан


def test_edge07_broken_sidecar_line_skipped_with_warn(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text('{"ts": "not json' + "\n", encoding="utf-8")
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "WARN: битая строка сайдкара" in out


def test_edge08_foreign_manifest_sha_deltas_by_common_paths(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(json.dumps({
        "ts": "2020-01-01T00:00:00", "manifest_sha": "deadbeef", "thresholds_version": 0,
        "artifacts": {"a.md": {"bytes": 5, "records": 1, "bpr": 5, "state": "—"}},
        "totals": {"sum_bytes": 5, "assigned_k": 0, "total_n": 1, "warn_count": 0, "breach_count": 0},
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "БАЗА ОТ ДРУГОГО МАНИФЕСТА" in out
    assert "Δbytes=" in out  # дельта по общему пути всё равно посчитана


def test_edge09_sidecar_not_writable_warn_exit0(tmp_path, capsys):
    root, _ = _sandbox(tmp_path)
    blocker = tmp_path / "blocker_file"
    blocker.write_bytes(b"x")
    bad_registry = blocker / "sidecar.jsonl"  # родитель -- ФАЙЛ, не каталог
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(bad_registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "WARN: сайдкар не записан" in out


def test_edge10_new_path_added_shows_novyi_and_threshold_slot(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    capsys.readouterr()
    _write_file(root, "b.md", _three_records())
    manifest2 = _write_manifest(root, [_art("a.md"), _art("b.md", bpr_max=100)])
    rc = _run(["--manifest", str(manifest2), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "b.md" in out
    assert "порогов 1/2" in out


def test_edge11_removed_from_manifest_departed_block(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", _three_records())
    _write_file(root, "b.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md"), _art("b.md")])
    _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    capsys.readouterr()
    manifest2 = _write_manifest(root, [_art("a.md")], name="manifest2.json")
    rc = _run(["--manifest", str(manifest2), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ВЫБЫЛИ ===" in out
    assert "b.md: последние числа" in out


def test_edge12_duplicate_path_is_defect(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md"), _art("a.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "дубль path: a.md" in out
    rc_check = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--check"])
    capsys.readouterr()
    assert rc_check == 1


@pytest.mark.parametrize("bad_artifact,msg_fragment", [
    (_art("a.md", bpr_max=0), "bpr_max<=0"),
    (_art("a.md", bpr_max=-5), "bpr_max<=0"),
    (_art("a.md", owner="boot-mirror", bpr_max=100), "порог у boot-mirror запрещён"),
    (_art("a.md", record_re="[unterminated"), "re.error"),
    (_art("/abs/a.md"), "абсолютный путь запрещён"),
    (_art("sub/../../a.md"), "'..' в пути запрещён"),
])
def test_edge13_form_defects_no_traceback(tmp_path, capsys, bad_artifact, msg_fragment):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [bad_artifact])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0  # не трейсбек, прогон состоялся
    assert msg_fragment in out


def test_edge14_manifest_missing_exit2(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    rc = _run(["--manifest", str(root / "nope.json"), "--registry", str(registry), "--root", str(root)])
    capsys.readouterr()
    assert rc == 2
    rc_check = _run(["--manifest", str(root / "nope.json"), "--registry", str(registry),
                      "--root", str(root), "--check"])
    capsys.readouterr()
    assert rc_check == 2


def test_edge14_manifest_not_json_exit2(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    manifest = _write_raw_manifest(root, "{not json")
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    capsys.readouterr()
    assert rc == 2


def test_edge15_temporal_tool_now_exists():
    """S7 край 15 -- темпоральный: 'инструмента нет сегодня' относился к
    моменту ДО диспатча t-508 (Glob corpus_* пуст при контроле
    calibration_* 2). Инструмент теперь существует -- условие снято;
    негативная часть его больше не наблюдаема, поэтому тест лишь
    подтверждает постусловие (позитивный факт, не повтор негатива)."""
    assert (REPO_ROOT / "tools" / "corpus_growth.py").exists()
    assert (REPO_ROOT / "tools" / "corpus_manifest.json").exists()


def test_edge16_sidecar_created_by_first_run(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    assert not registry.parent.exists()
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    capsys.readouterr()
    assert registry.exists()


def test_edge17_no_thresholds_dash_k_of_n_check_not_red(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", _three_records())
    _write_file(root, "b.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md"), _art("b.md")])  # все bpr_max: null
    out_plain = None
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out_plain = capsys.readouterr().out
    assert "порогов 0/2" in out_plain
    assert out_plain.count(" — |") >= 2 or out_plain.count("]: — |") >= 2
    rc_check = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--check"])
    capsys.readouterr()
    assert rc_check == 0  # вакуумно, --check не красный из-за отсутствия порогов


def test_edge18_rule_coverage_line_same_commit_not_applicable():
    """S7 край 18 -- процессное требование ('строка RULE_COVERAGE тем же
    коммитом, что чек 34') относится к посадке ЧЕКА 34 Lead'ом (non-goal
    этого диспатча: PROCESS/, RULE_COVERAGE -- см. owns/non-goals спеки);
    машинно этим тулом не проверяется. Документируется явно, не
    исполняется здесь."""
    assert True


def test_edge19_check34_header_position_not_applicable():
    """S7 край 19 -- позиционный инвариант шапки чека 34 в тексте
    протокола -- обязанность Lead при посадке ПОСЛЕ M2 (non-goal:
    PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md). Документируется явно."""
    assert True


def test_edge20_measurer_not_gate_exit0_on_breach_both_modes(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", ("R1 " + "x" * 500).encode("utf-8"))
    manifest = _write_manifest(root, [_art("a.md", bpr_max=1)])
    rc1 = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    capsys.readouterr()
    rc2 = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--check"])
    capsys.readouterr()
    assert rc1 == 0
    assert rc2 == 0


def test_edge21_no_boot_surfacing_not_applicable():
    """S7 край 21 -- Р2(A): всплытия в SessionStart нет. Этот инструмент
    не импортирует и не вызывает session_context.py (не-дублируемая
    зона, non-goal диспатча) -- проверяем отсутствие импорта/вызова,
    не голое упоминание имени в прозе докстринга (докстринг ссылается
    на session_context как на владельца бут-чисел, это не код-связь)."""
    src = (REPO_ROOT / "tools" / "corpus_growth.py").read_text(encoding="utf-8")
    assert "import session_context" not in src
    assert "session_context." not in src


def test_edge22_boot_mirror_measured_but_no_threshold_no_lines_metric(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "claude.md", "R1. правило\nR2a. правило\n".encode("utf-8"))
    manifest = _write_manifest(root, [_art("claude.md", owner="boot-mirror", record_re=r"^R\d+[a-z]?\.")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "зеркало бут-пути, порог запрещён" in out
    assert "сумма байт corpus=0" in out  # boot-mirror в сумму не входит


def test_edge23_diet_bytes_reduction_not_editorial_not_applicable():
    """S7 край 23 -- политическая рамка (снижение байт не самоцель, рост
    с сохранённой исполнимостью объясняется) -- решает AI-слой (Lead/
    чек 34(в)), не код. Инструмент печатает СЫРЫЕ числа без оценочных
    суждений; проверяем, что рендер не содержит директивных
    формулировок вида 'нужно сократить'."""
    root = REPO_ROOT
    src = (root / "tools" / "corpus_growth.py").read_text(encoding="utf-8")
    for banned in ("нужно сократить", "следует уменьшить", "обязаны снизить"):
        assert banned not in src


# ---------------------------------------------------------------------------
# Лимиты: тест на границе и за границей (D-0054, п.6а)
# ---------------------------------------------------------------------------

def test_limit_bpr_equals_max_is_warn(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", ("R" * 100).encode("utf-8"))  # 1 запись 'R', bytes=100
    manifest = _write_manifest(root, [_art("a.md", record_re=r"^R", bpr_max=100)])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "bpr=100" in out
    assert "]: WARN |" in out


def test_limit_bpr_max_plus_one_is_breach(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", ("R" * 101).encode("utf-8"))  # bytes=101, records=1
    manifest = _write_manifest(root, [_art("a.md", record_re=r"^R", bpr_max=100)])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "bpr=101" in out
    assert "]: BREACH |" in out


def test_limit_95_percent_boundary_is_ok(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", ("R" * 95).encode("utf-8"))  # bpr=95, warn_floor=95.0
    manifest = _write_manifest(root, [_art("a.md", record_re=r"^R", bpr_max=100)])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "]: OK |" in out


def test_limit_just_above_95_percent_is_warn(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", ("R" * 96).encode("utf-8"))  # bpr=96 > 95.0
    manifest = _write_manifest(root, [_art("a.md", record_re=r"^R", bpr_max=100)])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "]: WARN |" in out


def test_limit_record_re_200_bytes_accepted(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", _three_records())
    pattern = "^R" + "A" * 198  # итого 200 байт ASCII
    assert len(pattern.encode("utf-8")) == 200
    manifest = _write_manifest(root, [_art("a.md", record_re=pattern)])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "record_re длиннее" not in out


def test_limit_record_re_201_bytes_is_defect(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", _three_records())
    pattern = "^R" + "A" * 199  # итого 201 байт
    assert len(pattern.encode("utf-8")) == 201
    manifest = _write_manifest(root, [_art("a.md", record_re=pattern)])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "record_re длиннее 200 Б" in out


# ---------------------------------------------------------------------------
# Ключ 8: адверсариальная батарея CLI
# ---------------------------------------------------------------------------

def test_battery_manifest_top_level_list_exit2(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    manifest = _write_raw_manifest(root, json.dumps([_art("a.md")]))
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    capsys.readouterr()
    assert rc == 2


def test_battery_entry_without_path_is_defect_not_crash(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    manifest = _write_manifest(root, [{"unit": "x", "record_re": r"^R", "owner": "corpus", "bpr_max": None}])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "поле 'path' отсутствует" in out


def test_battery_root_not_a_directory_exit2(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    manifest = _write_manifest(root, [_art("a.md")])
    fake_root = tmp_path / "not_a_dir.txt"
    fake_root.write_bytes(b"x")
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(fake_root)])
    capsys.readouterr()
    assert rc == 2


def test_battery_non_ascii_filename(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "тест-файл.md", _three_records())
    manifest = _write_manifest(root, [_art("тест-файл.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "тест-файл.md" in out
    assert "records=3" in out


def test_battery_two_runs_healthy_and_broken_check(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    rc_healthy = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--check"])
    capsys.readouterr()
    assert rc_healthy == 0

    manifest_broken = _write_manifest(root, [_art("missing.md")], name="broken.json")
    rc_broken = _run(["--manifest", str(manifest_broken), "--registry", str(registry),
                       "--root", str(root), "--check"])
    capsys.readouterr()
    assert rc_broken == 1


def test_battery_json_flag_is_parseable(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", _three_records())
    manifest = _write_manifest(root, [_art("a.md")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["totals"]["total_n"] == 1
    assert payload["fixture_control"] == "3/3"


# ---------------------------------------------------------------------------
# Ключ 9: негативный контроль (счётчик способен упасть)
# ---------------------------------------------------------------------------

def test_key9_negative_control_counter_can_fail(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "synthetic.md", b"content with absolutely no matching tokens at all\n")
    manifest = _write_manifest(root, [_art("synthetic.md", record_re=r"^ZZZ-NEVER-\d+")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--check"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "регекс протух" in out


# ---------------------------------------------------------------------------
# --init-thresholds: печатает предложение, манифест не правит
# ---------------------------------------------------------------------------

def test_init_thresholds_prints_proposal_does_not_touch_manifest(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", ("R" * 100).encode("utf-8"))
    manifest = _write_manifest(root, [_art("a.md", record_re=r"^R")])
    before = manifest.read_bytes()
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--init-thresholds"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "предложение bpr_max=115" in out  # 100 * 1.15 = 115.0 -> ceil 115
    assert manifest.read_bytes() == before  # манифест не правится
    assert not registry.exists()  # init-thresholds не пишет сайдкар


def test_init_thresholds_skips_boot_mirror(tmp_path, capsys):
    root, registry = _sandbox(tmp_path)
    _write_file(root, "a.md", ("R" * 100).encode("utf-8"))
    manifest = _write_manifest(root, [_art("a.md", owner="boot-mirror", record_re=r"^R")])
    rc = _run(["--manifest", str(manifest), "--registry", str(registry), "--root", str(root), "--init-thresholds"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "boot-mirror -- порог запрещён" in out
