import json
import logging
import os
import re
import time

import anthropic

from config import AS_OF, MODEL, ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, OUTPUT_DIR
from tools import TOOL_DESCRIPTIONS, run_tool

logger = logging.getLogger("aster")

COST_PER_MTK_IN = 15.0
COST_PER_MTK_OUT = 75.0

llm_call_log = []


def _call_llm(system, user, max_tokens=4096, label="llm"):
    kwargs = {"api_key": ANTHROPIC_API_KEY}
    if ANTHROPIC_BASE_URL:
        kwargs["base_url"] = ANTHROPIC_BASE_URL
    client = anthropic.Anthropic(**kwargs)
    t0 = time.time()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    elapsed = time.time() - t0
    usage = resp.usage
    cost = (
        usage.input_tokens * COST_PER_MTK_IN + usage.output_tokens * COST_PER_MTK_OUT
    ) / 1_000_000
    logger.info(
        f"[LLM] {label} | model={MODEL} | tokens_in={usage.input_tokens:,} tokens_out={usage.output_tokens:,} | {elapsed:.1f}s | ${cost:.4f}"
    )
    llm_call_log.append(
        {
            "label": label,
            "model": MODEL,
            "tokens_in": usage.input_tokens,
            "tokens_out": usage.output_tokens,
            "elapsed_s": round(elapsed, 3),
            "cost_usd": round(cost, 6),
        }
    )
    return resp.content[0].text


PLANNER_SYSTEM = f"""You are a planning agent for a client intelligence system at Aster Vale Sports Data.
Today's date (as_of) is {AS_OF}.

Given a client profile, a trigger, and optional rep context, decide which analysis tools to run.

Available tools and what each returns:
{json.dumps(TOOL_DESCRIPTIONS, indent=2)}

Reason about which tools are relevant for this specific trigger and client situation. Be selective — not every tool is needed for every trigger. A renewal does not need whitespace analysis. An upsell does not need a full support deep-dive unless the rep's context mentions support issues.

Pick only the tools that directly serve the trigger's purpose. Fewer focused tools produce a better briefing than running everything.

Always include check_data_quality — data gaps must be surfaced in every briefing.

Return ONLY a JSON array of tool names, nothing else."""


def plan(client_profile, trigger, rep_context=""):
    user_msg = f"""Client: {json.dumps(client_profile)}
Trigger: {trigger}
Rep context: {rep_context or "None provided"}

Return a JSON array of tool names to run."""

    raw = _call_llm(PLANNER_SYSTEM, user_msg, max_tokens=512, label="planner")
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Planner did not return a JSON array: {raw}")
    tools = json.loads(match.group())
    valid = [t for t in tools if t in TOOL_DESCRIPTIONS]
    if "check_data_quality" not in valid:
        valid.append("check_data_quality")
    return valid


def run_tools(tool_names, client_id):
    results = {}
    for name in tool_names:
        kwargs = {"client_id": client_id}
        if name in (
            "get_contract_status",
            "get_usage_trend",
            "get_support_summary",
            "get_peer_comparison",
        ):
            kwargs["as_of"] = AS_OF
        t0 = time.time()
        results[name] = run_tool(name, **kwargs)
        elapsed = time.time() - t0
        data = results[name].get("data", {})
        if isinstance(data, list):
            row_count = len(data)
        elif isinstance(data, dict):
            first_val = next(iter(data.values()), None)
            row_count = len(first_val) if isinstance(first_val, list) else 1
        else:
            row_count = 0
        logger.info(f"[TOOL] {name} | {row_count} rows | {elapsed:.3f}s")
    return results


WRITER_SYSTEM = f"""You are a briefing writer for Aster Vale Sports Data.
Today's date (as_of) is {AS_OF}. All money is EUR.

You receive tool outputs (structured data with row IDs) and must produce a JSON array of claims.

Each claim must be:
{{
  "section": one of "headline", "account_snapshot", "contract_position", "usage_trends", "growth_opportunities", "support_health", "relationship_context", "risks", "next_steps", "data_gaps",
  "claim": a clear statement for the sales rep,
  "numeric_values": [list of key numbers in the claim, as numbers not strings],
  "citations": [list of source IDs like "contracts:K-0002", "usage:U-00422", "ticket:T-0123", "opp:O-0001", "note:N-003", "product:WIDGETS"],
  "source_tool": the tool name that provided the data
}}

Rules:
- CRITICAL: Every number in your output MUST appear verbatim in the tool output data. Do not calculate, subtract, add, divide, halve, multiply, or derive new numbers. Do not build hypothetical scenarios with computed figures. If a tool says ARR is 752000 and an opportunity is 541500, say both numbers — do NOT output 210500 as the gap. Use only the numbers the tools give you, exactly as given.
- Use the exact numeric values from tool outputs.
- Cite specific row IDs from tool output row_ids.
- If tool data shows a conflict (e.g. meeting note contradicts usage data), report BOTH sides with citations to each.
- If data is missing or insufficient, say so explicitly in a data_gaps claim.
- Lead with what matters for the trigger.
- Keep claims factual and concise. No speculation.
- Include next_steps claims with concrete actions for the rep.
- Return ONLY the JSON array, no other text."""


