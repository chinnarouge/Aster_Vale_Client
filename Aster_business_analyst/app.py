import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
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
    rewrite_claims,  # noqa: F401
    judge_needs_retry,  # noqa: F401
    judge_feedback,  # noqa: F401
)


st.set_page_config(page_title="Aster Vale · Client Intelligence", layout="wide")
st.title("Aster Vale · Client Intelligence")

col1, col2 = st.columns([1, 2])

with col1:
    client_input = st.text_input("Client (name or ID)", placeholder="Client name or ID")
    from config import TRIGGERS

    trigger_choice = st.radio("Trigger", TRIGGERS + ["Other"])
    if trigger_choice == "Other":
        trigger = st.text_input("Custom trigger", placeholder="e.g. quarterly_review")
    else:
        trigger = trigger_choice
    context = st.text_area(
        "Context (optional)",
        placeholder="Anything the data won't know, e.g. 'meeting is about the API outage'",
        height=80,
    )
    generate = st.button("Generate briefing", type="primary")

with col2:
    if generate:
        if not client_input:
            st.warning("Enter a client name or ID.")
            st.stop()
        with st.status("Generating briefing...", expanded=True) as status:
            st.write("Resolving client...")
            resolved = resolve_client(client_input)
            matches = resolved["data"]["matches"]

            if not matches:
                st.error(f"No client found matching '{client_input}'")
                st.stop()

            top = matches[0]
            if top["confidence"] == "fuzzy":
                st.error(f"Client not found: '{client_input}'")
                if matches:
                    st.write("Did you mean:")
                    for m in matches[:3]:
                        st.write(f"- {m['client_name']} ({m['client_id']})")
                st.stop()

            if top["confidence"] == "partial" and len(matches) > 1:
                st.warning(f"Multiple matches for '{client_input}':")
                for m in matches:
                    st.write(f"- {m['client_name']} ({m['client_id']})")
                st.write("Be more specific or use the client ID.")
                st.stop()

            client_id = top["client_id"]
            st.write(f"Matched: **{top['client_name']}** ({client_id})")

            profile = get_client_profile(client_id)
            if not profile["data"]:
                st.error(f"Client {client_id} not found in database")
                st.stop()
            client_data = profile["data"]

            st.write(f"Planning analysis for **{trigger}**...")
            tool_names = plan(client_data, trigger, context)
            st.write(f"Tools: {', '.join(tool_names)}")

            st.write("Running tools...")
            tool_results = run_tools(tool_names, client_id)

            st.write("Generating claims...")
            raw_claims = write_claims(trigger, client_data, tool_results, context)

            st.write("Verifying claims...")
            verified = verify_claims(raw_claims, tool_results)
            passed = sum(1 for c in verified if c["verification"] == "passed")
            flagged = sum(1 for c in verified if c["verification"] == "flagged")

            briefing = render_briefing(verified, client_data, trigger, tool_results)

            safe_trigger = re.sub(r"[^A-Za-z0-9_-]", "_", trigger)
            run_dir = os.path.join(OUTPUT_DIR, f"{client_id}_{safe_trigger}")
            os.makedirs(run_dir, exist_ok=True)
            briefing_path = os.path.join(run_dir, "briefing.md")
            with open(briefing_path, "w") as f:
                f.write(briefing)
            evidence_path = save_evidence(tool_results, verified, run_dir)

            st.write("Scoring briefing...")
            evidence_summary = json.dumps(
                {
                    k: list(v["data"].keys())
                    if isinstance(v["data"], dict)
                    else "present"
                    for k, v in tool_results.items()
                },
                indent=2,
            )
            scores = judge(briefing, trigger, evidence_summary)

            if judge_needs_retry(scores):
                st.write("Judge scored below threshold, retrying writer...")
                feedback = judge_feedback(scores)
                retry_claims = rewrite_claims(
                    trigger, client_data, tool_results, context, feedback
                )
                if retry_claims:
                    verified = verify_claims(retry_claims, tool_results)
                    passed = sum(1 for c in verified if c["verification"] == "passed")
                    flagged = sum(1 for c in verified if c["verification"] == "flagged")
                    briefing = render_briefing(
                        verified, client_data, trigger, tool_results
                    )
                    with open(briefing_path, "w") as f:
                        f.write(briefing)
                    save_evidence(tool_results, verified, run_dir)
                    scores = judge(briefing, trigger, evidence_summary)

            scores_path = os.path.join(run_dir, "scores.json")
            with open(scores_path, "w") as f:
                json.dump(scores, f, indent=2)

            status.update(
                label=f"Done — {passed} verified, {flagged} flagged", state="complete"
            )

        st.markdown(briefing)

        with st.expander(f"Evidence ({len(tool_results)} tools)", expanded=False):
            st.json(
                {
                    k: {"data": v["data"], "row_ids": v["row_ids"]}
                    for k, v in tool_results.items()
                }
            )

        with st.expander(f"Claims ({len(verified)} total)", expanded=False):
            st.json(verified)

        if "overall" in scores:
            with st.expander(
                f"Judge scores (overall: {scores['overall']}/5)", expanded=False
            ):
                st.json(scores)
