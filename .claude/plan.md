# Aster Vale client intelligence agent

## Context

`FDE_Takehome_Candidate_Brief.docx` asks for a working prototype of a client intelligence agent for a fictional sports-data company. A sales rep facing a renewal, a meeting, an upsell or a churn risk currently asks an analyst for client intelligence; the analyst pulls from several systems by hand and writes it up, which takes weeks, so briefings often arrive after the meeting. We build the middle box: client plus trigger in, a short cited briefing out, in one action.

Budget is 4 to 5 hours. The brief is transcribed verbatim at `task.md`. Assessment leads on whether the numbers are right and grounded, whether it generalises to clients we never looked at, and whether the briefing would actually help a rep. Clear reasoning and honest limitations count for more than polish.

### Work phases

1. **Data investigation** -- read data dictionary and tool catalogue, go through every table in client_intel.db, find quality issues and duplicates. Findings saved to `data_analysis.md` with corrections. No code written until findings are reviewed.
2. **Planning** -- architecture, framework, tech stack, LLM call budget, verification approach. All decisions recorded in this file (plan.md). No code written until plan is agreed.
3. **Building** -- step by step, each piece proposed before built, invariant checks after each milestone.

---

## Part 1. Product definition

Nearly all of this is fixed by the brief rather than chosen by us. Recorded so the build has one reference, and so a misreading is visible and correctable.

### Who it is for

| Audience | Needs from it |
| --- | --- |
| **Sales rep** (primary) | Short and specific, read in minutes before a conversation. Needs to know which claims are solid and what to ask the client where the data cannot answer. Will not read SQL. |
| **Sales business analyst** (whose work is automated) | The tool outputs next to the prose, so a briefing can be checked and corrected rather than trusted blindly. Becomes reviewer, not producer. |
| **Assessor / interviewer** | Will run a client and trigger we never tried, and change something with us live. Needs generality and code simple enough to modify in an interview. |

Not for: executives wanting a portfolio roll-up, or the client themselves.

### Problem it solves

1. **Latency.** The analysis takes weeks; short-notice meetings happen before it is ready.
2. **Scarcity.** Analyst time is rationed, so only the biggest accounts get a real briefing.
3. **Inconsistency.** Different analysts, or different weeks, ask different questions, so briefings are not comparable.
4. **Trust.** A briefing that quietly fills a gap with a plausible number is worse than none, because the rep repeats it to the client.

### What the product does

Takes a client (ID or name) and a trigger, validates the client exists, gathers evidence, analyses it, and writes a short briefing where every claim is grounded and cited, plus the evidence used.

```
uv run Aster_business_analyst/main.py --client "<id or name>" \
          --trigger <renewal|meeting_prep|upsell|at_risk> \
          [--context "<anything the data cannot know>"]
```

Writes to `output/<client_id>_<trigger>/`: `briefing.md`, `evidence.json`, `scores.json`, `trace.json`.

Streamlit UI: `uv run streamlit run Aster_business_analyst/app.py`

### Client resolution

The client field is free text accepting an ID or a name. Resolution is SQL, never a model, so it cannot hallucinate a client.

`resolve_client(raw)` queries `clients` in stages and stops at the first stage that returns rows:

1. exact `client_id`, case-insensitive
2. exact `client_name`, case-insensitive and trimmed
3. substring match on `client_name`, case-insensitive
4. fuzzy match via SequenceMatcher (threshold 0.4)

Four outcomes:

| Outcome | Condition | What happens |
| --- | --- | --- |
| **Resolved (exact)** | exact id or exact name match | proceeds |
| **Resolved (partial)** | single substring match | proceeds |
| **Ambiguous** | multiple substring matches | exits, lists candidates |
| **Not found** | only fuzzy matches or none | exits, shows "Did you mean:" suggestions |

The gate sits before everything expensive. No model call, no analysis, no tokens spent on a client that does not resolve.

### Capabilities, mapped to the must-haves

