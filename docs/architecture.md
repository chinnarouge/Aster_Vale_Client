# Architecture

## Overview

The agent takes a client (name or ID), a trigger (renewal, upsell, meeting_prep, at_risk, or any new trigger), and optional rep context. It resolves the client, runs deterministic SQL tools, feeds tool outputs to an LLM writer, verifies every claim in Python, and renders a cited Markdown briefing plus a JSON evidence file.

Two front doors: CLI (`main.py`) and Streamlit UI (`app.py`). Both run the same pipeline. Neither holds logic of its own.

Three LLM calls max. Everything else is Python.

## Data flow

```
CLI input (client, trigger, context)   or   Streamlit UI form
    |
    v
1. resolve_client  ---- SQL only, no LLM
    |                   exact ID > exact name > substring
    |                   ambiguous or missing = exit, no tokens spent
    v
2. get_client_profile  ---- SQL, returns segment/tier/tenure
    |
    v
3. planner (LLM call 1)
    |   receives: client profile, trigger, rep context, tool descriptions
    |   reasons freely about which tools are relevant — no hardcoded per-trigger lists
    |   returns: JSON array of tool names to run
    |   guardrail: check_data_quality always included (enforced in Python)
    v
4. run tools  ---- all deterministic SQL, no LLM
    |   each tool returns {tool, data, row_ids}
    |   dedup CTEs handle known duplicates (K-0010, T-0281, U-00422/U-01991)
    v
5. summarize for writer  ---- pure Python, no LLM
    |   strips raw rows, keeps computed stats + row_ids
    |   ~80% token reduction vs sending full tool data
    v
6. writer (LLM call 2)
    |   receives: trigger, client profile, summarized tool outputs
    |   returns: JSON array of structured claims
    |   each claim: section, statement, numeric_values, citations, source_tool
    |   rule: every number must come from tool output, no calculating
    v
7. verifier  ---- pure Python, NOT an LLM call
    |   checks: do cited row IDs exist in tool outputs?
    |   checks: do numeric values match full tool data (not summaries)?
    |   uses recursive number extraction, not string matching
    |   categorizes failures: llm_computed, hallucinated, missing_citation
    |   result: each claim marked "passed" or "flagged" with reason
    v
8. renderer  ---- pure Python, no LLM
    |   groups claims by section, ordered by SECTION_ORDER
    |   flagged claims get [UNVERIFIED: reason] tag, not silently removed
    |   outputs: briefing.md
    v
9. save evidence  ---- writes evidence.json with all tool data + claims
    |
    v
10. judge (LLM call 3)
    |   scores: completeness, accuracy, actionability, data_transparency (1-5)
    |   saves scores.json
    v
11. trace  ---- saves trace.json with step timings, token counts, costs
```

## Where the LLM is used vs not

| Step | LLM? | Why |
|------|-------|-----|
| Client resolution | No | SQL lookup. Cannot hallucinate a client. |
| Client profile | No | Direct SQL query on clients table. |
| Planning (which tools to run) | Yes | Judgement call based on trigger and rep context. Config defaults as guardrails. |
| All 10 tools | No | Deterministic SQL. Numbers come from the database, not the model. |
| Writing claims | Yes | Prose and emphasis. Forbidden from introducing numbers not in tool output. |
| Verification | No | Exact numeric matching and citation resolution. Python because LLMs cannot reliably compare 752,000 vs 751,000. |
| Rendering | No | Template-based markdown generation from verified claims. |
| Judging | Yes | Subjective quality scoring. Runs every time. |

## The 10 tools

All in tools.py. Each takes a client_id, runs SQL against client_intel.db, returns a dict with tool name, data, and row_ids.

1. **resolve_client** - finds client by ID, exact name, or substring match
2. **get_client_profile** - account metadata: segment, tier, tenure, country
3. **get_contract_status** - active contracts, ARR, renewal dates, notice deadlines, days_until_notice
4. **get_usage_trend** - monthly consumption per product, YoY and sequential change, utilization
5. **get_whitespace** - products client does not hold, with peer adoption rates
6. **get_support_summary** - ticket counts, severity, CSAT, ticket_change_abs, csat_change
7. **get_opportunities** - CRM pipeline: open, won, lost opportunities, current_arr_eur, arr_vs_pipeline_gap
8. **get_meeting_notes** - extracts from meeting note files for the client
9. **check_data_quality** - cross-source conflicts, duplicates, missing data
10. **get_peer_comparison** - client vs segment peers on usage, spend, product adoption

Shared infrastructure: three dedup CTEs (DEDUP_CONTRACTS, DEDUP_TICKETS, DEDUP_USAGE) handle known duplicate rows. A common `_query` helper runs parameterized SQL and returns dicts.

## Structured claims

The writer outputs JSON, not markdown. Each claim is:

```json
{
  "section": "contract_position",
  "claim": "Contract K-0002 expires 2027-02-28, 120 days from now.",
  "numeric_values": [120],
  "citations": ["contracts:K-0002"],
  "source_tool": "get_contract_status"
}
```

