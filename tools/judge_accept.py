"""Snapshot from exam_hybrid_kit/tools/judge_accept.py, 2026-07-22
(D-0081 batch item е): staffed operational detail of R13 (CLAUDE.md) --
a plain CLI over judge_client.judge_verdict() so a live coordinator
session has something to call as a judge (gateway-alias form, R13
"судья через шлюз-алиас"). Adapted verbatim from the kit copy; no
path/import changes were needed (judge_client sits alongside this file
in tools/, same convention as every other tools/*.py pair in this
repo). One reference corrected: the kit's original docstring below
cites "CLAUDE.md H2, this kit's H-section" -- exam_hybrid_kit's own
numbered H-mode subsection, which this repo's CLAUDE.md does not carry
under that label (verified by reading CLAUDE.md: it names the H-mode
generically under R13, with no "H2" heading) -- so that line is
replaced here with the R13 pointer above; every other line is
unchanged.

Original docstring follows.

---

judge_accept (t-250, H-kit leaf acceptance, H2): thin CLI over
judge_client.judge_verdict() for one DAG leaf cell -- the H-instruction's
"Приёмка листа -- ТОЛЬКО судьёй" mechanism.

Usage:
    python tools/judge_accept.py --cell <leaf-cell-dir> --keys keys/<node>.md \
        --task "<verbatim leaf task text>" [--stdout <stdout-tail-file>]

Prints JSON {"accept": bool, "feedback": str, "usage": {...},
"cost_usd": float|None} to stdout and exits:
    0  -- accept:true
    1  -- accept:false (reject)
    2  -- error (proxy unreachable, transport failure, unparseable judge
         reply after retry) -- an honest {"error": "..."} line on stdout,
         never a silent accept/reject.

Material assembly: build_material() runs with baseline_files=None
explicitly (there is no prepare()-style baseline_manifest.json in a
DAG-leaf sandbox -- this kit has no polygon assembly step) -- an honest
fallback marker (judge_client.BASELINE_UNAVAILABLE_MARKER) rather than
a silent unfiltered listing pretending nothing was excluded.

task_id (a judge_verdict()/build_prompt() parameter, used only for the
prompt's "Задача {task_id}:" label -- it does not affect the accept/
reject decision): this CLI's argument list is fixed to --cell/--keys/
--task/--stdout (H2's own invocation line) with no separate --task-id
flag, so task_id is derived from the --keys file's stem -- the file is
named keys/<node>.md per H1, so its stem IS the node id already.

Intent keys: --keys file is read as one intent key per non-empty
stripped line (the literal "файл интент-ключей" -- H1's node keys file
is prose/bullets; each line becomes one bullet judge_client.build_prompt
renders as "- <line>"). Blank lines are dropped, nothing else is
special-cased -- no markdown heading stripping, since the spec did not
ask for one and treating every non-empty line as a key is the simplest
behavior a keys-file author can predict.
"""

import argparse
import json
import sys
from pathlib import Path

import judge_client


def _read_keys(path):
    text = Path(path).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _read_stdout_tail(path):
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Judge acceptance of one H-kit DAG leaf cell")
    parser.add_argument("--cell", required=True, help="leaf cell directory (judge material source)")
    parser.add_argument("--keys", required=True, help="path to the intent-keys file (keys/<node>.md)")
    parser.add_argument("--task", required=True, help="leaf task text, verbatim")
    parser.add_argument("--stdout", default=None, help="optional path to a stdout-tail file")
    return parser


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args = build_arg_parser().parse_args(argv)

    task_id = Path(args.keys).stem
    intent_keys = _read_keys(args.keys)
    stdout_tail = _read_stdout_tail(args.stdout)

    try:
        verdict = judge_client.judge_verdict(
            task_id=task_id,
            task_text=args.task,
            intent_keys=intent_keys,
            cell_dir=args.cell,
            stdout_tail=stdout_tail,
            baseline_files=None,
        )
    except Exception as exc:  # proxy unreachable / transport error / JudgeParseError
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps({
        "accept": verdict["accept"],
        "feedback": verdict["feedback"],
        "usage": verdict["usage"],
        "cost_usd": verdict["cost_usd"],
    }, ensure_ascii=False))
    return 0 if verdict["accept"] else 1


if __name__ == "__main__":
    sys.exit(main())
