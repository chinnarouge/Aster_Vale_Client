# Client Intelligence Briefing: Halden Bet
**Trigger:** renewal | **Date:** 2026-11-01

## Headline

**Halden Bet (Strategic, ARR €752,000) renewal is at risk: notice deadline is 31 days away (2026-12-02), the client is trialling a competing in-play odds supplier, and CSAT has fallen to 2.22 amid recurring latency issues on the In-play Odds Feed.** (K-0002, N-003, T-0249, T-0269, T-0284) **[UNVERIFIED: no source found]**

## Account Snapshot

- Halden Bet is a Strategic-tier Sportsbook client based in GB, a customer since 2021-02-01, managed by Maya Lindgren. They are the #1 ARR client in the Sportsbook segment (€752,000 vs segment average of €499,500) with 4 products. (C001) **[UNVERIFIED: no source found]**

## Contract & Renewal Position

- Active renewal contract K-0002 runs from 2025-02-01 to 2027-01-31 (91 days remaining). Auto-renew is enabled with a notice deadline of 2026-12-02 (31 days away). ARR is €752,000, up 8.7% from the prior ARR of €692,000. (K-0002) **[UNVERIFIED: no source found]**
- Contract K-0002 covers four products: LIVE_DATA at €192,000, ODDS_PRE at €144,000, ODDS_LIVE at €240,000, and STREAM at €176,000. (L-00005, L-00006, L-00007, L-00008) **[UNVERIFIED: no source found]**

## Usage Trends

- In-play Odds Feed (ODDS_LIVE, €240,000 ARR) usage is declining sharply: YoY change of -31.0%, recent-vs-prior quarter -8.8%, and average utilization of only 60.6%. October 2026 usage fell to 991 thousand markets priced, down from 1,170 in both August and September. (U-00094, U-00086, U-00090, K-0002) **[UNVERIFIED: no source found]**
- Live Match Data Feed (LIVE_DATA, €192,000 ARR) usage is also declining: YoY -26.5%, recent-vs-prior -9.7%, average utilization 62.6%. October usage was 4,422 thousand API calls, down from 4,962 in August. (U-00093, U-00085)
- Pre-match Odds Feed (ODDS_PRE) is a bright spot: recent-vs-prior quarter usage is up 24.2% with average utilization of 77.0%. October usage was 1,149 thousand markets priced. YoY change is only -1.4%, essentially flat. (U-00095, U-00091)
- Live Streaming (STREAM) has low average utilization at 50.4% despite a recent-vs-prior quarter uptick of 23.2%. YoY change is -10.6%. (U-00088, U-00092, U-00096)
- Overall client utilization across all products averages 64.5%, significantly below the Sportsbook segment average of 86.1%. (C001)

## Growth Opportunities

- Pre-match Odds Feed usage is growing (recent-vs-prior +24.2%) and the client remains positive about it. There may be an opportunity to expand ODDS_PRE coverage (e.g., additional sports or leagues) to offset potential in-play revenue loss. (U-00095, N-003)
- The client previously expressed interest in expanding streaming to lower leagues (N-001). With STREAM utilization at only 50.4%, a right-sized streaming package for lower-league content could increase engagement and demonstrate value. (N-001, U-00096)
- Halden requested custom alert thresholds for ODDS_PRE (T-0169). Delivering this feature could strengthen the positive sentiment around pre-match products and support an upsell case. (T-0169) **[UNVERIFIED: no source found]**

## Support Health

- Support ticket volume surged from 2 tickets in the prior 12-month window to 12 in the current window — a 500% increase. 5 tickets are P1 and 6 are P2. Average CSAT is 2.22 out of 5 (90.0% response rate, 9 responses). (T-0151, T-0237, T-0249, T-0255, T-0269, T-0284)
- Latency is the dominant issue: 5 of 12 tickets are latency-related, mostly on ODDS_LIVE. Three P1 latency tickets (T-0249, T-0269, T-0284) received CSAT scores of 1, 1, and pending respectively. T-0269 was flagged as a repeat of contractual threshold breaches. (T-0249, T-0269, T-0284, T-0237, T-0273) **[UNVERIFIED: no source found]**
- There are 2 open tickets: T-0279 (P2, missing corner and card events in live feed) and T-0284 (P1, in-play latency spike during evening fixtures). These must be resolved before the renewal conversation. (T-0279, T-0284) **[UNVERIFIED: no source found]**
- A P1 outage (T-0255) caused the In-play feed to be unavailable for 35 minutes, scoring CSAT of 1. The client asked for service credits during the June 2026 service call. (T-0255, N-002) **[UNVERIFIED: no source found]**

