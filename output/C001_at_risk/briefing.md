# Client Intelligence Briefing: Halden Bet
**Trigger:** at_risk | **Date:** 2026-11-01

## Headline

**Halden Bet (Strategic, £752K ARR, #1 in Sportsbook segment) is at risk: in-play products show steep usage declines, support tickets have surged 500% YoY with a CSAT of 2.22, the client is trialling a competitor for in-play odds, and the notice deadline is only 31 days away on 2026-12-02.** (K-0002, T-0151, N-003, C001) **[UNVERIFIED: no source found]**

## Account Snapshot

- Halden Bet is a Strategic-tier Sportsbook client based in GB, a customer since 2021-02-01, managed by Maya Lindgren. They are the highest ARR account in the Sportsbook segment, ranking 1 of 6 peers with total ARR of 752,000 EUR versus a segment average of 499,500 EUR. (C001) **[UNVERIFIED: no source found]**

## Contract & Renewal Position

- Active renewal contract K-0002 runs from 2025-02-01 to 2027-01-31 (91 days remaining) with auto-renew enabled. The notice deadline is 2026-12-02 — only 31 days away. ARR is 752,000 EUR, up 8.7% from prior ARR of 692,000 EUR. Products: LIVE_DATA (192,000), ODDS_PRE (144,000), ODDS_LIVE (240,000), STREAM (176,000). (K-0002, L-00005, L-00006, L-00007, L-00008) **[UNVERIFIED: no source found]**
- Procurement explicitly asked for pricing for a reduced in-play scope at renewal, citing budget pressure from finance. The head of trading confirmed they have been trialling another in-play odds supplier for two leagues since the summer. (N-003)

## Usage Trends

- In-play Odds Feed (ODDS_LIVE) usage is declining sharply: YoY change of -31.0%, recent-vs-prior quarter change of -8.8%, and average utilization at only 60.6%. October 2026 usage fell to 991K markets priced, down from 1,170K in both August and September. (U-00094, U-00090, U-00086) **[UNVERIFIED: no source found]**
- Live Match Data Feed (LIVE_DATA) usage is also declining: YoY change of -26.5%, recent-vs-prior quarter change of -9.7%, average utilization of 62.6%. October 2026 usage dropped to 4,422K API calls from 4,962K in August and 4,883K in September. (U-00093, U-00085, U-00089) **[UNVERIFIED: no source found]**
- Pre-match Odds Feed (ODDS_PRE) is a bright spot: recent-vs-prior quarter change of +24.2% and average utilization of 77.0%. October usage was 1,149K markets priced, up from 988K in August. YoY change is only -1.4%. (U-00095, U-00087, U-00091)
- Live Streaming (STREAM) has recent-vs-prior quarter growth of +23.2% but YoY is still down -10.6% with average utilization of only 50.4%. October usage was 541 streamed hours. (U-00096, U-00088, U-00092)
- Halden Bet's overall average utilization is 64.5%, significantly below the Sportsbook segment average of 86.1%, indicating substantial under-use of contracted capacity across products. (C001)

## Growth Opportunities

- Pre-match Odds Feed usage is growing strongly (recent-vs-prior +24.2%) with 77.0% utilization — the healthiest product. The client remains positive about this product per the Oct meeting. This could be positioned as an anchor in renewal negotiations. (U-00095, N-003)
- Live Streaming utilization is only 50.4% with recent quarter-over-quarter growth of +23.2%. The Nov 2025 QBR noted client interest in streaming for lower leagues. Expanding streaming content could add value and offset potential in-play scope reductions. (U-00096, N-001) **[UNVERIFIED: no source found]**

## Support Health

- Support tickets surged from 2 in the prior 12-month window to 12 in the current window — a 500% increase. Prior tickets were all P3; current tickets include 5 P1s and 6 P2s, showing a dramatic escalation in severity. (T-0151, T-0169, T-0203, T-0237, T-0242, T-0249, T-0255, T-0259, T-0269, T-0273, T-0279, T-0284)
- Average CSAT across 9 responses is 2.22 out of 5 with a 90.0% response rate. Three P1 tickets related to ODDS_LIVE latency/outage received CSAT scores of 1, and a P1 outage ticket (T-0255) describes a 35-minute in-play feed outage. (T-0249, T-0255, T-0269) **[UNVERIFIED: no source found]**
- Latency is the dominant issue category with 5 tickets, all targeting the ODDS_LIVE product. There are also 2 data accuracy tickets for LIVE_DATA. Two tickets remain open: T-0279 (P2, missing corner/card events in live feed) and T-0284 (P1, in-play latency spike during evening fixtures). (T-0237, T-0249, T-0269, T-0273, T-0284, T-0279, T-0242) **[UNVERIFIED: no source found]**

## Relationship Context

- In the Oct 2026 renewal pre-discussion, the head of trading confirmed trialling another in-play odds supplier 'for two leagues' since the summer. Procurement is requesting pricing for a reduced in-play scope. However, they remain positive about the live data feed and pre-match odds. (N-003) **[UNVERIFIED: no source found]**
- In the Jun 2026 service call, Halden complained about in-play price delays during busy fixtures, stated traders had to suspend markets manually, requested a written explanation and service credits. Maya noted the client's tone was 'noticeably cooler than last quarter.' (N-002) **[UNVERIFIED: no source found]**
- In the Nov 2025 quarterly review, the trading team was happy with in-play coverage and pre-match pricing, though they raised the prior renewal price increase again. They expressed interest in more streaming for lower leagues. (N-001) **[UNVERIFIED: no source found]**
- A billing ticket (T-0259, P3) queried the price increase applied at last renewal, consistent with the Nov 2025 meeting note where the client raised the same concern. CSAT on that ticket was 2. (T-0259, N-001) **[UNVERIFIED: no source found]**

## Risks & Concerns

- CRITICAL RISK — Notice deadline in 31 days (2026-12-02): Halden is actively trialling a competitor for in-play odds, requesting reduced in-play scope pricing, and ODDS_LIVE usage is down 31.0% YoY. ODDS_LIVE is the largest product line at 240,000 EUR. Partial or full loss of this product is a material ARR threat. (K-0002, N-003, U-00094) **[UNVERIFIED: no source found]**
- Persistent ODDS_LIVE service quality issues (5 latency tickets, 1 outage, CSAT scores of 1 on P1 incidents) are the apparent driver of competitive evaluation. Two related tickets (T-0279, T-0284) remain open and unresolved. (T-0249, T-0255, T-0269, T-0284, T-0279) **[UNVERIFIED: no source found]**
- Overall utilization is only 64.5% vs segment average of 86.1%, giving the client leverage to argue they are over-paying relative to usage, especially given the 8.7% ARR increase at the last renewal. (C001, K-0002)

## Recommended Next Steps

- URGENT (by 2026-11-08): Escalate the two open tickets — T-0284 (P1, in-play latency spike) and T-0279 (P2, missing live events) — to engineering leadership and provide Halden with a written resolution timeline before any renewal conversation. (T-0284, T-0279) **[UNVERIFIED: no source found]**
- Prepare renewal options before the notice deadline of 2026-12-02 (31 days away), as committed in the Oct 7 meeting. Options should include a reduced in-play scope tier alongside a full-scope option with SLA guarantees and latency improvement commitments. (N-003, K-0002) **[UNVERIFIED: no source found]**
- Request a meeting with the head of trading and CTO within the next 2 weeks to present a remediation plan for ODDS_LIVE latency, share the in-play latency improvement roadmap (originally committed in Nov 2025 QBR), and discuss streaming expansion for lower leagues. (N-001, N-003, N-002) **[UNVERIFIED: no source found]**
- Assess whether SLA service credits are owed for the documented latency and outage incidents (35-minute feed outage T-0255, repeated above-threshold latency T-0269). Proactively offering credits could rebuild trust before the renewal negotiation. (T-0255, T-0269, N-002) **[UNVERIFIED: no source found]**

## Data Gaps & Confidence

- 3 closed support tickets have no CSAT score recorded, so the actual CSAT of 2.22 is based on only 9 of 12 tickets and may not fully represent client sentiment. **[UNVERIFIED: citation not in evidence]**
- No prior-window CSAT data is available, so it is not possible to quantify CSAT trend direction — only the current average of 2.22 is known. **[UNVERIFIED: citation not in evidence]**
- No opportunity pipeline data was returned, so it is unknown whether any upsell or renewal opportunity has been formally logged in the CRM. Maya should ensure a renewal opportunity is created immediately given the 31-day notice deadline. (K-0002)
