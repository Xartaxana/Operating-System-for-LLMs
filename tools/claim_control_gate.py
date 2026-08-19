"""tools/claim_control_gate.py -- PreToolUse hook (Edit|Write), WARN
MODE (non-blocking). Half B of the t-021 negative-claim correlation
gate: tools/search_control_gate.py (half A) records every observed
search AND examination (Read) into a per-session ledger; this hook
reads content about to be written to an in-scope path, looks for a
NEGATIVE CLAIM ("X does not exist", "не найден", ...), extracts
machine-tractable tokens from around the claim, and warns about any
token group that was never searched-for or read this session, per the
ledger. Живой файл, region-aware с 2026-08-19 (этап 2, СПЕКА B,
партия 1, docs/tasks/2026-08-19_md-regions-scanner-spec.md, класс
docs/SIBLING_MAP.md :496-510 "сторож не отличает утверждение автора от
цитируемого/вложенного содержимого"). Прежний (до-region) рационал
модуля восстановлен здесь дословно из коммита 6a139c8 (последняя
правка живого файла ДО посадки байт-копией region-сиблинга 89b6142,
которая заместила бОльшую часть этого докстринга и части докстрингов
функций -- находка критика 2026-08-19: файл сжался 853 -> 620 строк).

КЛАСС (docs/SIBLING_MAP.md :496-510): "сторож не отличает утверждение
автора от цитируемого/вложенного содержимого". Для claim_control_gate
это означает: маркер негативного утверждения ИЛИ токен-претензия могут
физически сидеть внутри цитаты/фенса (чужого/вложенного текста), а не в
собственной прозе автора -- пять существующих граничных регексов режут
текст на "предложения" ВНУТРИ одной физической строки/абзаца, но НИЧЕГО
не знают про markdown-цитаты/фенсы поперёк нескольких строк, поэтому
раньше флагали содержимое цитаты как если бы это было утверждение автора
(ложное срабатывание -- см. discrimination-тест ниже).

ПОЛИТИКА (B2, буквально из спеки): fenced/blockquote НЕ порождают окно
(маркер, чья СОБСТВЕННАЯ позиция попадает в fenced/blockquote регион, не
доходит даже до вычисления _sentence_window -- пропускается целиком, ни
одного токена из его окрестности не извлекается) И не засчитывают
токены (даже когда МАРКЕР сам в прозе и окно создаётся штатно, токен
ВНУТРИ этого окна, чья собственная позиция попадает в fenced/blockquote,
исключается из группы -- как если бы его не было); inline_code
засчитывается -- ни маркер, ни токен в inline_code не исключаются
регионом (то же приоритетное правило 1..5, что и в tools/
negative_lint_md.py._classify -- см. _classify ниже, идентичная логика,
задокументированная отдельно в этом файле, а не импортированная оттуда:
два разных сторожа с двумя разными политиками, D-0043 здесь не про общий
код классификации, а про общий СКАНЕР -- каждый потребитель решает
семантику сам, см. md_regions.py докстринг "Решение 08-16 (d3)").

ПОЗИЦИОННЫЙ ИНВАРИАНТ (буквально из спеки): пять граничных регексов
живого файла (_SENTENCE_PUNCT_RE, _PARAGRAPH_BREAK_RE,
_LIST_ITEM_BOUNDARY_RE, _TABLE_ROW_BOUNDARY_RE, _HEADING_BOUNDARY_RE и
их сборка _BOUNDARY_RES) скопированы сюда БАЙТ В БАЙТ, не изменены ни
байтом -- см. test_claim_control_gate_md.py::
test_five_boundary_regex_patterns_byte_identical_to_live, сверка
.pattern построчно против живого модуля -- регион здесь ШЕСТАЯ,
ДОПОЛНИТЕЛЬНАЯ граница, применяется ПОСЛЕ (не вместо) существующих пяти:
_find_claim_token_groups ниже вычисляет окно ТЕМ ЖЕ _sentence_window,
что и раньше, регион лишь (а) решает, создавать ли окно ВООБЩЕ для
данного вхождения маркера, и (б) фильтрует уже извлечённые токен-спаны
ДО их группировки _group_overlapping_spans (тоже нетронута). Р9(а)
решения Lead 08-19: границы claim_control_gate ВНУТРИ фенса НЕ
подавляются -- пять регексов матчатся по всему сырому тексту без
region-осведомлённости вообще (не проверяют, находятся ли они "внутри
фенса") -- ЭТОГО кода в файле попросту нет, что и есть буквальное
соблюдение Р9(а): нечего "не подавлять", раз это никогда не трогалось.

И-0 (ЛЮБОЙ отказ модуля md_regions) -> сторож ведёт себя КАК СЕГОДНЯ
побайтно: `_find_claim_token_groups(text, scan_result=None)` выполняет
РОВНО тот алгоритм живого файла (каждый `if scan_result is not None:`
ниже -- мёртвая ветка при None, тот же порядок вставки в `found`, тот же
результат) -- см. _safe_scan.

И-1 (Rule #1, ленивость) / B2 "вызов сканера после path-scoping и
маркер-хита": scan() вызывается РОВНО ОДИН РАЗ за весь decide(), и
ТОЛЬКО ПОСЛЕ (а) tool_name/tool_input/path/text прошли существующий
path-scoping (как и раньше -- ни один из этих шагов region не касается),
(б) дешёвая проверка "хотя бы один NEGATIVE_MARKERS-паттерн матчится
ГДЕ-ТО в тексте" (pattern.search, без вычисления окон/токенов) дала True
-- на тексте без единого маркера scan() не вызывается вовсе (счётчик 0).

--- Рационал ДО region-aware версии (восстановлено дословно из
6a139c8, см. шапку выше) -----------------------------------------

ORIGIN (D-0082 synk, 2026-07-29): this file is a PORT of the sibling
Dog deployment's tools/claim_control_gate.py (their task t-021,
critic-hardened through attempt 2), landing here per the Lead's
accepted synk item (docs/tasks/2026-07-29_dog-incoming-sync.md, item
M). The fix semantics D1/D4b/D5/D6/D7/D8 and the t-022 line-break fix
(a physical line break is a LINE break, not a SENTENCE break, except
at structural breaks) are preserved verbatim in meaning from the
source. The adaptations made FOR THIS DEPLOY are: (1) ROOT_FILES,
rescoped to this repo's own root-level policy carriers (see
ROOT_FILES below -- this repo has no AGENTS.md, so it is not
included; ROADMAP.md, ARCHITECTURE.md, ARCHITECTURE_BOOT.md,
MEMORY_ARCHITECTURE.md, WHITE_PAPER.md, PROJECT_CHARTER.md,
PROJECT_PHILOSOPHY.md, ANTI_GOALS.md are added, this deploy's own root
carriers the source repo does not have); the PROCESS/, docs/ prefixes
and the exact logs/routing-log.jsonl path are unchanged, same as the
source; (2) this docstring, rewritten for this repo, and internal
references to half A use this repo's own filename
(tools/search_control_gate.py).

WHY: the source deployment observed the SAME class of incident three
times in one session: an agent asserted "X does not exist" without
ever having run a search for X -- including one case where a session
wrote into a calibration finding that a named doc "this deployment
does not have", when the file had existed for a while and nothing in
that session ever searched for its token. CLAUDE.md command-hygiene
rule 6 already forbids reporting an unverified negative; it was
enforced on discipline alone, and discipline missed three times in one
day there. This hook mechanizes the check by correlating the claim
against the search/read trail that already exists in the tool log
(half A's ledger), rather than trusting the claim on its face.

DELIVERY NOTE (enforcement-file-review rule, CLAUDE.md rule 2 /
routing rules): delivered by the builder as the inert neighbor file
tools/claim_control_gate_next.py (D-0069 -- a self-activating hook
file is never placed on its live path by its own builder); the Lead
moved it onto this live path and registered the PreToolUse hook in
.claude/settings.json at acceptance of t-338 (2026-07-29).

DELIVERY CHANNEL, IDENTICAL TO THE OTHER GATES: exit 0 on every path,
including malformed JSON stdin, a non-dict payload, or any unexpected
exception (main()'s single fail-open try/except boundary, mirroring
tools/hygiene_gate.py's main()). Output is
hookSpecificOutput.additionalContext on stdout when at least one
unsatisfied token GROUP is found; permissionDecision is deliberately
ABSENT -- emitting "allow" would auto-approve the very write being
flagged and silence the operator's own permission prompt, exactly the
reasoning tools/hygiene_gate.py documents for its own PreToolUse
output: additionalContext still reaches the model without it, and the
real permission decision stays on the normal path.

PIPELINE, PATH SCOPING (t-021 spec point 1):
  1. tool_name must be Edit or Write (several plausible key spellings
     checked, same probe-friendly philosophy as the sibling gates) --
     anything else is a silent pass.
  2. The target file path (several plausible key spellings) must fall
     under one of the in-scope prefixes -- PROCESS/, docs/, the exact
     file logs/routing-log.jsonl, or one of the named root files (see
     ROOT_FILES below, this deploy's own root-level policy carriers).
     Anything under vault/ or elsewhere (including tools/ itself) is a
     silent pass. Both absolute and repo-relative paths are handled,
     case-folded (t-021 D8), including the Git-Bash POSIX drive form
     (`_normalize_repo_relative`, `_posix_drive_to_windows`).
  3. The text about to be written (content for Write, the replacement
     string for Edit; several plausible key spellings checked either
     way) must be extractable as a string -- if it cannot be found at
     all on an in-scope path, silent pass (never crash, never guess).

NEGATIVE MARKERS, TOKEN EXTRACTION, GROUPING, CORRELATION (spec points
3-6, reworked for t-021 attempt 2 -- see `NEGATIVE_MARKERS`,
`_extract_token_spans`, `_group_overlapping_spans`, and
`_token_satisfied` below, each documenting its own rationale in
place): only three machine-tractable token SHAPES are ever extracted
(path-like, dotted-with-known-extension, UPPER_SNAKE) from the same
SENTENCE as a marker hit -- ordinary natural-language words are
deliberately never treated as claim subjects, since the false-positive
cost of that would be unacceptable and this narrow class is exactly
where the source repo's real incidents fell.

t-021 ATTEMPT-2 FIXES (source repo critic verdict on attempt 1,
fit_with_fixes, four Majors -- D1/D4b/D5/D6/D7/D8 live here; D2/D3/D4a
live on half A, see tools/search_control_gate.py's own docstring):

  D1 -- overlapping-token correlation was broken for the commonest
  search form. Attempt 1 extracted "RELATED_WORK", "RELATED_WORK.md",
  and "docs/RELATED_WORK.md" as three INDEPENDENT tokens from one
  span and tested each independently against the ledger -- so a
  session that ran `grep -rn RELATED_WORK docs/` (recording the whole
  Bash command, per half A's own design) still warned about the two
  compound forms, because neither "RELATED_WORK.md" nor
  "docs/RELATED_WORK.md" is a boundary-safe substring of that command.
  Fixed: `_extract_token_spans` returns each match's character span
  (not just its text); `_group_overlapping_spans` merges spans that
  overlap (by character position, within one marker's sentence window)
  into ONE group; `decide()` warns about a group only when EVERY
  member of the group is unsatisfied. A session that searched for the
  bare token, the whole path, or anything in between now silences the
  whole group.

  D4b -- proximity is not aboutness. Attempt 1's +/-200-character
  window picked up unrelated paths merely sitting nearby. Fixed:
  `_sentence_window` scopes token extraction to the SAME SENTENCE as
  the marker, splitting on `.`/`!`/`?`/newline -- see its own
  docstring for one deliberate refinement: a `.` is only treated as a
  sentence end when followed by whitespace or end-of-string, so a
  file extension or dotted identifier sitting right next to a marker
  (e.g. "RELATED_WORK.md отсутствует") does not get sentence-split
  mid-token, which would have defeated D1's own grouping fix for
  exactly the token shapes this gate targets. This is narrower than a
  literal "split on any `.`" reading; a real abbreviation followed
  immediately by a capitalized word (e.g. "see e.g. Foo") would still
  register as a sentence end under this refinement, same residual any
  simple splitter has.
  RESIDUAL, accepted per the source dispatch, NOT chased with
  heuristics: a retrospective write-up describing a past false claim
  ("it claimed `X` does not exist") can still trigger a warning on ITS
  OWN prose, since this gate has no reporting-verb or tense model and
  is not given one.

  D5 -- marker lexicon widened with the nearest paraphrases, including
  the source incident's own natural phrasing: "has no", "have no",
  "there is no", "there are no", "is missing", "are missing", "lacks",
  "never found", RU "нет ", "не удалось найти", "не содержится".

  D6 -- session-key asymmetry. Half A falls back to `unknown.jsonl`
  when `session_id` is absent from a PostToolUse payload; half B, when
  it DOES have a session_id from its own PreToolUse payload, used to
  read only `<session>.jsonl`, silently ignoring anything half A had
  recorded under the fallback for the same real session (e.g. if an
  earlier search happened before session_id was ever observed present
  on any payload). Fixed: `_read_ledger_terms` now unions
  `unknown.jsonl` into every session-specific read too.

  D7 -- satisfaction was too loose in both directions: a recorded term
  of `"py"` silenced a claim about `escape_check.py`, a lone `"_"`
  silenced every UPPER_SNAKE claim, and a search for
  `RELATED_WORKFLOW_NOTES` silenced a claim about `RELATED_WORK`.
  Fixed: `_token_satisfied` requires `MIN_TERM_LEN` (3) on the
  recorded term before it is even considered, and matching goes
  through `_boundary_contains`, which only counts a match when neither
  side of the matched span is itself a word character (`[A-Za-z0-9_]`)
  -- a token embedded inside a longer identifier no longer counts.

  D8 -- path scoping missed two real forms on a Windows host: a
  case-variant path (`Docs/notes.md` -- the same file, this filesystem
  is case-insensitive) and the Git-Bash POSIX absolute form
  (`/d/repo/docs/notes.md`), a hazard class CLAUDE.md's own Windows
  environment notes name explicitly. Fixed: `_in_scope` case-folds
  every prefix/name comparison; `_normalize_repo_relative` recognizes
  the POSIX single-letter-drive shape via `_posix_drive_to_windows`
  before falling through to the existing absolute-path handling.
"""
import bisect
import glob
import json
import os
import re
import sys

