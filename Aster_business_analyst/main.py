import argparse
import json
import logging
import os
import sys
import time

from config import OUTPUT_DIR
from tools import resolve_client, get_client_profile
from agent import (
    plan,
    run_tools,
    write_claims,
    verify_claims,
    render_briefing,
    save_evidence,
    judge,
    llm_call_log,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("aster")


def main():
    parser = argparse.ArgumentParser(description="Aster Vale Client Intelligence Agent")
    parser.add_argument("--client", required=True, help="Client name or ID")
    parser.add_argument(
        "--trigger",
        required=True,
        help="Trigger: renewal, meeting_prep, upsell, at_risk, or any custom trigger",
    )
    parser.add_argument(
        "--context", default="", help="Optional context from the sales rep"
    )
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    args = parser.parse_args()

    pipeline_start = time.time()
    steps = []

    t0 = time.time()
    print(f"Resolving client: {args.client}")
    resolved = resolve_client(args.client)
    matches = resolved["data"]["matches"]
    if not matches:
        print(f"Client not found: '{args.client}'")
        sys.exit(1)
    top = matches[0]
    if top["confidence"] == "fuzzy":
        print(f"Client not found: '{args.client}'")
        suggestions = [f"  {m['client_name']} ({m['client_id']})" for m in matches[:3]]
        if suggestions:
            print("Did you mean:")
            for s in suggestions:
                print(s)
        sys.exit(1)
    if top["confidence"] == "partial" and len(matches) > 1:
        print(f"Multiple matches for '{args.client}':")
        for m in matches:
            print(f"  {m['client_name']} ({m['client_id']})")
        print("Be more specific or use the client ID.")
        sys.exit(1)
    client_id = top["client_id"]
    print(f"Matched: {top['client_name']} ({client_id})")

    profile = get_client_profile(client_id)
    if not profile["data"]:
        print(f"Client {client_id} not found in database")
        sys.exit(1)
    client_data = profile["data"]
    print(
        f"Segment: {client_data['segment']} | Tier: {client_data['tier']} | Owner: {client_data['account_owner']}"
    )
    steps.append(("resolve", time.time() - t0, None))

    t0 = time.time()
    print(f"\nPlanning analysis for trigger: {args.trigger}")
    tool_names = plan(client_data, args.trigger, args.context)
    print(f"Tools to run: {tool_names}")
    steps.append(("plan", time.time() - t0, None))

    t0 = time.time()
    print("\nRunning tools...")
    tool_results = run_tools(tool_names, client_id)
    steps.append(("tools", time.time() - t0, f"{len(tool_names)} tools"))

    t0 = time.time()
    print("\nGenerating claims...")
    raw_claims = write_claims(args.trigger, client_data, tool_results, args.context)
    print(f"Generated {len(raw_claims)} claims")
    steps.append(("write", time.time() - t0, f"{len(raw_claims)} claims"))

    t0 = time.time()
    print("Verifying claims...")
    verified = verify_claims(raw_claims, tool_results)
    passed = sum(1 for c in verified if c["verification"] == "passed")
    flagged = sum(1 for c in verified if c["verification"] == "flagged")
    print(f"Verified: {passed} passed, {flagged} flagged")
    steps.append(("verify", time.time() - t0, f"{passed} passed, {flagged} flagged"))

    t0 = time.time()
    briefing = render_briefing(verified, client_data, args.trigger, tool_results)
    run_dir = os.path.join(args.output_dir, f"{client_id}_{args.trigger}")
    os.makedirs(run_dir, exist_ok=True)
    briefing_path = os.path.join(run_dir, "briefing.md")
    with open(briefing_path, "w") as f:
        f.write(briefing)
    print(f"\nBriefing saved to {briefing_path}")
    evidence_path = save_evidence(tool_results, verified, run_dir)
    print(f"Evidence saved to {evidence_path}")
    steps.append(("render", time.time() - t0, None))

    t0 = time.time()
    print("\nScoring briefing...")
    evidence_summary = json.dumps(
        {
            k: list(v["data"].keys()) if isinstance(v["data"], dict) else "present"
            for k, v in tool_results.items()
        },
        indent=2,
    )
    scores = judge(briefing, args.trigger, evidence_summary)
    scores_path = os.path.join(run_dir, "scores.json")
    with open(scores_path, "w") as f:
        json.dump(scores, f, indent=2)
    print(f"Scores saved to {scores_path}")
    overall = scores.get("overall", "?")
    steps.append(("judge", time.time() - t0, f"overall: {overall}/5"))

    total_elapsed = time.time() - pipeline_start

    print("\n" + "=" * 60)
    print("TRACE SUMMARY")
    print("=" * 60)
    for name, elapsed, detail in steps:
        detail_str = f" ({detail})" if detail else ""
        logger.info(f"[STEP] {name:<10} | {elapsed:.2f}s{detail_str}")
    logger.info(f"[TOTAL] {total_elapsed:.2f}s | 3 LLM calls")
    if "overall" in scores:
        print(f"\nOverall score: {scores['overall']}/5")
    if "summary" in scores:
        print(f"Summary: {scores['summary']}")

    # Save trace to run directory
    trace = {
        "client_id": client_id,
        "trigger": args.trigger,
        "steps": [
            {"step": n, "elapsed_s": round(e, 3), "detail": d} for n, e, d in steps
        ],
        "total_elapsed_s": round(total_elapsed, 3),
        "llm_calls": list(llm_call_log),
        "claims_total": len(verified),
        "claims_passed": passed,
        "claims_flagged": flagged,
        "judge_overall": overall,
    }
    trace_path = os.path.join(run_dir, "trace.json")
    with open(trace_path, "w") as f:
        json.dump(trace, f, indent=2)
    logger.info(f"Trace saved to {trace_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
