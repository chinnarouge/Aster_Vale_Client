# Changelog

## Phase 1 — Data investigation

- Read data_dictionary.md and tool_catalogue.md to understand the schema and what an analyst does today
- Opened client_intel.db, went through every table: row counts, PK uniqueness, missing data
- Found 11 data quality issues including 3 planted duplicates (K-0010, T-0281, U-00422/U-01991)
- Found correlations: clients with multiple risk signals, missing products vs peers, meeting note contradictions
- Saved findings to data_analysis.md
- User reviewed and corrected: AI had miscounted products for C003, misread a contract date, wrongly flagged a CSAT score. Corrections recorded in data_analysis.md under "Corrections Made During Analysis"

## Phase 2 — Planning and design

### Architecture decision

Evaluated three approaches:

1. **Multi-agent (rejected):** separate LLM agents for each tool. Overkill — the tools are SQL queries, not tasks requiring reasoning. More LLM calls, more latency, more cost, more failure modes, for no accuracy gain.
2. **Full LLM pipeline (rejected):** LLM does everything including math and verification. Breaks the core requirement that numbers come from code, not the model. An LLM cannot reliably compare 752,000 against 751,000.
3. **Hybrid (chosen):** LLM plans and writes, Python calculates and verifies. Fewest LLM calls (3 max), deterministic tools, mechanical verification. The model does what it is good at (choosing what matters, writing prose) and Python does what it is good at (arithmetic, exact matching).

### Framework decision

- **Langchain/langgraph (rejected):** the pipeline is linear — plan, run tools, write, verify, render. No loops, no conditional routing, no state machine, no retries. Adding a framework for a straight-line pipeline adds dependency weight and abstraction layers without solving a problem we have. Three `anthropic.messages.create()` calls are simpler and more debuggable.
- **Claude Agent SDK (rejected):** built for coding and filesystem agents with Bash/Write/Edit tools. Its value-add is irrelevant to SQL analytics + writer, and giving a model `Bash` inside a system whose premise is deterministic tools fights the assignment requirements.
- **Direct anthropic SDK (chosen):** `anthropic.Anthropic()` with `messages.create()`. Minimal, no abstraction, easy to debug in an interview.

### Tech stack decisions

- **Python 3.12** — assignment suggests Python
- **anthropic SDK** — direct LLM calls, no wrapper
- **Plain Python validation** — 10 lines of key checks, no pydantic dependency needed
- **uv** — fast dependency management, clean `pyproject.toml`
- **Streamlit** — thin UI, stretch goal from assignment brief
- **stdlib sqlite3** — read-only analytics against provided client_intel.db, no ORM needed
- **stdlib argparse** — CLI with 4 flags, no framework needed
- **No pandas** — not needed for parameterized SQL queries returning dicts
- **No vector databases** — structured data, not embeddings

### LLM call budget

Three calls normally, up to 5 if the judge triggers a retry:

1. **Planner (LLM call 1):** receives client profile, trigger, rep context, tool descriptions. Returns JSON array of tool names. Free-flow reasoning, no hardcoded per-trigger lists. check_data_quality always included as a guardrail.
2. **Writer (LLM call 2):** receives all tool outputs with row IDs. Returns JSON array of structured claims. Key rule: every number must come from tool output, never calculate or estimate.
3. **Judge (LLM call 3):** scores briefing on completeness, accuracy, actionability, data transparency. If any dimension < 3, triggers one writer retry with feedback (LLM calls 4+5).

### Verifier design

Python, not an LLM. Two checks:
- Do cited row IDs exist in tool outputs?
- Do numeric values match source tool data exactly?

Uses `_extract_numbers()` recursive extraction instead of string matching. Flags failed claims with `[UNVERIFIED]` tag — never silently removes them, because removal hides model failures from the rep.

### Writer design

Outputs structured JSON claims, not markdown prose. Each claim has section, statement, numeric_values, citations, source_tool. An uncited claim is unrepresentable in the schema. The renderer turns verified claims into markdown. This makes verification structural instead of heuristic.

### Tool decisions

