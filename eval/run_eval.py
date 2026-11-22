"""Eval runner: 6 cases, 3 clients x 2 triggers.

Layer 1 (free, no LLM): expected facts from cases.yaml vs actual tool outputs.
Layer 2 (--full, costs money): full pipeline + ungrounded number check on briefing.

    uv run eval/run_eval.py                # layer 1 only, free
    uv run eval/run_eval.py --full         # both layers
    uv run eval/run_eval.py --full --report # both layers + write eval/report.md
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "Aster_business_analyst"))

from yaml import safe_load

from tools import (
    resolve_client,
    get_client_profile,
    get_contract_status,
    get_support_summary,
    get_opportunities,
    get_meeting_notes,
    get_whitespace,
)
from agent import (
    plan,
    run_tools,
    write_claims,
    verify_claims,
    render_briefing,
    save_evidence,
    judge,
    rewrite_claims,  # noqa: F401
    judge_needs_retry,  # noqa: F401
    judge_feedback,  # noqa: F401
)

CASES_PATH = Path(__file__).parent / "cases.yaml"
REPORT_PATH = Path(__file__).parent / "report.md"


def gather_facts(client_id, as_of):
    """Run all tools and extract key facts as a flat dict."""
    contracts = get_contract_status(client_id, as_of)
    profile = get_client_profile(client_id)
    support = get_support_summary(client_id, as_of)
    opps = get_opportunities(client_id)
    notes = get_meeting_notes(client_id)

    facts = {}
    facts["segment"] = profile["data"].get("segment") if profile["data"] else None
    facts["tier"] = profile["data"].get("tier") if profile["data"] else None

    cd = contracts["data"]
    facts["total_arr"] = cd.get("total_arr")
    if cd.get("active_contracts"):
        ac = cd["active_contracts"][0]
        facts["contract_end"] = ac.get("end_date")
        facts["notice_deadline"] = ac.get("notice_deadline")
        facts["days_until_notice"] = ac.get("days_until_notice")
        facts["auto_renew"] = ac.get("auto_renew")

    sd = support["data"]
    facts["open_tickets"] = len(sd.get("open_tickets", []))
    facts["avg_csat"] = sd.get("avg_csat")
    facts["total_tickets_current"] = sd.get("total_tickets")
    facts["total_tickets"] = sd.get("total_tickets")
    facts["ticket_change_pct"] = sd.get("change_pct")

    od = opps["data"]
    open_opps = [
        o
        for o in od.get("opportunities", [])
        if o["stage"] not in ("Closed Won", "Closed Lost")
    ]
    if open_opps:
        facts["renewal_opp_amount"] = open_opps[0]["amount_eur"]
        facts["open_opp_amount"] = open_opps[0]["amount_eur"]
    facts["arr_vs_pipeline_gap"] = od.get("arr_vs_pipeline_gap")

    facts["meeting_note_count"] = notes["data"].get("count")

    ws = get_whitespace(client_id)
    facts["products_held"] = len(ws["data"].get("held_products", []))

    return facts


def compare(case, as_of):
    """Compare expected facts against actual tool output."""
    resolved = resolve_client(case["client"])
    matches = resolved["data"].get("matches", [])
    if not matches:
        return ["did not resolve"]
    top = matches[0]
    if top["client_id"] != case["expect"]["client_id"]:
        return [
            f"resolved to {top['client_id']}, expected {case['expect']['client_id']}"
        ]

    actual = gather_facts(top["client_id"], as_of)
    problems = []
    for key, expected in case["facts"].items():
        got = actual.get(key)
        if not _same(expected, got):
            problems.append(f"{key}: expected {expected!r}, got {got!r}")
    return problems


def _same(expected, actual):
    if expected is None or actual is None:
        return expected is None and actual is None
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) < 0.05
    return str(expected).strip() == str(actual).strip()


def _numbers_in(text):
    """Extract all numbers from a string, ignoring dates and prefixed IDs."""
    text = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text)
    text = re.sub(r"[A-Z]-\d+", " ", text)
    return [float(m) for m in re.findall(r"-?\d[\d,]*\.?\d*", text.replace(",", ""))]


def ungrounded_check(briefing_md, tool_results):
    """Find numbers in the briefing that don't appear in any tool output."""
    all_nums = set()
    for result in tool_results.values():
        all_nums.update(_extract_all_numbers(result.get("data", {})))

    found = []
    for line in briefing_md.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        for num in _numbers_in(line):
            matched = False
            for sn in all_nums:
                if abs(num - sn) < 0.5:
                    matched = True
                    break
            if not matched and abs(num) > 1:
                found.append(f"{num} in: {line.strip()[:90]}")
    return found


