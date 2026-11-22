# Building a client intelligence agent

> Source: `FDE_Takehome_Candidate_Brief.docx` (verbatim transcription, reformatted as Markdown).

## The business situation

Aster Vale Sports Data is a fictional company that sells sports data products to business clients: live data feeds, odds, streaming, visualisation widgets, fan analytics and integrity monitoring. Its clients include sportsbooks, broadcasters, leagues, clubs and fantasy apps.

Before a renewal, an important meeting or a growth conversation, a sales rep asks a sales business analyst for client intelligence: how consumption is trending, which products the client could add, where the contract and renewal stand, what support issues they have had, and what was said in recent meetings. The analyst pulls data from several systems, works through it and writes it up. This often takes weeks, and meetings arranged at short notice can happen before the analysis is ready.

We want a rep to get a trustworthy, cited client briefing in one click.

## Your task

Build a working prototype of a client intelligence agent. Given a client and a trigger, it should gather evidence from the starter data, analyse it, and produce a short briefing for the rep in which every claim is grounded in the data and cited.

Three things matter most:

1. **It is general.** It should work for any of the 25 clients and any of the four triggers (renewal, meeting prep, upsell, at-risk) without logic written for a specific client or case. We will run it on clients you have not looked at.
2. **The numbers are right.** Figures come from code or SQL tools, not from the language model. The model plans, interprets and writes. When data is missing, sparse or inconsistent, the briefing says so instead of filling the gap.
3. **It is orchestrated.** Break the work into steps or agents with clear jobs: for example, a planner that picks analyses for the trigger, specialist tools or agents, a writer, and a verifier that checks each claim against the evidence. Keep it as simple as works; we are not counting agents.

Use AI coding tools such as Claude Code, Codex or Cursor. This is expected and encouraged, because the role involves building with them every day. We are interested in how you set them up and steer them, for example with an instruction file, a harness, sub-agents for different parts of the work, or a test loop that checks what they produce.

You can use any language (Python is suggested), any framework or none, and any LLM API or local model. A small, inexpensive model is enough. A command-line tool or a very small UI is fine; no deployment is needed.

> Figure 1. The inputs and the output. The middle box is yours to design.

## What we provide

`starter_pack.zip` contains synthetic data for 25 clients, extracted on **2026-11-01**. Treat that date as today.

| File | What it holds |
| --- | --- |
| `clients.csv` | 25 client accounts: segment, country, account owner, tier |
| `products.csv` | Product catalogue (8 products), usage units, typical segments, products often bought together |
| `contracts.csv`, `contract_lines.csv` | Contract dates, term, auto-renew, notice period, ARR, status; products, fees and included volumes per contract |
| `usage_monthly.csv` | Monthly consumption per client and product, November 2024 to October 2026 |
| `support_tickets.csv` | Tickets with priority, category, dates and satisfaction score |
| `crm_opportunities.csv` | Renewal, upsell and cross-sell opportunities |
| `meeting_notes/` | Free-text notes from account meetings, for some clients only |
| `client_intel.db` | SQLite copy of all of the above |
| `data_dictionary.md`, `tool_catalogue.md`, `sample_requests.json` | Column definitions and conventions; the analyses an analyst runs today, written as tool contracts; five example requests |

The data was exported from several systems and has not been cleaned. Like real data, it has gaps and inconsistencies, and handling them sensibly is part of the task. Read the data dictionary first. You can implement, change or replace the tools in the tool catalogue.

## What to build

### Must-haves

1. One command (or button) that takes a client (name or ID) and a trigger, and writes a briefing (Markdown is fine) plus an evidence file containing the tool outputs it used.
2. Deterministic tools covering at least: contract and renewal status, usage trends, white-space (products the client does not hold, with evidence for why they might fit), a support summary, and meeting notes.
3. A planning step that chooses analyses and emphasis for each trigger, driven by configuration or model reasoning, not by code for particular clients.
4. A writer that cites a source for every figure and claim, and a verifier that checks every number in the briefing appears in the evidence and every claim has a citation. Decide what happens when the check fails (repair, remove or flag), and tell us why.
5. Honest data handling: duplicates, missing months, short histories and conflicts between sources are detected and shown in a "data gaps and confidence" section, not hidden.
6. A short evaluation: run at least 3 clients with 2 triggers each, include an automated check for numbers in a briefing that do not appear in the tool outputs, and report what you found, including failures.

### Stretch goals, if you have time

- A very small UI (Streamlit, Gradio or a simple web page).
- Specialists running in parallel, with a trace for each run: steps, tool calls, tokens, time and cost.
- A new trigger added through configuration only.
- Conflicts between meeting notes and the data surfaced as questions for the rep.
- A portfolio view that ranks all clients by renewal risk or growth potential.
- Rubric-based or LLM-as-judge scoring of briefing quality alongside your factual checks.
- Unit tests for the tools and a regression run you can repeat after changing a prompt.

We would rather see the must-haves done well than many stretch goals done partly.

## What to submit

A git repository (a link or a zip) containing:

- Your code, with instructions to run it from a clean checkout. Use a placeholder for the API key; please do not include real keys.
- Sample outputs: the briefings and evidence files from your evaluation runs.
- The instruction files you gave your coding tools (for example `CLAUDE.md`, `AGENTS.md` or `.cursor/rules`) and the prompts your agent uses at run time.
- A README covering: how to run it; design notes (the flow, what each step does, where the model is and is not used, and why); your evaluation and its results; known limitations; what you would do next to make it production-ready; and a short "how I built it" note on how you worked with your coding tools (setup, instructions, sub-agents or checks, what worked and what you had to correct). Half a page is plenty for that note.

## How we will assess it

We look at whether it works end to end and is sensibly orchestrated; whether the numbers and claims are correct and grounded; whether it generalises to other clients and triggers; how well you designed the agent workflow and used your coding tools; engineering quality and evaluation; whether the briefing would actually help a rep; and how clearly the README explains your choices. Clear reasoning and honest limitations count for more than polish or volume.

We'll discuss your design in the technical interview. Expect to run your agent on a client or trigger you have not tried and to make a small change together.

## Time and practical arrangements

Plan on about 4 to 5 hours. This is a guideline: you do not need to finish everything. If you run out of time, write down what you would do next.

Use only the data in the starter pack; no access to any of our systems is needed. Do not include confidential material from current or previous employers. You keep the intellectual property in your work, and we use it only to assess your application. If you need an accessible format or other adjustments, or if access to an LLM API is a barrier, please tell your recruiting contact before you start.