try:
    from tools.md_regions import scan, KIND_FENCED, KIND_BLOCKQUOTE, KIND_INLINE_CODE  # package-style
except ImportError:
    try:
        from md_regions import scan, KIND_FENCED, KIND_BLOCKQUOTE, KIND_INLINE_CODE  # sibling-module fallback
    except ImportError:
        scan = None
        KIND_FENCED = "fenced"
        KIND_BLOCKQUOTE = "blockquote"
        KIND_INLINE_CODE = "inline_code"

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_LEDGER_DIR = os.path.join(REPO, "logs", ".search-ledger")

# --- path scoping (t-021 D8) ----------------------------------------------

# This deploy's own root-level policy carriers (spec adaptation --
# see module docstring "ORIGIN"): no AGENTS.md here; ROADMAP.md,
# ARCHITECTURE.md, ARCHITECTURE_BOOT.md, MEMORY_ARCHITECTURE.md,
# WHITE_PAPER.md, PROJECT_CHARTER.md, PROJECT_PHILOSOPHY.md,
# ANTI_GOALS.md are this repo's own additions.
ROOT_FILES = {
    "DECISIONS.md",
    "CURRENT_CONTEXT.md",
    "DELEGATION_TABLE.md",
    "CLAUDE.md",
    "SYSTEM_PROMPT.md",
    "README.md",
    "BOOT.md",
    "ROADMAP.md",
    "ARCHITECTURE.md",
    "ARCHITECTURE_BOOT.md",
    "MEMORY_ARCHITECTURE.md",
    "WHITE_PAPER.md",
    "PROJECT_CHARTER.md",
    "PROJECT_PHILOSOPHY.md",
    "ANTI_GOALS.md",
}
ROOT_FILES_LOWER = {f.lower() for f in ROOT_FILES}
ROUTING_LOG_PATH = "logs/routing-log.jsonl"