- 9 tools from tool_catalogue.md: resolve_client, get_client_profile, get_contract_status, get_usage_trend, get_whitespace, get_support_summary, get_opportunities, get_meeting_notes, check_data_quality
- Added 10th tool: **get_peer_comparison** — compares client's usage, spend, and product adoption against segment peers. Grounds "you should buy X" in "60% of your peers already have it."
- All tools are deterministic SQL, no LLM involvement
- All tools share dedup CTEs for the 3 known duplicate rows
- Trigger determines which subset of tools the planner picks

### Data handling decisions

- as_of date is 2026-11-01, never the wall clock — deterministic output
- Missing data = unknown, not zero (per data dictionary)
- Duplicates handled at query time, starter_pack never modified
- Usage trends: YoY primary (cancels sports seasonality), sequential fallback for short histories
- Failed verification: flag inline, never silently remove

### Model and provider

- Claude Opus 4.6 on Anthropic Foundry
- API key from ANTHROPIC_FOUNDRY_API_KEY env var
- Base URL from ANTHROPIC_FOUNDRY_BASE_URL env var

### Design saved to .claude/plan.md

## Phase 3 — Build

### Step 1: Project structure
- Created Aster_business_analyst/ folder

### Step 2: config.py
- DB_PATH, AS_OF (2026-11-01), MODEL, OUTPUT_DIR, API key from env var
- Updated to Anthropic Foundry: ANTHROPIC_FOUNDRY_API_KEY, ANTHROPIC_FOUNDRY_BASE_URL
- Model set to claude-opus-4-6

### Step 3: tools.py
- All 10 tool functions in one file (~590 lines)
- Three shared dedup CTEs: DEDUP_CONTRACTS, DEDUP_TICKETS, DEDUP_USAGE
- Common _query helper for parameterized SQL
- TOOL_REGISTRY and TOOL_DESCRIPTIONS for planner integration
- Smoke tested each tool against multiple clients

### Step 4: agent.py
- _call_llm: shared LLM client with Foundry base_url support
- plan(): planner LLM call, returns tool names as JSON array
- write_claims(): writer LLM call, returns structured claims
- verify_claims(): Python verifier, checks citations and numeric values
- render_briefing(): groups claims by section, writes markdown
- save_evidence(): writes evidence.json
- judge(): optional LLM quality scoring

### Step 5: main.py
- CLI with argparse: --client, --trigger, --context, --output-dir, --judge
- Pipeline: resolve > profile > plan > run tools > write > verify > render > save

### Bug fixes after code review

- **get_peer_comparison ARR bug**: JOIN multiplied ARR by number of contract lines. C001 showed 3M instead of 752K. Fixed by separating ARR sum and product count into distinct CTEs.
- **datetime.now() in evidence.json**: used wall clock instead of AS_OF, making output non-deterministic. Replaced with AS_OF.
- **Verifier substring matching**: `str(val) in tool_data_str` could match 200 inside 2000. Replaced with _extract_numbers() recursive extraction that compares actual parsed numeric values.
- **Set ordering non-determinism**: `list(set(...))` for ticket row_ids and held_products produced different orderings across runs. Changed to `sorted(set(...))`.
- **Citation prefix handling**: bare citations without a prefix (e.g. "K-0002" instead of "contracts:K-0002") would skip verification. Fixed by using `parts[-1]` to extract the raw ID regardless of prefix.

### Infrastructure setup

- Created .env and .env.example with Foundry key placeholders
- Created .gitignore (blocks .env, __pycache__, output/, *.key, etc.)
- Created .claude/settings.json with hooks:
  - PreToolUse: block-secrets.py scans for API key patterns
  - PostToolUse: format-python.py runs formatting on writes
- Created .claude/skills/run_eval.md with 6 eval scenario commands

### Documentation backfill

- Created docs/architecture.md: system design, data flow, LLM vs Python split, tool catalogue, verification design
- Created docs/changelog.md (this file)
- Rewrote .claude/plan.md to match actual decisions and build
- Updated CLAUDE.md: removed build log, restructured phases (1=investigate, 2=plan, 3=build)

### Planner rewrite

