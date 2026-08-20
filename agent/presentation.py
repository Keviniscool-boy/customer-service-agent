import json


def visible_reply(value: str | None) -> str:
    """Extract the user-facing text from a possibly structured model reply."""
    if not isinstance(value, str):
        return ""

    candidate = value.strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return candidate

    if not isinstance(parsed, dict) or not isinstance(parsed.get("reply"), str):
        return candidate

    reply = parsed["reply"].strip()
    follow_up = parsed.get("follow_up_question")
    if isinstance(follow_up, str) and follow_up.strip() and follow_up not in reply:
        reply = f"{reply}\n{follow_up.strip()}"
    return reply
