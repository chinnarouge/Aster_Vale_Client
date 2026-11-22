# Aster Vale Client Intelligence Agent

A client intelligence agent for Aster Vale Sports Data. Given a client and a trigger, it gathers evidence from a SQLite database, analyses it, and produces a cited briefing for a sales rep.

## Quick start

```bash
# Install dependencies
uv sync

# Set your API key
# The code reads ANTHROPIC_FOUNDRY_API_KEY for both Foundry and standard API
export ANTHROPIC_FOUNDRY_API_KEY="your-key-here"

# Foundry users also need the base URL:
export ANTHROPIC_FOUNDRY_BASE_URL="your-base-url-here"
# Standard API users: skip the base URL, it falls back to the default endpoint

# Run a briefing
uv run Aster_business_analyst/main.py --client "Halden Bet" --trigger at_risk --context "Usage feels down"

# Run the Streamlit UI
uv run streamlit run Aster_business_analyst/app.py

# Run unit tests (27 tests, no LLM, <1s)
uv run python -m pytest tests/test_tools.py -v

# Run evaluation (layer 1 is free, layer 2 needs LLM)
uv run eval/run_eval.py                # tool checks only, free
uv run eval/run_eval.py --full --report # full pipeline + report
```

Output goes to `output/<client_id>_<trigger>/` with `briefing.md`, `evidence.json`, `scores.json`, and `trace.json`.

## How it works

The pipeline has 7 steps. Three use the LLM (up to 5 if the judge triggers a retry), four are pure Python. All prompts live in `prompts.py`.

```
Client + Trigger + Context
  |
  v
1. Resolve client          SQL lookup, no LLM
2. Plan                    LLM picks which tools to run
3. Run tools               10 SQL tools, deterministic
4. Write claims            LLM writes structured JSON claims with citations
5. Verify                  Python checks every number and citation against tool data
6. Render                  Python formats verified claims into markdown
7. Judge                   LLM scores the briefing on 4 dimensions
                           if any dimension < 3 → retry writer with feedback (once)
  |
  v
briefing.md + evidence.json + scores.json + trace.json
```

### Where the model is and is not

The model plans (which tools to run), writes (prose with citations), and judges (quality scoring). It never does math, runs queries, or verifies its own output.

The tools are SQL queries. The verifier is Python set lookups. The renderer is string formatting. Numbers come from code, not the model.

### The 10 tools

All in `tools.py`. Client resolution accepts a name or ID; the remaining tools operate on the resolved client_id with parameterized SQL against the starter pack database, returning structured data with row IDs for citation.

1. `resolve_client` -- name/ID resolution with fuzzy matching
2. `get_client_profile` -- segment, tier, tenure, country
3. `get_contract_status` -- ARR, dates, notice deadline, days_until_notice
4. `get_usage_trend` -- per-product YoY and sequential change, utilization
5. `get_whitespace` -- products not held, peer adoption rates
6. `get_support_summary` -- ticket counts, CSAT, ticket_change_abs
7. `get_opportunities` -- pipeline, arr_vs_pipeline_gap
8. `get_meeting_notes` -- note text with IDs
9. `check_data_quality` -- duplicates, missing months, short history
10. `get_peer_comparison` -- client vs segment peers on ARR, usage, adoption

Tool 10 is my addition beyond the 9 suggested. It compares a client against segment peers so the briefing can say "60% of your peers hold this product" instead of just "you should buy it."

### Verification

The writer outputs structured JSON claims, not prose. Each claim has explicit `numeric_values` and `citations` fields. The verifier checks:

- Does every cited row ID exist in the tool outputs?
- Does every declared number match a value in the tool data?
- Does the claim text contain undeclared numbers not in any tool output?

When a number isn't found directly, `_find_derivation()` checks whether it's simple arithmetic (sum, difference, percentage) of two tool values. This distinguishes correct-math-from-wrong-source from hallucinated numbers. The number is still flagged — the model did the calculation, not a tool — but the flag explains what happened.

Failure categories:

- `[UNVERIFIED: LLM-computed value]` -- the number is correct arithmetic from tool data, but the model calculated it instead of a tool
- `[UNVERIFIED: no source found]` -- the number doesn't appear anywhere in tool data
- `[UNVERIFIED: citation not in evidence]` -- the row ID doesn't exist
- `[UNVERIFIED: no citations]` -- the claim has no citations at all

I chose to flag rather than repair or remove. Removing hides failures from the rep. Repairing adds another LLM call that might still fail. Flagging with a reason lets the rep decide whether to trust the claim.

### Data handling

The starter pack has intentional quality issues. Three known duplicates (K-0010, T-0281, U-00422/U-01991) are handled with dedup CTEs at query time. The source data is never modified. Missing data is reported as unknown, never filled with zero or a mean.

## Testing

Three layers, cheapest first. The eval runner executes all three in order and stops on failure.

- **Unit tests (free, <1s):** 27 pytest tests covering all 10 tools across 4 data shapes: normal data (C002), empty data (C004/C007 — no tickets, no contracts), short history (C004 — 2 months, no YoY), and duplicate rows (C006/C010 — dedup correctness). Verifies edge cases like CSAT=None with no tickets, YoY=None for short history, and determinism (same input, same output). Run standalone: `uv run python -m pytest tests/test_tools.py -v`
- **Layer 1 (free):** 30 expected facts from `eval/cases.yaml` checked against actual tool outputs. 6 cases across 3 clients (C002, C009, C017) and all 4 triggers. Catches tool regressions without spending tokens.
- **Layer 2 (costs money):** Full pipeline for each case. Automated check scans the rendered briefing for numbers not in any tool output. Results written to `eval/report.md`.

