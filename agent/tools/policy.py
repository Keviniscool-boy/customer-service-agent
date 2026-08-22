"""工具权限和确认规则。"""


CONFIRMATION_REQUIRED_TOOLS = {"apply_refund"}


def requires_confirmation(tool_name: str) -> bool:
    return tool_name in CONFIRMATION_REQUIRED_TOOLS


def has_explicit_refund_confirmation(message: str) -> bool:
    """判断当前消息是否明确同意退款，不把普通咨询当成确认。"""

    text = message.strip().lower()
    if not text or any(word in text for word in ("不确认", "取消退款", "先不退")):
        return False
    return any(
        phrase in text
        for phrase in (
            "确认退款",
            "同意退款",
            "确定退款",
            "可以退款",
            "我确认",
        )
    )