# A Git-Bash-style POSIX absolute path with a single-letter drive segment,
# e.g. /d/repo/docs/notes.md -- CLAUDE.md's own Windows-host guidance names
# this exact hazard class (POSIX paths from Git Bash are not valid for
# Node/Python child processes) as the reason this needs handling.
_POSIX_DRIVE_RE = re.compile(r"^/([A-Za-z])(/.*)?$")

# --- negative markers, case-insensitive, Russian and English -------------
# t-021 D5: widened with the nearest paraphrases, including the source
# incident's own natural phrasing.
#
# F4(1) (критик t-339, живая репродукция класса подстрочных ложных
# срабатываний -- тот же класс, что t-335 закрыл для owns_gate.py/
# dispatch_gate.py, D-0043): маркеры раньше матчились ЧИСТОЙ подстрокой
# (`lower.find(marker, ...)`) -- "нет " (с пробелом) ложно матчился
# ВНУТРИ "станет "/"интернет "/"достанет " (кириллица, "нет" в конце
# слова перед пробелом), "has no" -- внутри "has notes". ФИКС (см.
# _boundary_pattern_for_marker, _scan_negative_claims ниже): каждый
# маркер матчится по ГРАНИЦЕ СЛОВА с той стороны, где сам маркер
# начинается/кончается словесным символом -- тот же принцип, что
# OWNS_WORD_RE (tools/dispatch_gate.py, класс D-0043, t-335). ВАЖНОЕ
# ОТЛИЧИЕ (критик t-339, зафиксировано): питоновский `re` -- unicode-
# aware, `\b` РАБОТАЕТ на кириллице корректно (проверено этой же
# правкой живыми тестами) -- утверждение CLAUDE.md командной гигиены
# "\b не работает на кириллице" относится к КЛАССУ SHELL-GREP (POSIX
# regex/локаль конкретной оболочки), НЕ к python `re` вообще; эти два
# класса не путать.
#
# ЕДИНСТВЕННОЕ ИСКЛЮЧЕНИЕ: "отсутству" -- НАМЕРЕННЫЙ СТЕМ (общий корень
# "отсутствует"/"отсутствие"/"отсутствуют" и т.д.), у которого правого
# края СЛОВА в природе не бывает -- после "отсутству" ВСЕГДА идёт
# словообразующий (словесный) суффикс, поэтому правая `\b` там НИКОГДА
# не совпала бы и сделала бы маркер полностью неработающим, ломая уже
# живые тесты (test_russian_marker_with_path_token_warns и др.).
# Решение задокументировано, не угадано молча -- см.
# _MARKER_NO_SUFFIX_BOUNDARY.

