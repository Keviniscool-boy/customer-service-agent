import json


def visible_reply(value: str | None) -> str:
    """从可能带结构的模型回复中提取用户真正能看的文本。

    模型偶尔会把整段结构化数据原样返回，直接展示会把内部字段泄露给用户。
    """
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
