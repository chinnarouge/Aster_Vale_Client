# Evaluation Report

6 cases, 3 clients, as_of 2026-11-01.

## Layer 1: Figures (no model, free)

Expected facts from `cases.yaml` vs actual tool outputs.

| Case | Client | Trigger | Facts | Result |
| --- | --- | --- | --- | --- |
| c1_risk | C001 | at_risk | 12 | all match |
| c1_renew | C001 | renewal | 7 | all match |
| c3_upsell | C003 | upsell | 5 | all match |
| c3_meeting | C003 | meeting_prep | 3 | all match |
| c4_risk | C004 | at_risk | 3 | all match |
| c4_renew | C004 | renewal | 3 | all match |

## Layer 2: Briefings (end to end)

Full pipeline run. Claim-level = verifier pass/fail. Briefing-level = ungrounded numbers in rendered markdown.

| Case | Client | Trigger | Claims | Passed | Flagged | Ungrounded | Judge |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c1_risk | C001 | at_risk | 28 | 8 | 20 | 2 | 5/5 |
| c1_renew | C001 | renewal | 32 | 11 | 21 | 0 | 5/5 |
| c3_upsell | C003 | upsell | 24 | 10 | 14 | 1 | 5/5 |
| c3_meeting | C003 | meeting_prep | 25 | 9 | 16 | 2 | 5/5 |
| c4_risk | C004 | at_risk | 15 | 9 | 6 | 0 | 5/5 |
| c4_renew | C004 | renewal | 12 | 4 | 8 | 0 | 5/5 |

## What failed

### c1_risk

- 20 claims flagged by verifier (LLM-computed numbers not in tool output)
- ungrounded: 752.0 in: **Halden Bet (Strategic, £752K ARR, #1 in Sportsbook segment) is at risk: in-play products
- ungrounded: 7.0 in: - Prepare renewal options before the notice deadline of 2026-12-02 (31 days away), as comm

### c1_renew

- 21 claims flagged by verifier (LLM-computed numbers not in tool output)

### c3_upsell

- 14 claims flagged by verifier (LLM-computed numbers not in tool output)
- ungrounded: 6.0 in: - Brenmoor has been a customer since 2020-08-01 (over 6 years). Average utilization across

### c3_meeting

- 16 claims flagged by verifier (LLM-computed numbers not in tool output)
- ungrounded: 12.0 in: - 10 support tickets were logged in the past 12 months (unchanged from the prior period). 
- ungrounded: -142.0 in: - 10 support tickets were logged in the past 12 months (unchanged from the prior period). 

### c4_risk

- 6 claims flagged by verifier (LLM-computed numbers not in tool output)

### c4_renew

- 8 claims flagged by verifier (LLM-computed numbers not in tool output)

