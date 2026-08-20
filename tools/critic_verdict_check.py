"""Fail-closed checker for critic verdict JSON blocks (N3, D-construction R13/D-0087).

Extracts the LAST fenced ```json ... ``` block from a critic's final-message
text and validates it against the shape declared in
tools/critic_verdict.schema.json. Rules are hardcoded here (not a generic
JSON-Schema validator by design); tools/test_critic_verdict_check.py carries
an anti-drift check comparing this file's behavior against the schema.

Usage:
    python tools/critic_verdict_check.py <path-to-verdict-text>
    python tools/critic_verdict_check.py -        (reads stdin)

Exit codes:
    0  valid verdict -> stdout: "VERDICT OK: <verdict>, blockers: N, fixes: M"
    1  no block / broken JSON / not an object / schema violation -> stderr:
       ASCII diagnostic lines, one per violation, each naming the concrete
       field/rule that failed.

All diagnostic text and the success line are ASCII-only by construction:
diagnostics never interpolate raw field VALUES from the (possibly
non-ASCII) input, only field names, indices and fixed expected-shape text.

Two sharp edges of the fence-extraction regex, both intentional trade-offs
of the "no generic parser" design:
  - The fence opener is matched case-sensitively as a literal lowercase
    ```json. ```JSON, ```Json or a bare ``` opener are NOT recognized as
    a verdict block.
  - The block body is matched non-greedily up to the first ``` that
    follows the opener. A verdict field VALUE that itself contains a
    literal ``` sequence truncates the captured body there: the JSON
    typically fails to parse (or parses into something that no longer
    satisfies the schema), so an otherwise-valid verdict is rejected
    fail-closed rather than silently misread.
"""

import json
import os
import re
import sys
import threading
from pathlib import Path

VERDICT_ENUM = ("fit", "fit_with_fixes", "blocker")

_FENCE_RE = re.compile(r"```json[ \t]*\r?\n(.*?)```", re.DOTALL)


def extract_last_json_block(text):
    """Return the text of the LAST closed ```json ... ``` fence, or None."""
    matches = list(_FENCE_RE.finditer(text))
    if not matches:
        return None
    return matches[-1].group(1)


