# Data Analysis — Phase 1 Findings

Investigated starter_pack/client_intel.db on 2026-11-20. as_of date is 2026-11-01.


## Corrections Made During Analysis

The AI initially reported 82 unique contract line_ids. This was wrong. It was caused by joining contract_lines to contracts without handling the K-0010 duplicate, which doubled the result set. Actual count is 154 unique line_ids with zero duplicates.

The AI initially reported 25 active contracts and ARR of 6,505,500. After correcting for the K-0010 duplicate, the actual count is 24 active contracts with ARR of 6,329,500.

The AI initially reported 1990 unique usage_ids. All 1991 are unique at PK level. The duplicate is at business-key level only.

The AI initially reported CRM counts as cross_sell 7, Closed Lost 4, Proposal 4, Qualification 4. Corrected to cross_sell 8, Closed Lost 3, Proposal 5, Qualification 5.


## Table Summary

clients has 25 rows, all unique by client_id. 6 segments, 16 countries, 3 tiers (Core 11, Growth 9, Strategic 5), 5 account owners. Oldest client since 2019-11-01 (C005), newest is 2026-09-01 (C004).

products has 8 rows. Each product has a different usage unit. LIVE_DATA uses API calls in thousands, STREAM uses streamed hours, WIDGETS uses widget impressions in millions, and so on. Never aggregate usage across products because of the different units. ODDS_LIVE requires LIVE_DATA as a prerequisite. Each product has an often_bought_with field for cross-sell recommendations.

contracts has 46 rows but only 45 unique contract_ids. K-0010 for C006 appears twice, identical rows. After deduplication there are 24 active contracts with total ARR of 6,329,500, 20 expired, and 1 pending signature (K-0045 for C007).

contract_lines has 154 rows and all 154 line_ids are unique. No duplicates at all. But if you join contract_lines to contracts without deduplicating K-0010 first, you get doubled rows and wrong counts. This is what caused the earlier mistake of thinking there were only 82 unique lines.

usage_monthly has 1991 rows and all 1991 usage_ids are unique. No PK duplicates. There is one business-key duplicate: C006 LIVE_DATA 2026-08 has two rows (U-00422 and U-01991) with different PKs but identical values. Deduplicate by client_id, product_id, month. Coverage is 2024-11 to 2026-10, 24 months.

support_tickets has 289 rows. 286 closed and 3 open. By priority: P1 25, P2 56, P3 149, P4 59. 106 closed tickets have no CSAT score, response rate is 63%.

crm_opportunities has 19 rows. By type: cross_sell 8, renewal 7, upsell 3, new_business 1. By stage: Qualification 5, Proposal 5, Negotiation 3, Closed Won 3, Closed Lost 3.

meeting_notes_index has 14 rows. meeting_notes table also has 14 rows with the full note text in the body column. 10 clients have notes, 15 clients have none.


## Data Quality Issues

K-0010 is a duplicate contract row for C006 Tidewell Fantasy. Both rows are identical. Deduplicate by contract_id whenever querying contracts.

T-0281 is a duplicate ticket row for C010 Saltmarsh Data. Both rows are identical (P3, Access, closed). Deduplicate by ticket_id whenever querying support_tickets.

U-00422 and U-01991 are the same observation for C006 LIVE_DATA 2026-08. Same units_used (2176), same included_units (4000), same source. Deduplicate by client_id, product_id, month and keep the lower usage_id.

C005 is missing usage data for all 4 of their products for 2026-03. Meeting note N-010 from 2026-05-20 mentions they could not find their March usage statement. This is a data gap, not zero usage. Do not impute.

C004 started in September 2026 and only has 2 months of usage data. Not enough for any trend analysis. Flag as insufficient history.

C007 has no active contract as of 2026-11-01. K-0011 expired on 2026-09-30 and K-0045 is pending signature. Meeting note N-009 says renewal terms were agreed but legal is reviewing a data-rights clause. There is a contract gap right now.

106 of 286 closed support tickets have no CSAT score. Calculate averages from available scores only and always mention the response rate.

C005 contract K-0008 has a notice deadline of 2026-10-01 which has already passed. auto_renew is Y so it will renew automatically, but it is still worth flagging.

C003 contract K-0005 has a notice deadline of 2026-10-02 which has already passed. auto_renew is N, which means this contract will expire on 2026-12-31 unless a renewal is signed. This is urgent.

15 of 25 clients have no meeting notes at all. When a client has no notes, say so explicitly.

C003 meeting note N-006 from September 2026 says streaming usage is "up massively" since they moved second-division matches to the platform. But the actual usage data shows streaming declining from 580 in November 2024 to 435 in October 2026, a 22.5% drop year over year. Both the note and the data must be presented with the conflict flagged. There is a small recent uptick from 303 in July to 435 in October which might be what the director is referring to, but the overall trend is still down.


## Clients With Meeting Notes

