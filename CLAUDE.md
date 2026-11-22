# CLAUDE.md

Instructions for AI coding tools working in this repo. Read this before touching code.

## Project goals

Build a **client intelligence agent** for Aster Vale Sports Data: given a client and a trigger, gather evidence from a SQLite database, analyse it, and produce a short briefing for a sales rep in which **every claim is grounded in the data and cited**.

The assignment brief is transcribed verbatim at [task.md](task.md). Data investigation findings are at [data_analysis.md](data_analysis.md) -- read these before writing any tool code, they document every data quality issue, duplicate, and correction. The agreed plan, product definition and technical design are at [.claude/plan.md](.claude/plan.md).


## Prefer simple code, in Python and in SQL

**Always reach for the simplest form that works. Do not add structure in anticipation of a problem you have not got.** Three things the work is judged on, in order:

1. **General.** Works for any of the 25 clients and any of the 4 triggers, with no logic written for a specific client or case. It will be run on clients we never looked at.
2. **The numbers are right.** Figures come from code or SQL, never from the model. When data is missing, sparse or inconsistent, the briefing says so instead of filling the gap.
3. **Orchestrated.** Steps with clear jobs: planner, writer, verifier, judge. As simple as works.


## Invariants

These are not style preferences. Each is a hard fail.

| # | Invariant |
| --- | --- |
| **I1** | No number originates in the model. All arithmetic, date maths, ranking and thresholds live in tool code |
| **I2** | No logic for a specific client, name or segment. A grep for client IDs outside `tests/` and `eval/` must come back empty |
| **I3** | Every figure and claim carries a citation that resolves to a stable evidence ID |
| **I4** | Gaps are detected and shown, never filled with a default, a mean or a last-known value |
| **I5** | Tools are deterministic. Same input, same bytes out. The as-of date is **2026-11-01**, never `date.today()` |
| **I6** | No real credentials, ever. Placeholder in committed code, real key in gitignored `.env` only |
| **I7** | A new trigger needs no Python. The planner reasons freely from tool descriptions, not hardcoded per-trigger tool lists |


## Architecture overview

Two front doors, one engine. The CLI (`main.py`) and the Streamlit UI (`app.py`) both run the identical pipeline. The UI is a view, never a second code path.

```
Aster_business_analyst/
  config.py      — AS_OF, MODEL, DB_PATH, API key, trigger definitions
  prompts.py     — all LLM prompts (planner, writer, judge)
  tools.py       — 10 SQL tool functions + DB helpers + 3 dedup CTEs
  agent.py       — orchestration (plan, write, verify, render, judge, retry) 
  main.py        — CLI entry point + pipeline + tracing
  app.py         — Streamlit UI
tests/
  test_tools.py        — 27 unit tests, 4 data shapes, no LLM
eval/
  cases.yaml     — 6 test cases (3 clients x 2 triggers) with expected facts
  run_eval.py    — unit tests (layer 0) + layer 1 (free) + layer 2 (full pipeline)
starter_pack/    — read-only data, never modified
output/          — per-run folders: <client_id>_<trigger>/
docs/            — architecture.md, changelog.md
```

### Where the model is, and is not

| Stage | Model? |
| --- | --- |
| Resolve client | No. SQL only, so it cannot invent a client |
| Planner | **Yes.** Free-flow reasoning over tool descriptions, returns JSON array of tool names |
| 10 tool bodies | No. Deterministic SQL with dedup CTEs, computed fields, parameterised queries |
| Writer | **Yes.** Structured JSON claims with citations, forbidden from calculating numbers |
| Verifier | No. Python set lookups: citations in row_ids, numbers in tool data |
| Renderer | No. String formatting: claims to markdown with `[UNVERIFIED: reason]` tags |
| Judge | **Yes.** Scores briefing on 4 dimensions; if any < 3, triggers one writer retry with feedback |


## Data flow

