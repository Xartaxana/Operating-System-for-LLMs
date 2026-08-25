"""install_parity.py -- read-only CHECK that a host tree, after an
install or upgrade of this kit, physically carries every RULE and
CLAUSE of the policy this kit shipped (not just the files that carry
them). Class this closes: kit v0.8.1 delivered to a host (commit
ec4e6f0) where the host-branch-restoration step of an upgrade silently
reverted ~14 policy blocks in the host's CLAUDE.md back to their
pre-upgrade text -- the FILES all landed (the copy step worked), the
enforcement CHECKS that reference those rules landed and ran, but the
rule TEXT itself was gone; the checks were watching an empty room. A
file-existence check would have stayed green throughout. See this
tool's own spec and the "OUTBOUND" findings its own regression
fixture reproduces, for the real incident.

THIS TOOL NEVER WRITES TO THE HOST TREE. It only reads. The record of
an install-parity run belongs to the calling step (the upgrade skill's
own journal/ledger entry writes "Install parity: ..."), never to this
script -- a tool self-certifying its own delivery would be circular.

MANIFEST (install_parity_anchors.json, sibling of this script by
default) -- a JSON list of unit records:

    {
      "unit_id": "<ledger-key>[:<suffix>]",
      "kit_path": "toolkit/<path, forward slashes>",
      "host_path": "<path a host install carries this at, forward
                    slashes, relative to --root>",
      "anchors": ["<literal substring>", ...],
      "kind": "anchor" | "path"
    }

kind "anchor": the unit's HOST FILE must physically contain every one
of `anchors` as a literal substring (not a regex -- deliberately, so an
anchor string containing regex metacharacters like ".*" or "[" is
matched literally). Used for POLICY CARRIERS -- files whose CONTENT
matters, not just their presence: CLAUDE.md, `.claude/agents/*.md`
role profiles, `PROCESS/*.md`.

kind "path": only the host file/directory's PRESENCE is checked
(`anchors` must be `[]`). Used for the rest of the kit's shipped
mechanisms, one unit per row of ADOPTION_LEDGER.template.md not
already covered by an "anchor" unit above.

unit_id / ledger matching: the substring of unit_id before an optional
first ":" is the LEDGER KEY (the part after ":" is only a
human-readable disambiguator for units that share one ledger row, e.g.
five role-profile units share the ledger's single "Role profiles" row
-- "role-profiles:scout", "role-profiles:builder", ...). A unit MATCHES
a host adoption-ledger row when every STEM of the ledger key is a
STEM present in that row's "Kit mechanism" cell (order-independent,
plural/singular-insensitive -- see stems()). This is deliberately
looser than an exact string match: ledger row prose varies in
wording/casing and this tool must survive that without going stale
every time the ledger's own prose is touched.

CLASSIFICATION of a MISSING host path or a MISSING anchor within an
existing-but-incomplete host file (K6 of this tool's spec): looked up
by the unit's ledger row status --
  adopt                          -> MISSING      (a real problem)
  native-equivalent / deferred / rejected
                                  -> informational (host chose not to
                                     carry it; absence is expected)
  no matching row / unrecognized status text
                                  -> UNKNOWN      (can't tell -- also
                                     a real problem, reported loudly)
No ledger found at all (bootstrap host, pre-versioning): EVERY missing
path/anchor classifies UNKNOWN (there is nothing to consult), and the
report header says so explicitly.

SPECIAL CASE -- an existing but EMPTY host file (0 bytes / all
whitespace): every one of its anchors is reported MISSING
UNCONDITIONALLY, ledger status ignored. An adopted-or-not decision can
legitimately mean "this file was never copied here" -- it cannot
legitimately mean "this file was copied here empty"; that is always a
delivery defect, never a native-equivalent/deferred/rejected outcome.

FORM: both sides of every comparison go through normalize_text() --
BOM stripped, CRLF collapsed to LF -- before the literal-substring
check, so a host file checked out with different line endings than
the kit source the anchor was derived from still compares correctly.
Non-UTF8 host bytes are decoded with errors="replace" and a WARN line
is printed; the comparison still runs on the replaced text (fail-open,
never a crash). `model:` YAML-frontmatter lines are excluded from
anchor derivation by construction (see _strip_frontmatter) -- a host
binds its own model per role, and that is a legitimate difference, not
a parity gap.

EXIT CODE CONTRACT (K1): 0 -- every anchor/path present, or every
absence is `informational` per the ledger. 1 -- at least one MISSING
or UNKNOWN. 2 -- the run itself cannot be trusted (a broken manifest,
a bad --root); no traceback is ever allowed to reach the caller.

CLI:
  --check                  run the comparison, see EXIT CODE CONTRACT.
  --emit-anchors            derive anchors from one source file
                            (headers / numbered rules / CAPS-marker
                            phrases) and print them. With --unit-id
                            also given, prints one full manifest entry
                            (JSON object); without it, prints the bare
                            derived-anchor list (JSON array) -- the
                            entry is then hand-merged into the
                            committed manifest, the same way this
                            tool's own shipped manifest was built.
  --source <path>           file to derive anchors from (--emit-anchors).
  --unit-id / --kit-path / --host-path / --kind
                            fields of the manifest entry being emitted
                            (--emit-anchors, all optional except when
                            --unit-id is given, in which case
                            --kit-path/--host-path/--kind are also
                            required to build a well-formed entry).
  --root <path>             host tree root to check against (--check).
                            Default: the current working directory --
                            this mirrors how the tool is actually
                            invoked (from inside the freshly installed
                            or upgraded project, per INSTALL.md).
  --manifest <path>         manifest location. Default: sibling of
                            this script, install_parity_anchors.json.
  --ledger <path>           adoption-ledger path. Default: search
                            <root>/ADOPTION_LEDGER.md, then
                            <root>/docs/ADOPTION_LEDGER.md (K7); the
                            path actually used (or the list checked,
                            on a miss) is always printed in the report
                            header.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


MAX_ANCHOR_LEN = 200


def _reconfigure_stdout_utf8() -> None:
    """Same fix/pattern as every other CLI in this kit and its HQ twin
    (tools/parity_check.py._reconfigure_stdout_utf8, hygiene_gate.py,
    session_context.py, dod_track.py, journal_echo.py): stdout defaults
    to the process's console codepage when piped, not UTF-8, and this
    tool's own anchors/paths are free-form text with no charset
    restriction (Cyrillic/CJK anchors are an explicit adversarial
    case, M4). errors="replace" keeps this fail-open and cosmetic
    only -- never raises, never blocks the exit-code contract above."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class ManifestError(Exception):
    """The manifest itself (or a --root/--manifest argument) fails to
    parse or fails structural validation. Always means: abort the
    whole run, print exactly one ERROR line, exit 2 -- never attempt a
    partial per-unit report on top of an untrustworthy manifest."""