def _is_str_list(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def validate_verdict(obj):
    """Return a list of ASCII violation strings; empty list means valid."""
    errors = []

    if not isinstance(obj, dict):
        errors.append(
            "JSON root is not an object (type: %s)" % type(obj).__name__
        )
        return errors

    required_top = ("verdict", "blockers", "class_completeness", "trail")
    for field in required_top:
        if field not in obj:
            errors.append("missing required field: %s" % field)

    # verdict
    verdict = obj.get("verdict")
    verdict_valid = False
    if "verdict" in obj:
        if not isinstance(verdict, str) or verdict not in VERDICT_ENUM:
            errors.append(
                "field 'verdict' invalid: expected one of fit, fit_with_fixes, blocker"
            )
        else:
            verdict_valid = True

    # blockers
    blockers = obj.get("blockers")
    blockers_valid = False
    if "blockers" in obj:
        if not _is_str_list(blockers):
            errors.append("field 'blockers' must be an array of strings")
        else:
            blockers_valid = True

    if verdict_valid and blockers_valid:
        if verdict == "fit" and len(blockers) != 0:
            errors.append(
                "field 'blockers' must be empty when verdict is fit"
            )
        if verdict == "blocker" and len(blockers) == 0:
            errors.append(
                "field 'blockers' must be non-empty when verdict is blocker"
            )

    # class_completeness
    if "class_completeness" in obj:
        if not isinstance(obj.get("class_completeness"), str):
            errors.append("field 'class_completeness' must be a string")

    # trail
    if "trail" in obj:
        trail = obj.get("trail")
        if not isinstance(trail, dict):
            errors.append("field 'trail' must be an object")
        else:
            if "read" not in trail:
                errors.append("missing required field: trail.read")
            elif not _is_str_list(trail.get("read")):
                errors.append("field 'trail.read' must be an array of strings")

            if "reruns" not in trail:
                errors.append("missing required field: trail.reruns")
            else:
                reruns = trail.get("reruns")
                if not isinstance(reruns, list):
                    errors.append("field 'trail.reruns' must be an array")
                else:
                    for idx, item in enumerate(reruns):
                        if not isinstance(item, dict):
                            errors.append(
                                "field 'trail.reruns[%d]' must be an object" % idx
                            )
                            continue
                        if "command" not in item or not isinstance(
                            item.get("command"), str
                        ):
                            errors.append(
                                "field 'trail.reruns[%d]' missing required string field: command"
                                % idx
                            )
                        if "result" not in item or not isinstance(
                            item.get("result"), str
                        ):
                            errors.append(
                                "field 'trail.reruns[%d]' missing required string field: result"
                                % idx
                            )

    # fixes (conditionally required)
    if verdict_valid and verdict == "fit_with_fixes":
        fixes = obj.get("fixes")
        if "fixes" not in obj:
            errors.append(
                "missing required field: fixes (required when verdict is fit_with_fixes)"
            )
        elif not _is_str_list(fixes):
            errors.append("field 'fixes' must be an array of strings")
        elif len(fixes) == 0:
            errors.append(
                "field 'fixes' must be non-empty when verdict is fit_with_fixes"
            )
    elif "fixes" in obj and obj.get("fixes") is not None:
        if not _is_str_list(obj.get("fixes")):
            errors.append("field 'fixes' must be an array of strings")

    return errors


def check_text(text):
    """Run the full pipeline on raw text. Returns (ok, errors, obj_or_None)."""
    block = extract_last_json_block(text)
    if block is None:
        return False, ["no fenced ```json block found in input"], None

    try:
        obj = json.loads(block)
    except json.JSONDecodeError as exc:
        return False, ["invalid JSON in fenced block: %s" % str(exc)], None

    errors = validate_verdict(obj)
    if errors:
        return False, errors, obj
    return True, [], obj


# --- BEGIN stdin-deadline helper (П4; ЛОКАЛЬНАЯ копия, общий модуль запрещён) ---
_STDIN_DEADLINE_DEFAULT = 10.0
_STDIN_DEADLINE_MAX = 600.0
_STDIN_DEADLINE_ENV = "OSLLM_STDIN_TIMEOUT"


def _stdin_deadline_seconds():
    """Секунды дедлайна: env-переопределение, иначе дефолт. Невалидное,
    нечисловое, <=0 и > _STDIN_DEADLINE_MAX -> дефолт; режима
    "0 = ждать вечно" НЕТ намеренно (он воскрешает саму дыру)."""
    try:
        value = float(os.environ.get(_STDIN_DEADLINE_ENV, ""))
    except (TypeError, ValueError):
        return _STDIN_DEADLINE_DEFAULT
    if not (0.0 < value <= _STDIN_DEADLINE_MAX):
        return _STDIN_DEADLINE_DEFAULT
    return value


def _read_stdin_bytes_deadline():
    """(bytes, timed_out). Читает stdin до EOF, но не дольше дедлайна.
    Форма кроссплатформенная: select/poll на Windows не работает с
    пайпами, поэтому читает поток-демон, а дедлайн держит join(timeout).
    TTY -> b"" без чтения (прежний guard трёх файлов, теперь у всех).
    Любая ошибка чтения -> b"" (fail-open, как везде в этих хуках)."""
    stdin = getattr(sys, "stdin", None)
    if stdin is None:
        return b"", False
    try:
        if stdin.isatty():
            return b"", False
    except Exception:
        pass
    stream = getattr(stdin, "buffer", stdin)
    box = {}

    def _reader():
        try:
            box["data"] = stream.read()
        except Exception:
            box["data"] = b""

    thread = threading.Thread(target=_reader, name="stdin-deadline", daemon=True)
    thread.start()
    thread.join(_stdin_deadline_seconds())
    if thread.is_alive():
        return b"", True
    data = box.get("data") or b""
    if not isinstance(data, bytes):
        data = str(data).encode("utf-8", "replace")
    return data, False


_STDIN_DEADLINE_MSG = "stdin deadline exceeded -- fail-open, payload discarded"
# --- END stdin-deadline helper ---

# P4/В3.1 (K7-эмпирика builder t-539, В9(в) очередь спеки П4, 2026-08-20):
# та же угроза, что у 12+1 хуков -- фоновый reader-поток, оставленный
# заблокированным на РЕАЛЬНОМ stdin-буфере при обычном завершении
# интерпретатора, может уронить процесс "Fatal Python error:
# _enter_buffered_busy" вместо чистого exit. Эмпирика этой правки
# (subprocess с реально удержанным открытым stdin, см. отчёт builder'а,
# witness) ПОДТВЕРДИЛА тот же класс здесь -- поэтому __main__-эскалация
# ниже (os._exit на таймауте) добавлена той же формой, что у хуков.
_STDIN_DEADLINE_STATE = {"hit": False}


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: critic_verdict_check.py <path-or-->\n")
        return 1

    source = argv[1]
    if source == "-":
        raw_bytes, timed_out = _read_stdin_bytes_deadline()
        if timed_out:
            _STDIN_DEADLINE_STATE["hit"] = True
            sys.stderr.write(f"{Path(__file__).name}: {_STDIN_DEADLINE_MSG}\n")
            return 1  # прежний код выхода пустого входа (тот же класс отказа)
        try:
            text = raw_bytes.decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            sys.stderr.write("INVALID VERDICT: input is not valid UTF-8\n")
            return 1
    else:
        try:
            with open(source, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            sys.stderr.write("cannot read input file: %s\n" % str(exc))
            return 1
        except (UnicodeDecodeError, ValueError):
            sys.stderr.write("INVALID VERDICT: input is not valid UTF-8\n")
            return 1

    ok, errors, obj = check_text(text)
    if not ok:
        sys.stderr.write("INVALID VERDICT:\n")
        for err in errors:
            sys.stderr.write("  - %s\n" % err)
        return 1

    blockers = obj.get("blockers") or []
    fixes = obj.get("fixes") or []
    sys.stdout.write(
        "VERDICT OK: %s, blockers: %d, fixes: %d\n"
        % (obj.get("verdict"), len(blockers), len(fixes))
    )
    return 0


if __name__ == "__main__":
    _rc = main(sys.argv)
    if _STDIN_DEADLINE_STATE["hit"]:
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(_rc)
    sys.exit(_rc)