```
client (id or name) + trigger + optional rep context
  -> RESOLVE      SQL only: exact id > exact name > partial > fuzzy
                  fuzzy and not-found run nothing, spend no tokens
  -> PLAN         client profile + trigger + context -> tool names    MODEL
                  free-flow reasoning, check_data_quality always forced
  -> TOOLS        deterministic SQL, one by one, milliseconds each
                  -> tool results dict with data + row_ids
  -> WRITE        tool summaries -> structured JSON claims            MODEL
                  each claim: section, claim, numeric_values, citations, source_tool
  -> VERIFY       every number in tool data? every citation in row_ids?
       fail -> FLAG inline with reason, never silently delete
               four categories: LLM-computed | no source found | citation not in evidence | no citations
  -> RENDER       claims -> markdown briefing
  -> JUDGE        scores briefing on 4 dimensions                    MODEL
       if any dimension < 3 -> RETRY writer with feedback, re-verify, re-render, re-judge (once)
  -> briefing.md + evidence.json + scores.json + trace.json
```

### Verification failure handling

Decided: **flag with reason**, not repair or remove. Why:
- **Remove** hides model failures from the rep. They see a clean briefing and trust it, never knowing something was dropped. The assignment says gaps must be "shown, not hidden".
- **Repair** adds a 4th LLM call, might still fail, and asks an LLM to verify another LLM's math, which is the problem we are solving.
- **Flag** keeps everything visible. The rep sees `[UNVERIFIED: LLM-computed value]` and knows the number came from model arithmetic, or `[UNVERIFIED: no source found]` and knows to distrust it.


## Data handling

Do not edit any files in `starter_pack/`. All data cleaning happens in code at query time.

Known duplicates in the DB: contract K-0010 (duplicate row), ticket T-0281 (duplicate row), usage U-00422/U-01991 (same observation, different PKs). Every SQL query must deduplicate by business key (DISTINCT on contract_id, ticket_id, or client_id+product_id+month).

Missing data means unknown, not zero. 15 of 25 clients have no meeting notes. C004 has only 2 months of usage. C005 is missing March usage. These are gaps, not zeros.


## Tech stack

Python 3.12, uv, stdlib `sqlite3`, stdlib `argparse`, Anthropic SDK (direct, no wrapper), Streamlit for UI. Claude Opus 4.6 on Anthropic Foundry.

Do not add: pandas, langchain, langgraph, vector databases, an ORM, a CLI framework, or an orchestration framework. The pipeline is linear with 3 LLM calls (5 if the judge triggers a retry). A framework adds weight without solving a problem we have.


## Test loop

| Layer | What it catches | How to run |
| --- | --- | --- |
| **Unit tests** (free) | Tool correctness across 4 data shapes: normal, empty, short, duplicate | `uv run python -m pytest tests/test_tools.py -v` |
| **Layer 1** (free) | Tool output correctness: 30 expected facts across 6 cases | `uv run eval/run_eval.py` |
| **Layer 2** (costs money) | Full pipeline + ungrounded number check on rendered briefing | `uv run eval/run_eval.py --full` |
| **Report** | Markdown summary with pass/fail table and failure details | `uv run eval/run_eval.py --full --report` |
| **Tracing** | Per-run: LLM tokens/cost/latency, tool timings, pipeline steps | automatic, saved to `trace.json` |

**After modifying `tools.py`, run unit tests before anything else:** `uv run python -m pytest tests/test_tools.py -v`

**After changing a prompt, re-run the eval and compare violation counts, not prose.**

The runtime verifier is itself a test loop: every briefing is checked against its own evidence before it is written.


## Secrets

API key from `ANTHROPIC_FOUNDRY_API_KEY` env var. The `.env` file is gitignored. Only a placeholder example is committed. Never paste a real key into the conversation or commit it.


## Documentation

- [task.md](task.md) the assignment brief, verbatim
- [data_analysis.md](data_analysis.md) Phase 1 findings with corrections
- [.claude/plan.md](.claude/plan.md) agreed plan: product definition, technical design, build steps
- [docs/architecture.md](docs/architecture.md) system design, data flow, agent orchestration
- [docs/changelog.md](docs/changelog.md) version history

**Update the files in `docs/` after each milestone and after any major addition.** A build step is not finished until the changelog records it.