CLAIM_REQUIRED_KEYS = {"section", "claim", "numeric_values", "citations", "source_tool"}


def _validate_claim(claim):
    if not isinstance(claim, dict):
        return None
    missing = CLAIM_REQUIRED_KEYS - claim.keys()
    if missing:
        return None
    if not isinstance(claim["numeric_values"], list):
        claim["numeric_values"] = []
    if not isinstance(claim["citations"], list):
        claim["citations"] = []
    if not isinstance(claim["claim"], str) or not claim["claim"].strip():
        return None
    if not claim["citations"]:
        claim["citations"] = []
        claim["_empty_citations"] = True
    return claim


def _summarize_for_writer(tool_results):
    """Strip raw rows, keep computed summaries + row_ids. Cuts writer input tokens ~80%."""
    out = {}
    for name, result in tool_results.items():
        data = result.get("data", {})
        row_ids = result.get("row_ids", [])

        if name == "get_usage_trend" and isinstance(data, dict) and "products" in data:
            products = {}
            for pid, pdata in data["products"].items():
                products[pid] = {k: v for k, v in pdata.items() if k != "monthly"}
                recent = pdata.get("monthly", [])[-3:]
                products[pid]["recent_months"] = [
                    {
                        "month": r["month"],
                        "units_used": r["units_used"],
                        "usage_id": r["usage_id"],
                    }
                    for r in recent
                ]
            out[name] = {"data": {"products": products}, "row_ids": row_ids}

        elif name == "get_support_summary" and isinstance(data, dict):
            slim = {k: v for k, v in data.items() if k != "open_tickets"}
            slim["open_tickets"] = [
                {
                    "ticket_id": t["ticket_id"],
                    "priority": t["priority"],
                    "subject": t["subject"],
                }
                for t in data.get("open_tickets", [])
            ]
            out[name] = {"data": slim, "row_ids": row_ids}

        elif name == "get_peer_comparison" and isinstance(data, dict):
            slim = {k: v for k, v in data.items() if k != "peers"}
            out[name] = {"data": slim, "row_ids": row_ids}

        elif name == "get_contract_status" and isinstance(data, dict):
            contracts = []
            for c in data.get("active_contracts", []):
                slim_c = {k: v for k, v in c.items() if k != "products"}
                slim_c["product_ids"] = [p["product_id"] for p in c.get("products", [])]
                slim_c["product_fees"] = {
                    p["product_id"]: p.get("annual_fee_eur")
                    for p in c.get("products", [])
                }
                contracts.append(slim_c)
            out[name] = {
                "data": {**data, "active_contracts": contracts},
                "row_ids": row_ids,
            }

        else:
            out[name] = {"data": data, "row_ids": row_ids}

    return out


def write_claims(trigger, client_profile, tool_results, rep_context=""):
    tool_data = _summarize_for_writer(tool_results)

    user_msg = f"""Trigger: {trigger}
Client: {json.dumps(client_profile)}
Rep context: {rep_context or "None provided"}

Tool outputs:
{json.dumps(tool_data, indent=2, default=str)}

Produce the JSON claims array."""

    raw = _call_llm(WRITER_SYSTEM, user_msg, max_tokens=8192, label="writer")
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Writer did not return a JSON array: {raw}")
    json_str = match.group()
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
    try:
        raw_claims = json.loads(json_str)
    except json.JSONDecodeError:
        last_brace = json_str.rfind("}")
        if last_brace > 0:
            truncated = json_str[: last_brace + 1] + "]"
            truncated = re.sub(r",\s*\]", "]", truncated)
            raw_claims = json.loads(truncated)
            print(
                f"  Warning: writer output was truncated, recovered {len(raw_claims)} claims"
            )
        else:
            raise ValueError("Writer returned unparseable JSON")
    validated = [_validate_claim(c) for c in raw_claims]
    return [c for c in validated if c is not None]


