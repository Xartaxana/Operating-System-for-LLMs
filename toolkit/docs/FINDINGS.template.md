# Findings

Template shipped by the toolkit itself. Copy this file to
`docs/FINDINGS.md` in the host repo before the first finding is
recorded (an absent `docs/FINDINGS.md` is a normal pre-adoption state,
not an error -- see `tools/test_findings_form.py`'s own handling of a
missing file).

A registry of empirical observations from operating this architecture
itself (dogfooding) in the host repo -- entries produced by the
host's OWN sessions, as distinct from external priors the host's
telemetry is meant to confirm or refute (those belong in a separate
prior-art log, if the host keeps one).

Each entry: observation -> how it was obtained -> consequence for
the architecture -> status (does this need a decision recorded
elsewhere). Numbering (`F-1`, `F-2`, ...) follows recording order in
this registry, not the chronology of the underlying observation.

## Norm: the applicability question

An entry that carries a **Class.** section -- naming a CLASS of
defect or behavior, not just describing one instance of it -- also
carries an **Applicability question.** section, placed IMMEDIATELY
AFTER **Class.** (only blank lines or continuing prose belonging to
the Class section may sit between them; another field starting first
breaks adjacency). The applicability question is ONE SENTENCE, phrased
as a check a reader could run against a NEW candidate case to decide
whether it belongs to the same class -- written WITHOUT proper names
tied to the specific site where this entry was made (a class is
supposed to generalize past its own origin; naming the origin site
defeats that). When a class genuinely cannot be phrased without a
proper name, the entry carries an explicit line instead: "applicability
question not extracted: <why>" -- silence is not a legal outcome for
an entry that names a class.

An entry with NO **Class.** section (a purely factual observation, not
a named defect/behavior class) does not need an **Applicability
question.** field at all.

Field markers used by this norm (and recognized by the machine check
in `tools/test_findings_form.py`): `**Class.**` and `**Applicability
question.**`, exactly spelled and capitalized this way. A marker
appearing inside a fenced code block or a blockquote line (`>`) does
not count as filling the field -- a quotation is not an entry's own
assertion.

---

<!--
Worked example (a comment -- not a live entry; delete this block once
the first genuine entry is recorded, or leave it as a reference above
the live entries).

## F-1 -- Short title naming the observed fact

**Date:** YYYY-MM-DD.

**Observation.** What was seen, and in which session/run.

**Class.** The general shape of defect or behavior this instance
belongs to, phrased so it could apply to more than this one site.

**Applicability question.** One sentence a reader could check against
a NEW candidate case to decide whether it belongs to this class.

**Consequence.** What this implies for the architecture, if anything.

**Status.** Open / needs a decision / resolved by <pointer>.
-->