| # | Capability | Must-have |
| --- | --- | --- |
| C1 | Client + trigger in, briefing + evidence file out, one command | 1 |
| C2 | Ten deterministic analyses: client profile, contract and renewal status, usage trends, white-space, support summary, opportunities, meeting notes, cross-source data quality, peer comparison | 2 |
| C3 | A planning step choosing analyses and emphasis per trigger, free-flow reasoning from tool descriptions, never per-client code | 3 |
| C4 | Writer cites every figure and claim; verifier checks numbers against evidence and claims for citations; flags with categorized reasons | 4 |
| C5 | Duplicates, missing months, short histories and cross-source conflicts detected and shown, never filled | 5 |
| C6 | Repeatable evaluation over 3 clients and 2 triggers each, with automated ungrounded-number check and report | 6 |

### The briefing

Every figure carries analysis, and the analysis is cited too. There is no un-cited opinion section.

Section order and emphasis come from the trigger; the set is fixed so a rep always knows where to look.

1. **Headline**, the things that change what the rep does
2. **Account snapshot**, who the client is
3. **Contract position**, dates, notice deadline, ARR
4. **Usage trends**, per product, direction and magnitude
5. **Growth opportunities**, products not held, with the evidence for fit
6. **Support health**, volume, severity, satisfaction
7. **Relationship context**, meeting note themes and open commitments
8. **Risks**, what could go wrong
9. **Next steps**, concrete actions for the rep
10. **Data gaps and confidence**, required, never empty

### Trigger definitions

The brief names four triggers but does not define them. The planner reasons freely about which tools to run based on tool descriptions, trigger, and client context. `check_data_quality` is always forced in Python as a guardrail. No hardcoded per-trigger tool lists.

| Trigger | The rep's situation | Leads with | Plays down |
| --- | --- | --- | --- |
| `renewal` | Contract end approaching, needs a position | Contract clock, notice deadline, usage versus entitlement | White-space |
| `meeting_prep` | Any meeting, possibly short notice | Broad coverage, all relevant tools | Nothing |
| `upsell` | Growth conversation | White-space with fit evidence, peer comparison | Support noise, unless it blocks a sale |
| `at_risk` | Churn signals | Usage decline, support severity and satisfaction, peer comparison | Growth options |

### Scope boundary

In: four triggers, 25 clients, starter-pack tables only, Markdown output, CLI, Streamlit UI, evaluation suite.

Out: deployment, auth, multi-tenancy, CRM write-back, live data, PDF, portfolio roll-up, anything hardcoded per client.

---

## Part 2. Technical design

### Architecture decision

**Hybrid approach: LLM plans and writes, Python calculates and verifies.** No langchain, no langgraph, no multi-agent framework. The anthropic SDK handles the LLM calls directly.

Why not langchain/langgraph: the chain is linear. Plan, run tools, write, verify, render. No loops, no retries, no conditional routing, no state machine. Adding a framework for a linear pipeline adds dependency weight and abstraction layers without solving a problem we have. Three `anthropic.messages.create()` calls are simpler and more debuggable.

### Key technical decisions

