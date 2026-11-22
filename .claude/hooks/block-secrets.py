#!/usr/bin/env python
"""PreToolUse hook: keep credentials out of the model's context and out of the repo.

Blocks four things:
  1. any literal API key appearing anywhere in a tool call (command, file content, URL)
  2. reading or writing a credentials file (.env, *.pem, id_rsa, .aws/credentials, ...)
  3. expanding a credential-bearing env var, e.g. echo $ANTHROPIC_API_KEY
  4. a bare full environment dump, unless it is piped through a redactor

Denies by exiting 2 with the reason on stderr, which Claude Code feeds back to the model.

Self-check:  python -I .claude/hooks/block-secrets.py --selftest
"""

import json
import re
import sys

SECRET_FILE = re.compile(
    r"(^|[/\\])\.env(\.|$)"
    r"|(^|[/\\])\.?(secrets?|credentials?)(\.|$)"
    r"|\.(pem|p12|pfx|key|keystore|jks|ppk)$"
    r"|(^|[/\\])id_(rsa|dsa|ecdsa|ed25519)$"
    r"|(^|[/\\])\.(npmrc|pypirc|netrc|pgpass|htpasswd)$"
    r"|(^|[/\\])\.aws[/\\]credentials",
    re.IGNORECASE,
)
SAFE_FILE = re.compile(r"\.(example|sample|template|dist)$", re.IGNORECASE)

_SECRET_VAR = r"[A-Z0-9_]*(API_?KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Z0-9_]*"
EXPANDS_SECRET = re.compile(
    r"[$%]\{?" + _SECRET_VAR + r"|printenv\s+" + _SECRET_VAR, re.IGNORECASE
)
# `[ -n "$API_KEY" ]` only tests presence, it never prints the value, so allow it
PRESENCE_TEST = re.compile(
    r"-[nz]\s+\"?[$%]\{?" + _SECRET_VAR + r"\}?\"?", re.IGNORECASE
)
ENV_DUMP = re.compile(r"(^|[;&|]\s*)(env|printenv|set)\s*($|[;&|])", re.IGNORECASE)
REDACTOR = re.compile(
    r"sed\s+[^|]*=\\?\.\*|cut\s+-d\s*'?=|awk\s+-F\s*'?=", re.IGNORECASE
)
READS_FILE = re.compile(
    r"\b(cat|type|less|more|head|tail|strings|xxd|od|bat|nl|grep|rg|sed|awk|cp|mv|scp|curl)\b",
    re.IGNORECASE,
)
STAGES_FILE = re.compile(r"\bgit\s+(add|commit|stash)\b", re.IGNORECASE)

KEY_LITERAL = re.compile(
    r"sk-ant-[A-Za-z0-9_\-]{20,}"
    r"|sk-[A-Za-z0-9]{32,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|ASIA[0-9A-Z]{16}"
    r"|gh[pousr]_[A-Za-z0-9]{36,}"
    r"|AIza[0-9A-Za-z_\-]{35}"
    r"|xox[baprs]-[0-9A-Za-z\-]{10,}"
    r"|eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\."  # JWT
)

PATH_KEYS = ("file_path", "notebook_path", "path")


def secret_tokens(text):
    """Tokens in `text` that name a credentials file, excluding .example style files."""
    return [
        t
        for t in re.split(r"[\s'\"=:,()\[\];&|<>{}]+", text)
        if t and SECRET_FILE.search(t) and not SAFE_FILE.search(t)
    ]


