SUMMARY_PROMPT = """
请总结下面的客服对话，只保留重要信息：

- 用户身份或偏好
- 订单号和商品信息
- 用户的主要问题
- 客服已经承诺的事情
- 还没有解决的问题

不要写流水账，简洁总结即可。
"""


def summarize(client, model, old_messages, previous_summary=None):
    history_text = "\n".join(
        f"{message['role']}: {message['content']}"
        for message in old_messages
    )

    previous_summary = previous_summary or "暂无历史摘要"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SUMMARY_PROMPT},
            {
                "role": "user",
                "content": (
                    f"之前的摘要：\n{previous_summary}\n\n"
                    f"需要总结的对话：\n{history_text}"
                ),
            },
        ],
        temperature=0.0,
    )

    return (response.choices[0].message.content or "").strip()