- Removed hardcoded per-trigger tool lists from the planner prompt
- Planner now reasons freely about which tools to run based on tool descriptions, trigger, and client context
- Generalizes to unknown triggers without code changes (interview-ready)
- check_data_quality still enforced in Python as a guardrail

### Claim validation

- Added _validate_claim() in agent.py: checks required keys (section, claim, numeric_values, citations, source_tool), coerces wrong types, drops malformed claims
- Plain Python, no pydantic — one less dependency for 10 lines of validation

### uv setup

- Created pyproject.toml with dependencies: anthropic, streamlit
- Project installable via `uv sync`

### Streamlit UI

- Created Aster_business_analyst/app.py
- Form: client text input, trigger radio buttons, optional context textarea, judge checkbox
- Shows resolved client, tools selected, verification results
- Renders briefing as markdown with expandable evidence, claims, and judge scores
- Run with: `streamlit run Aster_business_analyst/app.py`

### Skills and MCP

- Created .claude/skills/data-analysis.md: Phase 1 investigation procedure
- Created .claude/skills/run-eval.md: 6 eval scenarios with CLI commands
- Added .mcp.json: Playwright MCP for browser-based UI testing

### First end-to-end run (C001 at_risk)

- Planner picked 8 tools with free-flow reasoning — no hardcoded lists
- Writer hit 4096 max_tokens and truncated mid-JSON. Increased to 8192.
- Added truncation recovery: finds last complete JSON object, closes the array
- Added trailing comma cleanup for LLM JSON output (`re.sub(r',\s*([}\]])', ...)`)
- 31 claims generated, 22 passed, 9 flagged. Judge scored 5/5.

### Verifier fix: check all tools, not just source_tool