# ---------------------------------------------------------------------------
# Text normalization (M3: CRLF->LF and BOM stripping on BOTH sides in one function)
# ---------------------------------------------------------------------------


def normalize_text(s: str) -> str:
    """BOM-strip + CRLF->LF, applied identically to anchor strings and
    host file content -- the ONE function both sides of every
    comparison route through, so a host checked out with different
    line endings than the kit source an anchor was derived from still
    compares correctly (a literal substring check, not a regex)."""
    if s.startswith("\ufeff"):
        s = s[1:]
    return s.replace("\r\n", "\n")


# ---------------------------------------------------------------------------
# Anchor derivation (--emit-anchors): headers, numbered rules, CAPS markers
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r"^#{1,6}\s+(.*\S)\s*$")
_NUMBERED_RULE_RE = re.compile(r"^(\d{1,3}[a-z]?)\.\s+(.*\S)\s*$")
_WORD_RE = re.compile(r"\S+")


def _strip_frontmatter(text: str) -> str:
    """Drop a leading YAML frontmatter block (--- ... ---) entirely --
    role-file `model:` bindings are excluded from parity BY
    CONSTRUCTION (M3's "model: во фронтматтере роль-файлов исключён"):
    a host binds its own model per role, legitimately. Other
    frontmatter fields (name/description) carry no policy clause
    either, so the whole block is dropped rather than special-casing
    just the `model:` line. A no-op on files with no frontmatter
    (CLAUDE.md, PROCESS/*.md)."""
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :])
    return text