NEGATIVE_MARKERS = (
    "не существует",
    "не найден",
    "отсутству",
    "нет ни одного",
    "нигде не",
    "не содержит",
    "не содержится",
    "не удалось найти",
    "нет ",
    "does not exist",
    "doesn't exist",
    "not found",
    "no such",
    "nowhere",
    "is absent",
    "are absent",
    "0 matches",
    "no matches",
    "does not have",
    "doesn't have",
    "never existed",
    "has no",
    "have no",
    "there is no",
    "there are no",
    "is missing",
    "are missing",
    "lacks",
    "never found",
)

# F4(1): markers whose intentional design is a STEM/prefix, not a
# complete word -- excluded from the trailing word-boundary (see
# NEGATIVE_MARKERS' own docstring comment above for "отсутству"'s
# rationale). Empty unless a future marker needs the same carve-out.
_MARKER_NO_SUFFIX_BOUNDARY = {"отсутству"}

_WORD_CHAR_RE = re.compile(r"\w", re.UNICODE)


def _boundary_pattern_for_marker(marker: str) -> str:
    """F4(1): builds a regex pattern string for *marker* with a `\\b`
    word-boundary anchor on whichever side(s) the marker's own edge
    character is itself a word character (`\\w`, unicode-aware) --
    e.g. "нет " (trailing space, non-word) gets ONLY a leading `\\b`;
    "has no" (both edges alphabetic) gets both. See NEGATIVE_MARKERS'
    own docstring comment for why "отсутству" is excluded from the
    trailing boundary specifically (_MARKER_NO_SUFFIX_BOUNDARY)."""
    escaped = re.escape(marker)
    prefix = r"\b" if _WORD_CHAR_RE.match(marker[0]) else ""
    if marker in _MARKER_NO_SUFFIX_BOUNDARY:
        suffix = ""
    else:
        suffix = r"\b" if _WORD_CHAR_RE.match(marker[-1]) else ""
    return prefix + escaped + suffix


# Compiled once at import time -- one (marker, compiled_pattern) pair
# per NEGATIVE_MARKERS entry, case-insensitive (unicode-aware, matches
# the previous `text.lower()` behavior for both Cyrillic and ASCII).
_MARKER_PATTERNS = tuple(
    (marker, re.compile(_boundary_pattern_for_marker(marker), re.IGNORECASE))
    for marker in NEGATIVE_MARKERS
)

# --- token shapes (spec point 4) ------------------------------------------

# (a) path-like: contains / or \ AND ends in a filename with an extension.
PATH_TOKEN_RE = re.compile(
    r"[A-Za-z0-9_.\-]+(?:[/\\][A-Za-z0-9_.\-]+)+\.[A-Za-z0-9]+"
)

# (b) dotted identifier with a known-ish extension, no slash required.
EXT_TOKEN_RE = re.compile(
    r"\b[A-Za-z0-9_\-]+\.(?:py|md|json|yaml|jsonl|js)\b"
)

# (c) UPPER_SNAKE identifier of 2+ segments (e.g. RELATED_WORK, SKIP_RE).
UPPER_SNAKE_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")

TOKEN_RES = (PATH_TOKEN_RE, EXT_TOKEN_RE, UPPER_SNAKE_RE)

# t-021 D7: a recorded ledger term shorter than this is never considered a
# correlation source, in either direction -- "py" or "_" is too generic to
# count as evidence anything specific was checked.
MIN_TERM_LEN = 3

MSG_TEMPLATE = (
    "Negative claim about to be written without a matching search/read this "
    "session (rule 6, command hygiene): a positive control is required "
    "before reporting absence. Unverified token(s): {tokens}"
)


def _ledger_dir():
    """The session-ledger directory half A writes to. Overridable via
    the SEARCH_CONTROL_GATE_LEDGER_DIR env var -- SAME env var name as
    tools/search_control_gate.py's `_ledger_dir()`, since the two
    scripts must agree on where the ledger lives (t-021 spec)."""
    return os.environ.get("SEARCH_CONTROL_GATE_LEDGER_DIR") or _DEFAULT_LEDGER_DIR


def _first(d, keys):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return None


# --- path scoping (t-021 D8) ----------------------------------------------


def _posix_drive_to_windows(p):
    """Converts a Git-Bash-style POSIX absolute path with a single-
    letter drive segment (e.g. /d/repo/docs/notes.md) to its Windows
    equivalent (d:/repo/docs/notes.md). Returns None when *p* does not
    match this specific shape."""
    m = _POSIX_DRIVE_RE.match(p)
    if not m:
        return None
    drive = m.group(1)
    rest = m.group(2) or "/"
    return f"{drive}:{rest}"


def _normalize_repo_relative(path_str):
    """Best-effort repo-relative, forward-slash path, handling an
    absolute Windows path, an absolute Git-Bash POSIX-drive path
    (t-021 D8), or an already-relative one. Never raises -- an
    unresolvable absolute path (outside the repo, or on a different
    drive) is returned as-is so the caller's prefix checks simply fail
    to match (safe: out-of-scope), rather than crashing."""
    p = path_str.replace("\\", "/")
    posix_win = _posix_drive_to_windows(p)
    candidate = posix_win if posix_win is not None else path_str
    if posix_win is not None or os.path.isabs(candidate):
        try:
            rel = os.path.relpath(candidate, REPO).replace("\\", "/")
            if not rel.startswith(".."):
                return rel
        except Exception:
            pass
        repo_prefix = REPO.replace("\\", "/").rstrip("/") + "/"
        base = posix_win if posix_win is not None else p
        if base.lower().startswith(repo_prefix.lower()):
            return base[len(repo_prefix):]
        return base
    if p.startswith("./"):
        p = p[2:]
    return p