def _extract_all_numbers(obj):
    nums = set()
    if isinstance(obj, dict):
        for v in obj.values():
            nums.update(_extract_all_numbers(v))
    elif isinstance(obj, list):
        for v in obj:
            nums.update(_extract_all_numbers(v))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        nums.add(obj)
        if isinstance(obj, float) and obj == int(obj):
            nums.add(int(obj))
    elif isinstance(obj, str):
        for m in re.findall(r"-?\d+\.?\d*", obj):
            try:
                nums.add(float(m))
            except ValueError:
                pass
    return nums


def run_briefing(case, as_of):
    """Full pipeline for one case."""
    import time

    resolved = resolve_client(case["client"])
    client_id = resolved["data"]["matches"][0]["client_id"]
    profile = get_client_profile(client_id)
    client_data = profile["data"]

    pipeline_start = time.time()
    steps = []

    t0 = time.time()
    tool_names = plan(client_data, case["trigger"], case.get("context", ""))
    steps.append(("plan", time.time() - t0, None))

    t0 = time.time()
    tool_results = run_tools(tool_names, client_id)
    steps.append(("tools", time.time() - t0, f"{len(tool_names)} tools"))

    t0 = time.time()
    raw_claims = write_claims(
        case["trigger"], client_data, tool_results, case.get("context", "")
    )
    steps.append(("write", time.time() - t0, f"{len(raw_claims)} claims"))

    t0 = time.time()
    verified = verify_claims(raw_claims, tool_results)
    passed = sum(1 for c in verified if c["verification"] == "passed")
    flagged = sum(1 for c in verified if c["verification"] == "flagged")
    steps.append(("verify", time.time() - t0, f"{passed} passed, {flagged} flagged"))

    t0 = time.time()
    briefing = render_briefing(verified, client_data, case["trigger"], tool_results)
    steps.append(("render", time.time() - t0, None))

    out_dir = os.path.join("output", f"{client_id}_{case['trigger']}")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "briefing.md"), "w") as f:
        f.write(briefing)
    save_evidence(tool_results, verified, out_dir)

    t0 = time.time()
    evidence_summary = json.dumps(
        {
            k: list(v["data"].keys()) if isinstance(v["data"], dict) else "present"
            for k, v in tool_results.items()
        },
        indent=2,
    )
    scores = judge(briefing, case["trigger"], evidence_summary)
    steps.append(
        ("judge", time.time() - t0, f"overall: {scores.get('overall', '?')}/5")
    )

    retried = False
    if judge_needs_retry(scores):
        feedback = judge_feedback(scores)
        t0 = time.time()
        retry_claims = rewrite_claims(
            case["trigger"],
            client_data,
            tool_results,
            case.get("context", ""),
            feedback,
        )
        if retry_claims:
            steps.append(
                ("write_retry", time.time() - t0, f"{len(retry_claims)} claims")
            )
            t0 = time.time()
            verified = verify_claims(retry_claims, tool_results)
            passed = sum(1 for c in verified if c["verification"] == "passed")
            flagged = sum(1 for c in verified if c["verification"] == "flagged")
            steps.append(
                (
                    "verify_retry",
                    time.time() - t0,
                    f"{passed} passed, {flagged} flagged",
                )
            )
            t0 = time.time()
            briefing = render_briefing(
                verified, client_data, case["trigger"], tool_results
            )
            steps.append(("render_retry", time.time() - t0, None))
            with open(os.path.join(out_dir, "briefing.md"), "w") as f:
                f.write(briefing)
            save_evidence(tool_results, verified, out_dir)
            t0 = time.time()
            scores = judge(briefing, case["trigger"], evidence_summary)
            steps.append(
                (
                    "judge_retry",
                    time.time() - t0,
                    f"overall: {scores.get('overall', '?')}/5",
                )
            )
            retried = True

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "scores.json"), "w") as f:
        json.dump(scores, f, indent=2)

    total_elapsed = time.time() - pipeline_start

    trace = {
        "client_id": client_id,
        "trigger": case["trigger"],
        "steps": [
            {"step": n, "elapsed_s": round(e, 3), "detail": d} for n, e, d in steps
        ],
        "total_elapsed_s": round(total_elapsed, 3),
        "retried": retried,
        "llm_calls": 5 if retried else 3,
        "claims_total": len(verified),
        "claims_passed": passed,
        "claims_flagged": flagged,
        "judge_overall": scores.get("overall", "?"),
    }
    with open(os.path.join(out_dir, "trace.json"), "w") as f:
        json.dump(trace, f, indent=2)

    ungrounded = ungrounded_check(briefing, tool_results)

    return {
        "client_id": client_id,
        "trigger": case["trigger"],
        "claims": len(verified),
        "passed": passed,
        "flagged": flagged,
        "ungrounded": ungrounded,
        "judge_overall": scores.get("overall", "?"),
        "out_dir": out_dir,
    }


