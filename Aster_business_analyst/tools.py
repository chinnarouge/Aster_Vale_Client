import sqlite3
from datetime import date, timedelta
from collections import defaultdict
from difflib import SequenceMatcher

from config import DB_PATH, AS_OF

DEDUP_CONTRACTS = """contracts_deduped AS (
    SELECT DISTINCT contract_id, client_id, contract_type, start_date, end_date,
        CAST(term_months AS INTEGER) AS term_months, auto_renew,
        CAST(notice_period_days AS INTEGER) AS notice_period_days,
        CAST(arr_eur AS INTEGER) AS arr_eur, currency, status, signed_date
    FROM contracts
)"""

DEDUP_TICKETS = """tickets_deduped AS (
    SELECT DISTINCT ticket_id, client_id, product_id, opened_date, closed_date,
        status, priority, category, subject, csat_score
    FROM support_tickets
)"""

DEDUP_USAGE = """usage_deduped AS (
    SELECT client_id, product_id, month,
        MIN(usage_id) AS usage_id,
        CAST(units_used AS REAL) AS units_used,
        CASE WHEN included_units = '' OR included_units IS NULL
             THEN NULL ELSE CAST(included_units AS REAL) END AS included_units,
        source
    FROM usage_monthly
    GROUP BY client_id, product_id, month
)"""