def _in_scope(path_str):
    """t-021 D8: every comparison is case-folded -- this filesystem is
    case-insensitive (Windows host), so `Docs/notes.md` is the same
    file as `docs/notes.md` and must be treated as in-scope too."""
    if not path_str:
        return False
    rel = _normalize_repo_relative(path_str)
    rel_lower = rel.lower()
    if rel_lower.startswith("process/"):
        return True
    if rel_lower.startswith("docs/"):
        return True
    if rel_lower == ROUTING_LOG_PATH.lower():
        return True
    if "/" not in rel and rel_lower in ROOT_FILES_LOWER:
        return True
    return False


# --- text extraction (spec point 2) --------------------------------------

WRITE_TEXT_KEYS = ("content", "text", "file_text", "fileText", "new_content")
EDIT_TEXT_KEYS = ("new_string", "newString", "replacement", "new_text", "newText")


def _extract_text(tool_name, tool_input):
    if not isinstance(tool_input, dict):
        return None
    primary = WRITE_TEXT_KEYS if tool_name == "Write" else EDIT_TEXT_KEYS
    secondary = EDIT_TEXT_KEYS if tool_name == "Write" else WRITE_TEXT_KEYS
    for k in primary + secondary:
        v = tool_input.get(k)
        if isinstance(v, str):
            return v
    return None


# --- negative-claim scan: sentence-scoped windowing (t-021 D4b, t-022 fix) -
#
# t-022 FIX (source repo's own reproduction, blocking promotion of t-021):
# attempt 2's D4b treated a bare `\n` as an UNCONDITIONAL sentence boundary,
# per a literal reading of "split on ./!/?/newline". Every policy file in
# a repo like this one is hard-wrapped markdown, so a marker and a token
# that merely landed on ADJACENT WRAPPED LINES of the same sentence (e.g.
# "...dies because gateway/requests.db\ndoes not exist...") went SILENT
# instead of warning -- worse than D4's original over-triggering complaint,
# because silence looks like success. A physical line break is a LINE
# break, not a SENTENCE break. Fixed: a `\n` is a boundary ONLY when it is
# part of a real structural break --
#   - `.`, `!`, or `?` followed by whitespace or end-of-text (the D4b
#     refinement, now applied uniformly to all three, not just `.`);
#   - a BLANK line -- `\n` + optional horizontal whitespace + another `\n`
#     (a paragraph break);
#   - the start of a markdown list item -- `\n` + optional horizontal
#     whitespace + a `-`/`*`/`+` or `N.` marker (list items are separate
#     statements even when unpunctuated);
#   - the start of a markdown TABLE ROW -- `\n` + optional horizontal
#     whitespace + `|` (F5, critic t-339: a table row/cell is its own
#     statement, same reasoning as a list item -- a marker in one cell
#     and a token in an ADJACENT cell of the same row/next row must not
#     be joined into one window just because they sit on one wrapped
#     "line" of source text);
#   - the start of a markdown HEADING -- `\n` + optional horizontal
#     whitespace + 1-6 `#` followed by whitespace or end-of-line (F5,
#     critic t-339, ATX heading syntax -- a heading line is a title,
#     never continues the previous paragraph's sentence).
# A single `\n` that is none of the above is NOT a boundary: the two lines
# it joins become ONE window, with the newline normalized to a space so a
# token or marker split only by the wrap still matches normally. Rejoining
# a TOKEN that is itself hyphenated/split mid-identifier across the wrap
# (e.g. "RELATED_\nWORK") is explicitly OUT OF SCOPE -- normalizing the
# newline to a space does not reconstruct that as one identifier, and no
# attempt is made to.
#
# ПОЗИЦИОННЫЙ ИНВАРИАНТ (region-aware добавление, 2026-08-19): пять
# регексов ниже -- байт-в-байт копия живого tools/claim_control_gate.py
# (:463-499 живого дерева на момент копии). НЕ РЕДАКТИРОВАТЬ без
# синхронной правки живого файла Lead'ом. См. test_claim_control_gate_md.py::
# test_five_boundary_regex_patterns_byte_identical_to_live.

# `.`/`!`/`?` immediately followed by whitespace or end-of-text.
_SENTENCE_PUNCT_RE = re.compile(r"[.!?](?=\s|$)")

# A blank line: \n, optional horizontal whitespace, another \n, optional
# horizontal whitespace before the next paragraph's first character. The
# WHOLE matched span is excluded from both neighboring windows.
_PARAGRAPH_BREAK_RE = re.compile(r"\n[ \t]*\n[ \t]*")

# The \n (+ optional horizontal whitespace) immediately BEFORE a markdown
# list marker (-, *, +, or N.) that is itself followed by whitespace or
# end-of-line/text -- the lookahead does not consume the marker itself, so
# the marker starts the NEXT window. The trailing-whitespace-after-marker
# requirement avoids misfiring on "**bold**" (a second "*" follows, not
# whitespace) or a horizontal rule ("---"), same narrow-by-design spirit as
# the rest of this file's marker/token regexes.
_LIST_ITEM_BOUNDARY_RE = re.compile(
    r"\n[ \t]*(?=[-*+](?:[ \t]|$)|\d+\.(?:[ \t]|$))"
)

# F5 (критик t-339): наш markdown (CURRENT_CONTEXT.md, SIBLING_MAP.md,
# CLAUDE.md, DECISIONS.md и т.д.) насыщен таблицами и заголовками --
# t-022 закрыл только предложение/абзац/список; строка таблицы и
# заголовок остаются НЕ границами до этой правки, что склеивает
# соседние ячейки/заголовок-и-параграф в одно "предложение" наравне с
# исходным t-022-дефектом. Тот же lookahead-стиль, что
# _LIST_ITEM_BOUNDARY_RE -- маркер (`|` / `#...#`) НЕ поглощается, он
# начинает СЛЕДУЮЩЕЕ окно.
_TABLE_ROW_BOUNDARY_RE = re.compile(r"\n[ \t]*(?=\|)")
_HEADING_BOUNDARY_RE = re.compile(r"\n[ \t]*(?=#{1,6}(?:[ \t]|$))")