## Relationship Context

- In the October 2026 renewal pre-discussion (N-003), Halden's head of trading confirmed they have been trialling another in-play odds supplier 'for two leagues' since the summer. Procurement wants pricing for a reduced in-play scope, citing budget pressure from their finance team. (N-003) **[UNVERIFIED: no source found]**
- Despite in-play dissatisfaction, the October meeting noted the client is 'still positive about the live data feed and pre-match odds.' This aligns with ODDS_PRE being the strongest-performing product by utilization (77.0%) and recent growth (24.2%). (N-003, U-00095)
- Relationship tone has deteriorated over the past year. The November 2025 quarterly review (N-001) was described as 'good quarter overall,' but by June 2026 (N-002) the tone was 'noticeably cooler' with complaints about in-play delays and manual market suspensions. (N-001, N-002) **[UNVERIFIED: no source found]**
- Halden queried the price increase applied at the last renewal via ticket T-0259 (Billing). They also raised the price increase during the November 2025 quarterly review, accepting it 'for now.' (T-0259, N-001) **[UNVERIFIED: no source found]**

## Risks & Concerns

- HIGH RISK — Partial churn on ODDS_LIVE (€240,000): The client is actively trialling a competitor for in-play odds, procurement wants reduced in-play scope, usage is down 31.0% YoY, and 5 latency tickets with rock-bottom CSAT scores signal deep dissatisfaction. (N-003, K-0002, U-00094, T-0249, T-0269, T-0284)
- Notice deadline is only 31 days away (2026-12-02). Although auto-renew is enabled, the client's explicit request for reduced-scope pricing means relying on auto-renew would likely trigger a formal cancellation notice. (K-0002, N-003) **[UNVERIFIED: no source found]**
- LIVE_DATA usage is also dropping (YoY -26.5%, utilization 62.6%), and there is an open P2 ticket for missing corner and card events (T-0279). This product could become a secondary churn risk if data quality issues are not addressed. (U-00093, T-0279) **[UNVERIFIED: no source found]**
- STREAM utilization is only 50.4% — the lowest of all four products. The client expressed interest in streaming for lower leagues in November 2025 but nothing materialized. At renewal, the client may challenge the €176,000 fee given low usage. (U-00096, N-001, L-00008) **[UNVERIFIED: no source found]**

## Recommended Next Steps

- URGENT (by 2026-11-08): Resolve the open P1 ticket T-0284 (in-play latency spike) and P2 ticket T-0279 (missing live feed events) before entering renewal negotiations. Escalate to engineering leadership. (T-0284, T-0279) **[UNVERIFIED: no source found]**
- Prepare renewal options before the notice deadline of 2026-12-02 (31 days), as committed in the October meeting (N-003). Options should include: (a) full renewal with SLA improvements and pricing concessions on ODDS_LIVE, (b) reduced in-play scope scenario, and (c) a value-add bundle pairing ODDS_PRE expansion with streaming. (N-003, K-0002) **[UNVERIFIED: no source found]**
- Address the service credit request from June 2026 (N-002). Failing to resolve this before renewal will worsen negotiation dynamics. Check SLA credit terms and present a resolution proactively. (N-002, T-0255) **[UNVERIFIED: no source found]**
- Schedule a technical deep-dive with Halden's trading operations lead to present a concrete latency improvement plan for ODDS_LIVE. The in-play latency roadmap was promised back in November 2025 (N-001) — confirm what has been delivered. (N-001, T-0269, T-0284) **[UNVERIFIED: no source found]**
- Gather competitive intelligence on the in-play odds supplier Halden is trialling. Identify which two leagues are involved and assess whether a targeted retention offer for those leagues could recapture the business. (N-003)

## Data Gaps & Confidence

- 3 closed support tickets have no CSAT score recorded. The actual average CSAT of 2.22 is based on 9 responses out of 12 tickets and may not reflect the full picture. **[UNVERIFIED: citation not in evidence]**
- No prior-window CSAT data is available for comparison, so the trend in satisfaction cannot be quantified — only inferred from the relationship context deterioration noted in meeting notes. (N-001, N-002)
- No opportunity pipeline data was returned. It is unclear whether a renewal or downsell opportunity has been created in the CRM for this account ahead of the 2026-12-02 notice deadline. **[UNVERIFIED: no source found]**
