"""parity_check.py -- machine visibility into drift between the HQ (repo
root) copy of a ported mechanism and its toolkit-staging twin (toolkit/),
per SIBLING_MAP.md axis 4/7 and the D-0074 moratorium (staging is synced
in batches, not on every touch -- so HQ moving ahead of staging is
EXPECTED and legal, not a defect to block on).

MANIFEST (tools/parity_manifest.json) -- a JSON list of pair records:

    {
      "hq": "tools/journal_echo.py",
      "kit": "toolkit/tools/journal_echo.py",
      "synced_hq_sha256": "<hex>",
      "synced_kit_sha256": "<hex>",
      "synced_at": "<ISO ts, local, no tz -- journal convention>",
      "note": "<one-line acknowledged difference, or empty>"
    }

Both paths are repo-root-relative (forward slashes). The two synced_*
hashes are the BASELINE snapshot recorded at the last reconciliation
(--init or --sync): if hq and kit differed at that moment (e.g. the HQ
copy carries a "STAGING_HQ VARIANT" docstring block the kit twin does
not), that difference is ALREADY baked into the baseline as two distinct
hashes -- there is no separate prose reconciliation step; the note field
is free-form commentary only, never load-bearing for the comparison.

FOUR OUTCOMES per pair on --check, comparing CURRENT file hashes against
the manifest baseline:

  clean       current hq hash == synced_hq_sha256 AND
              current kit hash == synced_kit_sha256
  hq-drift    hq changed, kit did not -- EXPECTED (port queue item),
              legal under D-0074, listed for visibility only
  kit-drift   kit changed, hq did not -- SUSPICIOUS: staging was touched
              directly, out of band from the HQ->staging port flow
  both-drift  both changed since the baseline -- a port likely happened
              but the manifest baseline was never updated (--sync)

HASHING IS OVER RAW BYTES (sha256 of the file's on-disk bytes, no text
normalization). LIMITATION, BY DESIGN, DOCUMENTED HERE: a bare CRLF/LF
checkout difference between the two working trees (e.g. one clone under
Windows line-ending settings, the other under Unix) registers as a hash
mismatch -- i.e. as drift -- even if the text content is identical. This
tool does not normalize line endings before hashing; a CRLF-only "drift"
must be recognized as such by whoever reads the report, not silently
absorbed by the tool.

EXIT CODE CONTRACT: this is a MEASUREMENT tool, not a gate -- there is
nothing legitimate to block on, since hq-drift alone is normal operation
under D-0074. `--check` exits 0 whenever the manifest itself is readable
and well-formed AND every pair's two files exist on disk, REGARDLESS of
how much drift is reported (drift is data, not failure). It exits 1, with
an explicit error line (never a traceback), in exactly two situations:
  (a) the manifest file is missing, not valid JSON, or fails structural
      validation (not a list / entries missing required keys or wrong
      types / a duplicate (hq, kit) pair registered twice) -- the WHOLE
      run is aborted, no per-pair report is attempted, since nothing can
      be trusted about a manifest that fails its own schema;
  (b) the manifest itself is fine, but one or more pairs reference a
      path that is not a file on disk -- the run continues and reports
      every other pair normally, but the missing-file pairs are listed
      under an explicit ERRORS section and the overall exit code is 1.

CLI:
  --check                 report drift for every pair in the manifest.
  --sync <hq-path>         recompute and store fresh baseline hashes +
                           synced_at for exactly the one pair whose "hq"
                           field equals <hq-path> (repo-root-relative,
                           e.g. "tools/journal_echo.py"); no match, or
                           more than one match, is an explicit error.
  --init [--force]         regenerate the manifest from scratch by
                           recomputing the pair set live from the repo
                           layout (see discover_pairs()); refuses to
                           overwrite an existing manifest file unless
                           --force is also given.
  --manifest <path>        manifest location (default: tools/parity_manifest.json,
                           resolved against the current working directory).
  --root <path>            repo root pairs are resolved against (default:
                           the manifest path's grandparent directory --
                           i.e. assumes the manifest lives at
                           <root>/tools/parity_manifest.json, matching
                           where this tool actually ships).

INITIAL PAIR SET (--init), built from the intersection rules of the
originating spec, in this fixed order:
  1. tools/*.py  ∩ toolkit/tools/*.py            (by filename)
  2. gateway/shadow_eval.py ↔ toolkit/gateway/shadow_eval.py (single pair)
  3. PROCESS/*.md ∩ toolkit/PROCESS/*.md          (by filename)
  4. CLAUDE.md ↔ toolkit/CLAUDE.md                (single pair)
Only pairs where BOTH sides exist on disk at generation time are
included. Baseline hashes are the ACTUAL CURRENT bytes of both sides at
generation time -- the "as-is" snapshot IS the sync baseline; any
existing difference between hq and kit at that moment is captured by
the two hashes differing, not by manifest prose.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST_RELPATH = "tools/parity_manifest.json"

REQUIRED_FIELDS = (
    "hq",
    "kit",
    "synced_hq_sha256",
    "synced_kit_sha256",
    "synced_at",
    "note",
)


class ManifestError(Exception):
    """Manifest fails to parse or fails structural validation.

    Raising this always means: abort the whole run, print one explicit
    error line, exit 1 -- never attempt a partial per-pair report.
    """


def sha256_of(path: Path) -> str:
    """sha256 hex digest of the file's raw on-disk bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now_iso() -> str:
    """Local time, no timezone suffix -- matches the routing journal's ts
    convention (CLAUDE.md: "ts (ISO, local time, no timezone")."""
    return datetime.datetime.now().isoformat(timespec="seconds")


