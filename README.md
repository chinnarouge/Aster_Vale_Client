# Aster Vale Client Intelligence Agent

A client intelligence agent for Aster Vale Sports Data. Given a client and a trigger, it gathers evidence from a SQLite database, analyses it, and produces a cited briefing for a sales rep.

## Quick start

```bash
# Install dependencies
uv sync

# Set your API key (Foundry)
export ANTHROPIC_FOUNDRY_API_KEY="your-key-here"
export ANTHROPIC_FOUNDRY_BASE_URL="your-base-url-here"

# Or use the standard Anthropic API (no base URL needed)
export ANTHROPIC_FOUNDRY_API_KEY="sk-ant-your-key-here"

# Run a briefing
uv run Aster_business_analyst/main.py --client "Halden Bet" --trigger at_risk --context "Usage feels down"

# Run the Streamlit UI
uv run streamlit run Aster_business_analyst/app.py

# Run evaluation (layer 1 is free, layer 2 needs LLM)
uv run eval/run_eval.py                # tool checks only, free
uv run eval/run_eval.py --full --report # full pipeline + report
```

Output goes to `output/<client_id>_<trigger>/` with `briefing.md`, `evidence.json`, `scores.json`, and `trace.json`.

## How it works

The pipeline has 7 steps. Three use the LLM, four are pure Python.

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
  |
  v
briefing.md + evidence.json + scores.json + trace.json
```

### Where the model is and is not

The model plans (which tools to run), writes (prose with citations), and judges (quality scoring). It never does math, runs queries, or verifies its own output.

The tools are SQL queries. The verifier is Python set lookups. The renderer is string formatting. Numbers come from code, not the model.

### The 10 tools

All in `tools.py`. Each takes a client_id, runs parameterized SQL against the starter pack database, and returns structured data with row IDs for citation.

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
- Does every number match a value in the tool data?

When verification fails, the claim is flagged with a reason:

- `[UNVERIFIED: LLM-computed value]` -- the number is correct arithmetic from tool data, but the model calculated it instead of a tool
- `[UNVERIFIED: no source found]` -- the number doesn't appear anywhere in tool data
- `[UNVERIFIED: citation not in evidence]` -- the row ID doesn't exist

I chose to flag rather than repair or remove. Removing hides failures from the rep. Repairing adds another LLM call that might still fail. Flagging with a reason lets the rep decide whether to trust the claim.

### Data handling

The starter pack has intentional quality issues. Three known duplicates (K-0010, T-0281, U-00422/U-01991) are handled with dedup CTEs at query time. The source data is never modified. Missing data is reported as unknown, never filled with zero or a mean.

## Evaluation

6 cases: C001 (at_risk, renewal), C003 (upsell, meeting_prep), C004 (at_risk, renewal).

Two layers:

- **Layer 1 (free):** 33 expected facts from `eval/cases.yaml` checked against actual tool outputs. Catches tool bugs without spending tokens.
- **Layer 2 (costs money):** Full pipeline for each case. Automated check scans the rendered briefing for numbers not in any tool output. Results written to `eval/report.md`.

Run `uv run eval/run_eval.py --full --report` to reproduce.

## Known limitations

- The writer occasionally calculates numbers instead of quoting tool output, despite the prompt forbidding it. These get flagged by the verifier.
- Tools run sequentially. Parallelism would save little since SQL queries take milliseconds; the LLM calls are the bottleneck.
- No repair loop. A flagged claim stays flagged. Adding repair is the obvious next step but adds cost and complexity.
- The planner sometimes selects more tools than needed. Selectivity guidance helps but isn't perfect.
- Meeting notes extraction is whatever the LLM decides to surface. No structured extraction step.

## What I would do next

- **Repair loop:** One retry for flagged claims, scoped to the specific number, with a budget cap.
- **Structured note extraction:** A dedicated LLM call for meeting notes that extracts quotes and verifies them as literal substrings of the source text.
- **Parallel tool execution:** asyncio for the SQL tools, though the real win would be batching the 3 LLM calls where possible.
- **Confidence scores per claim:** Based on data coverage (12 months of data = high, 2 months = low).
- **Portfolio view:** Rank all 25 clients by renewal risk or growth potential.

## How I built it

Worked with Claude Code across three phases.

**Phase 1 (investigation):** Had Claude read the data dictionary and go through every table. It found the planted duplicates and data quality issues but also made mistakes -- miscounted products for C003, misread a contract date, wrongly flagged a CSAT score. I corrected these and recorded them in `data_analysis.md`. The corrections prevented wrong assumptions from carrying into the code.

**Phase 2 (planning):** Decided the architecture (hybrid LLM + Python), framework (none, direct SDK), tech stack, LLM call budget (3 max), and verification approach (flag, not repair or remove). Wrote it up in `.claude/plan.md` before writing any code.

**Phase 3 (building):** Step by step, proposing each piece before building it. Claude Code's `/review` skill checked the 7 assignment invariants after each milestone. The PostToolUse hook ran formatting on every write. The block-secrets hook prevented API keys from leaking into tool calls.

**What worked:** The phased approach prevented building before understanding the data. User corrections during Phase 1 caught errors that would have produced wrong briefings. The invariant checklist caught 5 bugs before end-to-end testing.

**What I had to correct:** Verifier used substring matching that could match 200 inside 2000. Used `datetime.now()` instead of the fixed as_of date. A JOIN bug in peer comparison multiplied ARR by contract line count. The planner selected all tools regardless of trigger until I added selectivity guidance. Each fix is recorded in the changelog.

## File structure

```
Aster_business_analyst/
  config.py           -- AS_OF, MODEL, DB_PATH, API key, triggers
  tools.py            -- 10 SQL tools + dedup CTEs
  agent.py            -- planner, writer, verifier, renderer, judge
  main.py             -- CLI entry point + tracing
  app.py              -- Streamlit UI
eval/
  cases.yaml          -- 6 test cases with expected facts
  run_eval.py         -- layer 1 (free) + layer 2 (full pipeline)
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
- pyyaml (for eval)
- Python 3.12+
- uv