This makes verification structural. An uncited claim is unrepresentable in the schema. The verifier does set arithmetic, not judgement.

## Verification vs judging

These are different things solving different problems:

- **Verifier** (Python, mandatory): checks if the facts are correct. Do the cited row IDs exist? Do the numbers match the source data exactly? Categorizes failures: `llm_computed` (correct math but LLM did it), `hallucinated` (number not in any tool data), `missing_citation` (row ID doesn't exist), `missing_source` (source tool not run). Binary pass/fail per claim, with a reason on failure.
- **Judge** (LLM, mandatory): checks if the briefing is useful. Scores completeness, accuracy, actionability, data transparency on a 1-5 scale. Subjective quality assessment.

Both run every time. The verifier catches wrong numbers, the judge catches weak analysis.

## Writer input summarization

The writer receives summarized tool data, not raw rows. This reduces input tokens by ~80% without losing information the writer needs:

- `get_usage_trend`: drops full monthly arrays, keeps last 3 months + yoy/utilization stats
- `get_support_summary`: trims open ticket fields to id + priority + subject
- `get_peer_comparison`: drops individual peer rows, keeps segment averages
- `get_contract_status`: replaces product line objects with compact product_ids + fees map

The verifier still checks against full tool data, not summaries.

## Computed fields

Tools compute derived values so the writer can cite them instead of calculating:

- `days_until_notice`: integer days from as_of to notice deadline (get_contract_status)
- `ticket_change_abs`: current minus previous period ticket count (get_support_summary)
- `csat_change`: current minus previous period CSAT (get_support_summary)
- `current_arr_eur` and `arr_vs_pipeline_gap`: ARR minus pipeline total (get_opportunities)

This eliminates most UNVERIFIED flags that were caused by the LLM doing correct arithmetic that wasn't in the evidence.

## Tracing

Every run produces a trace.json with:

- LLM calls: model, tokens in/out, latency, cost per call
- Tool runs: name, row count, execution time
- Pipeline steps: wall-clock time for resolve, plan, tools, write, verify, render, judge
- Totals: elapsed time, LLM call count, claim pass/flag counts

## Deduplication strategy

The SQLite database has known duplicates planted intentionally:
- Contract K-0010: duplicate row
- Ticket T-0281: duplicate row  
- Usage U-00422/U-01991: same observation, different PKs

Every SQL query deduplicates at query time using DISTINCT on business keys. The starter_pack data is never modified.

## Claim validation

Before verification, every claim from the LLM is validated in Python. Required keys: section, claim, numeric_values, citations, source_tool. Malformed claims (missing keys, empty text, wrong types) are dropped before they reach the verifier. Plain Python, no pydantic — 10 lines handles it.

## Front doors

Two interfaces, same pipeline:

- **CLI** (`main.py`): `python Aster_business_analyst/main.py --client "C001" --trigger renewal`
- **Streamlit** (`app.py`): `streamlit run Aster_business_analyst/app.py`

Both call the same functions in the same order. Neither holds business logic. The UI adds a form and expandable evidence/claims/scores sections, nothing else.

## Key design decisions

1. **Hybrid architecture over multi-agent**: LLM plans + writes, Python calculates + verifies. Simpler than a multi-agent framework, same accuracy, fewer failure modes.
2. **No langchain/langgraph**: The chain is linear (plan > run tools > write > verify > render). No loops, no retries, no routing. The anthropic SDK handles the LLM calls directly.
3. **Free-flow planner**: The planner sees tool descriptions and reasons about which tools matter for the trigger. No hardcoded per-trigger tool lists. Generalizes to unknown triggers without code changes.
4. **Structured claims over prose**: Writer outputs JSON claims, not markdown. Makes verification mechanical instead of heuristic.
5. **Flag over remove**: Failed verification marks claims [UNVERIFIED] instead of silently dropping them. Removal hides model failures from the rep.
6. **as_of date, not wall clock**: Every date calculation uses 2026-11-01, never datetime.now(). Makes output deterministic.
7. **Missing = unknown, not zero**: Per the data dictionary, a missing value means we do not know, not that the answer is zero.
8. **Computed fields in tools**: Tools pre-compute derived values (days_until_notice, arr_vs_pipeline_gap, etc.) so the writer cites them instead of calculating. Reduces UNVERIFIED flags without weakening the verifier.
9. **Writer sees summaries, verifier sees full data**: Summarization reduces writer input tokens by ~80%. The verifier always checks against the original tool output.

## Evaluation

6 cases across 3 clients and 2 triggers each. Two layers:

- **Layer 1 (free)**: 33 expected facts from eval/cases.yaml checked against tool outputs. No LLM calls. Catches tool regressions.
- **Layer 2 (costs money)**: Full pipeline per case. Ungrounded number check scans rendered briefing for numbers absent from all tool data. Report written to eval/report.md.

Run with `uv run eval/run_eval.py --full --report`.