def _is_caps_token(tok: str) -> bool:
    core = tok.strip(".,;:()\"'`")
    if len(core) < 2:
        return False
    if not any(c.isalpha() for c in core):
        return False
    return core.upper() == core


def _extract_caps_phrases(line: str) -> list[str]:
    """A CAPS-marker phrase is a run of >=2 ALL-CAPS words, allowing up
    to 3 short (<=14 char) non-caps "glue" words/symbols between caps
    words in the same run -- real examples this must catch verbatim:
    "TWO-LAYER CRITIC ENTRY" (pure caps run) and "DRAFTING -> designer
    BY DEFAULT" (an arrow + one lowercase word glued between two caps
    words) -- both are load-bearing clause markers in this kit's own
    CLAUDE.md and both are exactly the class the ec4e6f0 regression
    silently dropped (see module docstring)."""
    words = list(_WORD_RE.finditer(line))
    phrases: list[str] = []
    i = 0
    n = len(words)
    while i < n:
        if _is_caps_token(words[i].group()):
            start = i
            last_caps = i
            glue_run = 0
            j = i + 1
            while j < n:
                if _is_caps_token(words[j].group()):
                    last_caps = j
                    glue_run = 0
                    j += 1
                else:
                    glue_run += 1
                    if glue_run > 3 or len(words[j].group()) > 14:
                        break
                    j += 1
            if last_caps > start:
                phrase = line[words[start].start() : words[last_caps].end()]
                phrases.append(phrase.strip())
                i = last_caps + 1
                continue
        i += 1
    return phrases


def derive_anchors(text: str) -> list[str]:
    """Derive structural anchors from one policy-carrier file's text:
    markdown headers, numbered top-level rule lines, and CAPS-marker
    phrases (see _extract_caps_phrases). Order-preserving, de-duplicated,
    each anchor truncated to MAX_ANCHOR_LEN (a longer heading/line is
    still a valid, if truncated, literal-substring anchor)."""
    text = normalize_text(text)
    body = _strip_frontmatter(text)
    anchors: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        a = raw.strip()
        if not a:
            return
        if len(a) > MAX_ANCHOR_LEN:
            a = a[:MAX_ANCHOR_LEN]
        if a in seen:
            return
        seen.add(a)
        anchors.append(a)

    for line in body.split("\n"):
        m = _HEADER_RE.match(line)
        if m:
            add(m.group(1))
            continue
        m = _NUMBERED_RULE_RE.match(line)
        if m:
            add(f"{m.group(1)}. {m.group(2)}")
        for phrase in _extract_caps_phrases(line):
            add(phrase)

    return anchors


# ---------------------------------------------------------------------------
# Manifest load + structural validation
# ---------------------------------------------------------------------------

REQUIRED_UNIT_FIELDS = ("unit_id", "kit_path", "host_path", "anchors", "kind")
VALID_KINDS = ("anchor", "path")


def _no_dup_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for k, v in pairs:
        if k in d:
            raise ManifestError(f"manifest object has a duplicate JSON key: {k!r}")
        d[k] = v
    return d


def _check_no_path_traversal(unit_id: str, field: str, value: str) -> None:
    parts = re.split(r"[\\/]+", value)
    if ".." in parts:
        raise ManifestError(
            f"unit {unit_id!r} field {field!r} contains a '..' path segment "
            f"({value!r}) -- refusing to read it"
        )