_BOUNDARY_RES = (
    _SENTENCE_PUNCT_RE,
    _PARAGRAPH_BREAK_RE,
    _LIST_ITEM_BOUNDARY_RE,
    _TABLE_ROW_BOUNDARY_RE,
    _HEADING_BOUNDARY_RE,
)
# --- конец байт-в-байт копии пяти регексов ---------------------------------


def _find_boundaries(text):
    """Returns every boundary match span (start, end) across the five
    boundary regexes, computed ONCE per text (not once per marker
    occurrence -- `_sentence_window` is called once per marker hit, and
    re-scanning the whole text each time would be wasteful for a file
    with many markers). Order is UNSORTED (regex-encounter order, not
    text-position order) -- callers needing a position-sorted view use
    `_sorted_boundary_edges` (F6, critic t-339) rather than assuming
    this list is sorted."""
    spans = []
    for regex in _BOUNDARY_RES:
        for m in regex.finditer(text):
            spans.append((m.start(), m.end()))
    return spans


def _sorted_boundary_edges(boundaries):
    """F6 (критик t-339): pre-sorts boundary EDGES into two flat lists
    -- every b_end, every b_start -- so `_sentence_window` can find its
    two answers via `bisect` (O(log n) per call) instead of a linear
    scan through ALL boundaries on EVERY marker occurrence (was
    O(occurrences * boundaries) -- quadratic in text length for a
    marker-DENSE text, where both occurrences and boundaries scale with
    length). Computed ONCE per text by `_scan_negative_claims`, same
    "once per text, not once per marker" principle `_find_boundaries`
    itself already followed. Splitting starts and ends into two
    INDEPENDENT sorted lists (rather than keeping (start, end) pairs
    together) is intentional and still correct: the two bisect lookups
    in `_sentence_window` only ever need "the nearest END <= X" and
    "the nearest START >= Y" independently of which ORIGINAL boundary
    span either edge came from -- see that function's own docstring."""
    ends_sorted = sorted(b_end for _b_start, b_end in boundaries)
    starts_sorted = sorted(b_start for b_start, _b_end in boundaries)
    return ends_sorted, starts_sorted


def _sentence_window(text, marker_start, marker_end, boundary_edges):
    """Returns (start, end) bounding the sentence containing
    text[marker_start:marker_end]: start is the END of the nearest
    boundary span that ends at or before marker_start (0 if none); end
    is the START of the nearest boundary span that starts at or after
    marker_end (len(text) if none). The boundary span itself is
    excluded from both windows on either side of it.

    F6 (критик t-339): *boundary_edges* is the (ends_sorted,
    starts_sorted) pair from `_sorted_boundary_edges`, NOT the raw
    `_find_boundaries` list -- `bisect.bisect_right`/`bisect_left` find
    both answers in O(log n) instead of the previous O(n) linear scan
    through every boundary on every call (this function is called once
    PER MARKER OCCURRENCE, so the old linear scan made the whole
    `_scan_negative_claims` pass O(occurrences * boundaries) --
    quadratic on a marker-dense text where both scale with length; see
    tools/test_claim_control_gate.py's F6 timing measurements)."""
    ends_sorted, starts_sorted = boundary_edges
    end_idx = bisect.bisect_right(ends_sorted, marker_start)
    start = ends_sorted[end_idx - 1] if end_idx > 0 else 0
    start_idx = bisect.bisect_left(starts_sorted, marker_end)
    end = starts_sorted[start_idx] if start_idx < len(starts_sorted) else len(text)
    return start, end


def _scan_negative_claims(text):
    """Немодифицированная форма (маркер, окно) -- сохранена для прямого
    юнит-тестирования/регресса паритета с живым файлом; region-осведом-
    лённый пайплайн (`_find_claim_token_groups` ниже) её НЕ вызывает --
    ему нужна ещё и позиция самого маркера (marker_start/marker_end) для
    региона, которую эта функция не отдаёт наружу.

    До-region докстринг (восстановлен из 6a139c8): yields (marker,
    window) for every case-insensitive, WORD-BOUNDARY-SAFE occurrence of
    a marker in *text* (F4(1), критик t-339 -- see NEGATIVE_MARKERS' own
    docstring comment and `_boundary_pattern_for_marker`), window being
    the SENTENCE containing the hit (t-021 D4b + t-022 fix; see
    `_sentence_window`). A lone `\\n` inside the window (a mere wrap, not
    a boundary) is normalized to a space before the window is handed to
    token extraction -- see this section's "t-022 FIX" note above for
    what this does and does not fix. Multiple occurrences of the same
    marker each yield their own window.

    F6: boundary edges are sorted ONCE per text (`_sorted_boundary_edges`),
    not once per marker occurrence -- `_sentence_window` below then does
    an O(log n) bisect lookup per occurrence instead of the previous
    O(n) linear scan."""
    boundary_edges = _sorted_boundary_edges(_find_boundaries(text))
    for marker, pattern in _MARKER_PATTERNS:
        for m in pattern.finditer(text):
            idx = m.start()
            marker_end = m.end()
            s, e = _sentence_window(text, idx, marker_end, boundary_edges)
            window = text[s:e].replace("\n", " ")
            yield marker, window


# --- token extraction + overlap grouping (t-021 D1) -----------------------


def _extract_token_spans(window):
    """Returns a list of (start, end, token_text) for every regex
    match in *window*, one entry per match -- spans MAY overlap across
    the three shapes (e.g. "docs/RELATED_WORK.md", "RELATED_WORK.md",
    and "RELATED_WORK" from the same location). Grouping these
    overlaps is `_group_overlapping_spans`'s job, not this function's."""
    spans = []
    for regex in TOKEN_RES:
        for m in regex.finditer(window):
            spans.append((m.start(), m.end(), m.group(0)))
    return spans