def _query(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _parse_date(s):
    return date.fromisoformat(s) if s else None


def _last_month(as_of):
    d = _parse_date(as_of)
    if d.month == 1:
        return f"{d.year - 1}-12"
    return f"{d.year}-{d.month - 1:02d}"


def _months_between(start_ym, end_ym):
    y, m = map(int, start_ym.split("-"))
    ey, em = map(int, end_ym.split("-"))
    result = []
    while (y, m) <= (ey, em):
        result.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return result


def resolve_client(query_str):
    q = query_str.strip()
    rows = _query(
        "SELECT client_id, client_name FROM clients WHERE client_id = ?", (q.upper(),)
    )
    if rows:
        return {
            "tool": "resolve_client",
            "data": {
                "matches": [
                    {
                        "client_id": rows[0]["client_id"],
                        "client_name": rows[0]["client_name"],
                        "confidence": "exact_id",
                    }
                ]
            },
            "row_ids": [rows[0]["client_id"]],
        }

    rows = _query(
        "SELECT client_id, client_name FROM clients WHERE LOWER(client_name) = LOWER(?)",
        (q,),
    )
    if rows:
        return {
            "tool": "resolve_client",
            "data": {
                "matches": [
                    {
                        "client_id": rows[0]["client_id"],
                        "client_name": rows[0]["client_name"],
                        "confidence": "exact_name",
                    }
                ]
            },
            "row_ids": [rows[0]["client_id"]],
        }

    all_clients = _query(
        "SELECT client_id, client_name FROM clients ORDER BY client_id"
    )
    scored = []
    q_lower = q.lower()
    for c in all_clients:
        name_lower = c["client_name"].lower()
        if q_lower in name_lower:
            scored.append({**c, "confidence": "partial", "score": 0.9})
        else:
            ratio = SequenceMatcher(None, q_lower, name_lower).ratio()
            if ratio > 0.4:
                scored.append({**c, "confidence": "fuzzy", "score": ratio})
    scored.sort(key=lambda x: x["score"], reverse=True)
    matches = [
        {
            "client_id": s["client_id"],
            "client_name": s["client_name"],
            "confidence": s["confidence"],
        }
        for s in scored[:5]
    ]
    return {
        "tool": "resolve_client",
        "data": {"query": q, "matches": matches},
        "row_ids": [m["client_id"] for m in matches],
    }


def get_client_profile(client_id):
    rows = _query("SELECT * FROM clients WHERE client_id = ?", (client_id,))
    if not rows:
        return {
            "tool": "get_client_profile",
            "client_id": client_id,
            "data": None,
            "row_ids": [],
        }
    return {
        "tool": "get_client_profile",
        "client_id": client_id,
        "data": dict(rows[0]),
        "row_ids": [client_id],
    }


def get_contract_status(client_id, as_of=AS_OF):
    as_of_date = _parse_date(as_of)

    active = _query(
        f"""
        WITH {DEDUP_CONTRACTS}
        SELECT * FROM contracts_deduped
        WHERE client_id = ? AND status = 'active'
        ORDER BY end_date DESC
    """,
        (client_id,),
    )

    pending = _query(
        f"""
        WITH {DEDUP_CONTRACTS}
        SELECT * FROM contracts_deduped
        WHERE client_id = ? AND status = 'pending_signature'
    """,
        (client_id,),
    )

    row_ids = []
    contracts_out = []
    for c in active:
        cid = c["contract_id"]
        row_ids.append(cid)
        end_d = _parse_date(c["end_date"])
        days_to_end = (end_d - as_of_date).days if end_d else None
        notice_deadline = (
            (end_d - timedelta(days=c["notice_period_days"]))
            if end_d and c["notice_period_days"]
            else None
        )
        notice_passed = notice_deadline < as_of_date if notice_deadline else None

        lines = _query(
            """
            SELECT line_id, product_id,
                   CAST(annual_fee_eur AS INTEGER) AS annual_fee_eur,
                   CAST(included_units_monthly AS INTEGER) AS included_units_monthly,
                   CAST(overage_rate_eur_per_unit AS REAL) AS overage_rate_eur
            FROM contract_lines WHERE contract_id = ?
            ORDER BY line_id
        """,
            (cid,),
        )
        for ln in lines:
            row_ids.append(ln["line_id"])

        prev = _query(
            f"""
            WITH {DEDUP_CONTRACTS}
            SELECT arr_eur FROM contracts_deduped
            WHERE client_id = ? AND contract_id != ? AND status = 'expired'
            ORDER BY end_date DESC LIMIT 1
        """,
            (client_id, cid),
        )
        prev_arr = prev[0]["arr_eur"] if prev else None
        arr_change_pct = (
            round((c["arr_eur"] - prev_arr) / prev_arr * 100, 1) if prev_arr else None
        )

        days_until_notice = (
            (notice_deadline - as_of_date).days
            if notice_deadline and not notice_passed
            else None
        )

        contracts_out.append(
            {
                "contract_id": cid,
                "contract_type": c["contract_type"],
                "start_date": c["start_date"],
                "end_date": c["end_date"],
                "days_to_end": days_to_end,
                "notice_deadline": str(notice_deadline) if notice_deadline else None,
                "days_until_notice": days_until_notice,
                "notice_passed": notice_passed,
                "auto_renew": c["auto_renew"],
                "arr_eur": c["arr_eur"],
                "products": [dict(ln) for ln in lines],
                "prev_arr_eur": prev_arr,
                "arr_change_pct": arr_change_pct,
            }
        )

    pending_out = []
    for p in pending:
        row_ids.append(p["contract_id"])
        pending_out.append(
            {
                "contract_id": p["contract_id"],
                "arr_eur": p["arr_eur"],
                "start_date": p["start_date"],
                "end_date": p["end_date"],
                "status": p["status"],
            }
        )

    return {
        "tool": "get_contract_status",
        "client_id": client_id,
        "data": {
            "active_contracts": contracts_out,
            "pending_contracts": pending_out,
            "total_arr": sum(c["arr_eur"] for c in contracts_out),
            "has_active_contract": len(contracts_out) > 0,
        },
        "row_ids": row_ids,
    }


def get_usage_trend(client_id, as_of=AS_OF, product_id=None):
    last_m = _last_month(as_of)
    params = [client_id]
    pf = ""
    if product_id:
        pf = "AND ud.product_id = ?"
        params.append(product_id)

    rows = _query(
        f"""
        WITH {DEDUP_USAGE}
        SELECT ud.*, p.usage_unit, p.product_name
        FROM usage_deduped ud
        JOIN products p ON p.product_id = ud.product_id
        WHERE ud.client_id = ? {pf}
        ORDER BY ud.product_id, ud.month
    """,
        params,
    )

    if not rows:
        return {
            "tool": "get_usage_trend",
            "client_id": client_id,
            "data": {"products": {}},
            "row_ids": [],
        }

    by_product = defaultdict(list)
    row_ids = []
    for r in rows:
        by_product[r["product_id"]].append(r)
        row_ids.append(r["usage_id"])

    products_out = {}
    for pid, records in by_product.items():
        monthly = [
            {
                "month": r["month"],
                "units_used": r["units_used"],
                "included_units": r["included_units"],
                "utilization_pct": round(r["units_used"] / r["included_units"] * 100, 1)
                if r["included_units"]
                else None,
                "usage_id": r["usage_id"],
            }
            for r in records
        ]

        all_months = sorted(set(r["month"] for r in records))
        recent_months = [m for m in all_months if m <= last_m][-6:]
        lookup = {r["month"]: r["units_used"] for r in records}

        yoy_change = None
        if len(recent_months) >= 3:
            pairs = []
            for m in recent_months:
                y, mo = m.split("-")
                prior_m = f"{int(y) - 1}-{mo}"
                if prior_m in lookup:
                    pairs.append((lookup[prior_m], lookup[m]))
            if pairs:
                prior_sum = sum(p for p, _ in pairs)
                current_sum = sum(c for _, c in pairs)
                if prior_sum > 0:
                    yoy_change = round((current_sum - prior_sum) / prior_sum * 100, 1)

        period_change = None
        recent_3 = recent_months[-3:] if len(recent_months) >= 3 else recent_months
        prior_3 = recent_months[-6:-3] if len(recent_months) >= 6 else []
        if recent_3 and prior_3:
            r3 = sum(lookup[m] for m in recent_3) / len(recent_3)
            p3 = sum(lookup[m] for m in prior_3) / len(prior_3)
            if p3 > 0:
                period_change = round((r3 - p3) / p3 * 100, 1)

        over_included = [
            r["month"]
            for r in records
            if r["included_units"] and r["units_used"] > r["included_units"]
        ]

        recent_with_inc = [
            r for r in records if r["month"] in recent_months and r["included_units"]
        ]
        avg_util = (
            round(
                sum(r["units_used"] / r["included_units"] for r in recent_with_inc)
                / len(recent_with_inc)
                * 100,
                1,
            )
            if recent_with_inc
            else None
        )

        gaps = []
        if len(all_months) >= 2:
            expected = _months_between(all_months[0], all_months[-1])
            gaps = [mo for mo in expected if mo not in set(all_months)]

        products_out[pid] = {
            "product_name": records[0]["product_name"],
            "usage_unit": records[0]["usage_unit"],
            "monthly": monthly,
            "months_of_data": len(records),
            "yoy_change_pct": yoy_change,
            "recent_vs_prior_pct": period_change,
            "months_over_included": len(over_included),
            "over_included_months": over_included,
            "avg_utilization_pct": avg_util,
            "data_gaps": gaps,
        }

    return {
        "tool": "get_usage_trend",
        "client_id": client_id,
        "data": {"products": products_out},
        "row_ids": row_ids,
    }


def get_whitespace(client_id):
    client = _query("SELECT segment FROM clients WHERE client_id = ?", (client_id,))
    if not client:
        return {
            "tool": "get_whitespace",
            "client_id": client_id,
            "data": None,
            "row_ids": [],
        }
    segment = client[0]["segment"]

    held = _query(
        f"""
        WITH {DEDUP_CONTRACTS}
        SELECT DISTINCT cl.product_id
        FROM contract_lines cl
        JOIN contracts_deduped c ON c.contract_id = cl.contract_id
        WHERE c.client_id = ? AND c.status = 'active'
    """,
        (client_id,),
    )
    held_ids = set(r["product_id"] for r in held)

    all_products = _query("SELECT * FROM products ORDER BY product_id")

    peer_products = _query(
        f"""
        WITH {DEDUP_CONTRACTS}
        SELECT cl.product_id, COUNT(DISTINCT c.client_id) AS peer_count
        FROM contract_lines cl
        JOIN contracts_deduped c ON c.contract_id = cl.contract_id
        JOIN clients cli ON cli.client_id = c.client_id
        WHERE cli.segment = ? AND c.client_id != ? AND c.status = 'active'
        GROUP BY cl.product_id
    """,
        (segment, client_id),
    )
    peer_count = {r["product_id"]: r["peer_count"] for r in peer_products}

    total_peers = _query(
        "SELECT COUNT(*) AS cnt FROM clients WHERE segment = ? AND client_id != ?",
        (segment, client_id),
    )[0]["cnt"]

    opps = _query(
        """
        SELECT opp_id, product_id, stage, CAST(amount_eur AS INTEGER) AS amount_eur
        FROM crm_opportunities
        WHERE client_id = ? AND product_id IS NOT NULL AND product_id != ''
    """,
        (client_id,),
    )
    opp_by_product = defaultdict(list)
    opp_ids = []
    for o in opps:
        opp_by_product[o["product_id"]].append(o)
        opp_ids.append(o["opp_id"])

    gaps = []
    for p in all_products:
        pid = p["product_id"]
        if pid in held_ids:
            continue
        typical_segs = p["typical_segments"].split(";") if p["typical_segments"] else []
        related_to_held = [
            rel for rel in (p["often_bought_with"] or "").split(";") if rel in held_ids
        ]
        gaps.append(
            {
                "product_id": pid,
                "product_name": p["product_name"],
                "is_typical_for_segment": segment in typical_segs,
                "peers_holding": peer_count.get(pid, 0),
                "total_peers": total_peers,
                "related_to_held": related_to_held,
                "existing_opportunities": opp_by_product.get(pid, []),
            }
        )
    gaps.sort(key=lambda g: (not g["is_typical_for_segment"], -g["peers_holding"]))

    return {
        "tool": "get_whitespace",
        "client_id": client_id,
        "data": {
            "segment": segment,
            "held_products": sorted(held_ids),
            "gaps": gaps,
            "total_peers_in_segment": total_peers,
        },
        "row_ids": sorted(held_ids) + [g["product_id"] for g in gaps] + opp_ids,
    }


def get_support_summary(client_id, as_of=AS_OF, window_days=365):
    as_of_date = _parse_date(as_of)
    window_start = str(as_of_date - timedelta(days=window_days))
    prev_start = str(as_of_date - timedelta(days=window_days * 2))

    current = _query(
        f"""
        WITH {DEDUP_TICKETS}
        SELECT * FROM tickets_deduped
        WHERE client_id = ? AND opened_date >= ? AND opened_date < ?
        ORDER BY ticket_id
    """,
        (client_id, window_start, as_of),
    )

    previous = _query(
        f"""
        WITH {DEDUP_TICKETS}
        SELECT * FROM tickets_deduped
        WHERE client_id = ? AND opened_date >= ? AND opened_date < ?
        ORDER BY ticket_id
    """,
        (client_id, prev_start, window_start),
    )

    open_tickets = _query(
        f"""
        WITH {DEDUP_TICKETS}
        SELECT * FROM tickets_deduped
        WHERE client_id = ? AND status = 'open'
        ORDER BY ticket_id
    """,
        (client_id,),
    )

    row_ids = sorted(set(t["ticket_id"] for t in current + open_tickets))

    by_priority = {}
    by_category = {}
    for t in current:
        by_priority[t["priority"]] = by_priority.get(t["priority"], 0) + 1
        by_category[t["category"]] = by_category.get(t["category"], 0) + 1

    prev_by_priority = {}
    for t in previous:
        prev_by_priority[t["priority"]] = prev_by_priority.get(t["priority"], 0) + 1

    closed_current = [t for t in current if t["status"] == "closed"]
    csat_scores = [
        int(t["csat_score"])
        for t in closed_current
        if t["csat_score"] and t["csat_score"].strip()
    ]
    avg_csat = round(sum(csat_scores) / len(csat_scores), 2) if csat_scores else None
    csat_response_rate = (
        round(len(csat_scores) / len(closed_current) * 100, 1)
        if closed_current
        else None
    )

    prev_csat = [
        int(t["csat_score"])
        for t in previous
        if t["csat_score"] and t["csat_score"].strip()
    ]
    prev_avg_csat = round(sum(prev_csat) / len(prev_csat), 2) if prev_csat else None

    notable = []
    for t in current:
        if t["priority"] in ("P1", "P2") or (
            t["csat_score"] and t["csat_score"].strip() and int(t["csat_score"]) <= 2
        ):
            notable.append(
                {
                    "ticket_id": t["ticket_id"],
                    "priority": t["priority"],
                    "category": t["category"],
                    "subject": t["subject"],
                    "product_id": t["product_id"],
                    "status": t["status"],
                    "csat_score": int(t["csat_score"])
                    if t["csat_score"] and t["csat_score"].strip()
                    else None,
                }
            )

    return {
        "tool": "get_support_summary",
        "client_id": client_id,
        "data": {
            "window": {"start": window_start, "end": as_of, "days": window_days},
            "total_tickets": len(current),
            "by_priority": by_priority,
            "by_category": by_category,
            "prev_window_total": len(previous),
            "prev_by_priority": prev_by_priority,
            "ticket_change_abs": len(current) - len(previous),
            "change_pct": round((len(current) - len(previous)) / len(previous) * 100, 1)
            if previous
            else None,
            "open_tickets": [
                {
                    "ticket_id": t["ticket_id"],
                    "priority": t["priority"],
                    "category": t["category"],
                    "subject": t["subject"],
                    "product_id": t["product_id"],
                    "opened_date": t["opened_date"],
                }
                for t in open_tickets
            ],
            "avg_csat": avg_csat,
            "csat_response_rate": csat_response_rate,
            "csat_responses": len(csat_scores),
            "prev_avg_csat": prev_avg_csat,
            "csat_change": round(avg_csat - prev_avg_csat, 2)
            if avg_csat is not None and prev_avg_csat is not None
            else None,
            "notable_tickets": notable,
        },
        "row_ids": row_ids,
    }


def get_opportunities(client_id):
    rows = _query(
        """
        SELECT opp_id, client_id, opp_type, product_id, stage,
               CAST(amount_eur AS INTEGER) AS amount_eur,
               created_date, expected_close_date, owner, next_step
        FROM crm_opportunities WHERE client_id = ?
        ORDER BY expected_close_date
    """,
        (client_id,),
    )
    open_opps = [r for r in rows if r["stage"] not in ("Closed Won", "Closed Lost")]
    total_pipeline = sum(r["amount_eur"] for r in open_opps)

    current_arr = _query(
        f"""
        WITH {DEDUP_CONTRACTS}
        SELECT SUM(arr_eur) AS total_arr FROM contracts_deduped
        WHERE client_id = ? AND status = 'active'
    """,
        (client_id,),
    )
    arr = (
        current_arr[0]["total_arr"]
        if current_arr and current_arr[0]["total_arr"]
        else None
    )
    arr_vs_pipeline = arr - total_pipeline if arr is not None else None

    return {
        "tool": "get_opportunities",
        "client_id": client_id,
        "data": {
            "opportunities": [dict(r) for r in rows],
            "open_count": len(open_opps),
            "total_pipeline_eur": total_pipeline,
            "current_arr_eur": arr,
            "arr_vs_pipeline_gap": arr_vs_pipeline,
        },
        "row_ids": [r["opp_id"] for r in rows],
    }


def get_meeting_notes(client_id):
    rows = _query(
        """
        SELECT note_id, client_id, meeting_date, author, title, body
        FROM meeting_notes WHERE client_id = ?
        ORDER BY meeting_date DESC
    """,
        (client_id,),
    )
    return {
        "tool": "get_meeting_notes",
        "client_id": client_id,
        "data": {"notes": [dict(r) for r in rows], "count": len(rows)},
        "row_ids": [r["note_id"] for r in rows],
    }


def check_data_quality(client_id):
    issues = []
    row_ids = []

    for label, tbl, col in [
        ("contract", "contracts", "contract_id"),
        ("ticket", "support_tickets", "ticket_id"),
    ]:
        dups = _query(
            f"SELECT {col}, COUNT(*) AS cnt FROM {tbl} WHERE client_id = ? GROUP BY {col} HAVING cnt > 1",
            (client_id,),
        )
        for d in dups:
            issues.append(
                {
                    "type": f"duplicate_{label}",
                    "detail": f"{d[col]} appears {d['cnt']} times",
                }
            )
            row_ids.append(d[col])

    dup_usage = _query(
        "SELECT product_id, month, COUNT(*) AS cnt FROM usage_monthly WHERE client_id = ? GROUP BY client_id, product_id, month HAVING cnt > 1",
        (client_id,),
    )
    for d in dup_usage:
        issues.append(
            {
                "type": "duplicate_usage",
                "detail": f"{d['product_id']} {d['month']} has {d['cnt']} rows",
            }
        )

    usage_ranges = _query(
        "SELECT product_id, MIN(month) AS first_m, MAX(month) AS last_m, COUNT(DISTINCT month) AS actual FROM usage_monthly WHERE client_id = ? GROUP BY product_id",
        (client_id,),
    )
    for ur in usage_ranges:
        expected = len(_months_between(ur["first_m"], ur["last_m"]))
        if ur["actual"] < expected:
            issues.append(
                {
                    "type": "missing_months",
                    "detail": f"{ur['product_id']}: {expected - ur['actual']} missing month(s) between {ur['first_m']} and {ur['last_m']}",
                }
            )
        if ur["actual"] < 6:
            issues.append(
                {
                    "type": "short_history",
                    "detail": f"{ur['product_id']}: only {ur['actual']} months of data",
                }
            )

    active = _query(
        f"WITH {DEDUP_CONTRACTS} SELECT contract_id FROM contracts_deduped WHERE client_id = ? AND status = 'active'",
        (client_id,),
    )
    pending_q = _query(
        f"WITH {DEDUP_CONTRACTS} SELECT contract_id FROM contracts_deduped WHERE client_id = ? AND status = 'pending_signature'",
        (client_id,),
    )
    if not active:
        detail = (
            "No active contract; pending exists"
            if pending_q
            else "No active or pending contract"
        )
        issues.append({"type": "contract_gap", "detail": detail})

    tickets = _query(
        f"""
        WITH {DEDUP_TICKETS}
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status='closed' AND (csat_score IS NULL OR csat_score='') THEN 1 ELSE 0 END) AS blank_csat
        FROM tickets_deduped WHERE client_id = ?
    """,
        (client_id,),
    )
    if tickets and tickets[0]["blank_csat"]:
        issues.append(
            {
                "type": "blank_csat",
                "detail": f"{tickets[0]['blank_csat']} closed tickets have no CSAT score",
            }
        )

    notes = _query(
        "SELECT COUNT(*) AS cnt FROM meeting_notes WHERE client_id = ?", (client_id,)
    )
    if not notes or notes[0]["cnt"] == 0:
        issues.append(
            {
                "type": "no_meeting_notes",
                "detail": "No meeting notes available for this client",
            }
        )

    return {
        "tool": "check_data_quality",
        "client_id": client_id,
        "data": {"issues": issues, "issue_count": len(issues)},
        "row_ids": row_ids,
    }


def get_peer_comparison(client_id, as_of=AS_OF):
    client = _query("SELECT segment FROM clients WHERE client_id = ?", (client_id,))
    if not client:
        return {
            "tool": "get_peer_comparison",
            "client_id": client_id,
            "data": None,
            "row_ids": [],
        }
    segment = client[0]["segment"]

    peers = _query(
        f"""
        WITH {DEDUP_CONTRACTS},
        client_arr AS (
            SELECT client_id, SUM(arr_eur) AS total_arr
            FROM contracts_deduped WHERE status = 'active'
            GROUP BY client_id
        ),
        client_products AS (
            SELECT c.client_id, COUNT(DISTINCT cl.product_id) AS product_count
            FROM contracts_deduped c
            JOIN contract_lines cl ON cl.contract_id = c.contract_id
            WHERE c.status = 'active'
            GROUP BY c.client_id
        )
        SELECT cli.client_id, cli.client_name, cli.tier,
               ca.total_arr, COALESCE(cp.product_count, 0) AS product_count
        FROM clients cli
        JOIN client_arr ca ON ca.client_id = cli.client_id
        LEFT JOIN client_products cp ON cp.client_id = cli.client_id
        WHERE cli.segment = ?
        ORDER BY cli.client_id
    """,
        (segment,),
    )

    if not peers:
        return {
            "tool": "get_peer_comparison",
            "client_id": client_id,
            "data": {"segment": segment, "peers": []},
            "row_ids": [],
        }

    last_m = _last_month(as_of)
    y, m = map(int, last_m.split("-"))
    months_3 = []
    for _ in range(3):
        months_3.append(f"{y}-{m:02d}")
        m -= 1
        if m < 1:
            m = 12
            y -= 1

    peer_ids = [p["client_id"] for p in peers]
    ph_peers = ",".join("?" * len(peer_ids))
    ph_months = ",".join("?" * len(months_3))

    util_rows = _query(
        f"""
        WITH {DEDUP_USAGE}
        SELECT client_id,
               AVG(CASE WHEN included_units > 0 THEN units_used / included_units * 100 ELSE NULL END) AS avg_util
        FROM usage_deduped
        WHERE client_id IN ({ph_peers}) AND month IN ({ph_months})
        GROUP BY client_id
    """,
        peer_ids + months_3,
    )
    util_map = {
        r["client_id"]: round(r["avg_util"], 1) if r["avg_util"] is not None else None
        for r in util_rows
    }

    this_client = None
    peer_list = []
    for p in peers:
        entry = {
            "client_id": p["client_id"],
            "client_name": p["client_name"],
            "tier": p["tier"],
            "total_arr": p["total_arr"],
            "product_count": p["product_count"],
            "avg_utilization_pct": util_map.get(p["client_id"]),
        }
        if p["client_id"] == client_id:
            this_client = entry
        peer_list.append(entry)

    arrs = [p["total_arr"] for p in peer_list]
    prods = [p["product_count"] for p in peer_list]
    utils = [
        p["avg_utilization_pct"]
        for p in peer_list
        if p["avg_utilization_pct"] is not None
    ]

    arr_rank = None
    if this_client:
        sorted_arr = sorted(peer_list, key=lambda x: x["total_arr"], reverse=True)
        arr_rank = next(
            i + 1 for i, p in enumerate(sorted_arr) if p["client_id"] == client_id
        )

    return {
        "tool": "get_peer_comparison",
        "client_id": client_id,
        "data": {
            "segment": segment,
            "this_client": this_client,
            "peer_count": len(peer_list) - 1,
            "segment_avg_arr": round(sum(arrs) / len(arrs)) if arrs else None,
            "segment_min_arr": min(arrs) if arrs else None,
            "segment_max_arr": max(arrs) if arrs else None,
            "segment_avg_products": round(sum(prods) / len(prods), 1)
            if prods
            else None,
            "segment_avg_utilization": round(sum(utils) / len(utils), 1)
            if utils
            else None,
            "arr_rank": arr_rank,
            "arr_rank_of": len(peer_list),
            "peers": [p for p in peer_list if p["client_id"] != client_id],
        },
        "row_ids": peer_ids,
    }


TOOL_REGISTRY = {
    "resolve_client": resolve_client,
    "get_client_profile": get_client_profile,
    "get_contract_status": get_contract_status,
    "get_usage_trend": get_usage_trend,
    "get_whitespace": get_whitespace,
    "get_support_summary": get_support_summary,
    "get_opportunities": get_opportunities,
    "get_meeting_notes": get_meeting_notes,
    "check_data_quality": check_data_quality,
    "get_peer_comparison": get_peer_comparison,
}

TOOL_DESCRIPTIONS = {
    "get_client_profile": "Client segment, country, owner, tier, customer_since",
    "get_contract_status": "Active/pending contracts, ARR, end date, notice deadline, days_until_notice, auto-renew, products, ARR change at last renewal",
    "get_usage_trend": "Monthly usage per product, utilization vs included, YoY change, period trend, overages, data gaps",
    "get_whitespace": "Products the client does not hold, segment peer adoption, related products, existing opportunities",
    "get_support_summary": "Ticket counts by priority/category, open tickets, CSAT, csat_change, ticket_change_abs, change vs prior window, notable tickets",
    "get_opportunities": "Open and recently closed CRM opportunities with stage, amount, next steps, current_arr_eur, arr_vs_pipeline_gap",
    "get_meeting_notes": "Meeting note text with IDs and dates",
    "check_data_quality": "Duplicates, missing months, short history, contract gaps, blank fields for this client",
    "get_peer_comparison": "Client's ARR, usage, product count vs segment peers; ranking and averages",
}


def run_tool(tool_name, **kwargs):
    fn = TOOL_REGISTRY.get(tool_name)
    if not fn:
        return {
            "tool": tool_name,
            "error": f"Unknown tool: {tool_name}",
            "data": None,
            "row_ids": [],
        }
    return fn(**kwargs)