def load_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    if not manifest_path.is_file():
        raise ManifestError(f"manifest not found: {manifest_path}")
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"manifest unreadable: {manifest_path} ({exc})") from exc
    try:
        data = json.loads(raw, object_pairs_hook=_no_dup_keys)
    except ManifestError:
        raise
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {manifest_path} ({exc})") from exc

    if not isinstance(data, list):
        raise ManifestError(
            f"manifest must be a JSON list of unit records, got {type(data).__name__}"
        )

    seen_ids: set[str] = set()
    total_anchor_count = 0
    units: list[dict[str, Any]] = []

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ManifestError(f"manifest entry #{i} is not an object")
        missing = [f for f in REQUIRED_UNIT_FIELDS if f not in entry]
        if missing:
            raise ManifestError(f"manifest entry #{i} missing field(s): {missing}")

        unit_id = entry["unit_id"]
        kit_path = entry["kit_path"]
        host_path = entry["host_path"]
        anchors = entry["anchors"]
        kind = entry["kind"]

        for fname, fval in (("unit_id", unit_id), ("kit_path", kit_path), ("host_path", host_path), ("kind", kind)):
            if not isinstance(fval, str):
                raise ManifestError(
                    f"manifest entry #{i} field {fname!r} must be a string, got {type(fval).__name__}"
                )
        if not isinstance(anchors, list):
            raise ManifestError(
                f"manifest entry #{i} field 'anchors' must be a list, got {type(anchors).__name__}"
            )
        for a in anchors:
            if not isinstance(a, str):
                raise ManifestError(
                    f"manifest entry #{i} ({unit_id!r}) has a non-string anchor: {a!r}"
                )

        if kind not in VALID_KINDS:
            raise ManifestError(f"manifest entry #{i} ({unit_id!r}) has an unknown kind: {kind!r}")

        if unit_id in seen_ids:
            raise ManifestError(f"manifest has a duplicate unit_id: {unit_id!r}")
        seen_ids.add(unit_id)

        _check_no_path_traversal(unit_id, "kit_path", kit_path)
        _check_no_path_traversal(unit_id, "host_path", host_path)

        seen_anchor_pairs: set[str] = set()
        for a in anchors:
            if a in seen_anchor_pairs:
                raise ManifestError(f"unit {unit_id!r} has a duplicate anchor: {a!r}")
            seen_anchor_pairs.add(a)
            if a.strip() == "":
                raise ManifestError(f"unit {unit_id!r} has an empty/whitespace-only anchor")
            if len(a) > MAX_ANCHOR_LEN:
                raise ManifestError(
                    f"unit {unit_id!r} has an anchor over {MAX_ANCHOR_LEN} chars "
                    f"({len(a)} chars): {a[:40]!r}..."
                )
            if kind == "path":
                raise ManifestError(f"unit {unit_id!r} has kind 'path' but a non-empty anchors list")

        if kind == "anchor":
            total_anchor_count += len(anchors)

        units.append(entry)

    if total_anchor_count == 0:
        raise ManifestError(
            "manifest carries zero total anchors across every 'anchor'-kind unit -- "
            "a check that can never fail is indistinguishable from a broken one"
        )

    return units


# ---------------------------------------------------------------------------
# Ledger: search order (K7), parse, classify (K6)
# ---------------------------------------------------------------------------

_STATUS_RE = re.compile(r"^(adopt|native-equivalent|deferred|rejected)\b", re.IGNORECASE)
_STEM_SPLIT_RE = re.compile(r"[^a-zA-Z0-9]+")


def stems(s: str) -> set[str]:
    out: set[str] = set()
    for tok in _STEM_SPLIT_RE.split(s.lower()):
        if not tok:
            continue
        if len(tok) > 3 and tok.endswith("s"):
            tok = tok[:-1]
        out.add(tok)
    return out


def ledger_key(unit_id: str) -> str:
    return unit_id.split(":", 1)[0]


def find_ledger(root: Path, ledger_arg: str | None) -> tuple[Path | None, list[Path]]:
    if ledger_arg:
        p = Path(ledger_arg)
        if not p.is_absolute():
            p = root / p
        checked = [p]
        return (p, checked) if p.is_file() else (None, checked)
    candidates = [root / "ADOPTION_LEDGER.md", root / "docs" / "ADOPTION_LEDGER.md"]
    for c in candidates:
        if c.is_file():
            return c, candidates
    return None, candidates


