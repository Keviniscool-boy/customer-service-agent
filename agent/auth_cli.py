from getpass import getpass

from api.auth import authenticate_user, register_user


def read_password(prompt: str = "密码：") -> str:
    return getpass(prompt)


def login_or_register() -> dict | None:
    while True:
        print("\n=== 小极客服 ===")
        print("1. 登录")
        print("2. 注册")
        print("0. 退出")
        choice = input("请选择：").strip()

        if choice == "0":
            return None

        if choice == "1":
            username = input("用户名：").strip()
            password = read_password()
            user = authenticate_user(username, password)
            if user:
                print(f"登录成功，欢迎 {user['username']}。")
                return user
            print("用户名或密码错误，请重试。")
            continue

        if choice == "2":
            username = input("用户名：").strip()
            password = read_password()
            password_again = read_password("再次输入密码：")
            if password != password_again:
                print("两次密码不一致，请重新注册。")
                continue

            try:
                user = register_user(username, password)
            except ValueError as error:
                print(f"注册失败：{error}")
                continue

            print(f"注册成功，欢迎 {user['username']}。")
            return user

        print("无效选择，请输入 1、2 或 0。")
