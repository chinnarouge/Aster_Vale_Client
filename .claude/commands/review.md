---
description: Review changes against this assignment's non-negotiable invariants, then hunt generic bugs
argument-hint: Optional scope (a path, a branch, or blank for all uncommitted changes)
---

# Review

Two passes. The **invariant gate** is specific to this assignment and no generic reviewer knows about it, so it runs first and it blocks. The **bug hunt** is delegated.

Scope: `$ARGUMENTS` if given, otherwise all uncommitted changes (`git diff HEAD` plus untracked files). If the repo has no commits yet, review the working tree.

## Pass 1: invariant gate

These come straight from [task.md](../../task.md) and are what this submission is actually assessed on. Each is a hard fail, not a suggestion. Report file and line, and say whether the change introduced it or merely left it in place.

### I1. No number originates in the model

Must-have 2: "Figures come from code or SQL tools, not from the language model."

Check that arithmetic, aggregation, date maths, trend direction, ranking and thresholds all live in tool code. Look for:

- a prompt asking the model to calculate, total, average, compare or rank
- a model response parsed into a figure that reaches the briefing without passing through a tool
- a number in the briefing that does not exist in the evidence file

### I2. No logic for a specific client or case

Must-have: it works for any of the 25 clients and any of the four triggers "without logic written for a specific client or case. We will run it on clients you have not looked at."

```
grep -rniE "\b(C[0-9]{3})\b" --include=*.py --include=*.yaml src/ prompts/
```

Any client ID, client name or hardcoded segment branch outside `tests/` and fixtures is a fail. Same for a trigger handled by an `if trigger == ...` chain where configuration would do.

### I3. Every figure is cited and verifiable

Must-have 4: a writer that cites a source for every figure and claim, and a verifier that checks every number appears in the evidence and every claim has a citation.

- every numeric fact a tool produces is addressable by a stable ID
- the writer cannot emit a figure without a citation token
- the verifier resolves citation tokens against the evidence and fails when one dangles
- the decided failure path is applied consistently, and never silently drops a claim

### I4. Gaps are surfaced, never filled

Must-have 5: duplicates, missing months, short histories and conflicts "are detected and shown... not hidden."

- no default substituting zero, the mean, or last-known-value for missing data without saying so
- a client with no meeting notes, no tickets, or a two-month history still produces a briefing, with the gap stated
- the gaps section cannot render empty merely because nothing was checked

### I5. Tools are deterministic

Same input, same bytes out. Look for unseeded randomness, wall-clock reads where the 2026-11-01 as-of date belongs, dict or set iteration order leaking into output, and unordered SQL feeding a ranked list.

### I6. No real credentials

Submission rule: "Use a placeholder for the API key; please do not include real keys."

```
git ls-files | grep -iE "(^|/)\.env$|\.pem$|credential"
```

The real key file must be gitignored, with only a placeholder example committed. The `block-secrets` hook covers my tool calls but not what a human pasted in, so check by eye.

### I7. A new trigger needs no Python

Stretch goal, and the cleanest proof that I2 and I3 hold. Adding a trigger should be a config edit. Flag any change that moves trigger behaviour into code.

## Pass 2: generic bug hunt

Delegate to the `code-reviewer` subagent for correctness, security and convention issues. Give it the diff and the conventions from CLAUDE.md, and tell it to skip the invariants above rather than duplicate pass 1.

Also worth a direct look, because they bite this kind of code specifically:

- division by zero or `None` where a client has one month of history, or none
- date arithmetic across month ends and the notice-period boundary
- a SQL aggregate silently dropping rows via an inner join when the right side is sparse
- rounding applied twice, so briefing and evidence disagree on the last digit
- a tool that raises where it should return an empty envelope with a recorded gap

## Report

Group by severity. For each finding: file and line, what breaks, and the smallest fix.

1. **Invariant violations**, each tagged `I1`..`I7`. These block.
2. **Bugs**, ordered by whether a rep would see a wrong number.
3. **Nits**, at most five, and only if they cost nothing to fix.

End with one line: pass or fail, and the invariant that failed first. If nothing fails, say so plainly rather than inventing findings to look thorough.
