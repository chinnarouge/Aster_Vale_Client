---
name: run-eval
description: "Run evaluation scenarios: 3+ clients x 2 triggers each against the agent"
---

# Evaluation Scenarios

Run these client/trigger combinations to evaluate the agent. Each tests different data conditions.

## Commands

```bash
# C001 Halden Bet — large client, full data, good baseline
python Aster_business_analyst/main.py --client "C001" --trigger renewal --judge
python Aster_business_analyst/main.py --client "C001" --trigger at_risk --context "Usage feels down" --judge

# C003 Ridgemont Broadcasting — notice deadline passed, auto_renew=N, meeting note contradicts usage data
python Aster_business_analyst/main.py --client "C003" --trigger renewal --judge
python Aster_business_analyst/main.py --client "C003" --trigger meeting_prep --judge

# C004 Dawnfield Analytics — only 2 months of history, insufficient for trends
python Aster_business_analyst/main.py --client "C004" --trigger upsell --judge
python Aster_business_analyst/main.py --client "C004" --trigger at_risk --judge
```

## What to check per run

1. Does it complete without errors?
2. Are all numbers in the briefing traceable to evidence.json?
3. Are data gaps flagged (missing months, short history, no meeting notes)?
4. Does C003 flag the meeting note vs usage data conflict?
5. Does C004 say history is too short for trends instead of computing bad percentages?
6. Are duplicate rows (K-0010, T-0281, U-00422/U-01991) handled correctly?
7. Does the judge score match what you see in the briefing?

## After running

Save the output briefings and evidence files. Report: which passed, which failed, what the judge scored, any ungrounded numbers found.
