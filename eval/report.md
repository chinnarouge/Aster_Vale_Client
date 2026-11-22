# Evaluation Report

6 cases, 3 clients, as_of 2026-11-01.

## Layer 1: Figures (no model, free)

Expected facts from `cases.yaml` vs actual tool outputs.

| Case | Client | Trigger | Facts | Result |
| --- | --- | --- | --- | --- |
| c2_renewal | C002 | renewal | 8 | all match |
| c2_upsell | C002 | upsell | 4 | all match |
| c9_at_risk | C009 | at_risk | 8 | all match |
| c9_meeting | C009 | meeting_prep | 3 | all match |
| c17_at_risk | C017 | at_risk | 4 | all match |
| c17_meeting | C017 | meeting_prep | 3 | all match |

## Layer 2: Briefings (end to end)

Full pipeline run. Claim-level = verifier pass/fail. Briefing-level = ungrounded numbers in rendered markdown.

| Case | Client | Trigger | Claims | Passed | Flagged | Ungrounded | Judge |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c2_renewal | C002 | renewal | 26 | 14 | 12 | 1 | 5/5 |
| c2_upsell | C002 | upsell | 21 | 18 | 3 | 0 | 5/5 |
| c9_at_risk | C009 | at_risk | 24 | 24 | 0 | 0 | 5/5 |
| c9_meeting | C009 | meeting_prep | 25 | 20 | 5 | 0 | 5/5 |
| c17_at_risk | C017 | at_risk | 23 | 20 | 3 | 0 | 5/5 |
| c17_meeting | C017 | meeting_prep | 27 | 23 | 4 | 0 | 5/5 |

## What failed

### c2_renewal

- 12 claims flagged by verifier (LLM-computed numbers not in tool output)
- ungrounded: 30.0 in: - Schedule a renewal planning meeting with Corvane's head of digital well before the notic

### c2_upsell

- 3 claims flagged by verifier (LLM-computed numbers not in tool output)

### c9_meeting

- 5 claims flagged by verifier (LLM-computed numbers not in tool output)

### c17_at_risk

- 3 claims flagged by verifier (LLM-computed numbers not in tool output)

### c17_meeting

- 4 claims flagged by verifier (LLM-computed numbers not in tool output)

