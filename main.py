from agent.auth_cli import login_or_register
from agent.chat import EcomAgent
from agent.database import init_db
from agent.presentation import visible_reply


def main():
    init_db()
    user = login_or_register()
    if user is None:
        print("已退出。")
        return
    agent = EcomAgent(user_id=user["id"])

    while True:
        user_input = input("👤 你: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("再见！")
            break
        if user_input.lower() == "reset":
            agent.reset()
            print("当前会话已重置")
            continue
        try:
            response = agent.chat(user_input)
            print(f"\n🤖 小极: {visible_reply(response.reply)}\n")
        except Exception as error:
            print(f"出错了: {error}")


if __name__ == "__main__":
    main()
