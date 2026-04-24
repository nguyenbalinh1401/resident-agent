#!/usr/bin/env python3
"""Test SSE streaming endpoint for Resident Agent API."""

import argparse
import json
import sys
import uuid

import requests

BASE_URL = "http://localhost:8081"

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def login(base_url: str, email: str, password: str) -> str:
    resp = requests.post(
        f"{base_url}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    print(f"{GREEN}Logged in as {email}{RESET}\n")
    return token


def parse_sse_events(response):
    buf = ""
    for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
        if chunk is None:
            continue
        buf += chunk
        while "\n\n" in buf:
            raw, buf = buf.split("\n\n", 1)
            for line in raw.splitlines():
                if line.startswith("data: "):
                    payload = line[6:]
                    try:
                        yield json.loads(payload)
                    except json.JSONDecodeError:
                        print(f"{RED}[Invalid JSON] {payload}{RESET}")
    # flush remaining
    if buf.strip():
        for line in buf.splitlines():
            if line.startswith("data: "):
                payload = line[6:]
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    pass


def print_event(event: dict):
    etype = event.get("type", "")
    content = event.get("content", "")
    session_id = event.get("session_id", "")

    if etype == "thinking":
        print(f"\n{YELLOW}{content or 'Processing...'}{RESET}", end="", flush=True)

    elif etype in ("token", "content"):
        print(f"{GREEN}{content}{RESET}", end="", flush=True)

    elif etype == "tool_call":
        tc = event.get("tool_call", {})
        tool_name = tc.get("tool", "unknown")
        params = tc.get("params", {})
        params_str = json.dumps(params, ensure_ascii=False) if params else ""
        print(f"\n{CYAN}[Tool: {tool_name}] {params_str}{RESET}", end="", flush=True)

    elif etype == "action":
        action = event.get("action", {})
        label = action.get("label", "")
        atype = action.get("action_type", "")
        print(f"\n{BLUE}[Action] {label} ({atype}){RESET}", end="", flush=True)

    elif etype == "actions":
        actions = event.get("actions", [])
        print(f"\n{BLUE}[Actions]{RESET}")
        for a in actions:
            # Support both ActionButton format and tool-registry format
            label = a.get("label", a.get("tool", ""))
            atype = a.get("action_type", "")
            style = a.get("style", "")
            tool = a.get("tool", "")
            allowed = a.get("allowed")
            if tool:
                allowed_str = f", allowed={allowed}" if allowed is not None else ""
                print(f"  {BLUE}- {label} [{tool}]{allowed_str}{RESET}")
            else:
                print(f"  {BLUE}- {label} ({atype}, {style}){RESET}")

    elif etype == "complete":
        print(f"\n{BOLD}{GREEN}[Complete] session={session_id}{RESET}")

    elif etype == "error":
        print(f"\n{RED}[Error] {content or event.get('error', 'Unknown')}{RESET}")

    else:
        print(f"\n{DIM}[{etype}] {content}{RESET}", end="", flush=True)


def stream_chat(base_url: str, token: str, message: str, session_id: str | None = None):
    if not session_id:
        session_id = str(uuid.uuid4())[:8]

    params = {"message": message, "session_id": session_id}
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print(f"{DIM}--- Sending: \"{message}\" (session: {session_id}) ---{RESET}\n")

    try:
        resp = requests.get(
            f"{base_url}/api/v1/chat/stream",
            params=params,
            headers=headers,
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()

        for event in parse_sse_events(resp):
            print_event(event)

    except requests.exceptions.ConnectionError:
        print(f"{RED}Connection failed. Is the API running at {base_url}?{RESET}")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"{RED}HTTP {e.response.status_code}: {e.response.text}{RESET}")
        sys.exit(1)

    print()  # trailing newline


def interactive_chat(base_url: str, token: str):
    session_id = str(uuid.uuid4())[:8]
    print(f"{BOLD}Interactive chat (session: {session_id}){RESET}")
    print(f"{DIM}Type 'quit' to exit, 'new' for new session{RESET}\n")

    while True:
        try:
            message = input(f"{BOLD}You> {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Bye!{RESET}")
            break

        if not message:
            continue
        if message.lower() == "quit":
            print(f"{DIM}Bye!{RESET}")
            break
        if message.lower() == "new":
            session_id = str(uuid.uuid4())[:8]
            print(f"{DIM}New session: {session_id}{RESET}\n")
            continue

        stream_chat(base_url, token, message, session_id)
        print()  # spacing


def main():
    parser = argparse.ArgumentParser(description="Test Resident Agent SSE streaming")
    parser.add_argument("--url", default=BASE_URL, help=f"API base URL (default: {BASE_URL})")
    parser.add_argument("--email", help="email number for login")
    parser.add_argument("--password", help="Password for login")
    parser.add_argument("--token", help="JWT token (skip login)")
    parser.add_argument("--message", "-m", help="Single message to send")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive chat mode")
    parser.add_argument("--session-id", help="Session ID (default: auto-generated)")
    args = parser.parse_args()

    # Get token
    token = args.token
    if not token and args.email and args.password:
        token = login(args.url, args.email, args.password)
    elif not token:
        print(f"{YELLOW}Warning: No auth token. Unauthenticated request.{RESET}\n")

    if args.interactive:
        interactive_chat(args.url, token)
    elif args.message:
        stream_chat(args.url, token, args.message, args.session_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
