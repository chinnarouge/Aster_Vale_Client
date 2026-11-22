---
name: investigate-data
description: "Phase 1: Investigate the SQLite database, find data quality issues, correlations, and save findings to data_analysis.md for review"
---

# Data Analysis — Phase 1 Investigation

You are investigating starter_pack/client_intel.db for a client intelligence agent project. The as_of date is 2026-11-01.

## What to do

1. Read `starter_pack/data_dictionary.md` and `starter_pack/tool_catalogue.md` first. Understand the schema, column meanings, and what "missing" means (unknown, not zero).

2. Open `starter_pack/client_intel.db` and go through every table:
   - Row counts
   - Whether PKs are actually unique
   - Any duplicates at PK level or business-key level
   - Missing data, null counts per column
   - Min/max/distribution of key fields
   - Conflicts between tables (e.g. ARR vs sum of contract lines)

3. The data has intentional quality issues. Look carefully for:
   - Duplicate rows (same PK or same business key with different PKs)
   - Missing months in usage series
   - Contracts that have expired but show active status
   - Notice deadlines that have already passed
   - CSAT scores that are missing vs zero
   - Meeting notes that contradict the numbers
   - Usage outside contract date ranges

4. Find correlations and cross-client patterns:
   - Which clients show multiple risk signals at once (declining usage + support issues + expiring contract)?
   - Which clients are missing products their segment peers have?
   - Do meeting notes match or contradict the usage/contract data?
   - Which clients have upcoming contract deadlines?
   - CSAT outliers — unusually high or low?

5. For each finding, note the specific row IDs, values, and tables involved. Be precise.

## Output

Save everything to `data_analysis.md` at the project root. Structure:

- **Corrections Made During Analysis** — if the user catches any errors, record them here with what was wrong and what was corrected
- **Table Summary** — row counts, PK uniqueness, key distributions per table
- **Data Quality Issues** — each issue with specific IDs and values
- **Client Findings** — correlations, risk signals, upsell opportunities, conflicts
- **Evaluation Scenarios** — interesting clients to test the agent against and why

## Then stop

Do not write any code. Show the findings and wait for the user to review. The user will correct any mistakes and tell you what matters and what to skip before Phase 2.