| # | Decision | Choice and reason |
| --- | --- | --- |
| T1 | Orchestration | **Direct anthropic SDK calls.** Three calls normally: planner, writer, judge. Up to 5 if the judge triggers a retry (writer retry + re-judge). Each is a single `messages.create()`. No Tool Runner, no agent loop. All prompts in `prompts.py`. |
| T2 | Verifier failure policy | **Flag with categorized reason, never silently remove.** Four failure categories: `LLM-computed value`, `no source found`, `citation not in evidence`, `no citations`. The judge closes the loop: if any dimension scores below 3, the writer retries with judge feedback, then re-verifies and re-judges. One retry max. |
| T3 | Stack | Python 3.12 + uv, stdlib `sqlite3`, stdlib `argparse`, Claude Opus 4.6 on Anthropic Foundry, Streamlit for UI. Plain Python validation (no pydantic — 10 lines of validation doesn't justify a dependency). |
| T4 | Planner approach | **Free-flow reasoning.** No hardcoded per-trigger tool lists. Planner sees tool descriptions and reasons about which are relevant. Generalizes to unknown triggers without code changes (interview-ready). `check_data_quality` always forced in Python. |
| T5 | Writer input | **Summarized tool data.** Raw tool outputs are trimmed before sending to the writer — drop full monthly arrays, keep computed stats + row_ids. Cuts input tokens ~80%, full data stays in evidence.json. |
| T6 | Stretch goals | Judge always runs (3 LLM calls normally, 5 with retry). Streamlit UI. Evaluation suite with 3 layers (unit tests, facts, full pipeline). Tracing with per-step timing, LLM token counts and cost. 27 unit tests across 4 data shapes. |

### Data flow

```
CLI or Streamlit: client + trigger + optional context
    |
    v
1. RESOLVE CLIENT                      SQL only, no model
   exact id > exact name > partial > fuzzy
   fuzzy or not found = exit, no tokens spent
    |
    v
2. GET CLIENT PROFILE                  SQL, returns segment/tier/tenure
    |
    v
3. PLANNER                             LLM call 1
   sees: client profile, trigger, rep context, tool descriptions
   free-flow reasoning, returns JSON array of tool names
   guardrail: check_data_quality always included in Python
    |
    v
4. RUN TOOLS                           deterministic SQL, sequential
   each tool returns {tool, data, row_ids}
   dedup CTEs handle known duplicates
   computed fields: days_until_notice, tenure_years, arr_vs_pipeline_gap, ticket_change_abs, csat_change
   traced: name, row count, execution time per tool
    |
    v
5. SUMMARIZE                           pure Python
   strips raw rows, keeps computed stats + row_ids
   cuts writer input tokens ~80%
    |
    v
6. WRITER                              LLM call 2
   sees: trigger, client profile, summarized tool outputs
   returns: JSON array of structured claims
   rule: NEVER calculate, only quote verbatim numbers from tool output
   truncation recovery: find last complete JSON object, close array
    |
    v
7. VALIDATE + VERIFY                   pure Python
   validate: required keys present (section, claim, numeric_values, citations, source_tool)
   verify: cited row IDs exist? numeric values match tool data?
   categorize failures: llm_computed | hallucinated | missing_citation
   _find_derivation() explains flagged numbers as arithmetic of tool values
    |
    v
8. RENDER                              pure Python
   groups claims by section, appends citations inline
   flagged claims: [UNVERIFIED: LLM-computed value] or [UNVERIFIED: no source found]
    |
    v
9. JUDGE                               LLM call 3 (always runs)
   scores: completeness, accuracy, actionability, data_transparency (1-5)
   if any dimension < 3:
       -> RETRY WRITER with judge feedback (LLM call 4)
       -> re-verify, re-render
       -> RE-JUDGE (LLM call 5)
   one retry max
    |
    v
10. SAVE
    output/<client_id>_<trigger>/
      briefing.md, evidence.json, scores.json, trace.json
```

### Where the model is, and is not

| Stage | Model? | Why |
| --- | --- | --- |
| Resolve client | No | SQL only. Cannot hallucinate a client. |
| Client profile | No | Direct SQL query on clients table. |
| Planner | **Yes** | Judgement call: which tools matter for this trigger and context. |
| All 10 tools | No | Deterministic SQL. Numbers come from the database. |
| Summarizer | No | Python dict trimming for writer efficiency. |
| Writer | **Yes** | Prose and emphasis. Forbidden from introducing numbers not in tool output. |
| Validator | No | Required key checks, type coercion. |
| Verifier | No | Exact numeric matching and citation resolution. Categorized failure reasons. |
| Renderer | No | String formatting: claims to markdown with flag tags. |
| Judge | **Yes** | Quality scoring on 4 dimensions. Triggers one writer retry if any dimension < 3. |

### Writer and verifier design (must-have 4)

**The writer emits structured claims, not prose.** Citation becomes structural rather than detected.

Each claim carries its text, numeric values as actual numbers, citations as source row IDs, and the tool that provided the data. An uncited claim is unrepresentable in the schema.

```json
{
  "section": "contract_position",
  "claim": "Contract K-0002 expires 2027-01-31, 91 days from now.",
  "numeric_values": [91],
  "citations": ["contracts:K-0002"],
  "source_tool": "get_contract_status"
}
```

**The verifier is Python, not an LLM.** Three checks:

1. Every cited row ID resolves to an actual ID in the tool outputs.
2. Every numeric value in a claim matches a value in any tool's data (not just source_tool, since claims combine data from multiple tools).
3. Source tool was actually run.

The numeric check uses `_extract_numbers()`, which recursively walks all nested dicts/lists in tool output and builds a set of all numeric values.

**Verification failure categories:**

| Category | Meaning | Briefing tag |
| --- | --- | --- |
| `llm_computed` | Number is arithmetic of two tool values (e.g. 752K - 541K = 210K) | `[UNVERIFIED: LLM-computed value]` |
| `hallucinated` | Number doesn't exist in any tool output and can't be explained as simple math | `[UNVERIFIED: no source found]` |
| `missing_citation` | Cited row ID doesn't exist in tool outputs | `[UNVERIFIED: citation not in evidence]` |
| `missing_source` | Claims a tool that wasn't run | `[UNVERIFIED: source tool not run]` |

**Why flag instead of repair or remove:**
- **Remove** hides model failures. The rep sees a clean briefing, never knowing claims were dropped. The assignment says gaps must be "shown, not hidden."
- **Repair** adds a 4th LLM call, might still fail, and asks an LLM to check another LLM's math — which is the problem we're solving.
- **Flag with reason** keeps everything visible. The rep sees the category and decides: "LLM-computed" is probably fine, "no source found" is dangerous.

### The 10 tools

All in one file (`tools.py`). They share three dedup CTEs and a common `_query` helper.

| # | Tool | What it returns | Computed fields |
| --- | --- | --- | --- |
| 1 | `resolve_client` | client_id, name, confidence level | — |
| 2 | `get_client_profile` | segment, tier, tenure, country, account owner | `tenure_years` |
| 3 | `get_contract_status` | ARR, dates, notice deadline, products held | `days_until_notice`, `arr_change_pct` |
| 4 | `get_usage_trend` | per-product monthly usage, YoY and sequential change | `yoy_change_pct`, `recent_vs_prior_pct`, `avg_utilization_pct` |
| 5 | `get_whitespace` | products not held, peer adoption rates, segment fit | — |
| 6 | `get_support_summary` | ticket counts by priority/category, CSAT | `ticket_change_abs`, `csat_change`, `change_pct` |
| 7 | `get_opportunities` | open/won/lost pipeline, values, products | `arr_vs_pipeline_gap`, `current_arr_eur` |
| 8 | `get_meeting_notes` | note content with IDs and dates | — |
| 9 | `check_data_quality` | duplicates, missing months, short history, gaps | — |
| 10 | `get_peer_comparison` | client vs segment peers on ARR, usage, product adoption | `segment_avg_arr`, `arr_rank` |

Computed fields exist so the writer can cite them instead of calculating. This eliminates the most common source of UNVERIFIED flags (the LLM doing math the tools should have done).

### Deduplication strategy

Three shared CTE strings:
- `DEDUP_CONTRACTS`: DISTINCT on contract_id (handles K-0010)
- `DEDUP_TICKETS`: DISTINCT on ticket_id (handles T-0281)
- `DEDUP_USAGE`: GROUP BY client_id + product_id + month, MIN(usage_id) (handles U-00422/U-01991)

The starter_pack data is never modified. All cleaning happens at query time.

### Analysis decisions

**Usage trend window: year-on-year primary, sequential fallback.** Sports data follows competition calendars; a 3-month-vs-prior-3 comparison would report swings caused by an off-season.

**Missing data = unknown, not zero.** Per the data dictionary, a missing value means we do not know. The briefing says "data not available" rather than filling the gap.

---

## Build steps

| # | Step | Status |
| --- | --- | --- |
| 1 | Project structure (`Aster_business_analyst/`) | done |
| 2 | `config.py` — DB path, AS_OF, model, API key from env var | done |
| 3 | `tools.py` — 10 tools, dedup CTEs, query helper | done |
| 4 | `agent.py` — planner, writer, verifier, renderer, judge | done |
| 5 | `main.py` — CLI + pipeline orchestration | done |
| 6 | Bug fixes — ARR JOIN, datetime.now(), verifier substring, set ordering, citation prefix | done |
| 7 | Infrastructure — .env, .gitignore, hooks, skills | done |
| 8 | Documentation — CLAUDE.md, plan.md, architecture.md, changelog.md | done |
| 9 | uv + pyproject.toml — dependency management | done |
| 10 | Streamlit UI — form, briefing display, evidence/claims/scores expanders | done |
| 11 | End-to-end tests — C001 at_risk, C003 renewal with live LLM | done |
| 12 | Free-flow planner — removed hardcoded tool lists, selectivity guidance | done |
| 13 | Claim validation — required keys check, type coercion, plain Python | done |
| 14 | Verifier fixes — check all tools not just source_tool, false positive reduction | done |
| 15 | Judge always runs — removed --judge flag, 3 LLM calls per run | done |
| 16 | Output per run — `output/<client_id>_<trigger>/` subfolders | done |
| 17 | Client resolution fix — fuzzy = not found with suggestions | done |
| 18 | Streamlit sync — judge always runs, per-run output, client resolution | done |
| 19 | Playwright UI tests — 4 tests, headless Chromium | done |
| 20 | Tracing — LLM calls (tokens, cost, latency), tool timings, pipeline steps, trace.json | done |
| 21 | Computed fields — days_until_notice, arr_vs_pipeline_gap, ticket_change_abs, csat_change | done |
| 22 | Verifier explains flags — categorized failures, _find_derivation() | done |
| 23 | Writer prompt hardened — explicit "do not calculate" with examples | done |
| 24 | Writer input summarization — _summarize_for_writer(), ~80% token reduction | done |
| 25 | Eval suite — eval/cases.yaml, eval/run_eval.py, layer 1 (free) + layer 2 (full) | done |
| 26 | Unit tests — 27 pytest tests, 4 data shapes, layer 0 in eval runner | done |
| 27 | CLAUDE.md rewrite — invariants table, architecture, data flow, test loop | done |
| 28 | requirements.txt | done |
| 29 | README.md — how to run, design notes, eval results, limitations | done |

---

## Coding tool setup

The brief asks how the coding tools were set up and steered.

### Instruction files

- `CLAUDE.md` at project root: invariants table, architecture overview, data flow, test loop, rules
- `data_analysis.md`: Phase 1 findings that carry forward — data quality issues, corrections, correlations

### Hooks

- `block-secrets` PreToolUse hook: scans files for API key patterns, blocks if found
- `format-python` PostToolUse hook: runs formatting on Python writes

### MCP servers

- **Playwright MCP** (`.mcp.json`): browser automation for testing the Streamlit UI via `npx @playwright/mcp@latest`

### Skills

- `/review`: checks the 7 assignment invariants (I1-I7) then delegates generic bug hunting to code-reviewer subagent
- `/run_eval`: lists the 6 eval scenarios with exact CLI commands

### What worked

- Phased approach (investigate -> plan -> build) prevented building before understanding the data
- User corrections during Phase 1 caught errors the AI made (miscounted products, misread dates, wrong CSAT flags)
- Code review against the 7 invariants found 5 bugs before any end-to-end testing
- Free-flow planner generalizes to unknown triggers without code changes
- Computed fields in tools eliminated most UNVERIFIED flags by giving the writer numbers to cite instead of calculate

### What had to be corrected

- AI built code without user steering in one session — user kept the code but walked through every function
- Verifier used substring matching (`str(val) in str(data)`) which could match 200 inside 2000
- Used `datetime.now()` instead of AS_OF in evidence.json
- Used `list(set(...))` producing non-deterministic ordering
- get_peer_comparison had a JOIN bug multiplying ARR by contract line count
- Planner selected all tools regardless of trigger until selectivity guidance was added
- Writer hit max_tokens truncation at 4096, increased to 8192 with truncation recovery
- Verifier only checked source_tool numbers, missed cross-tool claims — fixed to check all tools
- Fuzzy client resolution matched garbage input to real clients — fixed to show "not found"
