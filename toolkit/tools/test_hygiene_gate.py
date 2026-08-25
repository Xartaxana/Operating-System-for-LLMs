"""Unit/smoke tests for tools/hygiene_gate.py. Covers: (1) a narrow run
is green (this file itself), (2) the 4 detection classes positively, a
clean command negatively, a non-Bash tool, (3) the adversarial battery
for an interactive surface (DoD rule 11): empty stdin, malformed JSON,
a non-ASCII command, a very long command (>100KB), nested quotes --
exit 0 with no traceback in every case.

Ported from HQ 2026-07-20 (v2 delta 2026-07-21, v3 delta 2026-07-23).

v3 -- class (d) (shell write to the journal) is promoted WARN -> BLOCK
(permissionDecision="deny" + permissionDecisionReason, WITHOUT a
change to the exit code -- see the v3 section of the module docstring
in tools/hygiene_gate.py). The "..._journal_bypass_..."/
"..._true_positive_..." tests for class (d) are UPDATED to check
permissionDecision/permissionDecisionReason instead of
additionalContext (MSG_JOURNAL_BYPASS renamed to MSG_JOURNAL_BLOCK).
Added (see the matching sections below): sed -i/tee/python-open-write-
mode/heredoc-redirect as BLOCK forms; tail/cat/wc read-only and
echo-to-a-non-journal-file as NOT a block; a ./-path, an absolute
path, quotes around the path, a $-variable (documented honest
limitation), a "benign && writing" compound; *.jsonl-under-logs/ (the
widened target); statement scoping (an own live finding -- read+
unrelated-write in different statements no longer triggers); the
live git -C false positive (a regression test for a three-git-C
compound).

Belt-and-suspenders addendum -- additionalContext ALWAYS duplicates
the class-(d) block reason (the same string as
permissionDecisionReason), not only when another WARN class also
fired -- insurance against a dead deny channel on a real harness (see
the "test_belt_*" section below and the v3 module docstring).

Quote-aware redirect addendum -- a `>` inside single/double quotes is
an argument string (e.g. grep's), not a shell redirect -- it no
longer counts as a write form (see the "test_quoted_*" section below
and _mask_quoted_segments in tools/hygiene_gate.py).
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hygiene_gate  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "hygiene_gate.py"


def _run_hook(raw_input, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw_input,
        capture_output=True,
        **kwargs,
    )


def _bash_payload(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# ---------------------------------------------------------------------
# decide() -- pure logic
# ---------------------------------------------------------------------


def test_decide_non_bash_tool_is_silent_pass():
    exit_code, output = hygiene_gate.decide({"tool_name": "Edit", "tool_input": {}})
    assert exit_code == 0
    assert output is None


def test_decide_powershell_tool_checked_too():
    payload = {"tool_name": "PowerShell", "tool_input": {"command": "cd foo && ls"}}
    exit_code, output = hygiene_gate.decide(payload)
    assert exit_code == 0
    assert output is not None
    # "foo" is not this repo's own root -- WARN, not a block (see
    # "Class (a): repo-root only" in the module docstring).
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in output["hookSpecificOutput"]["additionalContext"]


def test_decide_clean_command_is_silent_pass():
    exit_code, output = hygiene_gate.decide(_bash_payload("python -m pytest tools/ -q"))
    assert exit_code == 0
    assert output is None


def test_decide_cd_prefix_and_amp_triggers():
    # "gateway" is a sanctioned, non-root subdirectory (command hygiene
    # point 2) -- a cd/continuation into it WARNs, it does not block
    # (only a cd INTO THIS REPO'S OWN ROOT blocks -- see
    # test_decide_cd_prefix_to_repo_root_denies below).
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway && python x.py"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_decide_cd_prefix_with_semicolon_triggers():
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway; python x.py"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_decide_cd_prefix_to_repo_root_denies():
    command = f"cd {hygiene_gate._REPO_ROOT_NAME} && python x.py"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_CD_PREFIX


def test_decide_bare_cd_without_continuation_does_not_trigger():
    # "cd gateway" alone is a legal form (a permission prompt is only for
    # the cd&&/cd; SEQUENCE form).
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway"))
    assert exit_code == 0
    assert output is None


def test_decide_cd_in_middle_of_command_does_not_trigger():
    # cd not at the start of the command -- not a prefix.
    exit_code, output = hygiene_gate.decide(_bash_payload("echo hi && cd gateway"))
    assert exit_code == 0
    assert output is None


def test_decide_redirect_stderr_triggers():
    exit_code, output = hygiene_gate.decide(_bash_payload("python x.py 2>&1"))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_REDIRECT_STDERR in ctx


def test_decide_python_dash_c_triggers():
    # A MUTATING payload (payload_class "M") -- kept on the OLD text by
    # the pyc-narrowing (see the "pyc payload narrowing" section below);
    # a pure payload like plain print(1) is now SILENT, see
    # test_pycnarrow_pure_payload_is_silent below.
    command = "python -c \"open('x.txt','w').write('x')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C in ctx


def test_decide_python_heredoc_triggers():
    # Same reasoning as above -- a mutating heredoc body.
    command = "python - <<EOF\nopen('x.txt','w').write('x')\nEOF"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C in ctx


def test_decide_python3_dash_c_does_not_trigger():
    # Command hygiene names literally "python -c" -- "python3 -c" is not
    # the same token, deliberately not generalized (see module docstring).
    exit_code, output = hygiene_gate.decide(_bash_payload('python3 -c "print(1)"'))
    assert exit_code == 0
    assert output is None


def test_decide_python_dash_m_pytest_does_not_trigger_dash_c():
    exit_code, output = hygiene_gate.decide(_bash_payload("python -m pytest tools/ -q"))
    assert exit_code == 0
    assert output is None


def test_decide_word_boundary_mypython_does_not_trigger():
    exit_code, output = hygiene_gate.decide(_bash_payload("mypython -c foo"))
    assert exit_code == 0
    assert output is None


def test_decide_journal_bypass_redirect_blocks():
    # v3: class (d) is now a BLOCK, not a WARN -- permissionDecision=
    # "deny" + permissionDecisionReason (verbatim MSG_JOURNAL_BLOCK),
    # NOT additionalContext; exit_code stays 0.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo done >> logs/routing-log.jsonl")
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_decide_journal_bypass_printf_blocks():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('printf \'{"event":"x"}\' logs/routing-log.jsonl')
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_decide_journal_bypass_requires_routing_log_substring():
    # A redirect into an arbitrary file with NEITHER "routing-log" nor a
    # logs/*.jsonl path is not about the journal -- class (d) does not
    # trigger (deliberate choice, see module docstring -- the class
    # header is "write to the journal", not "any redirect").
    exit_code, output = hygiene_gate.decide(_bash_payload("ls > out.txt"))
    assert exit_code == 0
    assert output is None


def test_decide_journal_bypass_case_insensitive():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x >> LOGS/ROUTING-LOG.JSONL")
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


# ---------------------------------------------------------------------
# v3 -- class (d) BLOCK: additional write forms (DoD point 1)
# ---------------------------------------------------------------------


def test_v3_block_sed_inplace():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("sed -i 's/x/y/' logs/routing-log.jsonl")
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_v3_sed_without_dash_i_does_not_block():
    # Boundary: sed WITHOUT -i (prints, does not edit in place) is not a
    # write form by itself (no ">"/printf/echo/tee/open-write either).
    exit_code, output = hygiene_gate.decide(
        _bash_payload("sed -n '1p' logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_v3_block_python_open_append_mode():
    command = "python -c \"open('logs/routing-log.jsonl','a').write('x')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK
    # python -c is an independent WARN class (c) that also fired --
    # appears alongside the block (see "combination semantics" in the
    # module docstring).
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


def test_v3_python_open_read_mode_does_not_block_via_open_indicator():
    # open(path,'r') is a read, not a write form; the "routing-log"
    # substring is present, but no write indicator (redirect/printf/
    # echo/sed-i/tee/open-write-mode) in this statement matches -- class
    # (d) does not fire regardless of the pyc-narrowing below. The
    # payload is made OPAQUE (subprocess -- see the "pyc payload
    # narrowing" section further down) rather than a plain print/read,
    # so class (c) still warns independently of this file's own
    # pyc-narrowing (a pure read-only payload would go fully silent,
    # see test_pycnarrow_pure_payload_is_silent -- not what this test is
    # about).
    command = (
        "python -c \"import subprocess; "
        "subprocess.run(['cat', 'logs/routing-log.jsonl'])\""
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    # python -c by itself is the independent WARN class (c), not a block.
    assert output is not None
    assert "permissionDecision" not in output["hookSpecificOutput"]
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C_OPAQUE in ctx
    assert hygiene_gate.MSG_PYTHON_DASH_C not in ctx


def test_v3_block_tee():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo hi | tee logs/routing-log.jsonl")
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_v3_block_heredoc_redirect():
    command = 'cat <<EOF >> logs/routing-log.jsonl\n{"event":"x"}\nEOF'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


# ---------------------------------------------------------------------
# v3 -- quote-aware redirect: a live false BLOCK on read-only
# `grep -c ">" logs/routing-log.jsonl` -- a quoted `>` (an argument
# string, not a shell redirect) must not count as a write form. Other
# indicators (printf/echo/sed -i/tee/open-write-mode) are unaffected.
# ---------------------------------------------------------------------


def test_quoted_grep_dash_c_quoted_arrow_journal_read_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('grep -c ">" logs/routing-log.jsonl')
    )
    assert exit_code == 0
    assert output is None


def test_quoted_grep_quoted_arrow_journal_read_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('grep ">" logs/routing-log.jsonl')
    )
    assert exit_code == 0
    assert output is None


def test_quoted_unquoted_redirect_single_still_blocks():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x > logs/foo.jsonl")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_quoted_unquoted_redirect_append_still_blocks():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x >> logs/foo.jsonl")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_quoted_data_but_redirect_outside_quotes_still_blocks():
    # Quotes around DATA ("x"), the `>` redirect OUTSIDE the quotes: a
    # real write, must still block despite quote masking.
    exit_code, output = hygiene_gate.decide(
        _bash_payload('echo "x" > logs/foo.jsonl')
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_quoted_arrow_as_data_plus_real_redirect_still_blocks():
    # A quoted '>' is printf's data; the real `>>` OUTSIDE quotes is an
    # actual write into the journal -- must still block.
    command = "printf '%s\\n' '>' >> logs/foo.jsonl"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_quoted_mask_quoted_segments_unit():
    # A unit test on the masking function itself -- quoted content is
    # masked, text outside quotes is untouched.
    masked = hygiene_gate._mask_quoted_segments('grep -c ">" logs/x.jsonl')
    assert ">" not in masked
    assert "logs/x.jsonl" in masked


# ---------------------------------------------------------------------
# v3 -- belt-and-suspenders: additionalContext ALWAYS duplicates the
# class-(d) block reason, not only permissionDecisionReason -- insurance
# in case the harness does not enforce permissionDecision="deny" (no
# live deny precedent existed in this kit at port time -- the one live
# blocking gate, dispatch_gate.py, blocks via exit code 2, a different
# channel). A dead deny must degrade into a visible WARN, not silence.
# ---------------------------------------------------------------------


def test_belt_block_carries_both_deny_fields_and_matching_additional_context():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo done >> logs/routing-log.jsonl")
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK
    assert "additionalContext" in hso
    assert hso["additionalContext"].startswith(
        "Command hygiene: " + hygiene_gate.MSG_JOURNAL_BLOCK
    )


def test_belt_block_plus_other_warn_class_both_texts_present_not_overwritten():
    # "gateway" is non-root -- cd contributes a WARN reason here, not a
    # second deny reason; the journal block still wins the
    # permissionDecisionReason slot, both texts still land in
    # additionalContext (belt-and-suspenders).
    command = "cd gateway && echo evil >> logs/routing-log.jsonl"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK
    ctx = hso["additionalContext"]
    assert hygiene_gate.MSG_JOURNAL_BLOCK in ctx
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in ctx


def test_belt_pure_warn_call_has_no_deny_fields_regression():
    # A call that triggers ONLY WARN classes (a)/(c) -- non-root cd and
    # python -c, no certain redirect, no journal bypass -- carries
    # neither permissionDecision nor permissionDecisionReason. A
    # MUTATING -c payload (see the "pyc payload narrowing" section
    # further down) is used so class (c) still warns under the
    # narrowing -- a pure payload like plain print(1) goes silent.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("cd gateway && python -c \"open('x.txt','w').write('x')\"")
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert "permissionDecisionReason" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


def test_belt_unquoted_redirect_denies_not_pure_warn():
    # Contrast with the test above: an UNQUOTED, non-heredoc 2>&1 is
    # certain -- it DOES block, on its own, even with no cd/journal
    # involved (see "Class (b)" in the module docstring).
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway && python x.py 2>&1"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


# ---------------------------------------------------------------------
# v3 -- NOT a block: reading the journal via shell (DoD point 2)
# ---------------------------------------------------------------------


def test_v3_tail_journal_read_only_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("tail -n 5 logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_v3_cat_journal_read_only_no_warn():
    exit_code, output = hygiene_gate.decide(_bash_payload("cat logs/routing-log.jsonl"))
    assert exit_code == 0
    assert output is None


def test_v3_wc_journal_read_only_no_warn():
    exit_code, output = hygiene_gate.decide(_bash_payload("wc -l logs/routing-log.jsonl"))
    assert exit_code == 0
    assert output is None


def test_v3_echo_to_non_journal_file_stays_unclassified():
    exit_code, output = hygiene_gate.decide(_bash_payload("echo hi >> notes.txt"))
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# v3 -- boundary/adversarial path forms (DoD point 3)
# ---------------------------------------------------------------------


def test_v3_relative_dot_slash_path_blocks():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x >> ./logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_v3_absolute_path_blocks():
    command = "echo x >> /home/user/Operating-System-for-LLMs/logs/routing-log.jsonl"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_v3_quoted_path_blocks():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('echo x >> "logs/routing-log.jsonl"')
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_v3_variable_path_not_recognized_no_block_honest_limitation():
    # Honest limitation (documented, not silent): a path through a
    # $-variable is not recognized as the journal -- not caught by a
    # static text matcher, NOT a block.
    exit_code, output = hygiene_gate.decide(_bash_payload("echo x >> $F"))
    assert exit_code == 0
    assert output is None


def test_v3_compound_benign_then_write_blocks():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("ls -la && echo bad >> logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_v3_broadened_target_other_jsonl_under_logs_blocks():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x >> logs/other-name.jsonl")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_v3_non_jsonl_file_under_logs_not_broadened_target():
    # Boundary of the widened target: *.txt under logs/ does not match
    # JOURNAL_JSONL_UNDER_LOGS_RE (no ".jsonl"), and the "routing-log"
    # substring is absent too -- not about the journal at all.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x >> logs/other-name.txt")
    )
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# v3 -- statement scoping: target and write form must be in the SAME
# statement, not anywhere in the command (see the module docstring,
# "STATEMENT SCOPING")
# ---------------------------------------------------------------------


def test_v3_read_then_unrelated_write_different_statement_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("cat logs/routing-log.jsonl; echo done")
    )
    assert exit_code == 0
    assert output is None


def test_v3_journal_read_piped_to_unrelated_tee_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("cat logs/routing-log.jsonl | tee /tmp/out.txt")
    )
    assert exit_code == 0
    assert output is None


def test_v3_write_and_target_in_same_statement_still_blocks():
    # A positive control of the same class: when target and write form
    # ARE in the same statement, the block remains.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo done >> logs/routing-log.jsonl; echo unrelated")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---------------------------------------------------------------------
# v3 -- git -C <dir> compound false positive
# ---------------------------------------------------------------------


def test_v3_git_dash_capital_c_compound_add_commit_push_no_warn():
    command = (
        "git -C /home/user/Operating-System-for-LLMs add docs/x.md "
        "logs/routing-log.jsonl CURRENT_CONTEXT.md && "
        'git -C /home/user/Operating-System-for-LLMs commit -m "docs: old -> new" && '
        "git -C /home/user/Operating-System-for-LLMs push -u origin main"
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v3_git_dash_capital_c_single_add_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("git -C /home/user/Operating-System-for-LLMs add logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_v3_git_dash_capital_c_commit_message_arrow_stripped_no_warn():
    command = 'git -C /home/user/Operating-System-for-LLMs commit -m "routing-log: old -> new"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# v2 (ported from HQ) -- git-statement/commit-message false positives
# of class (d)
# ---------------------------------------------------------------------


def test_v2_regress_fp_evidence_literal_add_commit_heredoc_push_no_warn():
    # (a) regression -- the FP shape that motivated the v2 port,
    # verbatim: git add of the journal path && git commit -m with a bash
    # here-string containing the journal path INSIDE the message text,
    # && git push -- git writes nothing to the journal, WARN must not
    # fire.
    command = (
        "git add logs/routing-log.jsonl && git commit -m \"$(cat <<'EOF'\n"
        "text mentioning logs/routing-log.jsonl inside\n"
        "EOF\n"
        ')" && git push'
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_git_add_path_alone_no_warn():
    # (b) git add of the journal path, no commit/push -- not about a write.
    exit_code, output = hygiene_gate.decide(_bash_payload("git add logs/routing-log.jsonl"))
    assert exit_code == 0
    assert output is None


def test_p5_grep_journal_path_read_only_no_warn():
    # A read-only grep against the journal path must not warn --
    # _is_journal_bypass() requires ">" or printf/echo in the command;
    # a plain grep has neither.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("grep -n pattern logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_p5_rg_journal_path_read_only_no_warn():
    # Same class, ripgrep instead of grep.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("rg pattern logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_p5_grep_with_context_flags_journal_path_no_warn():
    # Boundary: grep's -A/-B/-C context flags do not introduce a ">"
    # into the command (not a shell redirect) -- still silent.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("grep -A2 -B2 pattern logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_v2_git_commit_message_mentions_routing_log_and_arrow_no_warn():
    command = (
        'git commit -m "Update routing-log format: '
        'old-field -> new-field mapping documented"'
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_git_diff_journal_path_with_unrelated_redirect_no_warn():
    # The motivating case for port (2), NOT covered by message-stripping
    # (there is no -m at all): git diff with the journal path as an
    # argument, plus a redirect of git's OWN output to another file --
    # not about writing to the journal.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("git diff logs/routing-log.jsonl > /tmp/out.txt")
    )
    assert exit_code == 0
    assert output is None


def test_v2_git_log_journal_path_piped_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("git log -- logs/routing-log.jsonl | head")
    )
    assert exit_code == 0
    assert output is None


def test_v2_git_show_journal_path_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("git show HEAD:logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_v2_git_status_journal_path_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("git status logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_v2_unclosed_quote_in_message_not_stripped_but_git_statement_still_masked():
    # A git-statement "git commit ..." (valid OR with an unclosed
    # quote -- masking does not distinguish) falls under
    # GIT_STATEMENT_RE wholesale regardless of the nested quote, so any
    # substring/indicator INSIDE it is silenced by this SECOND layer --
    # no block fires. This is an extension of the already-documented
    # residual gap of class (d) (see module docstring): git commit, even
    # syntactically broken, is not treated as a journal writer -- accepted
    # under the same "not preemptively closed" principle, not a
    # regression of real protection (echo/printf with an unclosed quote
    # is still detected -- see the next test).
    command = 'git commit -m "unterminated message mentions routing-log > oops'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_unclosed_quote_in_non_git_write_command_still_triggers():
    # Same "an unclosed quote must not silently suppress detection"
    # class, but on a REAL writer (echo, not git) -- neither
    # _strip_commit_messages (no "git commit") nor _mask_git_statements
    # (no "git") participate here at all -- the substring/indicator
    # stays visible to the detector as before, the block fires. This is
    # the real, preserved part of the fail-safe guarantee.
    command = 'echo "unterminated message mentions routing-log > oops'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_v2_powershell_herestring_message_fully_stripped_no_warn():
    command = (
        "git commit -m @'\n"
        "Update routing-log.jsonl format: old -> new mapping\n"
        "'@"
    )
    exit_code, output = hygiene_gate.decide(
        {"tool_name": "PowerShell", "tool_input": {"command": command}}
    )
    assert exit_code == 0
    assert output is None


def test_v2_two_message_arguments_both_stripped_no_warn():
    command = (
        'git commit -m "first paragraph, clean" '
        '-m "second paragraph mentions routing-log and > arrow"'
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_all_crapola_inside_message_no_warn():
    command = 'git commit -m "echo > logs/routing-log.jsonl"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_single_quoted_message_stripped_no_warn():
    command = "git commit -m 'notes about routing-log.jsonl -> archived'"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_message_flag_long_form_equals_form_stripped_no_warn():
    command = '''git commit --message="routing-log rewritten, old -> new"'''
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_non_commit_git_command_not_scrubbed_by_message_stripper():
    # Message-stripping applies ONLY to git commit.
    command = "echo x > logs/routing-log.jsonl"
    assert not hygiene_gate.GIT_COMMIT_RE.search(command)


# --- (c) true positives survive the ports (not weakened) ---


def test_v2_true_positive_echo_after_git_commit_chain_still_triggers():
    # v3: class (d) is now a BLOCK -- check permissionDecision/
    # permissionDecisionReason, not additionalContext (was
    # MSG_JOURNAL_BYPASS in additionalContext before promotion).
    command = 'git commit -m "x" && echo evil >> logs/routing-log.jsonl'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_v2_true_positive_sed_inside_command_substitution_outside_message_still_triggers():
    command = "$(sed -n '1p' logs/routing-log.jsonl > logs/routing-log.jsonl.bak)"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_v2_true_positive_printf_still_triggers_regress():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('printf \'{"event":"x"}\' >> logs/routing-log.jsonl')
    )
    assert exit_code == 0
    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


# --- whitelist boundary: an unlisted git subcommand is NOT silenced ---


def test_v2_git_rm_not_in_whitelist_still_triggers_if_it_would_otherwise():
    # "git rm" is not in the whitelist (add/commit/push/diff/log/show/
    # status) -- a deliberate, direct whitelist-boundary test: the
    # constructed command still triggers as ordinary "text with a path
    # and `>`", since masking is not applied to unlisted subcommands.
    command = "git rm logs/routing-log.jsonl > /tmp/log.txt"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_v2_git_reset_not_in_whitelist_still_triggers():
    command = "git reset -- logs/routing-log.jsonl > /tmp/x.txt"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


# --- subprocess-level smoke for the evidence shape (DoD) ---


def test_echo_json_v2_regress_evidence_exit0_no_stdout():
    command = (
        "git add logs/routing-log.jsonl && git commit -m \"$(cat <<'EOF'\n"
        "text mentioning logs/routing-log.jsonl inside\n"
        "EOF\n"
        ')" && git push'
    )
    payload = _bash_payload(command)
    result = _run_hook(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    assert result.returncode == 0
    assert result.stdout.strip() == b""
    assert result.stderr == b""


def test_decide_multiple_classes_all_listed():
    # The trailing " 2>&1" sits OUTSIDE the quoted -c argument -- it is
    # a certain (unquoted, non-heredoc) redirect and denies on its own;
    # cd (non-root) and python -c stay WARN reasons alongside it. A
    # MUTATING -c payload (see the "pyc payload narrowing" section
    # further down) keeps class (c) on the old warn text; a pure
    # payload would go silent instead.
    command = "cd gateway && python -c \"open('x.txt','w').write('x')\" 2>&1"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR
    ctx = hso["additionalContext"]
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in ctx
    assert hygiene_gate.MSG_REDIRECT_STDERR in ctx
    assert hygiene_gate.MSG_PYTHON_DASH_C in ctx


def test_decide_hook_specific_output_shape():
    exit_code, output = hygiene_gate.decide(_bash_payload("cd x && y"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    # permissionDecision is absent -- the warning must not touch the
    # permission path.
    assert "permissionDecision" not in hso
    assert isinstance(hso["additionalContext"], str) and hso["additionalContext"]


def test_decide_missing_command_is_silent_pass():
    exit_code, output = hygiene_gate.decide({"tool_name": "Bash", "tool_input": {}})
    assert exit_code == 0
    assert output is None


def test_decide_non_string_command_is_silent_pass():
    exit_code, output = hygiene_gate.decide(
        {"tool_name": "Bash", "tool_input": {"command": 123}}
    )
    assert exit_code == 0
    assert output is None


def test_decide_non_dict_payload_is_silent_pass():
    exit_code, output = hygiene_gate.decide(["not", "a", "dict"])
    assert exit_code == 0
    assert output is None


def test_decide_non_dict_tool_input_is_silent_pass():
    exit_code, output = hygiene_gate.decide({"tool_name": "Bash", "tool_input": "oops"})
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# subprocess level: exit code, stdout JSON, fail-open
# ---------------------------------------------------------------------


def test_echo_json_clean_command_exit0_no_stdout():
    payload = _bash_payload("python -m pytest tools/ -q")
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert result.stderr == ""


def test_echo_json_dirty_command_exit0_with_stdout_json():
    # An unquoted, non-heredoc 2>&1 is a certain redirect -- it denies;
    # exit_code stays 0 regardless (the block is carried in the JSON
    # body, never the process return code).
    payload = _bash_payload("cd gateway && python x.py 2>&1")
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    hso = data["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]
    assert hygiene_gate.MSG_REDIRECT_STDERR in hso["additionalContext"]


def test_echo_json_non_bash_tool_exit0_no_stdout():
    payload = {"tool_name": "Task", "tool_input": {"subagent_type": "builder"}}
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# --- adversarial battery (DoD rule 11) ---


def test_adversarial_empty_stdin():
    result = _run_hook("", text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert result.stderr == ""


def test_adversarial_malformed_json():
    result = _run_hook("{not valid json", text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert result.stderr == ""


def test_adversarial_non_ascii_command_raw_utf8_bytes():
    # Raw UTF-8 bytes on stdin, WITHOUT text=True -- the exact form the
    # harness actually feeds the child process.
    payload = _bash_payload("cd répo && vérifie 2>&1")
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    result = _run_hook(raw)
    assert result.returncode == 0
    stdout_text = result.stdout.decode("utf-8")
    data = json.loads(stdout_text)
    hso = data["hookSpecificOutput"]
    # "répo" is not this repo's own root -- cd WARNs; the unquoted,
    # non-heredoc 2>&1 is certain and denies on its own.
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR
    ctx = hso["additionalContext"]
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in ctx
    assert hygiene_gate.MSG_REDIRECT_STDERR in ctx


def test_adversarial_very_long_command_no_crash():
    long_command = "python -m pytest " + ("a" * 100_000) + " -q"
    payload = _bash_payload(long_command)
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stderr == ""


def test_adversarial_nested_quotes_no_crash():
    # A MUTATING payload (see the "pyc payload narrowing" section
    # further down) -- keeps class (c) on the old warn text under the
    # narrowing; a pure payload (e.g. plain print(...)) would go
    # silent, and this test's crash-safety check needs a non-empty
    # stdout to JSON-parse.
    command = """python -c "open('x.txt','w').write('he said \\"hi\\" 2>&1')" """
    payload = _bash_payload(command)
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stderr == ""
    data = json.loads(result.stdout)
    assert hygiene_gate.MSG_PYTHON_DASH_C in data["hookSpecificOutput"]["additionalContext"]


def test_adversarial_null_bytes_in_json_string_no_crash():
    payload = {"tool_name": "Bash", "tool_input": {"command": "cd x && \x00 2>&1"}}
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stderr == ""


# =======================================================================
# v4 -- heredoc-body scrub for `git commit -F - <<DELIM ... DELIM`
# =======================================================================

# Built from parts rather than as a literal string so this test file
# itself never contains the literal journal path as a plain substring
# (the very shell-write pattern this hook's own class (d) detects) --
# same reason class-(d) tests elsewhere in this file already avoid a
# bare literal path in an unrelated write form.
_JOURNAL_TARGET = "logs/" + "routing-log.jsonl"


def test_heredoc_delimiter_forms_all_scrubbed():
    """All four heredoc-opener delimiter quotings scrub the body: a
    journal-path mention INSIDE the commit-message body must disappear
    after _strip_commit_messages, for every quoting form."""
    for opener in ("<<EOF", "<<'EOF'", '<<"EOF"', "<<-EOF"):
        cmd = f"git commit -F - {opener}\nSee {_JOURNAL_TARGET} for details\nEOF"
        stripped = hygiene_gate._strip_commit_messages(cmd)
        assert "routing-log" not in stripped.lower(), opener


def test_heredoc_unclosed_not_matched_left_as_is():
    """A heredoc with no closing delimiter line does not match
    COMMIT_HEREDOC_RE at all -- fail-safe toward detection: the text is
    left completely unchanged, not silently half-scrubbed."""
    cmd = f"git commit -F - <<EOF\nSee {_JOURNAL_TARGET} here, no closer at all"
    stripped = hygiene_gate._strip_commit_messages(cmd)
    assert stripped == cmd


def test_heredoc_scrub_preserves_opener_line_trailing_content():
    """Content on the SAME line as the opener, after `<<DELIM`, is kept
    verbatim (group 4) -- only the body (group 5) is cut."""
    cmd = f"git commit -F - <<EOF trailing-marker\nSee {_JOURNAL_TARGET} here\nEOF"
    stripped = hygiene_gate._strip_commit_messages(cmd)
    assert "trailing-marker" in stripped
    assert "routing-log" not in stripped.lower()


def test_heredoc_pin_chained_write_after_closing_delimiter_still_blocks():
    """PIN: a real write chained via && on the line AFTER the heredoc's
    closing delimiter must still BLOCK class (d) -- the scrub must not
    eat a trailing `&& echo ... >> journal` that sits outside the
    heredoc body itself."""
    cmd = (
        "git commit -F - <<EOF\n"
        "Commit message body, nothing journal-related here.\n"
        "EOF\n"
        f'&& echo "{{}}" >> {_JOURNAL_TARGET}'
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(cmd))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_heredoc_pin_python_heredoc_after_git_commit_not_scrubbed_write_detected():
    """PIN: `git commit -m "x" && python - <<'PY'` with a real journal
    write inside the python heredoc's OWN body -- that heredoc belongs
    to the python statement, not to git commit (class (c)'s own
    heredoc form, `_is_python_heredoc_opener`), so it must NOT be
    scrubbed; the real write inside it must still be detected by
    class (d)."""
    cmd = (
        'git commit -m "x" && python - <<\'PY\'\n'
        f'with open("{_JOURNAL_TARGET}", "a") as f:\n'
        '    f.write("x")\n'
        "PY"
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(cmd))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_heredoc_scrub_only_applies_when_git_commit_present():
    """No `git commit` in the command at all -- _strip_commit_messages
    returns the command completely unchanged (early return), the
    heredoc-scrub machinery never even runs."""
    cmd = f"cat <<EOF\nSee {_JOURNAL_TARGET} here\nEOF"
    stripped = hygiene_gate._strip_commit_messages(cmd)
    assert stripped == cmd


def test_heredoc_nested_heredoc_documented_residual_not_crashing():
    """Nested heredocs (one heredoc's body containing another opener)
    are a documented residual limitation, not specially handled --
    this must not crash regardless of exactly which portion ends up
    scrubbed."""
    cmd = (
        "git commit -F - <<OUTER\n"
        "outer body start\n"
        "cat <<INNER\n"
        f"mentions {_JOURNAL_TARGET}\n"
        "INNER\n"
        "outer body end\n"
        "OUTER"
    )
    # Must not raise; the exact scrub boundary on nested heredocs is not
    # asserted (documented residual), only that decide() stays callable.
    exit_code, _ = hygiene_gate.decide(_bash_payload(cmd))
    assert exit_code == 0


def test_heredoc_body_redirect_stderr_still_warns_class_b_documented_residual():
    """Documented residual: a literal ` 2>&1` INSIDE a git-commit
    heredoc body still fires the class-(b) WARN -- classes (a)/(b)/(c)
    are evaluated against the RAW, un-scrubbed command; only class (d)
    consults _strip_commit_messages's output."""
    cmd = "git commit -F - <<EOF\nRun the tests 2>&1 and check the output.\nEOF"
    exit_code, output = hygiene_gate.decide(_bash_payload(cmd))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_REDIRECT_STDERR in ctx


# =========================================================================
# Determinism principle: quote-masking for class (b) (` 2>&1`), via
# _collect_redirect_signal -- see the module docstring, "Determinism
# principle" / "Class (b)".
# =========================================================================


def test_collect_redirect_signal_unit_absent():
    assert hygiene_gate._collect_redirect_signal("git status") == {
        "present": False, "certain": False,
    }


def test_collect_redirect_signal_unit_certain_deny():
    assert hygiene_gate._collect_redirect_signal("make 2>&1") == {
        "present": True, "certain": True,
    }


def test_collect_redirect_signal_unit_ambiguous_heredoc_warn():
    command = "python - <<'PY'\nbody\nPY\nls 2>&1"
    signal = hygiene_gate._collect_redirect_signal(command)
    assert signal["present"] is True
    assert signal["certain"] is False


def test_collect_redirect_signal_unit_quoted_2_greater_1_silent():
    command = "python -c \"print('ran 2>&1 here')\""
    assert hygiene_gate._collect_redirect_signal(command) == {
        "present": False, "certain": False,
    }


def test_redirect_denies_when_no_quotes_no_heredoc():
    exit_code, output = hygiene_gate.decide(_bash_payload("python foo.py 2>&1"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR


def test_redirect_fully_silent_when_quoted():
    # " 2>&1" sits ENTIRELY inside the -c argument's quotes --
    # _mask_quoted_segments hides it before the check; class (b) does
    # not fire at all (class (c) python -c/heredoc is a separate,
    # independent WARN -- it still fires). A MUTATING payload (see the
    # "pyc payload narrowing" section further down) keeps class (c) on
    # the old warn text; a pure payload would go silent instead.
    command = "python -c \"open('x.txt','w').write('ran 2>&1 here')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_REDIRECT_STDERR not in hso["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


def test_redirect_fully_silent_when_quoted_chain():
    # Two -c invocations, chained; the second's payload is mutating so
    # the OVERALL payload_class stays "M" (strictest class wins) and
    # class (c) keeps the old warn text under the narrowing -- see the
    # "pyc payload narrowing" section further down.
    command = (
        'python -c "a" ; python -c "open(\'x.txt\',\'w\').write(\'b 2>&1\')"'
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_REDIRECT_STDERR not in hso["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


def test_redirect_warns_when_heredoc_present_unquoted():
    # The heredoc's own delimiter is quoted ('PY', masked), but the `<<`
    # TOKEN ITSELF sits outside any quotes and stays visible.
    command = "python - <<'PY'\nbody\nPY\nmake 2>&1"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_REDIRECT_STDERR in hso["additionalContext"]


def test_redirect_denies_when_shift_operator_quoted_real_redirect_outside():
    # `<<` used as a real Python shift operator, but ENTIRELY inside a
    # quoted -c argument -- masked; the real redirect after `&&` is
    # outside any quotes and denies.
    command = 'python -c "print(1 << 3)" && ls 2>&1'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR


def test_redirect_warn_uses_verbatim_message_text():
    # Rule-of-three port (2026-08-25): the literal text changed shape
    # (what's wrong / what breaks / what to do instead), the pin below
    # tracks it verbatim rather than re-deriving it from the constant --
    # a silent text drift here would defeat the point of this test.
    command = "python - <<'PY'\nbody\nPY\nx 2>&1"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert hygiene_gate.MSG_REDIRECT_STDERR == (
        "a trailing \" 2>&1\" does not match the allowlist -- an extra "
        "permission prompt, or the command gets refused outright; drop "
        "\" 2>&1\" from the command (command hygiene point 3)"
    )
    assert hygiene_gate.MSG_REDIRECT_STDERR in output["hookSpecificOutput"]["additionalContext"]


def test_cmd_slash_c_quoted_redirect_fully_silent():
    command = 'cmd /c "pi some_pipeline 2>&1"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_powershell_command_quoted_redirect_fully_silent():
    command = 'powershell -Command "Set-Location tools; pytest . 2>&1 | tee out.txt"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_gate_smoke_probe_json_line_fully_silent():
    # A smoke probe of the gate itself -- a command (echo | python
    # tools/hygiene_gate.py) carrying a JSON string with "2>&1" INSIDE
    # the "command" value (double quotes, escaped internally by single
    # quotes outside) -- silence.
    command = (
        "echo '{...\"command\":\"cd gateway && ls 2>&1\"}' "
        "| python tools/hygiene_gate.py"
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_dash_m_message_2_greater_1_still_fully_silent():
    # The -m value is ALWAYS quoted -- quote-masking (_mask_quoted_
    # segments) hides it whole; no git-specific mechanism is needed for
    # this class any more.
    command = 'git commit -m "note about pytest 2>&1 output redirection"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


# =========================================================================
# Class (a): cd/Set-Location target parsing + the repo-root-only check.
# =========================================================================


def test_gateway_falls_into_generic_non_root_warn_no_special_case():
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway && python x.py"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_non_root_cd_target_variants_all_warn_not_deny():
    for command in [
        "cd gateway && ls",
        "Set-Location gateway; ls",
        "cd ./gateway && ls",
        'cd "gateway" && ls',
        "cd D:\\repo\\gateway && ls",
        "cd D:\\SomeOtherTree && ls",
        "cd D:\\Somewhere\\exam_kit && ls",
        "cd tools && ls",
        "cd scratchpad && ls",
    ]:
        exit_code, output = hygiene_gate.decide(_bash_payload(command))
        assert exit_code == 0
        hso = output["hookSpecificOutput"]
        assert "permissionDecision" not in hso, command
        assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"], command


def test_cd_to_subdirectory_of_repo_warns_not_denies():
    # cd INTO A SUBDIRECTORY of this repo (not the root itself) -- WARN,
    # not a block; only a cd to the root itself blocks.
    exit_code, output = hygiene_gate.decide(_bash_payload("cd tools && python x.py"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_repo_root_target_denies():
    command = f"cd {hygiene_gate._REPO_ROOT_NAME} && python x.py"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_CD_PREFIX


def test_repo_root_target_case_insensitive_denies():
    command = f"cd {hygiene_gate._REPO_ROOT_NAME.upper()} && python x.py"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_set_location_dash_path_flag_target_parsed_correctly():
    command = "Set-Location -Path gateway && ls"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_set_location_dash_path_flag_repo_root_denies():
    command = f"Set-Location -Path {hygiene_gate._REPO_ROOT_NAME} && ls"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_quoted_path_with_spaces_parsed_correctly_not_truncated():
    command = 'cd "some dir with spaces" && ls'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_extract_cd_prefix_target_unit_quoted_with_spaces():
    target = hygiene_gate._extract_cd_prefix_target('cd "some dir with spaces" && ls')
    assert target == '"some dir with spaces"'


def test_extract_cd_prefix_target_unit_dash_path_flag_skipped():
    target = hygiene_gate._extract_cd_prefix_target("Set-Location -Path gateway && ls")
    assert target == "gateway"


def test_extract_cd_prefix_target_unit_literal_path_flag_skipped():
    target = hygiene_gate._extract_cd_prefix_target("Set-Location -LiteralPath gateway && ls")
    assert target == "gateway"


def test_extract_cd_prefix_target_unit_bare_no_flag():
    target = hygiene_gate._extract_cd_prefix_target("cd gateway && ls")
    assert target == "gateway"


def test_extract_cd_prefix_target_unit_no_target_returns_none():
    assert hygiene_gate._extract_cd_prefix_target("cd") is None
    assert hygiene_gate._extract_cd_prefix_target("echo hi") is None


def test_three_blocking_classes_all_listed_fixed_order():
    # A fixed order: journal -> cd -> 2>&1.
    command = (
        f"cd {hygiene_gate._REPO_ROOT_NAME} && echo x >> logs/routing-log.jsonl "
        "&& python y.py 2>&1"
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK
    ctx = hso["additionalContext"]
    assert hygiene_gate.MSG_JOURNAL_BLOCK in ctx
    assert hygiene_gate.MSG_CD_PREFIX in ctx
    assert hygiene_gate.MSG_REDIRECT_STDERR in ctx
    assert (
        ctx.index(hygiene_gate.MSG_JOURNAL_BLOCK)
        < ctx.index(hygiene_gate.MSG_CD_PREFIX)
        < ctx.index(hygiene_gate.MSG_REDIRECT_STDERR)
    )


# --- a newline closes the cd bypass (a third, equal separator) ---------


def test_newline_separated_cd_root_denies():
    command = f'cd "{hygiene_gate._REPO_ROOT_NAME}"\ngit status'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_CD_PREFIX


def test_newline_separated_cd_non_root_warns_not_denies():
    command = "cd gateway\ngit status"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_is_cd_prefix_unit_newline_true():
    assert hygiene_gate._is_cd_prefix("cd gateway\nls") is True


def test_is_cd_prefix_unit_bare_no_continuation_false():
    assert hygiene_gate._is_cd_prefix("cd gateway") is False


def test_is_cd_prefix_unit_not_at_start_false():
    assert hygiene_gate._is_cd_prefix("echo hi\ncd gateway") is False


# --- a trailing newline with NOTHING after it stays legal (same
# semantics as a bare cd) -- the only way back to the root once a
# session has legitimately cd'd elsewhere. --------------------------


def test_trailing_newline_no_continuation_is_none_not_deny():
    command = f"cd {hygiene_gate._REPO_ROOT_NAME}\n"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_trailing_newline_no_continuation_unit_false():
    assert hygiene_gate._is_cd_prefix("cd gateway\n") is False


def test_bare_cd_root_still_none_same_semantics():
    exit_code, output = hygiene_gate.decide(
        _bash_payload(f"cd {hygiene_gate._REPO_ROOT_NAME}")
    )
    assert exit_code == 0
    assert output is None


def test_trailing_double_ampersand_no_continuation_is_none():
    assert hygiene_gate._is_cd_prefix("cd gateway && ") is False


def test_real_continuation_after_newline_still_true_regression():
    assert hygiene_gate._is_cd_prefix("cd gateway\nls") is True


# =========================================================================
# PowerShell write cmdlets for class (d) -- Add-Content/Set-Content/
# Out-File; PowerShell's redirect (>) is already covered by the
# existing check, and Tee-Object is already covered by TEE_RE.
# =========================================================================


@pytest.mark.parametrize(
    "cmdlet,args",
    [
        ("Add-Content", "-Path logs/routing-log.jsonl -Value x"),
        ("Set-Content", "-Path logs/routing-log.jsonl -Value x"),
        ("Out-File", "-FilePath logs/routing-log.jsonl"),
    ],
)
def test_ps_write_cmdlet_with_journal_target_denies(cmdlet, args):
    command = f"{cmdlet} {args}"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


@pytest.mark.parametrize(
    "cmdlet,args",
    [
        ("Add-Content", "-Path notes.txt -Value x"),
        ("Set-Content", "-Path notes.txt -Value x"),
        ("Out-File", "-FilePath notes.txt"),
    ],
)
def test_ps_write_cmdlet_non_journal_target_never_blocks(cmdlet, args):
    command = f"{cmdlet} {args}"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_ps_write_cmdlet_statement_scope_preserved():
    # The journal TARGET in one statement, the PS write form in a
    # DIFFERENT statement, writing to a non-journal file -- not a block
    # (the same statement-scoping principle _is_journal_bypass already
    # carries for bash forms).
    command = "cat logs/routing-log.jsonl; Add-Content -Path notes.txt -Value x"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_tee_object_already_covered_by_existing_tee_re():
    # "Tee-Object" already matches the existing TEE_RE (`\btee\b`) --
    # the "Tee" substring plus a word boundary at the hyphen -- so it is
    # NOT separately added to _PS_WRITE_CMDLET_RE (no duplicate
    # detector for the same class).
    command = "Tee-Object -FilePath logs/routing-log.jsonl"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"


# =========================================================================
# pyc payload narrowing (PYC_DENY_ENABLED, _is_python_dash_c_certain,
# _classify_pyc_payload) -- M/P/O/U class battery, ported from HQ's
# 2026-08-25 predicate-narrowing work. PYC_DENY_ENABLED stays False by
# default in every test below unless a test explicitly monkeypatches it.
# =========================================================================


def _payload_class(command: str) -> str:
    return hygiene_gate._classify_pyc_payload(command)


# --- acceptance: silent / old-text / new-text ----------------------------


def test_pycnarrow_pure_arithmetic_expression_silent():
    exit_code, output = hygiene_gate.decide(_bash_payload('python -c "print(1+1)"'))
    assert exit_code == 0
    assert output is None


def test_pycnarrow_pure_json_read_silent():
    command = 'python -c "import json; print(json.load(open(\'x.json\')))"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_pycnarrow_mutation_warns_old_text():
    command = "python -c \"open('x.txt','w').write('x')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C_OPAQUE not in hso["additionalContext"]


def test_pycnarrow_opaque_subprocess_warns_new_text_only():
    command = 'python -c "import subprocess; subprocess.run([\'ls\'])"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    ctx = hso["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C_OPAQUE in ctx
    # The M/U text is not a substring of the opaque text -- a
    # replacement, not an addition.
    assert hygiene_gate.MSG_PYTHON_DASH_C not in ctx


def test_pycnarrow_asymmetry_pure_payload_still_denies_when_switch_on(monkeypatch):
    # I2 invariant: the deny path reads ONLY `pyc_certain`, never
    # `pyc_payload` -- a proven-clean payload still BLOCKS when
    # PYC_DENY_ENABLED is (hypothetically) on, exactly like any other
    # certain match. This is the switch's OWN behavior, independent of
    # whether it is actually live (it is not, by default).
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = 'python -c "print(1+1)"'
    assert _payload_class(command) == "P"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_PYTHON_DASH_C_BLOCK


# --- empty / unextractable payload -> O -----------------------------------


def test_pycnarrow_bare_dash_c_no_argument_opaque():
    assert _payload_class("python -c") == "O"


def test_pycnarrow_empty_quoted_argument_opaque():
    assert _payload_class('python -c ""') == "O"


def test_pycnarrow_empty_heredoc_opaque():
    assert _payload_class("python - <<EOF\nEOF") == "O"


def test_pycnarrow_heredoc_without_closer_opaque():
    # No closing delimiter -- extraction finds no payload at all (the
    # regex requires a closing delimiter line), even though the opener
    # itself is still a certain match.
    command = "python - <<EOF\nprint(1)\n"
    assert hygiene_gate._is_python_dash_c_certain(command) is True
    assert _payload_class(command) == "O"


def test_pycnarrow_whitespace_only_payload_opaque():
    assert _payload_class('python -c "   "') == "O"


# --- string literal / comment mention -- not code -> P --------------------


def test_pycnarrow_w_inside_string_literal_pure():
    assert _payload_class("python -c \"x = 'w'\"") == "P"


def test_pycnarrow_comment_only_pure():
    assert _payload_class('python -c "# just a comment"') == "P"


def test_pycnarrow_mutation_mentioned_in_string_literal_pure():
    # "open(f,'w')" is TEXT (a print argument), not a REAL open() call.
    command = "python -c \"print('mentions open(f, mode w) as text')\""
    assert _payload_class(command) == "P"


# --- case sensitivity (legal: NameError at actual runtime) ----------------


def test_pycnarrow_uppercase_open_not_recognized_pure():
    assert _payload_class("python -c \"OPEN('x','w')\"") == "P"


def test_pycnarrow_pyc_key_survives_uppercase_python_dash_c():
    # The BROAD `pyc` key (unchanged) is case-insensitive; classifying
    # the payload's CONTENT is a separate, case-sensitive question (see
    # the test above).
    signals = hygiene_gate._collect_signals('PYTHON -C "OPEN(\'x\',\'w\')"')
    assert signals["pyc"] is True


# --- open() -- the full mode matrix ---------------------------------------


def test_pycnarrow_open_no_mode_pure():
    assert _payload_class("python -c \"open('x').read()\"") == "P"


def test_pycnarrow_open_r_mode_pure():
    assert _payload_class("python -c \"open('x','r').read()\"") == "P"


def test_pycnarrow_open_w_mode_mutation():
    assert _payload_class("python -c \"open('x','w')\"") == "M"


def test_pycnarrow_open_a_mode_mutation():
    assert _payload_class("python -c \"open('x','a')\"") == "M"


def test_pycnarrow_open_x_mode_mutation():
    assert _payload_class("python -c \"open('x','x')\"") == "M"


def test_pycnarrow_open_rplus_mode_mutation():
    assert _payload_class("python -c \"open('x','r+')\"") == "M"


def test_pycnarrow_open_mode_variable_opaque():
    assert _payload_class("python -c \"m='w'; open('x', m)\"") == "O"


def test_pycnarrow_open_kwargs_unpack_opaque():
    assert _payload_class("python -c \"d={'mode':'w'}; open('x', **d)\"") == "O"


def test_pycnarrow_open_mode_kwarg_w_mutation():
    assert _payload_class("python -c \"open('x', mode='w')\"") == "M"


def test_pycnarrow_method_open_no_mode_pure():
    command = "python -c \"import pathlib; pathlib.Path('x').open()\""
    assert _payload_class(command) == "P"


def test_pycnarrow_method_open_r_mode_pure():
    command = "python -c \"import pathlib; pathlib.Path('x').open('r')\""
    assert _payload_class(command) == "P"


# --- non-Python content / unclosed quote -- parse failure -> O ------------


def test_pycnarrow_non_python_content_opaque():
    assert _payload_class('python -c "this is not { python : code"') == "O"


def test_pycnarrow_unclosed_quote_opaque():
    assert _payload_class('python -c "print(\'unclosed') == "O"


# --- multiple calls / contributions -- strictest class wins ---------------


def test_pycnarrow_two_calls_different_classes_strictest_wins():
    command = 'python -c "print(1)" ; python -c "open(\'x\',\'w\')"'
    assert _payload_class(command) == "M"


def test_pycnarrow_two_mutating_calls_one_warn_line():
    command = "python -c \"open('a','w').write('x'); open('b','w').write('y')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert ctx.count(hygiene_gate.MSG_PYTHON_DASH_C) == 1


def test_pycnarrow_dunder_import_os_remove_opaque():
    # __import__('os').remove -- the base of `.remove` is a CALL, not a
    # Name -- no dotted name is built; only __import__(...) itself
    # contributes the opaque class.
    assert _payload_class("python -c \"__import__('os').remove('f')\"") == "O"


def test_pycnarrow_mutation_plus_opaque_together_mutation_wins():
    command = "python -c \"import subprocess; open('x','w').write('y')\""
    assert _payload_class(command) == "M"


# --- import aliases (import X as Y / from X import Y [as Z]) --------------


def _assert_never_silent(command: str, expected_class: str) -> None:
    assert _payload_class(command) == expected_class
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None, f"attack passed SILENTLY (regression): {command}"
    assert "permissionDecision" not in output["hookSpecificOutput"]


def test_pycnarrow_alias_import_as_qualified_os_remove_mutation():
    command = "python -c \"import os as o; o.remove('f.txt')\""
    _assert_never_silent(command, "M")


def test_pycnarrow_alias_import_as_qualified_shutil_rmtree_mutation():
    command = "python -c \"import shutil as sh; sh.rmtree('d')\""
    _assert_never_silent(command, "M")


def test_pycnarrow_alias_import_as_qualified_subprocess_opaque():
    command = "python -c \"import subprocess as sp; sp.run(['ls'])\""
    _assert_never_silent(command, "O")


def test_pycnarrow_alias_from_import_bare_name_mutation():
    command = "python -c \"from os import remove; remove('f.txt')\""
    _assert_never_silent(command, "M")


def test_pycnarrow_alias_from_import_asname_mutation():
    command = "python -c \"from os import remove as rm; rm('f.txt')\""
    _assert_never_silent(command, "M")


def test_pycnarrow_alias_from_import_opaque_name_opaque():
    command = "python -c \"from subprocess import run; run(['ls'])\""
    _assert_never_silent(command, "O")


# --- chained receivers (the call's base is itself a CALL) -----------------


def test_pycnarrow_chained_receiver_path_write_text_mutation():
    command = "python -c \"from pathlib import Path; Path('x.txt').write_text('x')\""
    _assert_never_silent(command, "M")


def test_pycnarrow_chained_receiver_journal_path_write_text_mutation():
    command = (
        "python -c \"from pathlib import Path; "
        "Path('logs/routing-log.jsonl').write_text('')\""
    )
    _assert_never_silent(command, "M")
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert hygiene_gate.MSG_PYTHON_DASH_C in output["hookSpecificOutput"]["additionalContext"]


def test_pycnarrow_chained_receiver_pathlib_path_open_w_mutation():
    # Method-form open(mode) -- the mode is the FIRST (not second)
    # argument, self is implicit.
    command = "python -c \"import pathlib; pathlib.Path('x').open('w')\""
    _assert_never_silent(command, "M")


def test_pycnarrow_chained_receiver_io_open_write_mutation():
    command = "python -c \"import io; io.open('x','w').write('y')\""
    _assert_never_silent(command, "M")


# --- reassigned callable (w = open; w(p, 'w')) -----------------------------


def test_pycnarrow_reassign_open_then_call_opaque():
    command = "python -c \"w = open; w('p', 'w')\""
    _assert_never_silent(command, "O")


def test_pycnarrow_reassign_os_remove_then_call_opaque():
    command = "python -c \"import os; r = os.remove; r('f')\""
    _assert_never_silent(command, "O")


def test_pycnarrow_reassign_control_non_mo_name_not_flagged_pure():
    # `x = 5` does not reference open/an M/O name -- must NOT flag O.
    command = 'python -c "x = 5; print(x)"'
    assert _payload_class(command) == "P"


# --- "U": certain=False -- classification not attempted, old text stays --


def test_pycnarrow_uncertain_form_not_classified():
    command = 'git commit -m "run python -c to test this"'
    assert hygiene_gate._is_python_dash_c_certain(command) is False
    assert _payload_class(command) == "U"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


# --- PYC_PAYLOAD_LIMIT -- AT and BEYOND the boundary (rule 6a) ------------


def test_pycnarrow_payload_exactly_at_limit_parses():
    body = "x = 1" + " " * (hygiene_gate.PYC_PAYLOAD_LIMIT - len("x = 1"))
    assert len(body) == hygiene_gate.PYC_PAYLOAD_LIMIT
    command = f'python -c "{body}"'
    assert _payload_class(command) == "P"


def test_pycnarrow_payload_one_past_limit_opaque_no_parse():
    body = "x" * (hygiene_gate.PYC_PAYLOAD_LIMIT + 1)
    command = f'python -c "{body}"'
    assert _payload_class(command) == "O"


def test_pycnarrow_nesting_depth_50_pure():
    payload = "(" * 50 + "1" + ")" * 50
    assert _payload_class(f'python -c "{payload}"') == "P"


def test_pycnarrow_nesting_depth_5000_no_traceback_opaque():
    payload = "(" * 5000 + "1" + ")" * 5000
    result = _payload_class(f'python -c "{payload}"')
    assert result == "O"


def test_pycnarrow_1mb_command_exit0():
    command = 'python -c "print(\'' + ("a" * 1_000_000) + "')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["additionalContext"].count(
        hygiene_gate.MSG_PYTHON_DASH_C_OPAQUE
    ) == 1


def test_pycnarrow_perf_100kb_1mb_number_not_gated():
    # A generous ceiling, not a strict perf gate -- a regression trap
    # against a catastrophic blowup; the actual measured numbers go
    # into the builder's report verbatim.
    cmd_100kb = 'python -c "print(\'' + ("a" * 100_000) + "')\""
    t0 = time.perf_counter()
    hygiene_gate.decide(_bash_payload(cmd_100kb))
    elapsed_100kb = time.perf_counter() - t0

    cmd_1mb = 'python -c "print(\'' + ("a" * 1_000_000) + "')\""
    t0 = time.perf_counter()
    hygiene_gate.decide(_bash_payload(cmd_1mb))
    elapsed_1mb = time.perf_counter() - t0

    print(f"pyc_payload classify 100KB: {elapsed_100kb:.4f}s, 1MB: {elapsed_1mb:.4f}s")
    assert elapsed_100kb < 2.0, f"pyc_payload classify 100KB: {elapsed_100kb:.4f}s"
    assert elapsed_1mb < 2.0, f"pyc_payload classify 1MB: {elapsed_1mb:.4f}s"


def test_pycnarrow_emoji_and_greek_pure():
    command = "python -c \"print('αβ\U0001F600')\""
    assert _payload_class(command) == "P"


def test_pycnarrow_null_bytes_stdin_no_crash():
    result = _run_hook(b"\xff\xfe not json \x00")
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_pycnarrow_journal_block_plus_clean_pyc_payload_no_pyc_line():
    command = "echo x >> logs/routing-log.jsonl; python -c \"print(1+1)\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK
    ctx = hso["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C not in ctx
    assert hygiene_gate.MSG_PYTHON_DASH_C_OPAQUE not in ctx


def test_pycnarrow_certain_computed_once_signal_matches_direct_call():
    command = "python -c \"open('x.txt','w').write('x')\""
    signals = hygiene_gate._collect_signals(command)
    assert signals["pyc_payload"] == hygiene_gate._classify_pyc_payload(command)


def test_pycnarrow_measurer_reads_pyc_not_pyc_payload():
    import permission_audit

    command = 'python -c "print(1+1)"'
    assert permission_audit.classify_hygiene(command) == ["python -c/heredoc"]


# =========================================================================
# MAX_HEREDOC_OPENERS -- quadratic-backtracking prefilter, on BOTH paths
# that share COMMIT_HEREDOC_RE.sub (`_is_python_dash_c_certain` via
# `_mask_heredoc_bodies`, and `_is_journal_bypass` via
# `_strip_commit_messages`) -- AT and BEYOND the boundary (rule 6a).
# =========================================================================


def _unterminated_heredoc_openers(n: int, filler_len: int = 200) -> str:
    """n DISTINCT (a unique delimiter per opener) `python - <<DELIM_i`
    openers with NO closer at all -- no regex pass finds a closing line
    for any of them (the live catastrophic-backtracking shape)."""
    filler = "x" * filler_len
    parts = [f"python - <<DELIM_{i}\n{filler}" for i in range(n)]
    return "\n".join(parts)


def test_heredoc_cap_boundary_at_64_openers_is_certain_and_fast():
    # AT the boundary (n == MAX_HEREDOC_OPENERS == 64): the prefilter
    # does NOT fire (`count("<<") > 64` is false at exactly 64) -- the
    # expensive path runs as before, and stays fast at this size.
    assert hygiene_gate.MAX_HEREDOC_OPENERS == 64
    command = _unterminated_heredoc_openers(64)
    t0 = time.perf_counter()
    certain = hygiene_gate._is_python_dash_c_certain(command)
    elapsed = time.perf_counter() - t0
    print(f"heredoc cap perf: n=64 openers ({len(command)} bytes) -> {elapsed:.4f}s")
    assert certain is True  # these are REAL python-heredoc openers
    assert elapsed < 2.0, f"n=64 (at boundary) took {elapsed:.4f}s -- unexpectedly slow"


def test_heredoc_cap_65_openers_one_past_boundary_forces_early_exit():
    # BOUNDARY+1 (n=65): one opener past the cap -- the prefilter now
    # fires (`65 > 64`), certain=False -- discriminates from n=64 above.
    command = _unterminated_heredoc_openers(65)
    assert hygiene_gate._is_python_dash_c_certain(command) is False


def test_heredoc_cap_beyond_boundary_4000_openers_early_exit_linear():
    # WELL beyond the boundary (n=4000): early exit -- certain is
    # ALWAYS False (conservative, deny never widens), and the time is
    # NOT quadratic -- the cheap count("<<") is linear in command
    # length, not quadratic in opener count.
    command = _unterminated_heredoc_openers(4000)
    t0 = time.perf_counter()
    certain = hygiene_gate._is_python_dash_c_certain(command)
    elapsed = time.perf_counter() - t0
    print(f"heredoc cap perf: n=4000 openers ({len(command)} bytes) -> {elapsed:.4f}s")
    assert certain is False
    assert elapsed < 1.0, (
        f"n=4000 (beyond boundary) took {elapsed:.4f}s -- early exit did not fire"
    )


def test_heredoc_cap_over_limit_classification_falls_back_to_u_not_deny(monkeypatch):
    # Beyond the cap, classification is "U" (not M/P) -- decide() keeps
    # the OLD unconditional WARN behavior, never deny, even with
    # PYC_DENY_ENABLED=True (the I2 invariant: deny never widens from a
    # pathological input -- the form degrades to WARN, not silence and
    # not a block).
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = _unterminated_heredoc_openers(65)
    assert _payload_class(command) == "U"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso, (
        "a giant form past MAX_HEREDOC_OPENERS denied -- the conservative "
        "direction is broken"
    )
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


def test_heredoc_cap_i2_invariant_existing_deny_tests_green_without_body_changes():
    # A narrow, standalone pin (alongside the boundary battery above)
    # that the prefilter left an ordinary `python -c` payload alone.
    command = 'python -c "print(1+1)"'
    assert hygiene_gate._is_python_dash_c_certain(command) is True
    assert _payload_class(command) == "P"


# --- the SAME cap, on the journal-bypass path (`_is_journal_bypass`) -----


def _git_commit_with_unterminated_heredocs(n: int) -> str:
    return 'git commit -m "msg" && ' + _unterminated_heredoc_openers(n)


def test_heredoc_cap_journal_path_boundary_at_64_openers_runs_real_check():
    # AT the boundary (n == 64, WITH "git commit"): the prefilter does
    # NOT fire -- the expensive scrub runs as before, and stays fast at
    # this size (the quadratic blowup only becomes visible at n=500+).
    command = _git_commit_with_unterminated_heredocs(64)
    t0 = time.perf_counter()
    result = hygiene_gate._is_journal_bypass(command)
    elapsed = time.perf_counter() - t0
    print(f"heredoc cap perf (journal path): n=64 + git commit ({len(command)} bytes) -> {elapsed:.4f}s")
    assert result is False  # no actual journal write in this synthetic form
    assert elapsed < 2.0, f"n=64 (at boundary) took {elapsed:.4f}s -- unexpectedly slow"


def test_heredoc_cap_journal_path_65_openers_one_past_boundary_forces_early_exit():
    command = _git_commit_with_unterminated_heredocs(65)
    assert hygiene_gate._is_journal_bypass(command) is False


def test_heredoc_cap_journal_path_beyond_boundary_2000_openers_not_quadratic():
    command = _git_commit_with_unterminated_heredocs(2000)
    t0 = time.perf_counter()
    result = hygiene_gate._is_journal_bypass(command)
    elapsed = time.perf_counter() - t0
    print(f"heredoc cap perf (journal path): n=2000 + git commit ({len(command)} bytes) -> {elapsed:.4f}s")
    assert result is False
    assert elapsed < 1.0, (
        f"n=2000 (beyond boundary, past the size HQ's own critic measured) took "
        f"{elapsed:.4f}s -- early exit did not fire"
    )


def test_heredoc_cap_journal_path_negative_control_no_git_commit_stays_cheap():
    # Negative control (command hygiene point 6, paired with the
    # positive above): the SAME form WITHOUT "git commit" was already
    # cheap before this cap (the GIT_COMMIT_RE guard short-circuits
    # `_strip_commit_messages` first) -- fast regardless of opener
    # count, proving the cheapness is not solely this new cap's doing.
    command = _unterminated_heredoc_openers(4000)  # no "git commit" at all
    t0 = time.perf_counter()
    result = hygiene_gate._is_journal_bypass(command)
    elapsed = time.perf_counter() - t0
    assert result is False
    assert elapsed < 1.0, f"no-git-commit form took {elapsed:.4f}s -- unexpectedly slow"


def test_heredoc_cap_journal_path_real_bypass_still_detected_below_limit():
    # Regression pin: a genuine journal bypass (an echo redirect into
    # logs/routing-log.jsonl, below the opener cap) is still detected --
    # the prefilter does not blind ordinary detection.
    command = 'echo "x" >> logs/routing-log.jsonl'
    assert hygiene_gate._is_journal_bypass(command) is True