def load_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    """Read and structurally validate the manifest. Raises ManifestError
    on anything wrong -- missing file, invalid JSON, wrong shape, missing/
    wrong-typed fields, or a duplicate (hq, kit) pair."""
    if not manifest_path.is_file():
        raise ManifestError(f"manifest not found: {manifest_path}")
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"manifest unreadable: {manifest_path} ({exc})") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {manifest_path} ({exc})") from exc

    if not isinstance(data, list):
        raise ManifestError(
            f"manifest must be a JSON list of pair records, got {type(data).__name__}"
        )

    seen_pairs: set[tuple[str, str]] = set()
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ManifestError(f"manifest entry #{i} is not an object")
        missing = [f for f in REQUIRED_FIELDS if f not in entry]
        if missing:
            raise ManifestError(f"manifest entry #{i} missing field(s): {missing}")
        for f in REQUIRED_FIELDS:
            if not isinstance(entry[f], str):
                raise ManifestError(
                    f"manifest entry #{i} field '{f}' must be a string, "
                    f"got {type(entry[f]).__name__}"
                )
        key = (entry["hq"], entry["kit"])
        if key in seen_pairs:
            raise ManifestError(f"manifest has a duplicate pair: hq={key[0]!r} kit={key[1]!r}")
        seen_pairs.add(key)

    return data