C001 Halden Bet has 3 notes (N-001, N-002, N-003). C002 Corvane Media has 2 (N-004, N-005). C003 Brenmoor League has 2 (N-006, N-007). C005 has 1 (N-010). C006 has 1 (N-013). C007 has 1 (N-009). C008 has 1 (N-008). C009 has 1 (N-011). C010 has 1 (N-014). C011 has 1 (N-012).

No notes: C004, C012, C013, C014, C015, C016, C017, C018, C019, C020, C021, C022, C023, C024, C025.


## Key Client Findings

C001 Halden Bet is the strongest at-risk case in the dataset. They trigger every risk signal at once. 5 P1 tickets and 6 P2 tickets, the most in the portfolio. 2 open tickets right now, one P1 latency and one P2 data accuracy. Average CSAT of 2.2, the worst by far, next lowest is C018 at 3.5. Three products declining: LIVE_DATA down 36%, ODDS_LIVE down 40%, STREAM down about 10%. Meeting notes show competitor trial for in-play odds, procurement wants reduced scope, budget pressure. CRM opportunity O-0001 proposes renewal at 541,500 which is a 28% reduction from current ARR of 752,000. Notice deadline is 2026-12-02, 31 days away.

C002 Corvane Media is a strong upsell candidate. Meeting note N-005 specifically asks about embeddable live match visualisations which is the WIDGETS product. They already hold LIVE_DATA, STREAM, and STATS_ARCHIVE. WIDGETS is a natural fit for broadcasters and is related to products they hold. Previous FAN_INSIGHTS opportunity O-0002 was Closed Lost with reason "no budget this year" in 2025, so do not push that one again too soon. Streaming usage is up 25% year over year. Contract K-0004 ends 2027-05-31 with auto_renew N and no renewal opportunity in CRM. This is a hidden risk.

C003 Brenmoor League has the streaming data conflict described above. Renewal opportunity O-0003 at 258,500 is a 10% increase from current ARR. Notice deadline passed on 2026-10-02 and auto_renew is N, making this urgent.

C007 Varrow Racing Authority has a contract gap. Renewal O-0005 is in Negotiation at 200,000. Note N-009 says terms are agreed commercially but legal is reviewing.

C004 Quillon Esports is a brand new client with only 2 months of data and 1 product. Good for testing edge cases around short history.

C009 Pellucid Odds is growing fast. All products showing growth. Note N-011 mentions they want live streaming. Cross-sell O-0007 for STREAM is in Qualification.


## Contracts Ending Within 6 Months

With renewal opportunity: C003 ends 2026-12-31 auto_renew N (O-0003 Proposal), C001 ends 2027-01-31 auto_renew Y (O-0001 Negotiation), C011 ends 2027-01-31 auto_renew N (O-0010 Proposal), C025 ends 2027-03-31 auto_renew N (O-0019 Proposal).

Without renewal opportunity: C005 ends 2026-11-30 auto_renew Y notice passed, C022 ends 2026-12-31 auto_renew Y 30 days to notice, C006 ends 2027-02-28 auto_renew Y 59 days, C016 ends 2027-02-28 auto_renew Y 59 days, C020 ends 2027-02-28 auto_renew Y 59 days, C002 ends 2027-05-31 auto_renew N no opp at all which is high risk.

C007 has a contract gap right now with K-0045 pending signature.


## Open Support Tickets

T-0284 for C001, ODDS_LIVE, P1, Latency, in-play latency spike during evening fixtures. T-0279 for C001, LIVE_DATA, P2, Data accuracy, missing corner and card events in live feed. T-0286 for C024, ODDS_LIVE, P4, Access, new user accounts needed.

Only C001 has critical open tickets.


## Strongest Upsell Opportunities

C002 for WIDGETS. Broadcaster segment fits, related to held products LIVE_DATA and STATS_ARCHIVE, meeting note asks about embeddable visualisations.

C008 for WIDGETS. Broadcaster, related to held products, note N-008 shows strong interest, O-0006 already in Proposal.

C009 for STREAM. Sportsbook, related to WIDGETS which they hold, note N-011 says they want streaming, O-0007 in Qualification.

C016 for STREAM. Sportsbook, O-0013 in Proposal with pricing agreed.

Avoid re-pitching: C002 FAN_INSIGHTS (O-0002 Closed Lost), C015 ODDS_LIVE (O-0012 Closed Lost not a sportsbook use case), C017 STREAM (O-0014 Closed Lost rights held by league).


## CSAT Outliers

C001 average CSAT 2.2 from 9 responses. This is far below everyone else. Next lowest is C018 at 3.5. All other clients range from 4.0 to 4.8.


## Recommended Eval Scenarios

C001 at_risk because it triggers all risk signals. C001 renewal for the same client with different trigger emphasis. C002 upsell for the WIDGETS opportunity. C003 meeting_prep for the streaming conflict. C007 renewal for the contract gap edge case. C004 upsell for the short history edge case.
