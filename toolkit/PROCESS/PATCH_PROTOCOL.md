# Patch Protocol

Status: fallback mechanism.

Direct git commits are the standard way to change the repository when
the LLM has repository access. A patch/diff file is used only in
environments without such access.

Whether applied as a commit or a patch, every change should:

1. Solve one conceptual problem.
2. Preserve repository consistency.
3. Update affected documentation.
4. Leave the repository in a self-contained state.
5. Avoid hidden knowledge.