def save_manifest(manifest_path: Path, pairs: list[dict[str, Any]]) -> None:
    manifest_path.write_text(
        json.dumps(pairs, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def discover_pairs(root: Path) -> list[dict[str, Any]]:
    """Recompute the live pair set from the current repo layout (used by
    --init). Only pairs where both sides currently exist are returned."""
    pairs: list[dict[str, Any]] = []
    ts = now_iso()

    def add_pair(hq_rel: str, kit_rel: str) -> None:
        hq_path = root / hq_rel
        kit_path = root / kit_rel
        if not (hq_path.is_file() and kit_path.is_file()):
            return
        pairs.append(
            {
                "hq": hq_rel,
                "kit": kit_rel,
                "synced_hq_sha256": sha256_of(hq_path),
                "synced_kit_sha256": sha256_of(kit_path),
                "synced_at": ts,
                "note": "",
            }
        )

    # 1. tools/*.py ∩ toolkit/tools/*.py, by filename, sorted.
    tools_dir = root / "tools"
    kit_tools_dir = root / "toolkit" / "tools"
    if tools_dir.is_dir() and kit_tools_dir.is_dir():
        hq_names = {p.name for p in tools_dir.glob("*.py")}
        kit_names = {p.name for p in kit_tools_dir.glob("*.py")}
        for name in sorted(hq_names & kit_names):
            add_pair(f"tools/{name}", f"toolkit/tools/{name}")

    # 2. gateway/shadow_eval.py <-> toolkit/gateway/shadow_eval.py (single pair)
    add_pair("gateway/shadow_eval.py", "toolkit/gateway/shadow_eval.py")

    # 3. PROCESS/*.md ∩ toolkit/PROCESS/*.md, by filename, sorted.
    process_dir = root / "PROCESS"
    kit_process_dir = root / "toolkit" / "PROCESS"
    if process_dir.is_dir() and kit_process_dir.is_dir():
        hq_names = {p.name for p in process_dir.glob("*.md")}
        kit_names = {p.name for p in kit_process_dir.glob("*.md")}
        for name in sorted(hq_names & kit_names):
            add_pair(f"PROCESS/{name}", f"toolkit/PROCESS/{name}")

    # 4. CLAUDE.md <-> toolkit/CLAUDE.md (single pair)
    add_pair("CLAUDE.md", "toolkit/CLAUDE.md")

    return pairs


def classify(
    synced_hq: str, synced_kit: str, current_hq: str, current_kit: str
) -> str:
    hq_changed = current_hq != synced_hq
    kit_changed = current_kit != synced_kit
    if not hq_changed and not kit_changed:
        return "clean"
    if hq_changed and not kit_changed:
        return "hq-drift"
    if kit_changed and not hq_changed:
        return "kit-drift"
    return "both-drift"


def run_check(manifest_path: Path, root: Path) -> int:
    try:
        pairs = load_manifest(manifest_path)
    except ManifestError as exc:
        print(f"ERROR: {exc}")
        return 1

    sections: dict[str, list[str]] = {
        "clean": [],
        "hq-drift": [],
        "kit-drift": [],
        "both-drift": [],
    }
    errors: list[str] = []

    for entry in pairs:
        hq_rel = entry["hq"]
        kit_rel = entry["kit"]
        hq_path = root / hq_rel
        kit_path = root / kit_rel

        missing = []
        if not hq_path.is_file():
            missing.append(hq_rel)
        if not kit_path.is_file():
            missing.append(kit_rel)
        if missing:
            errors.append(
                f"MISSING FILE(S) for pair hq={hq_rel!r} kit={kit_rel!r}: "
                + ", ".join(missing)
            )
            continue

        current_hq = sha256_of(hq_path)
        current_kit = sha256_of(kit_path)
        outcome = classify(
            entry["synced_hq_sha256"], entry["synced_kit_sha256"], current_hq, current_kit
        )
        note = f" note={entry['note']!r}" if entry["note"] else ""
        line = f"hq={hq_rel}  kit={kit_rel}  synced_at={entry['synced_at']}{note}"
        sections[outcome].append(line)

    print(f"parity_check --check : {len(pairs)} pair(s) in manifest")
    print()
    print(f"CLEAN ({len(sections['clean'])})")
    for line in sections["clean"]:
        print(f"  {line}")
    print()
    print(f"HQ-DRIFT -- expected, port queue, legal under D-0074 ({len(sections['hq-drift'])})")
    for line in sections["hq-drift"]:
        print(f"  {line}")
    print()
    print(f"KIT-DRIFT -- SUSPICIOUS, staging touched out of band ({len(sections['kit-drift'])})")
    for line in sections["kit-drift"]:
        print(f"  {line}")
    print()
    print(f"BOTH-DRIFT -- port likely happened, manifest baseline stale ({len(sections['both-drift'])})")
    for line in sections["both-drift"]:
        print(f"  {line}")
    print()
    print(f"ERRORS ({len(errors)})")
    for line in errors:
        print(f"  {line}")

    return 1 if errors else 0


def run_sync(manifest_path: Path, root: Path, hq_target: str) -> int:
    try:
        pairs = load_manifest(manifest_path)
    except ManifestError as exc:
        print(f"ERROR: {exc}")
        return 1

    matches = [p for p in pairs if p["hq"] == hq_target]
    if not matches:
        print(f"ERROR: no pair with hq={hq_target!r} found in manifest")
        return 1
    if len(matches) > 1:
        print(f"ERROR: {len(matches)} pairs with hq={hq_target!r} found in manifest (ambiguous)")
        return 1

    entry = matches[0]
    hq_path = root / entry["hq"]
    kit_path = root / entry["kit"]
    missing = [str(p) for p in (entry["hq"], entry["kit"]) if not (root / p).is_file()]
    if missing:
        print(f"ERROR: cannot sync, missing file(s): {', '.join(missing)}")
        return 1

    entry["synced_hq_sha256"] = sha256_of(hq_path)
    entry["synced_kit_sha256"] = sha256_of(kit_path)
    entry["synced_at"] = now_iso()

    save_manifest(manifest_path, pairs)
    print(f"synced pair hq={entry['hq']} kit={entry['kit']} at {entry['synced_at']}")
    return 0


def run_init(manifest_path: Path, root: Path, force: bool) -> int:
    if manifest_path.exists() and not force:
        print(f"ERROR: manifest already exists: {manifest_path} (use --force to overwrite)")
        return 1

    pairs = discover_pairs(root)
    save_manifest(manifest_path, pairs)
    print(f"initialized manifest with {len(pairs)} pair(s): {manifest_path}")
    for entry in pairs:
        print(f"  hq={entry['hq']}  kit={entry['kit']}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Machine visibility into HQ<->toolkit-staging pair drift (SIBLING_MAP axis 4/7)."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report drift for every manifest pair")
    mode.add_argument("--sync", metavar="HQ_PATH", help="resync baseline hashes for one pair, by its hq path")
    mode.add_argument("--init", action="store_true", help="regenerate the manifest from scratch")
    parser.add_argument("--force", action="store_true", help="with --init: overwrite an existing manifest")
    parser.add_argument(
        "--manifest",
        default=None,
        help=f"manifest path (default: {DEFAULT_MANIFEST_RELPATH}, resolved against cwd)",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="repo root pairs are resolved against (default: manifest path's grandparent dir)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest) if args.manifest else Path(DEFAULT_MANIFEST_RELPATH)
    manifest_path = manifest_path.resolve()
    root = Path(args.root).resolve() if args.root else manifest_path.parent.parent

    if args.check:
        return run_check(manifest_path, root)
    if args.sync is not None:
        return run_sync(manifest_path, root, args.sync)
    if args.init:
        return run_init(manifest_path, root, args.force)

    parser.error("no mode selected")  # pragma: no cover - argparse enforces required group
    return 2


if __name__ == "__main__":
    sys.exit(main())