def _extract_numbers(obj):
    """Recursively extract all numeric values from a nested dict/list."""
    nums = set()
    if isinstance(obj, dict):
        for v in obj.values():
            nums.update(_extract_numbers(v))
    elif isinstance(obj, list):
        for v in obj:
            nums.update(_extract_numbers(v))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        nums.add(obj)
        if isinstance(obj, float) and obj == int(obj):
            nums.add(int(obj))
    elif isinstance(obj, str):
        try:
            nums.add(float(obj))
            if float(obj) == int(float(obj)):
                nums.add(int(float(obj)))
        except (ValueError, OverflowError):
            pass
    return nums


def _find_derivation(val, nums):
    """Check if val is a simple arithmetic result of two numbers in nums."""
    for i, a in enumerate(nums):
        if not isinstance(a, (int, float)) or a == 0:
            continue
        for b in nums[i + 1 :]:
            if not isinstance(b, (int, float)):
                continue
            if abs(a - b - val) < 0.5 or abs(b - a - val) < 0.5:
                return f"appears to be {max(a, b)} - {min(a, b)} = {val}"
            if abs(a + b - val) < 0.5:
                return f"appears to be {a} + {b} = {val}"
            if b != 0 and abs(a / b * 100 - val) < 0.5:
                return f"appears to be {a}/{b}*100 = {val}%"
            if a != 0 and abs(b / a * 100 - val) < 0.5:
                return f"appears to be {b}/{a}*100 = {val}%"
    return None


def verify_claims(claims, tool_results):
    verified = []
    all_row_ids = set()
    for result in tool_results.values():
        all_row_ids.update(result.get("row_ids", []))

    tool_numbers = {}
    for name, result in tool_results.items():
        tool_numbers[name] = _extract_numbers(result.get("data", {}))

    for claim in claims:
        issues = []

        if not claim.get("citations"):
            if claim.get("numeric_values"):
                issues.append(
                    {
                        "type": "missing_citation",
                        "detail": "claim has numeric values but no citations",
                    }
                )

        for cite in claim.get("citations", []):
            parts = cite.split(":")
            raw_id = parts[-1] if parts else cite
            if raw_id not in all_row_ids:
                issues.append(
                    {
                        "type": "missing_citation",
                        "detail": f"citation {cite} not found in tool outputs",
                    }
                )

        source = claim.get("source_tool", "")
        if source and source not in tool_results:
            issues.append(
                {
                    "type": "missing_source",
                    "detail": f"source_tool {source} was not run",
                }
            )

        all_nums = set()
        for nums in tool_numbers.values():
            all_nums.update(nums)
        all_nums_list = sorted(all_nums)

        prose_nums = set()
        for m in re.findall(r"-?\d[\d,]*\.?\d*", claim.get("claim", "")):
            try:
                prose_nums.add(float(m.replace(",", "")))
            except ValueError:
                pass
        declared = set()
        for v in claim.get("numeric_values", []):
            if isinstance(v, (int, float)):
                declared.add(float(v))
        undeclared = {
            n
            for n in prose_nums
            if abs(n) > 1 and not any(abs(n - d) < 0.5 for d in declared)
        }
        for val in undeclared:
            if not any(abs(val - sn) < 0.5 for sn in all_nums):
                issues.append(
                    {
                        "type": "hallucinated",
                        "detail": f"{val} in claim text but not in numeric_values or tool output",
                    }
                )

        for val in claim.get("numeric_values", []):
            if not isinstance(val, (int, float)):
                continue
            matched = False
            for sn in all_nums:
                if val == sn:
                    matched = True
                    break
                if isinstance(val, float) and isinstance(sn, (int, float)):
                    if abs(val - sn) < 0.5:
                        matched = True
                        break
            if not matched:
                derivation = _find_derivation(val, all_nums_list)
                if derivation:
                    issues.append(
                        {
                            "type": "llm_computed",
                            "detail": f"{val} not in tool output — {derivation}",
                        }
                    )
                else:
                    issues.append(
                        {
                            "type": "hallucinated",
                            "detail": f"{val} not found in any tool output",
                        }
                    )

        claim_out = dict(claim)
        claim_out["verification"] = "flagged" if issues else "passed"
        if issues:
            claim_out["verification_issues"] = issues
            types = set(i["type"] for i in issues)
            if "hallucinated" in types:
                claim_out["flag_reason"] = "no source found"
            elif "llm_computed" in types:
                claim_out["flag_reason"] = "LLM-computed value"
            elif "missing_citation" in types:
                claim_out["flag_reason"] = "citation not in evidence"
            else:
                claim_out["flag_reason"] = "source tool not run"
        verified.append(claim_out)

    return verified


SECTION_ORDER = [
    "headline",
    "account_snapshot",
    "contract_position",
    "usage_trends",
    "growth_opportunities",
    "support_health",
    "relationship_context",
    "risks",
    "next_steps",
    "data_gaps",
]