def check(tool, inp):
    """Return a denial reason, or None to allow."""
    hit = KEY_LITERAL.search(json.dumps(inp))
    if hit:
        return (
            f"this call contains what looks like a real credential ({hit.group()[:8]}...). "
            "Never put a key in a command, a URL or a committed file. "
            "Reference it as an env var and keep the real value out of the transcript."
        )

    for key in PATH_KEYS:
        path = inp.get(key)
        if isinstance(path, str) and secret_tokens(path):
            return (
                f"{path} holds credentials, so it must not enter the context. "
                "Read the .example variant instead, or ask the user for the variable "
                "NAMES only. If you need to know whether a key is set, test for "
                'presence: [ -n "$ANTHROPIC_API_KEY" ] && echo set'
            )

    if tool == "Bash":
        cmd = inp.get("command", "")
        if secret_tokens(cmd) and (READS_FILE.search(cmd) or STAGES_FILE.search(cmd)):
            return (
                "this reads or stages a credentials file. Use the .example variant. "
                "Real secret files belong in .gitignore, never in a commit."
            )
        if EXPANDS_SECRET.search(PRESENCE_TEST.sub("", cmd)):
            return (
                "this expands a credential-bearing environment variable, which would "
                "print its value into the transcript. Test for presence instead: "
                '[ -n "$ANTHROPIC_API_KEY" ] && echo set'
            )
        if ENV_DUMP.search(cmd) and not REDACTOR.search(cmd):
            return (
                "a full environment dump would put credential values in the transcript. "
                "Pipe it through a redactor so only names survive: env | cut -d= -f1"
            )
    return None


def selftest():
    deny = [
        ("Read", {"file_path": "/proj/.env"}),
        ("Read", {"file_path": "C:\\proj\\.env.local"}),
        ("Read", {"file_path": "~/.aws/credentials"}),
        ("Read", {"file_path": "keys/server.pem"}),
        ("Read", {"file_path": "/home/u/.ssh/id_ed25519"}),
        ("Bash", {"command": "cat .env"}),
        ("Bash", {"command": "grep -i key .env | head"}),
        ("Bash", {"command": "git add .env && git commit -m x"}),
        ("Bash", {"command": "echo $ANTHROPIC_API_KEY"}),
        ("Bash", {"command": 'curl -H "x: ${AZURE_OPENAI_API_KEY}" https://x.dev'}),
        ("Bash", {"command": "printenv AWS_BEARER_TOKEN_BEDROCK"}),
        ("Bash", {"command": "env"}),
        ("Bash", {"command": "env | grep -i anthropic"}),
        ("Bash", {"command": "printenv | sort"}),
        (
            "Write",
            {
                "file_path": "cfg.py",
                "content": 'KEY = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA"',
            },
        ),
        ("WebFetch", {"url": "https://x.dev/?k=AKIAIOSFODNN7EXAMPLE"}),
        ("Bash", {"command": "export GH=ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}),
        # a presence test is allowed, but it must not become a cover for printing the value
        ("Bash", {"command": '[ -n "$ANTHROPIC_API_KEY" ] && echo $ANTHROPIC_API_KEY'}),
    ]
    allow = [
        ("Read", {"file_path": "/proj/.env.example"}),
        ("Read", {"file_path": "/proj/.env.template"}),
        ("Read", {"file_path": "src/avi/cli.py"}),
        ("Bash", {"command": "cat .env.example"}),
        ("Bash", {"command": "env | cut -d= -f1 | sort"}),
        ("Bash", {"command": "env | sed 's/=.*/=<redacted>/'"}),
        ("Bash", {"command": '[ -n "$ANTHROPIC_API_KEY" ] && echo set'}),
        ("Bash", {"command": "uv sync && pytest -q"}),
        ("Write", {"file_path": ".gitignore", "content": ".env\n*.pem\n"}),
        (
            "Write",
            {"file_path": "README.md", "content": "Copy .env.example and add your key"},
        ),
        ("Bash", {"command": "git add src/ && git commit -m 'tools'"}),
        (
            "Write",
            {
                "file_path": ".env.example",
                "content": "ANTHROPIC_API_KEY=your-key-here\n",
            },
        ),
        ("Bash", {"command": "cp plan.md out.md; ls .env.example; echo ok"}),
        ("Grep", {"pattern": "api_key", "path": "src"}),
    ]
    for tool, inp in deny:
        assert check(tool, inp), f"should have blocked: {tool} {inp}"
    for tool, inp in allow:
        assert check(tool, inp) is None, (
            f"should have allowed: {tool} {inp} -> {check(tool, inp)}"
        )
    print(f"ok: {len(deny)} blocked, {len(allow)} allowed")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return  # malformed event: do not wedge the session
    reason = check(event.get("tool_name", ""), event.get("tool_input") or {})
    if reason:
        print(f"Blocked by block-secrets hook: {reason}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