def _extract_tokens(window):
    """Flat set of token strings from *window*, ignoring position --
    kept as a small convenience/test-surface on top of
    `_extract_token_spans`; `decide()` itself uses the grouped form."""
    return {tok for _, _, tok in _extract_token_spans(window)}


def _group_overlapping_spans(spans):
    """Merges (start, end, token) tuples whose character spans overlap
    into groups (t-021 D1 fix): "RELATED_WORK", "RELATED_WORK.md", and
    "docs/RELATED_WORK.md" extracted from the SAME location are one
    group, not three independent claims -- a search that matches ANY
    member of the group is evidence for the whole group (see
    `_token_satisfied` usage in `decide()`). Returns a list of
    frozensets of token strings, one per merged group. Sweeps spans
    sorted by start position, extending the current group's end
    whenever the next span starts before it -- O(n log n)."""
    if not spans:
        return []
    ordered = sorted(spans, key=lambda t: (t[0], t[1]))
    groups = []
    current = [ordered[0]]
    current_end = ordered[0][1]
    for span in ordered[1:]:
        if span[0] < current_end:
            current.append(span)
            current_end = max(current_end, span[1])
        else:
            groups.append(current)
            current = [span]
            current_end = span[1]
    groups.append(current)
    return [frozenset(tok for _, _, tok in g) for g in groups]


# --- region gate (B2, t-509) -----------------------------------------------


def _safe_scan(text: str):
    """И-0: None при отсутствии md_regions / исключении scan() /
    degraded=True -- все три триггера сводятся к одному сигналу
    вызывающему коду (region-путь целиком отключается)."""
    if scan is None:
        return None
    try:
        result = scan(text)
    except Exception:
        return None
    if result.degraded:
        return None
    return result


def _region_at(scan_result, offset: int):
    regions = scan_result.regions
    if not regions:
        return None
    starts = [r.start for r in regions]
    idx = bisect.bisect_right(starts, offset) - 1
    if idx < 0:
        return None
    region = regions[idx]
    if region.start <= offset < region.end:
        return region
    return None


def _classify(region) -> str:
    """Тот же приоритет, что tools/negative_lint_md.py._classify (см.
    его докстринг для полного обоснования порядка) -- НАМЕРЕННО не
    импортирован оттуда: два сторожа, две отдельные семантики region-
    политики, D-0043 здесь про общий СКАНЕР, не общий predicate."""
    if region is None:
        return "prose"
    if region.unterminated and KIND_FENCED in region.kinds:
        return "prose"
    if KIND_FENCED in region.kinds:
        return "fenced"
    if KIND_INLINE_CODE in region.kinds:
        return "inline_code"
    if KIND_BLOCKQUOTE in region.kinds:
        return "blockquote"
    return "prose"


_EXCLUDED_KINDS = ("fenced", "blockquote")


def _find_claim_token_groups(text, scan_result=None):
    """Region-осведомлённая версия. scan_result=None (И-0 дефолт) ->
    ПОЛНОСТЬЮ совпадает с алгоритмом живого файла: каждый
    `if scan_result is not None:` ниже -- мёртвая ветка, тот же порядок
    matcherов (_MARKER_PATTERNS -> finditer), тот же порядок вставки в
    `found` (первый маркер группы побеждает) -- см. докстринг модуля
    "И-0". scan_result передан (region доступен) -> B2 политика: маркер,
    чья ПОЗИЦИЯ попадает в fenced/blockquote, не порождает окно вовсе
    (continue до _sentence_window); токен, чья ПОЗИЦИЯ (после перевода
    из window-относительных координат в абсолютные: s + rel_start --
    замена "\\n"->" " в window не меняет длину, абсолютное индексирование
    остаётся валидным) попадает в fenced/blockquote, не засчитывается --
    отфильтрован ДО _group_overlapping_spans, так что группа, все токены
    которой были только цитируемыми, исчезает целиком (frozenset()
    falsy -> `if group` ниже её отбрасывает, как и раньше для пустых
    групп).

    До-region докстринг (восстановлен из 6a139c8, всё ещё описывает
    ядро этой функции при scan_result=None): returns
    {frozenset(tokens): marker} for every unique overlap group extracted
    from every negative-claim sentence in *text* (t-021 D1 + D4b). The
    first marker found for a given group wins, for the report message.
    An empty group (should not occur, defensive) is skipped."""
    found = {}
    boundary_edges = _sorted_boundary_edges(_find_boundaries(text))
    for marker, pattern in _MARKER_PATTERNS:
        for m in pattern.finditer(text):
            idx = m.start()
            marker_end = m.end()
            if scan_result is not None:
                mkind = _classify(_region_at(scan_result, idx))
                if mkind in _EXCLUDED_KINDS:
                    continue  # B2: fenced/blockquote -- окно не создаётся
            s, e = _sentence_window(text, idx, marker_end, boundary_edges)
            window = text[s:e].replace("\n", " ")
            spans = _extract_token_spans(window)
            if scan_result is not None:
                spans = [
                    sp for sp in spans
                    if _classify(_region_at(scan_result, s + sp[0])) not in _EXCLUDED_KINDS
                ]
            for group in _group_overlapping_spans(spans):
                if group and group not in found:
                    found[group] = marker
    return found


# --- ledger correlation (spec point 5, t-021 D6/D7) ------------------------


def _session_id(payload):
    """Same literal-key philosophy as the ledger writer
    (tools/search_control_gate.py's `_session_id()`): only the
    exact `session_id` key is checked, not a guessed alias list."""
    if isinstance(payload, dict):
        value = payload.get("session_id")
        if isinstance(value, str) and value:
            return value
    return None