Run `uv run eval/run_eval.py --full --report` to reproduce all three layers.

## Known limitations

- The writer occasionally calculates numbers instead of quoting tool output, despite the prompt forbidding it. These get flagged by the verifier.
- Tools run sequentially. Parallelism would save little since SQL queries take milliseconds; the LLM calls are the bottleneck.
- The judge triggers one writer retry if any dimension scores below 3. This handles most quality issues but is capped at one retry to control cost.
- The planner sometimes selects more tools than needed. Selectivity guidance helps but isn't perfect.
- Meeting notes extraction is whatever the LLM decides to surface. No structured extraction step.

## What I would do next

- **Structured note extraction:** A dedicated LLM call for meeting notes that extracts quotes and verifies them as literal substrings of the source text.
- **Parallel tool execution:** asyncio for the SQL tools, though the real win would be batching the LLM calls where possible.
- **Confidence scores per claim:** Based on data coverage (12 months of data = high, 2 months = low).
- **Portfolio view:** Rank all 25 clients by renewal risk or growth potential.
- **Targeted claim repair:** Instead of retrying the full writer, re-run only the flagged claims with focused context.
- **Manual verification:** The automated verifier proves figures resolve to evidence, not that the briefing is useful. Hand-check a sample against the database and feed findings back into prompts.
- **Access control:** Nothing currently checks whether a rep is entitled to an account. Scope resolution and every query to the rep's permitted clients.

## How I built it

Worked with Claude Code across three phases.

**Phase 1 (investigation):** Had Claude read the data dictionary and go through every table. It found the planted duplicates and data quality issues but also made mistakes -- miscounted products for C003, misread a contract date, wrongly flagged a CSAT score. I corrected these and recorded them in `data_analysis.md`. The corrections prevented wrong assumptions from carrying into the code.

**Phase 2 (planning):** Decided the architecture (hybrid LLM + Python), framework (none, direct SDK), tech stack, LLM call budget (3 normally, 5 with judge retry), and verification approach (flag, not repair or remove). Wrote it up in `.claude/plan.md` before writing any code.

**Phase 3 (building):** Step by step, proposing each piece before building it. Claude Code's `/review` skill checked the 7 assignment invariants after each milestone. The PostToolUse hook ran formatting on every write. The block-secrets hook prevented API keys from leaking into tool calls.

**What worked:** The phased approach prevented building before understanding the data. User corrections during Phase 1 caught errors that would have produced wrong briefings. The invariant checklist caught 5 bugs before end-to-end testing.

**Key design choices I made along the way:**
- **Computed fields in tools** (days_until_notice, tenure_years, arr_vs_pipeline_gap, ticket_change_abs) so the writer cites pre-computed values instead of doing arithmetic the verifier would flag.
- **Writer input summarization** -- raw tool data trimmed before sending to the writer, cutting input tokens ~80%. The verifier still checks against full data.
- **LLM-as-judge with retry** -- the judge scores the briefing on 4 dimensions; if any score is below 3, the writer retries with the judge's critique. One retry max (3 LLM calls normal, 5 with retry).
- **Trigger definitions in config** -- the planner receives a description of what each trigger means, improving tool selection without hardcoding per-trigger logic.
- **Unit tests across 4 data shapes** -- normal, empty, short history, and duplicate rows. Catches edge cases like CSAT=None with no tickets and YoY=None for 2-month histories. Runs as layer 0 in the eval suite before spending LLM tokens.

## File structure

```
Aster_business_analyst/
  config.py           -- AS_OF, MODEL, DB_PATH, API key, trigger definitions
  prompts.py          -- all LLM prompts (planner, writer, judge)
  tools.py            -- 10 SQL tools + dedup CTEs
  agent.py            -- orchestration (plan, write, verify, render, judge, retry)
  main.py             -- CLI entry point + pipeline + tracing
  app.py              -- Streamlit UI
tests/
  test_tools.py       -- 27 unit tests, 4 data shapes, no LLM
eval/
  cases.yaml          -- 6 test cases with expected facts
  run_eval.py         -- unit tests (layer 0) + layer 1 (free) + layer 2 (full pipeline)
  report.md           -- evaluation results
starter_pack/         -- read-only source data (SQLite + CSVs + meeting notes)
output/               -- per-run results (briefing.md, evidence.json, scores.json, trace.json)
docs/
  architecture.md     -- system design and data flow
  changelog.md        -- version history
.claude/
  plan.md             -- agreed plan, product definition, technical design
  settings.json       -- hooks config (block-secrets, format-python)
  skills/             -- investigate-data, run-eval
  hooks/              -- block-secrets.py, format-python.py
  agents/             -- code-architect, code-explorer, code-reviewer
  commands/           -- review
data_analysis.md      -- Phase 1 data investigation findings
task.md               -- assignment brief (verbatim)
CLAUDE.md             -- AI coding tool instructions
```

## Dependencies

- anthropic
- streamlit
- pytest (for unit tests)
- pyyaml (for eval)
- Python 3.12+
- uv
