"""Unit tests for the 10 SQL tools.

Four data shapes per tool:
  - Normal:    C002 (Corvane Media) — full data across all dimensions
  - Empty:     C004 (no tickets, no notes, no opps) / C007 (no active contracts)
  - Short:     C004 — only 2 months of usage, no YoY possible
  - Duplicate: C006 (dup contract K-0010, dup usage) / C010 (dup ticket T-0281)

Client IDs appear here and nowhere else outside eval/.
as_of is always 2026-11-01.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "Aster_business_analyst"))

from tools import (
    resolve_client,
    get_client_profile,
    get_contract_status,
    get_usage_trend,
    get_whitespace,
    get_support_summary,
    get_opportunities,
    get_meeting_notes,
    check_data_quality,
    get_peer_comparison,
)

AS_OF = "2026-11-01"


# ── resolve_client ──────────────────────────────────────────────


class TestResolveClient:
    def test_exact_id(self):
        r = resolve_client("C002")
        m = r["data"]["matches"][0]
        assert m["client_id"] == "C002"
        assert m["confidence"] == "exact_id"

    def test_exact_name(self):
        r = resolve_client("Corvane Media")
        m = r["data"]["matches"][0]
        assert m["client_id"] == "C002"
        assert m["confidence"] == "exact_name"

    def test_partial_name(self):
        r = resolve_client("Corvane")
        m = r["data"]["matches"][0]
        assert m["client_id"] == "C002"
        assert m["confidence"] == "partial"

    def test_not_found(self):
        r = resolve_client("XYZNOTREAL")
        assert r["data"]["matches"][0]["confidence"] == "fuzzy"


# ── get_client_profile ──────────────────────────────────────────


class TestClientProfile:
    def test_normal(self):
        r = get_client_profile("C002")
        d = r["data"]
        assert d["client_id"] == "C002"
        assert d["segment"] == "Broadcaster"
        assert d["tier"] == "Strategic"
        assert d["tenure_years"] == 4.4

    def test_empty_client_still_returns_profile(self):
        r = get_client_profile("C004")
        assert r["data"] is not None
        assert r["data"]["client_id"] == "C004"
        assert r["data"]["tenure_years"] is not None


# ── get_contract_status ─────────────────────────────────────────


class TestContractStatus:
    def test_normal(self):
        r = get_contract_status("C002", AS_OF)
        d = r["data"]
        assert d["total_arr"] == 351000
        assert len(d["active_contracts"]) == 1
        ac = d["active_contracts"][0]
        assert ac["days_to_end"] == 211
        assert ac["days_until_notice"] == 121
        assert ac["auto_renew"] == "N"

    def test_no_active_contracts(self):
        """C007 has only expired and pending contracts."""
        r = get_contract_status("C007", AS_OF)
        d = r["data"]
        assert len(d["active_contracts"]) == 0
        assert d["total_arr"] == 0

    def test_duplicate_contract_deduped(self):
        """C006 has duplicate K-0010. Should appear once."""
        r = get_contract_status("C006", AS_OF)
        contract_ids = [c["contract_id"] for c in r["data"]["active_contracts"]]
        assert contract_ids.count("K-0010") == 1


# ── get_usage_trend ─────────────────────────────────────────────


class TestUsageTrend:
    def test_normal(self):
        r = get_usage_trend("C002", AS_OF)
        prods = r["data"]["products"]
        assert len(prods) == 3
        ld = prods["LIVE_DATA"]
        assert ld["months_of_data"] == 24
        assert ld["yoy_change_pct"] is not None
        assert isinstance(ld["yoy_change_pct"], (int, float))

    def test_short_history_no_yoy(self):
        """C004 has only 2 months. YoY must be None, not zero."""
        r = get_usage_trend("C004", AS_OF)
        prods = r["data"]["products"]
        for pid, pdata in prods.items():
            assert pdata["months_of_data"] == 2
            assert pdata["yoy_change_pct"] is None, (
                f"{pid} YoY should be None with 2 months"
            )

    def test_duplicate_usage_deduped(self):
        """C006 has duplicate usage row for LIVE_DATA 2026-08. Should have 24 months, not 25."""
        r = get_usage_trend("C006", AS_OF)
        ld = r["data"]["products"]["LIVE_DATA"]
        assert ld["months_of_data"] == 24
        assert len(ld["monthly"]) == 24


# ── get_whitespace ──────────────────────────────────────────────


class TestWhitespace:
    def test_normal(self):
        r = get_whitespace("C002")
        assert len(r["data"]["held_products"]) == 3
        assert len(r["data"]["gaps"]) > 0
        for gap in r["data"]["gaps"]:
            assert "product_id" in gap
            assert "peers_holding" in gap


# ── get_support_summary ─────────────────────────────────────────


class TestSupportSummary:
    def test_normal(self):
        r = get_support_summary("C002", AS_OF)
        d = r["data"]
        assert d["total_tickets"] == 13
        assert abs(d["avg_csat"] - 4.55) < 0.01
        assert abs(d["change_pct"] - 44.4) < 0.1

    def test_no_tickets(self):
        """C004 has zero tickets. CSAT must be None, not zero."""
        r = get_support_summary("C004", AS_OF)
        d = r["data"]
        assert d["total_tickets"] == 0
        assert d["avg_csat"] is None, "CSAT with no tickets must be None, not 0"
        assert d["change_pct"] is None, "change_pct with no tickets must be None"

    def test_duplicate_ticket_deduped(self):
        """C010 has duplicate T-0281. Should count once."""
        r = get_support_summary("C010", AS_OF)
        assert r["row_ids"].count("T-0281") == 1


# ── get_opportunities ───────────────────────────────────────────


class TestOpportunities:
    def test_normal(self):
        r = get_opportunities("C002")
        d = r["data"]
        assert len(d["opportunities"]) == 1

    def test_no_opportunities(self):
        """C006 has no opportunities."""
        r = get_opportunities("C006")
        d = r["data"]
        assert len(d["opportunities"]) == 0
        assert d.get("pipeline_total") is None or d.get("pipeline_total") == 0

    def test_no_active_contracts_arr_none(self):
        """C007 has no active contracts. current_arr_eur must be None."""
        r = get_opportunities("C007")
        d = r["data"]
        assert d.get("current_arr_eur") is None, (
            "ARR with no active contracts must be None"
        )


# ── get_meeting_notes ───────────────────────────────────────────


class TestMeetingNotes:
    def test_normal(self):
        r = get_meeting_notes("C002")
        assert r["data"]["count"] == 2
        assert len(r["data"]["notes"]) == 2

    def test_no_notes(self):
        """C004 has no meeting notes. Count must be 0, not None."""
        r = get_meeting_notes("C004")
        assert r["data"]["count"] == 0
        assert r["data"]["notes"] == []


# ── check_data_quality ──────────────────────────────────────────


class TestDataQuality:
    def test_normal_finds_issues(self):
        """C002 has blank CSAT on 3 tickets."""
        r = check_data_quality("C002")
        types = [i["type"] for i in r["data"]["issues"]]
        assert "blank_csat" in types

    def test_short_history_flagged(self):
        """C004 has only 2 months. Must flag short_history, not treat as normal."""
        r = check_data_quality("C004")
        types = [i["type"] for i in r["data"]["issues"]]
        assert "short_history" in types, "2-month history must be flagged as short"

    def test_missing_notes_flagged(self):
        """C004 has no meeting notes. Must flag, not silently skip."""
        r = check_data_quality("C004")
        types = [i["type"] for i in r["data"]["issues"]]
        assert "no_meeting_notes" in types

    def test_duplicates_flagged(self):
        """C006 has duplicate contract and usage rows."""
        r = check_data_quality("C006")
        types = [i["type"] for i in r["data"]["issues"]]
        assert "duplicate_contract" in types
        assert "duplicate_usage" in types


# ── get_peer_comparison ─────────────────────────────────────────


class TestPeerComparison:
    def test_normal(self):
        r = get_peer_comparison("C002", AS_OF)
        d = r["data"]
        assert d["segment"] == "Broadcaster"
        assert d["peer_count"] == 5
        assert d["this_client"]["total_arr"] == 351000
        assert "segment_avg_arr" in d


# ── Determinism: same input, same output ────────────────────────


class TestDeterminism:
    def test_tools_are_deterministic(self):
        """Running the same tool twice must produce identical output."""
        r1 = get_contract_status("C002", AS_OF)
        r2 = get_contract_status("C002", AS_OF)
        assert r1 == r2

        s1 = get_support_summary("C002", AS_OF)
        s2 = get_support_summary("C002", AS_OF)
        assert s1 == s2

        u1 = get_usage_trend("C002", AS_OF)
        u2 = get_usage_trend("C002", AS_OF)
        assert u1 == u2