def parse_ledger(path: Path) -> tuple[list[tuple[str, str]], bool]:
    """Returns (rows, corrupt). rows is a list of (mechanism_cell,
    status_cell_raw) for every parsed pipe-table data row. A read/parse
    failure is fail-open (corrupt=True, rows=[]) -- never aborts the
    whole run (M4: "битый леджер (fail-open WARN-строка, не exit 2)")."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], True

    rows: list[tuple[str, str]] = []
    try:
        for line in raw.split("\n"):
            line = normalize_text(line).strip()
            if not line.startswith("|") or not line.endswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 2:
                continue
            first = cells[0]
            if not first or set(first) <= {"-", ":"}:
                continue
            if first.lower() in ("kit mechanism",):
                continue
            rows.append((first, cells[1] if len(cells) > 1 else ""))
    except Exception:
        return [], True

    return rows, False


def classify_missing(unit_id: str, ledger_found: bool, rows: list[tuple[str, str]]) -> str:
    """K6: MISSING / informational / UNKNOWN for one unit's missing
    path (or missing anchor within an existing file)."""
    if not ledger_found:
        return "UNKNOWN"
    key_stems = stems(ledger_key(unit_id))
    for mech_text, status_raw in rows:
        if key_stems and key_stems <= stems(mech_text):
            m = _STATUS_RE.match(status_raw.strip())
            if not m:
                return "UNKNOWN"
            status = m.group(1).lower()
            if status == "adopt":
                return "MISSING"
            return "informational"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# --check
# ---------------------------------------------------------------------------


def _read_host_file(path: Path) -> tuple[str | None, bool, bool]:
    """Returns (normalized_content_or_None, is_empty, non_utf8_warn).
    content is None when the file does not exist at all."""
    if not path.is_file():
        return None, False, False
    data = path.read_bytes()
    if len(data) == 0:
        return "", True, False
    non_utf8 = False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
        non_utf8 = True
    text = normalize_text(text)
    is_empty = text.strip() == ""
    return text, is_empty, non_utf8


def run_check(manifest_path: Path, root: Path, ledger_arg: str | None) -> int:
    try:
        if not root.is_dir():
            print(f"ERROR: --root is not a directory: {root}")
            return 2

        try:
            units = load_manifest(manifest_path)
        except ManifestError as exc:
            print(f"ERROR: {exc}")
            return 2

        ledger_path, checked = find_ledger(root, ledger_arg)
        rows: list[tuple[str, str]] = []
        ledger_found = ledger_path is not None

        print("install_parity --check")
        if ledger_found:
            print(f"ledger: {ledger_path}")
            rows, corrupt = parse_ledger(ledger_path)  # type: ignore[arg-type]
            if corrupt:
                print(f"WARN: ledger unreadable/unparseable, treating as no ledger: {ledger_path}")
                ledger_found = False
                rows = []
            elif len(rows) == 0:
                print("ledger found, zero rows parsed")
        else:
            print("no ledger found; checked: " + ", ".join(str(c) for c in checked))
        print()

        missing_lines: list[str] = []
        unknown_lines: list[str] = []
        informational_lines: list[str] = []
        clean_units = 0

        for unit in units:
            unit_id = unit["unit_id"]
            host_path = root / unit["host_path"]
            kind = unit["kind"]

            if kind == "path":
                if host_path.exists():
                    clean_units += 1
                    continue
                verdict = classify_missing(unit_id, ledger_found, rows)
                line = f"unit={unit_id}  host_path={unit['host_path']}  (file/dir not found)"
                if verdict == "MISSING":
                    missing_lines.append(line)
                elif verdict == "UNKNOWN":
                    unknown_lines.append(line)
                else:
                    informational_lines.append(line)
                continue

            # kind == "anchor"
            content, is_empty, non_utf8 = _read_host_file(host_path)
            if content is None:
                verdict = classify_missing(unit_id, ledger_found, rows)
                line = f"unit={unit_id}  host_path={unit['host_path']}  (file not found; {len(unit['anchors'])} anchor(s))"
                if verdict == "MISSING":
                    missing_lines.append(line)
                elif verdict == "UNKNOWN":
                    unknown_lines.append(line)
                else:
                    informational_lines.append(line)
                continue

            if non_utf8:
                print(f"WARN: non-UTF8 bytes in {unit['host_path']}, decoded with errors=replace")

            if is_empty:
                for a in unit["anchors"]:
                    missing_lines.append(
                        f"unit={unit_id}  host_path={unit['host_path']}  anchor={a!r}  (host file is empty)"
                    )
                continue

            unit_verdict_cache: str | None = None
            any_missing_here = False
            for a in unit["anchors"]:
                needle = normalize_text(a)
                if needle in content:
                    continue
                any_missing_here = True
                if unit_verdict_cache is None:
                    unit_verdict_cache = classify_missing(unit_id, ledger_found, rows)
                line = f"unit={unit_id}  host_path={unit['host_path']}  anchor={a!r}"
                if unit_verdict_cache == "MISSING":
                    missing_lines.append(line)
                elif unit_verdict_cache == "UNKNOWN":
                    unknown_lines.append(line)
                else:
                    informational_lines.append(line)
            if not any_missing_here:
                clean_units += 1

        print(f"CLEAN units ({clean_units})")
        print()
        print(f"MISSING ({len(missing_lines)})")
        for line in missing_lines:
            print(f"  {line}")
        print()
        print(f"UNKNOWN ({len(unknown_lines)})")
        for line in unknown_lines:
            print(f"  {line}")
        print()
        print(f"informational ({len(informational_lines)})")
        for line in informational_lines:
            print(f"  {line}")

        return 1 if (missing_lines or unknown_lines) else 0
    except Exception as exc:  # pragma: no cover - last-resort safety net (K1: no traceback out)
        print(f"ERROR: unexpected failure in install_parity --check: {exc}")
        return 2


# ---------------------------------------------------------------------------
# --emit-anchors
# ---------------------------------------------------------------------------


def run_emit_anchors(
    source: Path,
    unit_id: str | None,
    kit_path: str | None,
    host_path: str | None,
    kind: str | None,
) -> int:
    try:
        if not source.is_file():
            print(f"ERROR: --source not found: {source}")
            return 2
        text = source.read_text(encoding="utf-8", errors="replace")
        anchors = derive_anchors(text)

        if unit_id is None:
            print(json.dumps(anchors, ensure_ascii=False, indent=2))
            return 0

        if kit_path is None or host_path is None or kind is None:
            print(
                "ERROR: --emit-anchors with --unit-id also needs --kit-path, "
                "--host-path and --kind to build a well-formed manifest entry"
            )
            return 2

        entry = {
            "unit_id": unit_id,
            "kit_path": kit_path,
            "host_path": host_path,
            "anchors": anchors,
            "kind": kind,
        }
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: unexpected failure in install_parity --emit-anchors: {exc}")
        return 2


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only check: does the host tree physically carry every "
        "rule and clause of this kit's shipped policy (installer-parity)."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="compare a host tree against the manifest")
    mode.add_argument("--emit-anchors", action="store_true", help="derive anchors from --source")
    parser.add_argument("--source", default=None, help="file to derive anchors from (--emit-anchors)")
    parser.add_argument("--unit-id", default=None, help="manifest entry unit_id to emit (--emit-anchors)")
    parser.add_argument("--kit-path", default=None, help="manifest entry kit_path to emit (--emit-anchors)")
    parser.add_argument("--host-path", default=None, help="manifest entry host_path to emit (--emit-anchors)")
    parser.add_argument("--kind", default=None, choices=list(VALID_KINDS), help="manifest entry kind to emit (--emit-anchors)")
    parser.add_argument("--root", default=None, help="host tree root to check (--check). Default: cwd.")
    parser.add_argument(
        "--manifest",
        default=None,
        help="manifest path (default: install_parity_anchors.json, sibling of this script)",
    )
    parser.add_argument("--ledger", default=None, help="adoption-ledger path (default: search order, K7)")
    return parser


def main(argv: list[str] | None = None) -> int:
    _reconfigure_stdout_utf8()
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.check:
        manifest_path = Path(args.manifest) if args.manifest else Path(__file__).resolve().parent / "install_parity_anchors.json"
        root = Path(args.root).resolve() if args.root else Path.cwd()
        return run_check(manifest_path, root, args.ledger)

    if args.emit_anchors:
        if not args.source:
            print("ERROR: --emit-anchors requires --source")
            return 2
        return run_emit_anchors(Path(args.source), args.unit_id, args.kit_path, args.host_path, args.kind)

    parser.error("no mode selected")  # pragma: no cover - argparse enforces required group
    return 2


if __name__ == "__main__":
    sys.exit(main())