- Writer combines data from multiple tools in one claim (e.g. headline has numbers from contracts + support + opportunities)
- Verifier was only checking numeric values against `source_tool` — false positives when claims cross tools
- Fixed: check every number against all tool outputs
- Reduced false flags from 9 to 5 on C001 at_risk. Remaining 5 are legitimate (LLM did math it shouldn't have)

### Judge always runs

- Removed --judge flag. Judge LLM call runs on every briefing.
- 3 LLM calls per run: planner, writer, judge

### Output per run

- Each run saves to `output/<client_id>_<trigger>/` instead of overwriting a single `output/` folder
- Contains: briefing.md, evidence.json, scores.json

### Client resolution fix

- "XYZNOTREAL" was fuzzy matching to "Novaterra Bet" and saying "ambiguous match"
- Fixed: fuzzy matches now show "Client not found" with "Did you mean:" suggestions
- Partial matches with multiple hits list all candidates and ask to be more specific
- Only exact_id, exact_name, or single partial match proceeds

### Planner selectivity

- Planner was picking all 9 tools regardless of trigger
- Added guidance: "be selective, not every tool is needed for every trigger"
- Renewal now picks 6 tools (drops whitespace, opportunities, meeting_notes)
- Still generalizes to unknown triggers

### Second end-to-end run (C003 renewal)

- 36 claims, only 2 flagged. Both legitimate: LLM calculated 16-7=9 and invented the number 20.
- Judge scored the briefing. Output saved to output/C003_renewal/

### Streamlit UI sync

- Removed judge checkbox — judge always runs, matching CLI behavior
- Output saves to per-run folders (`output/<client_id>_<trigger>/`) instead of flat `output/`
- Client resolution fix applied: fuzzy = "Client not found" with suggestions, partial multi = list candidates
- Removed `disabled=not client_input` on button (broke Streamlit reactivity), replaced with validation warning
- Scores saved to `scores.json` in run directory

### Playwright UI tests

- Installed Playwright with Chromium for headless browser testing
- 4 tests: page load, empty client warning, invalid client error, full briefing generation
- Screenshot captured at `tests/screenshots/c001_at_risk.png`
- Tests run with `uv run tests\test_streamlit_ui.py`

### requirements.txt

- Added `requirements.txt` with `anthropic>=0.125.0` and `streamlit>=1.28.0`
- Complements `pyproject.toml` for users who prefer pip over uv

### Tracing and observability

- **LLM call traces**: each `_call_llm` logs model, tokens in/out, latency, and cost
  - Format: `[LLM] planner | model=claude-opus-4-6 | tokens_in=1,240 tokens_out=85 | 2.3s | $0.04`
- **Tool traces**: each SQL tool logs name, row count, and execution time
  - Format: `[TOOL] get_contract_status | 4 rows | 0.005s`
- **Pipeline step traces**: each major step (resolve, plan, tools, write, verify, render, judge) logged with wall-clock time and summary
- Trace summary printed at end of every run
- `trace.json` saved to run output directory with all step timings and claim counts

### Computed fields in tools (reduce UNVERIFIED flags)

- Root cause: LLM was calculating values (752K - 541K = 210K, days between dates) that didn't exist in tool output, so verifier correctly flagged them
- Fix: compute these in Python tools so they exist in evidence for the writer to cite
- `get_contract_status`: added `days_until_notice` (integer days from as_of to notice deadline)
- `get_support_summary`: added `ticket_change_abs` (current - previous count), `csat_change` (current - prev CSAT)
- `get_opportunities`: added `current_arr_eur` and `arr_vs_pipeline_gap` (ARR minus pipeline total)
- Tool descriptions updated to reflect new fields

### Verifier explains flags

- Previously: "numeric value 210500 not found in any tool output"
- Now: "numeric value 328000 not in tool output (but appears to be 240000 + 88000 = 328000)"
- `_find_derivation()` checks if a flagged number is a +, -, or % of two numbers in tool data
- Still flags the claim, but the explanation distinguishes correct-math-from-wrong-source from hallucinated numbers

### Writer prompt hardened

- Strengthened "do not calculate" rule with explicit examples
- Added: "Do not build hypothetical scenarios with computed figures"
- Added: "If a tool says ARR is 752000 and an opportunity is 541500, say both numbers — do NOT output 210500 as the gap"

### Writer input summarization

- Writer was slow because it received all raw tool data (every row, every field)
- Added `_summarize_for_writer()`: strips raw rows, keeps computed summaries + row_ids
- `get_usage_trend`: drops full monthly arrays, keeps last 3 months + yoy/utilization stats
- `get_support_summary`: trims open ticket fields to id + priority + subject
- `get_peer_comparison`: drops individual peer rows, keeps segment averages
- `get_contract_status`: replaces product line objects with compact product_ids + fees map
- Evidence file still has full raw data; verifier still checks against full data

### Verifier categorized failure reasons

- Previously: `[UNVERIFIED]` with no explanation in the briefing
- Now: `[UNVERIFIED: LLM-computed value]`, `[UNVERIFIED: no source found]`, `[UNVERIFIED: citation not in evidence]`, `[UNVERIFIED: source tool not run]`
- Verification issues stored as typed objects with `type` and `detail` fields
- `flag_reason` field on each claim summarizes the worst failure category
- Rep can distinguish "probably correct math" from "hallucinated number"

### Eval suite

- Created `eval/cases.yaml`: 6 test cases across 3 clients (C002, C009, C017) and all 4 triggers
- Created `eval/run_eval.py` with three layers:
  - Layer 0 (pytest): 27 unit tests run first, fail fast before spending tokens
  - Layer 1 (free, no LLM): 30 expected facts from cases.yaml vs actual tool outputs. Validates tool correctness.
  - Layer 2 (`--full`, costs money): full pipeline + `ungrounded_check()` scans rendered briefing for numbers not in any tool output
  - `--report` writes `eval/report.md` with pass/fail tables and failure details
- Layer 1 passes: all 30 facts match across 6 cases
- Added pyyaml to dependencies

### Verification and determinism hardening

- Verifier now extracts numbers from claim prose text and flags undeclared numbers not found in tool data
- Verifier flags claims with numeric values but no citations
- Renderer applies `[UNVERIFIED: reason]` flags in all section loops, including fallback sections
- `render_briefing` takes `tool_results` parameter; fallback data gaps section pulls actual issues from `check_data_quality` instead of a placeholder
- `check_data_quality` detects missing meeting notes (15 of 25 clients have none)
- `get_opportunities` ARR defaults to `None` instead of `0` when no active contracts (missing = unknown, not zero)
- Peer utilization check changed from `if r["avg_util"]` to `if r["avg_util"] is not None` (0.0 is valid, not missing)
- Removed client-specific placeholder from app.py, replaced with generic text
- CLI accepts any trigger string (removed `choices=` restriction)
- Triggers moved to `config.TRIGGERS` list, Streamlit reads from config. Added "Other" option for custom triggers
- Added ORDER BY to: resolve_client, contract_lines, products, tickets (3 queries), peers
- `all_nums_list` and `held_ids` sorted for deterministic output
- `llm_call_log` captures per-call model, tokens, latency, cost — included in trace.json
- Updated Playwright test placeholder to match UI change

### Citation verification strengthened

- Verifier now flags all factual claims without citations, not just numeric ones (I3 compliance)
- Data gaps and next steps sections exempted from citation requirement — these are observations about missing data and recommendations, not factual assertions
- Judge LLM call wrapped in try/except for malformed JSON — returns error envelope instead of crashing the pipeline

### Path traversal fix

- Trigger string sanitized to `[A-Za-z0-9_-]` before use in output directory names (main.py and app.py)
- Prevents custom triggers containing `..` or path separators from writing outside `output/`

### Eval cases replaced

- Replaced C001/C003/C004 test cases with C002 (Corvane Media), C009 (Pellucid Odds), C017 (Wexley Athletic FC)
- 3 clients × 2 triggers = 6 cases, covering all 4 trigger types (renewal, upsell, at_risk, meeting_prep)
- Different segments (Broadcaster, Sportsbook, Club) and tiers (Strategic, Growth) for broader coverage
- 30 expected facts, all passing layer 1
- Eval runner updated to support new fact keys: `total_tickets`, `open_opp_amount`, `products_held`

### Reduced false UNVERIFIED flags

- Prose number scanner was parsing dates (`2027-05-31` → `-31.0`) and IDs (`T-0247` → `-247.0`) as numbers, causing false "hallucinated" flags on most claims
- Fixed: strip ISO dates and prefixed IDs from claim text before extracting numbers
- Added `tenure_years` computed field to `get_client_profile` so the LLM can cite tenure instead of calculating it

### LLM-as-judge made functional

- Judge was a passive scorer — it ran, produced scores, but the scores didn't affect anything
- Now closes the loop: if any dimension scores below 3, the writer retries with judge feedback
- `rewrite_claims()` re-runs the writer with the judge's critique appended
- After retry: re-verify, re-render, re-judge. One retry max (3 LLM calls normal, 5 with retry)
- `RETRY_THRESHOLD = 3` in agent.py controls the cutoff

### Trigger definitions

- Added `TRIGGER_DEFINITIONS` dict to config.py with descriptions for all 4 triggers
- Planner now receives trigger definitions alongside tool descriptions
- Custom triggers still work (I7 compliant) — they just don't get a definition

### Unit tests for all 10 tools

- 27 pytest tests in `tests/test_tools.py` covering all 10 tools across 4 data shapes: normal (C002), empty (C004/C007), short history (C004), duplicate rows (C006/C010)
- Edge case coverage: CSAT=None with no tickets, YoY=None for 2-month history, dedup correctness for K-0010/T-0281/U-00422
- Determinism test: same tool called twice produces identical output
- All 27 pass in <0.3s, no LLM calls needed
- Eval runner (`run_eval.py`) runs unit tests as layer 0 before spending LLM tokens — fails fast on tool regressions
- CLAUDE.md updated: "After modifying tools.py, run unit tests before anything else"

### Prompts extracted to prompts.py

- All LLM prompts moved from agent.py to `Aster_business_analyst/prompts.py`
- `planner_system(as_of, tool_descriptions)` — function since it needs runtime values
- `WRITER_SYSTEM` — constant string with claim schema and rules
- `JUDGE_SYSTEM` — constant string with 4 scoring dimensions
- agent.py imports from prompts.py, no inline prompt definitions remain