def generate_report(dataset, figure_results, briefing_results):
    lines = [
        "# Evaluation Report",
        "",
        f"{len(dataset['cases'])} cases, {len({c['expect']['client_id'] for c in dataset['cases']})} clients, as_of {dataset['as_of']}.",
        "",
        "## Layer 1: Figures (no model, free)",
        "",
        "Expected facts from `cases.yaml` vs actual tool outputs.",
        "",
        "| Case | Client | Trigger | Facts | Result |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case, problems in figure_results:
        count = len(case["facts"])
        verdict = f"**{len(problems)} wrong**" if problems else "all match"
        lines.append(
            f"| {case['id']} | {case['expect']['client_id']} | {case['trigger']} | {count} | {verdict} |"
        )

    if briefing_results:
        lines += [
            "",
            "## Layer 2: Briefings (end to end)",
            "",
            "Full pipeline run. Claim-level = verifier pass/fail. Briefing-level = ungrounded numbers in rendered markdown.",
            "",
            "| Case | Client | Trigger | Claims | Passed | Flagged | Ungrounded | Judge |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for case_id, row in briefing_results.items():
            lines.append(
                f"| {case_id} | {row['client_id']} | {row['trigger']} | {row['claims']}"
                f" | {row['passed']} | {row['flagged']} | {len(row['ungrounded'])} | {row['judge_overall']}/5 |"
            )

        failures = [
            (cid, r)
            for cid, r in briefing_results.items()
            if r["flagged"] > 0 or r["ungrounded"]
        ]
        if failures:
            lines += ["", "## What failed", ""]
            for case_id, row in failures:
                lines.append(f"### {case_id}")
                lines.append("")
                if row["flagged"] > 0:
                    lines.append(
                        f"- {row['flagged']} claims flagged by verifier (LLM-computed numbers not in tool output)"
                    )
                for item in row["ungrounded"]:
                    lines.append(f"- ungrounded: {item}")
                lines.append("")
        else:
            lines += [
                "",
                "## What failed",
                "",
                "Nothing. Every figure in every briefing resolves to the evidence.",
                "",
            ]

    return "\n".join(lines) + "\n"


def run_unit_tests():
    """Layer 0: run pytest on tool unit tests. Fail fast before spending LLM tokens."""
    import subprocess

    print("=" * 60)
    print("LAYER 0: Unit tests (pytest)")
    print("=" * 60)

    test_file = Path(__file__).parent.parent / "tests" / "test_tools.py"
    if not test_file.exists():
        print("  SKIP — tests/test_tools.py not found")
        return True

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        print("\nUnit tests failed. Fix before running eval.\n")
        return False
    return True


def main():
    if not run_unit_tests():
        return 1

    dataset = safe_load(CASES_PATH.read_text(encoding="utf-8"))
    as_of = dataset["as_of"]

    print("=" * 60)
    print("LAYER 1: Figures (no model)")
    print("=" * 60)

    figure_results = []
    failures = 0
    for case in dataset["cases"]:
        problems = compare(case, as_of)
        figure_results.append((case, problems))
        count = len(case["facts"])
        if problems:
            failures += 1
            print(
                f"  {case['id']:<12} {case['trigger']:<14} FAIL  {len(problems)}/{count} wrong"
            )
            for p in problems:
                print(f"    {p}")
        else:
            print(f"  {case['id']:<12} {case['trigger']:<14} OK    {count} facts match")

    print(f"\n{len(dataset['cases'])} cases, {failures} with wrong figures\n")

    briefing_results = {}
    if "--full" in sys.argv:
        print("=" * 60)
        print("LAYER 2: Briefings (end to end)")
        print("=" * 60)

        for case in dataset["cases"]:
            print(
                f"\n  Running {case['id']} ({case['expect']['client_id']} {case['trigger']})..."
            )
            row = run_briefing(case, as_of)
            briefing_results[case["id"]] = row
            print(
                f"    {row['claims']} claims, {row['passed']} passed, {row['flagged']} flagged, "
                f"{len(row['ungrounded'])} ungrounded, judge {row['judge_overall']}/5"
            )
            if row["ungrounded"]:
                for u in row["ungrounded"][:5]:
                    print(f"      {u}")
            print(f"    -> {row['out_dir']}")

        total_flagged = sum(r["flagged"] for r in briefing_results.values())
        total_claims = sum(r["claims"] for r in briefing_results.values())
        print(
            f"\n{len(briefing_results)} briefings, {total_claims} total claims, {total_flagged} flagged"
        )

    if "--report" in sys.argv:
        report_md = generate_report(dataset, figure_results, briefing_results)
        REPORT_PATH.write_text(report_md, encoding="utf-8")
        print(f"\nReport written to {REPORT_PATH}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