SECTION_TITLES = {
    "headline": "Headline",
    "account_snapshot": "Account Snapshot",
    "contract_position": "Contract & Renewal Position",
    "usage_trends": "Usage Trends",
    "growth_opportunities": "Growth Opportunities",
    "support_health": "Support Health",
    "relationship_context": "Relationship Context",
    "risks": "Risks & Concerns",
    "next_steps": "Recommended Next Steps",
    "data_gaps": "Data Gaps & Confidence",
}


def render_briefing(claims, client_profile, trigger, tool_results=None):
    by_section = {}
    for c in claims:
        by_section.setdefault(c.get("section", "other"), []).append(c)

    lines = []
    name = client_profile.get("client_name", client_profile.get("client_id", "Unknown"))
    lines.append(f"# Client Intelligence Briefing: {name}")
    lines.append(f"**Trigger:** {trigger} | **Date:** {AS_OF}")
    lines.append("")

    for section in SECTION_ORDER:
        if section not in by_section:
            continue
        lines.append(f"## {SECTION_TITLES.get(section, section)}")
        lines.append("")
        for c in by_section[section]:
            text = c["claim"]
            cites = c.get("citations", [])
            if c.get("verification") == "flagged":
                reason = c.get("flag_reason", "unverified")
                flag = f" **[UNVERIFIED: {reason}]**"
            else:
                flag = ""
            cite_str = f" ({', '.join(cites)})" if cites else ""
            if section == "headline":
                lines.append(f"**{text}**{cite_str}{flag}")
            else:
                lines.append(f"- {text}{cite_str}{flag}")
        lines.append("")

    for section, section_claims in by_section.items():
        if section in SECTION_ORDER:
            continue
        lines.append(f"## {section}")
        lines.append("")
        for c in section_claims:
            cites = c.get("citations", [])
            cite_str = f" ({', '.join(cites)})" if cites else ""
            if c.get("verification") == "flagged":
                reason = c.get("flag_reason", "unverified")
                flag = f" **[UNVERIFIED: {reason}]**"
            else:
                flag = ""
            lines.append(f"- {c['claim']}{cite_str}{flag}")
        lines.append("")

    if "data_gaps" not in by_section:
        lines.append(f"## {SECTION_TITLES['data_gaps']}")
        lines.append("")
        dq = (
            tool_results.get("check_data_quality", {}).get("data", {})
            if tool_results
            else {}
        )
        dq_issues = dq.get("issues", [])
        if dq_issues:
            for issue in dq_issues:
                lines.append(f"- {issue['type']}: {issue['detail']}")
        else:
            lines.append("- No data quality issues detected.")
        lines.append("")

    return "\n".join(lines)


def save_evidence(tool_results, claims, output_dir=OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)
    tools_summary = {}
    for name, result in tool_results.items():
        data = result.get("data", {})
        tools_summary[name] = {
            "row_ids": result.get("row_ids", []),
            "keys": list(data.keys()) if isinstance(data, dict) else [],
        }
    evidence = {
        "as_of": AS_OF,
        "tools_run": list(tool_results.keys()),
        "tools_summary": tools_summary,
        "claims": claims,
        "tool_outputs": {
            k: {"data": v["data"], "row_ids": v["row_ids"]}
            for k, v in tool_results.items()
        },
    }
    path = os.path.join(output_dir, "evidence.json")
    with open(path, "w") as f:
        json.dump(evidence, f, indent=2, default=str)
    return path


JUDGE_SYSTEM = f"""You are a quality judge for client intelligence briefings at Aster Vale Sports Data.
Today's date (as_of) is {AS_OF}.

Score the briefing on these dimensions (1-5 each):
- completeness: Does it cover what the trigger requires?
- accuracy: Are claims supported by the evidence?
- actionability: Are next steps concrete and useful for the rep?
- data_transparency: Does it flag gaps, conflicts, and uncertainty?

Return ONLY a JSON object:
{{
  "completeness": {{"score": N, "comment": "..."}},
  "accuracy": {{"score": N, "comment": "..."}},
  "actionability": {{"score": N, "comment": "..."}},
  "data_transparency": {{"score": N, "comment": "..."}},
  "overall": N,
  "summary": "one sentence overall assessment"
}}"""


def judge(briefing, trigger, evidence_summary):
    user_msg = f"""Trigger: {trigger}

Briefing:
{briefing}

Evidence summary (tool outputs used):
{evidence_summary}

Score this briefing."""

    raw = _call_llm(JUDGE_SYSTEM, user_msg, max_tokens=1024, label="judge")
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    return {"error": "Judge did not return valid JSON", "raw": raw}