def _read_ledger_terms(session):
    """Reads every recorded search/read TERM relevant to *session*.
    When session is None (unknown), reads EVERY ledger file instead of
    just "unknown.jsonl" -- spec point 5: "better a false silence than
    a false accusation is WRONG here; prefer reading more". When
    session IS known, `unknown.jsonl` is unioned in too (t-021 D6): a
    search recorded before session_id was ever observed present on any
    payload must not become invisible to a later claim in the same
    real session just because it landed under the fallback name. Never
    raises; a missing directory or unreadable/malformed file yields
    fewer terms rather than a crash (fail toward warning, not toward
    silently passing a real gap)."""
    terms = []
    try:
        ledger_dir = _ledger_dir()
        if not os.path.isdir(ledger_dir):
            return terms
        if session:
            names = [session + ".jsonl"]
            if session != "unknown":
                names.append("unknown.jsonl")
            paths = [os.path.join(ledger_dir, n) for n in names]
        else:
            paths = glob.glob(os.path.join(ledger_dir, "*.jsonl"))
        for path in paths:
            if not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    term = rec.get("term") if isinstance(rec, dict) else None
                    if isinstance(term, str) and term:
                        terms.append(term)
    except Exception:
        pass
    return terms


def _is_word_char(ch):
    return bool(ch) and (ch.isalnum() or ch == "_")


def _boundary_contains(haystack, needle):
    """True if *needle* occurs in *haystack* (case-insensitive) at a
    boundary-safe position -- neither character immediately before nor
    after the match is itself a "word" character (`[A-Za-z0-9_]`), so a
    token embedded inside a longer identifier does not count (t-021
    D7): `RELATED_WORK` inside `RELATED_WORKFLOW_NOTES` fails this
    check (the character right after the match, `F`, is a word char),
    while `RELATED_WORK` inside `docs/RELATED_WORK.md` passes (bounded
    by `/` and `.`, neither a word char)."""
    if len(needle) < MIN_TERM_LEN:
        return False
    h = haystack.lower()
    n = needle.lower()
    start = 0
    while True:
        idx = h.find(n, start)
        if idx == -1:
            return False
        before_ok = idx == 0 or not _is_word_char(h[idx - 1])
        after_pos = idx + len(n)
        after_ok = after_pos == len(h) or not _is_word_char(h[after_pos])
        if before_ok and after_ok:
            return True
        start = idx + 1


def _token_satisfied(token, terms):
    """A token is SATISFIED if it appears, boundary-safe, inside a
    recorded term, OR a recorded term appears, boundary-safe, inside
    the token -- so a search/read of `docs/RELATED_WORK.md` satisfies
    a claim about `RELATED_WORK`, and vice versa. t-021 D7: a recorded
    term shorter than `MIN_TERM_LEN` is skipped entirely, in either
    direction -- too generic (`"py"`, `"_"`) to count as evidence
    anything specific was checked."""
    for term in terms:
        if len(term) < MIN_TERM_LEN:
            continue
        if _boundary_contains(term, token):
            return True
        if _boundary_contains(token, term):
            return True
    return False


def decide(payload):
    """Pure logic, no I/O beyond reading the ledger -- directly
    testable. Returns (0, None) on a silent pass, or (0, dict) ready
    for json.dumps on stdout when at least one unsatisfied token GROUP
    is found (t-021 D1: a group is unsatisfied only when EVERY member
    is unsatisfied). exit_code is ALWAYS 0 (WARN mode is absolute,
    identical contract to the sibling gates). region-aware addition:
    scan() called at most once, AFTER path-scoping and a cheap "any
    marker occurs anywhere" pre-check (И-1)."""
    if not isinstance(payload, dict):
        return 0, None

    tool_name = _first(payload, ("tool_name", "toolName", "tool"))
    if tool_name not in ("Edit", "Write"):
        return 0, None

    tool_input = _first(payload, ("tool_input", "toolInput", "input", "parameters"))
    if not isinstance(tool_input, dict):
        return 0, None

    path = _first(tool_input, ("file_path", "path", "filePath", "file"))
    if not isinstance(path, str) or not _in_scope(path):
        return 0, None

    text = _extract_text(tool_name, tool_input)
    if not text:
        return 0, None

    # И-1: дешёвый предфильтр -- хотя бы один негативный маркер ГДЕ-ТО в
    # тексте, БЕЗ вычисления окон/токенов. На тексте без маркеров scan()
    # не вызывается вовсе (см. test_scan_not_called_when_no_marker_hit).
    if not any(pattern.search(text) for _marker, pattern in _MARKER_PATTERNS):
        return 0, None

    scan_result = _safe_scan(text)
    groups = _find_claim_token_groups(text, scan_result)
    if not groups:
        return 0, None

    terms = _read_ledger_terms(_session_id(payload))
    unsatisfied = {
        group: marker
        for group, marker in groups.items()
        if not any(_token_satisfied(tok, terms) for tok in group)
    }
    if not unsatisfied:
        return 0, None

    parts = []
    for group, marker in sorted(unsatisfied.items(), key=lambda kv: sorted(kv[0])[0]):
        rep = max(group, key=len)
        parts.append(f'"{rep}" (flagged by "{marker}")')
    context = MSG_TEMPLATE.format(tokens="; ".join(parts))
    # permissionDecision deliberately absent -- see module docstring.
    return 0, {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        }
    }


def _reconfigure_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _read_stdin_bytes():
    """Reads stdin as raw bytes, but ONLY when stdin is not a TTY (same
    guard and rationale as tools/hygiene_gate.py's `_read_stdin_bytes`):
    a PreToolUse hook receives the harness's JSON on stdin, piped; a
    human running this script by hand from an interactive shell has no
    piped input, and blocking on a read there would hang forever."""
    if sys.stdin.isatty():
        return b""
    return sys.stdin.buffer.read()


def main():
    """The ONE fail-open try/except boundary for the whole script
    (mirrors tools/hygiene_gate.py's main()): WARN mode is absolute --
    exit 0 on every path, including a TTY with nothing piped in,
    malformed stdin, a non-dict payload, or any unexpected exception.
    Never raises, never returns non-zero."""
    try:
        _reconfigure_stdout_utf8()
        raw_bytes = _read_stdin_bytes()
        if not raw_bytes:
            return 0
        raw = raw_bytes.decode("utf-8", errors="replace")
        payload = json.loads(raw)
        exit_code, output = decide(payload)
        if output is not None:
            sys.stdout.write(json.dumps(output, ensure_ascii=False) + "\n")
        return exit_code
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
