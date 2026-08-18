"""Battery for tools/norm_retire.py (Phase 5, W1 retirement checker).

Спека: docs/tasks/2026-08-18_w1-retirement-spec.md (A4 -- машинный
слой: инварианты чекера + синтетическая батарея; A9 -- проверочный
прогон). Покрытие:

  T1 -- живой прогон: --check на реальном дереве обязан быть зелёным
        (гейт фазы (в) "ни одна норма не потеряна"); дайджесты первой
        партии (D-0011, F-21, F-22, F-26) пин-регрессированы против
        значений, зафиксированных builder-отчётом ДО/ПОСЛЕ переноса
        (A7 шаги 1/5) -- дрейф архива после посадки будет ПОЙМАН этим
        тестом; граница секции _iter_sections сверена с
        escape_check.extract_decision_section() на живой не-стаб
        записи (border-contract equivalence).
  T2 -- CLI: --check живого дерева (exit 0), usage-ошибки (exit 2),
        неопознанная форма ID / не найдено / задвоено (exit 1).
  T3 -- синтетическая батарея (A4, tmp_path-фикстуры, живые артефакты
        не трогаются): по одному падающему кейсу на I1..I8 + оба
        граничных кейса каждого лимита (4/5 строк, 400/401 байт) +
        доп. кейсы, явно перечисленные A4 (указатель на дом чужой
        пары; секция архива без канонного заголовка; секция архива
        с телом при полном тексте в каноне; стаб с **Класс.**;
        CRLF-вариант стаба) + реанимация (happy path + канон
        остался стабом) + не-UTF-8 архив (A8.4).

Run: python -m pytest tools/test_norm_retire.py -q
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import escape_check
import norm_retire

REPO_ROOT = Path(norm_retire.REPO_ROOT)


# ---------------------------------------------------------------------
# Фикстура-строитель синтетического дерева.
# ---------------------------------------------------------------------


def _baseline():
    return {
        "docs/DECISIONS_FULL.md": (
            "# Decisions Log -- Full Texts (D-0051)\n\n"
            "Preamble paragraph.\n\n"
            "## D-0001\n"
            "Some decision text.\n"
        ),
        "DECISIONS.md": (
            "# Decisions Log (index)\n\n"
            "Preamble paragraph.\n\n"
            "- D-0001 -- Some decision text.\n"
        ),
        "docs/FINDINGS.md": (
            "# Findings\n\n"
            "Preamble paragraph.\n\n"
            "## F-1 -- Some finding\n"
            "Some finding text.\n"
        ),
    }


def _write_repo(tmp_path, overrides=None, extra_bytes=None):
    """Материализует синтетическое дерево под tmp_path: baseline() +
    overrides (перезаписывает путь целиком, текст) + extra_bytes
    (путь -> сырые байты, для не-UTF-8 кейса)."""
    files = _baseline()
    if overrides:
        files.update(overrides)
    for rel, content in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if extra_bytes:
        for rel, raw in extra_bytes.items():
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    return tmp_path


def _run(tmp_path, overrides=None, extra_bytes=None):
    _write_repo(tmp_path, overrides, extra_bytes)
    return norm_retire.run_check(repo_root=tmp_path)


def _findings_canon(extra_section=""):
    return _baseline()["docs/FINDINGS.md"] + extra_section


def _stub_body_lines(n_lines, fid, archive_rel, reason="Причина."):
    """Тело стаба РОВНО из n_lines непустых строк: маркер + (n-2)
    filler-строк + указатель."""
    assert n_lines >= 2
    lines = ["**РЕТИРОВАНО 2026-08-18.** %s" % reason]
    for i in range(n_lines - 2):
        lines.append("Доп. строка %d." % (i + 1))
    lines.append(
        "Полный текст VERBATIM -- %s, секция `## %s`." % (archive_rel, fid)
    )
    return "\n".join(lines)


def _stub_body_bytes(total_bytes, fid, archive_rel):
    """Тело стаба РОВНО из total_bytes байт UTF-8 (2 непустые строки:
    маркер+pad, указатель) -- pad считается точно (ASCII 'x' = 1 байт)."""
    prefix = "**РЕТИРОВАНО 2026-08-18.** "
    pointer = "Полный текст VERBATIM -- %s, секция `## %s`." % (archive_rel, fid)
    base = prefix + "\n" + pointer
    base_bytes = len(base.encode("utf-8"))
    pad = total_bytes - base_bytes
    assert pad >= 0, "target_bytes too small for base content (%d < %d)" % (
        total_bytes,
        base_bytes,
    )
    body = prefix + ("x" * pad) + "\n" + pointer
    assert len(body.encode("utf-8")) == total_bytes
    return body


def _has_fail_containing(lines, needle):
    return any(needle in l for l in lines)


def _status_of(lines, inv):
    for l in lines:
        if l.startswith(inv + " "):
            return l.split(" ", 1)[1]
    return None


# ---------------------------------------------------------------------
# T1 -- живой прогон.
# ---------------------------------------------------------------------


def test_live_check_all_invariants_ok():
    ok, lines = norm_retire.run_check(repo_root=REPO_ROOT)
    assert ok is True, "\n".join(lines)
    for n in range(1, 9):
        assert _status_of(lines, "I%d" % n) == "OK", "\n".join(lines)


# Дайджесты, зафиксированные builder-отчётом ДО переноса (A7 шаг 1,
# python tools/norm_retire.py --hash-canon <ID> на живом дереве ДО
# правок) и подтверждённые ПОСЛЕ переноса (A7 шаг 5, --hash-archive,
# совпадение с шагом 1). Регрессионный пин: последующий дрейф архива
# (не-VERBATIM правка) сломает --hash-archive и этот тест.
_BATCH_DIGESTS = {
    "D-0011": "33c8d46f71aec023bc141f7fc804bf90ba6c81f3745047ea68d47a49ad62f6f9",
    "F-21": "f7c5a048e2d814d36090f2e7cc73d4dde581ba648f696a5ed9b98dbe56f0f501",
    "F-22": "48e6197216eac78d3104434fabe9a222e5cafd8b7a2fbbdc91632b3c7f5de2cf",
    "F-26": "01c66b34fdf076a683415dac28f3152b59aebdbfd530ac23ddf14c5ec09e3461",
}


@pytest.mark.parametrize("fid,digest", sorted(_BATCH_DIGESTS.items()))
def test_live_batch_archive_digest_pinned(fid, digest):
    pair = norm_retire._pair_for_id(fid)
    text, err = norm_retire.read_utf8(REPO_ROOT / pair.archive_rel)
    assert err is None, err
    got, status = norm_retire._section_sha256_for_id(text, fid, pair)
    assert status == "ok"
    assert got == digest


@pytest.mark.parametrize("fid", sorted(_BATCH_DIGESTS))
def test_live_batch_ids_are_recognized_stubs_in_canon(fid):
    pair = norm_retire._pair_for_id(fid)
    text, err = norm_retire.read_utf8(REPO_ROOT / pair.canon_rel)
    assert err is None, err
    sections = dict(norm_retire._iter_sections(text, pair.header_re))
    assert fid in sections, "id missing from canon"
    assert norm_retire.is_stub(sections[fid]), "batch id not recognized as stub"


def test_iter_sections_matches_escape_check_border_contract_on_live_decision():
    """D-0012 -- живая, НЕ ретированная запись; граница секции,
    которую даёт _iter_sections(), обязана совпасть с
    escape_check.extract_decision_section() дословно (общий контракт,
    заявленный в docstring модуля)."""
    text, err = norm_retire.read_utf8(REPO_ROOT / "docs/DECISIONS_FULL.md")
    assert err is None, err
    sections = dict(norm_retire._iter_sections(text, norm_retire.DECISIONS_PAIR.header_re))
    mine = sections["D-0012"]
    header_plus_body = "## D-0012\n" + mine if mine else "## D-0012"
    ref_text, ref_status = escape_check.extract_decision_section(text, "D-0012")
    assert ref_status == "ok"
    assert header_plus_body == ref_text


# ---------------------------------------------------------------------
# T2 -- CLI.
# ---------------------------------------------------------------------


def _run_cli(args):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "norm_retire.py")] + args,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_cli_check_live_tree_exit_0():
    proc = _run_cli(["--check"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    for n in range(1, 9):
        assert ("I%d OK" % n) in proc.stdout


@pytest.mark.parametrize("fid,digest", sorted(_BATCH_DIGESTS.items()))
def test_cli_hash_archive_live_batch_matches_pin(fid, digest):
    proc = _run_cli(["--hash-archive", fid])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip() == digest


def test_cli_no_args_exit_2():
    proc = _run_cli([])
    assert proc.returncode == 2
    assert "usage" in proc.stderr


def test_cli_unknown_flag_exit_2():
    proc = _run_cli(["--bogus"])
    assert proc.returncode == 2


def test_cli_hash_canon_unrecognized_id_form_exit_1():
    proc = _run_cli(["--hash-canon", "X-9"])
    assert proc.returncode == 1
    assert "unrecognized id form" in proc.stderr


def test_cli_hash_canon_not_found_exit_1(tmp_path):
    # синтетическое дерево -- ID заведомо отсутствует
    _write_repo(tmp_path)
    ok = norm_retire._cli_hash("D-9999", use_canon=True, repo_root=tmp_path)
    assert ok == 1


def test_cli_hash_canon_duplicate_exit_1(tmp_path):
    dup = _baseline()["docs/DECISIONS_FULL.md"] + "\n## D-0001\nDup text.\n"
    _write_repo(tmp_path, overrides={"docs/DECISIONS_FULL.md": dup})
    ok = norm_retire._cli_hash("D-0001", use_canon=True, repo_root=tmp_path)
    assert ok == 1


# ---------------------------------------------------------------------
# T3 -- синтетическая батарея (tmp_path).
# ---------------------------------------------------------------------

ARCHIVE_REL = "docs/FINDINGS_ARCHIVE.md"


def _valid_pair(n_lines=None, total_bytes=None, fid="F-2", reason="Причина."):
    """Строит согласованную пару (canon-extra, archive-extra) -- стаб
    F-2 в каноне + такая же секция в архиве, ровно одна, валидная по
    всем инвариантам кроме тех, что тест намеренно портит."""
    if total_bytes is not None:
        body = _stub_body_bytes(total_bytes, fid, ARCHIVE_REL)
    else:
        body = _stub_body_lines(n_lines or 4, fid, ARCHIVE_REL, reason)
    canon_extra = "\n## %s\n%s\n" % (fid, body)
    archive_extra = "\n## %s\nАрхивное тело (произвольное, для --check не хешируется).\n" % fid
    return canon_extra, archive_extra


# ---- лимиты: 4/5 непустых строк, 400/401 байт ------------------------


def test_limit_4_nonempty_lines_passes(tmp_path):
    canon_extra, archive_extra = _valid_pair(n_lines=4)
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is True, "\n".join(lines)


def test_limit_5_nonempty_lines_fails(tmp_path):
    canon_extra, archive_extra = _valid_pair(n_lines=5)
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "> 4 непустых строк")


def test_limit_400_bytes_passes(tmp_path):
    canon_extra, archive_extra = _valid_pair(total_bytes=400)
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is True, "\n".join(lines)


def test_limit_401_bytes_fails(tmp_path):
    canon_extra, archive_extra = _valid_pair(total_bytes=401)
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "> 400 байт")


# ---- I1 ----------------------------------------------------------------


def test_i1_stub_without_pointer_fails(tmp_path):
    body = "**РЕТИРОВАНО 2026-08-18.** Причина без указателя."
    canon_extra = "\n## F-2\n%s\n" % body
    archive_extra = "\n## F-2\nАрхивное тело.\n"
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "нет строки-указателя")


def test_i1_pointer_wrong_pair_fails(tmp_path):
    body = (
        "**РЕТИРОВАНО 2026-08-18.** Причина.\n"
        "Полный текст VERBATIM -- docs/DECISIONS_ARCHIVE.md, секция `## F-2`."
    )
    canon_extra = "\n## F-2\n%s\n" % body
    archive_extra = "\n## F-2\nАрхивное тело.\n"
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "указатель ссылается на архив чужой пары")


def test_i1_stub_points_to_missing_id_in_existing_home_fails(tmp_path):
    # архив существует и непуст, но НЕ несёт секцию F-2 (несёт F-3
    # вместо неё) -- I1 "дом несёт 0 секций F-2, ожидалась 1".
    canon_extra, _ = _valid_pair(n_lines=4)
    archive_extra = "\n## F-3\nЧужая секция.\n"
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "дом несёт 0 секций F-2")


# ---- I2 ------------------------------------------------------------------


def test_i2_archive_section_without_canon_header_fails(tmp_path):
    archive_extra = "\n## F-99\nОсиротевшая архивная секция.\n"
    ok, lines = _run(
        tmp_path,
        overrides={ARCHIVE_REL: "# Findings Archive\n" + archive_extra},
    )
    assert ok is False
    assert _has_fail_containing(lines, "F-99: архивная секция без канонного заголовка")


def test_i2_body_present_both_sides_fails(tmp_path):
    # канон несёт ПОЛНЫЙ (не-стаб) текст F-2, архив ТОЖЕ несёт тело.
    canon_extra = "\n## F-2 -- Живая запись\nПолный текст записи, не стаб.\n"
    archive_extra = "\n## F-2 -- Живая запись\nАрхивное тело (дубль).\n"
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "тело и там и там")


def test_i2_empty_canon_body_form_not_recognized_fails(tmp_path):
    canon_extra = "\n## F-2\n"  # заголовок, пустое тело
    archive_extra = "\n## F-2\nАрхивное тело.\n"
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "форма не распознана")


def test_i2_archive_header_without_body_or_reanimation_fails(tmp_path):
    canon_extra, _ = _valid_pair(n_lines=4)
    archive_extra = "\n## F-2\n"  # заголовок без тела, без реанимации
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "заголовок архива без тела и без реанимации")


def test_i2_reanimation_happy_path_passes(tmp_path):
    canon_extra = "\n## F-2 -- Живая запись\nПолный текст, вернувшийся из архива.\n"
    archive_extra = (
        "\n## F-2 -- Живая запись\n"
        "**РЕАНИМИРОВАНО 2026-08-19 -> docs/FINDINGS.md.**\n"
    )
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is True, "\n".join(lines)


def test_i2_reanimation_but_canon_still_stub_fails(tmp_path):
    canon_extra, _ = _valid_pair(n_lines=4)
    archive_extra = (
        "\n## F-2\n**РЕАНИМИРОВАНО 2026-08-19 -> docs/FINDINGS.md.**\n"
    )
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "канон остался стабом")


# ---- I3 (только D-пара) ---------------------------------------------------


def test_i3_index_missing_entry_fails(tmp_path):
    full_extra = "\n## D-0002\nВторое решение.\n"
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/DECISIONS_FULL.md": _baseline()["docs/DECISIONS_FULL.md"] + full_extra
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "в индексе нет строк для")


def test_i3_full_missing_section_fails(tmp_path):
    idx_extra = "- D-0002 -- Второе решение.\n"
    ok, lines = _run(
        tmp_path,
        overrides={"DECISIONS.md": _baseline()["DECISIONS.md"] + idx_extra},
    )
    assert ok is False
    assert _has_fail_containing(lines, "в DECISIONS_FULL нет секций для")


# ---- I4 (только D-пара) ---------------------------------------------------


def test_i4_index_line_without_retired_token_fails(tmp_path):
    stub_body = _stub_body_lines(4, "D-0002", "docs/DECISIONS_ARCHIVE.md")
    full_extra = "\n## D-0002\n%s\n" % stub_body
    idx_extra = "- D-0002 -- [ретировано без токена]\n"
    archive_extra = "\n## D-0002\nАрхивное тело.\n"
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/DECISIONS_FULL.md": _baseline()["docs/DECISIONS_FULL.md"] + full_extra,
            "DECISIONS.md": _baseline()["DECISIONS.md"] + idx_extra,
            "docs/DECISIONS_ARCHIVE.md": "# Decisions Archive\n" + archive_extra,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "строка индекса без токена РЕТИРОВАНО")


# ---- I5 (только D-пара, пины) ---------------------------------------------


def test_i5_pinned_decision_stubbed_fails(tmp_path):
    stub_body = _stub_body_lines(4, "D-0002", "docs/DECISIONS_ARCHIVE.md")
    full_extra = "\n## D-0002\n%s\n" % stub_body
    idx_extra = "- D-0002 -- [РЕТИРОВАНО 2026-08-18]\n"
    archive_extra = "\n## D-0002\nАрхивное тело.\n"
    allowlist = json.dumps(
        {"entries": [{"id": "x", "decision_id": "D-0002"}]}
    )
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/DECISIONS_FULL.md": _baseline()["docs/DECISIONS_FULL.md"] + full_extra,
            "DECISIONS.md": _baseline()["DECISIONS.md"] + idx_extra,
            "docs/DECISIONS_ARCHIVE.md": "# Decisions Archive\n" + archive_extra,
            "tools/escape_allowlist.json": allowlist,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "запинненные решения стабированы")


def test_i5_unpinned_decision_stub_passes(tmp_path):
    """Позитивный контроль I5: тот же стаб, allowlist пуст -- PASS
    (доказывает, что I5-фейл выше сработал ИМЕННО из-за пина, а не
    из-за формы стаба)."""
    stub_body = _stub_body_lines(4, "D-0002", "docs/DECISIONS_ARCHIVE.md")
    full_extra = "\n## D-0002\n%s\n" % stub_body
    idx_extra = "- D-0002 -- [РЕТИРОВАНО 2026-08-18]\n"
    archive_extra = "\n## D-0002\nАрхивное тело.\n"
    allowlist = json.dumps({"entries": []})
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/DECISIONS_FULL.md": _baseline()["docs/DECISIONS_FULL.md"] + full_extra,
            "DECISIONS.md": _baseline()["DECISIONS.md"] + idx_extra,
            "docs/DECISIONS_ARCHIVE.md": "# Decisions Archive\n" + archive_extra,
            "tools/escape_allowlist.json": allowlist,
        },
    )
    assert ok is True, "\n".join(lines)


# ---- I6 --------------------------------------------------------------


def test_i6_duplicate_canon_header_fails(tmp_path):
    dup = _findings_canon() + "\n## F-1 -- Дубль заголовка\nДубль.\n"
    ok, lines = _run(tmp_path, overrides={"docs/FINDINGS.md": dup})
    assert ok is False
    assert _has_fail_containing(lines, "I6 findings/канон: F-1 встречается 2 раз")


def test_i6_duplicate_archive_header_fails(tmp_path):
    canon_extra, _ = _valid_pair(n_lines=4)
    archive_extra = (
        "\n## F-2\nАрхивное тело.\n\n## F-2\nАрхивное тело дубля.\n"
    )
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "I6 findings/архив: F-2 встречается 2 раз")


# ---- I7 ----------------------------------------------------------------


def test_i7_klass_marker_in_stub_fails(tmp_path):
    body = (
        "**РЕТИРОВАНО 2026-08-18.** Причина.\n"
        "**Класс.** Это не должно быть в стабе.\n"
        "Полный текст VERBATIM -- %s, секция `## F-2`." % ARCHIVE_REL
    )
    canon_extra = "\n## F-2\n%s\n" % body
    archive_extra = "\n## F-2\nАрхивное тело.\n"
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "стаб несёт **Класс.**")


def test_i7_klass_without_dot_in_stub_fails(tmp_path):
    body = (
        "**РЕТИРОВАНО 2026-08-18.** Причина.\n"
        "**Класс** без точки тоже запрещён.\n"
        "Полный текст VERBATIM -- %s, секция `## F-2`." % ARCHIVE_REL
    )
    canon_extra = "\n## F-2\n%s\n" % body
    archive_extra = "\n## F-2\nАрхивное тело.\n"
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n" + archive_extra,
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "стаб несёт **Класс.**")


# ---- I8 ------------------------------------------------------------------


def test_i8_stub_with_no_archive_file_fails(tmp_path):
    canon_extra, _ = _valid_pair(n_lines=4)
    ok, lines = _run(tmp_path, overrides={"docs/FINDINGS.md": _findings_canon(canon_extra)})
    assert ok is False
    assert _has_fail_containing(lines, "стаб указывает на несуществующий дом")
    assert not _has_fail_containing(lines, "архив пуст")


def test_i8_stub_with_empty_archive_file_fails(tmp_path):
    canon_extra, _ = _valid_pair(n_lines=4)
    ok, lines = _run(
        tmp_path,
        overrides={
            "docs/FINDINGS.md": _findings_canon(canon_extra),
            ARCHIVE_REL: "# Findings Archive\n\nPreamble only, no sections.\n",
        },
    )
    assert ok is False
    assert _has_fail_containing(lines, "стаб указывает на несуществующий дом (архив пуст)")


def test_i8_vacuous_zero_stubs_no_archive_passes(tmp_path):
    ok, lines = _run(tmp_path)
    assert ok is True, "\n".join(lines)
    assert _status_of(lines, "I8") == "OK"


def test_i8_vacuous_archive_exists_zero_stubs_passes(tmp_path):
    ok, lines = _run(
        tmp_path,
        overrides={ARCHIVE_REL: "# Findings Archive\n\nJust a preamble, no sections at all.\n"},
    )
    assert ok is True, "\n".join(lines)
    assert _status_of(lines, "I8") == "OK"


# ---- CRLF-вариант стаба (робастность) --------------------------------


def test_crlf_stub_variant_passes(tmp_path):
    canon_extra, archive_extra = _valid_pair(n_lines=4)
    canon_text = _findings_canon(canon_extra).replace("\n", "\r\n")
    archive_text = ("# Findings Archive\n" + archive_extra).replace("\n", "\r\n")
    ok, lines = _run(
        tmp_path,
        overrides={"docs/FINDINGS.md": canon_text, ARCHIVE_REL: archive_text},
    )
    assert ok is True, "\n".join(lines)


# ---- не-UTF-8 архив (A8.4) ---------------------------------------------


def test_non_utf8_archive_reports_error(tmp_path):
    canon_extra, _ = _valid_pair(n_lines=4)
    _write_repo(
        tmp_path,
        overrides={"docs/FINDINGS.md": _findings_canon(canon_extra)},
        extra_bytes={ARCHIVE_REL: b"\xff\xfe not valid utf-8 \x80\x81"},
    )
    ok, lines = norm_retire.run_check(repo_root=tmp_path)
    assert ok is False
    assert any(l.startswith("UTF8-ERROR") for l in lines)


# ---------------------------------------------------------------------
# extract_finding_section / finding_section_sha256 -- юнит-контракт
# (зеркало escape_check.extract_decision_section, border contract A4).
# ---------------------------------------------------------------------


def test_extract_finding_section_not_found():
    text = "# Findings\n\n## F-1\nBody.\n"
    section, status = norm_retire.extract_finding_section(text, "F-2")
    assert status == "not_found"
    assert section is None


def test_extract_finding_section_duplicate():
    text = "# Findings\n\n## F-1\nBody.\n\n## F-1\nDup.\n"
    section, status = norm_retire.extract_finding_section(text, "F-1")
    assert status == "duplicate"
    assert section is None


def test_extract_finding_section_trailing_blank_lines_stripped():
    text = "# Findings\n\n## F-1\nBody line.\n\n\n\n## F-2\nNext.\n"
    section, status = norm_retire.extract_finding_section(text, "F-1")
    assert status == "ok"
    assert section == "## F-1\nBody line."


def test_extract_finding_section_id_boundary_not_fooled_by_prefix():
    # "## F-2" не должно ложно совпасть при поиске "## F-21" и наоборот
    text = "# Findings\n\n## F-2\nShort id body.\n\n## F-21\nLonger id body.\n"
    section2, status2 = norm_retire.extract_finding_section(text, "F-2")
    section21, status21 = norm_retire.extract_finding_section(text, "F-21")
    assert status2 == "ok" and section2 == "## F-2\nShort id body."
    assert status21 == "ok" and section21 == "## F-21\nLonger id body."


def test_finding_section_sha256_crlf_lf_equivalence():
    text_lf = "# Findings\n\n## F-1\nBody text here.\n\n## F-2\nNext.\n"
    text_crlf = text_lf.replace("\n", "\r\n")
    digest_lf, status_lf = norm_retire.finding_section_sha256(text_lf, "F-1")
    digest_crlf, status_crlf = norm_retire.finding_section_sha256(text_crlf, "F-1")
    assert status_lf == status_crlf == "ok"
    assert digest_lf == digest_crlf
