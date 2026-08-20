from getpass import getpass

from agent.database import get_user_by_username, init_db, set_user_role
from api.auth import register_user, reset_user_password


def main():
    init_db()
    username = input("管理员用户名：").strip()
    password = getpass("管理员密码（输入时不显示，完成后按回车）：")
    confirm = getpass("再次输入密码（输入时不显示，完成后按回车）：")

    if password != confirm:
        print("两次密码不一致。")
        return

    existing_user = get_user_by_username(username)
    try:
        if existing_user:
            reset_user_password(username, password)
        else:
            register_user(username, password)
    except ValueError as error:
        if str(error) != "用户名已存在":
            print(f"创建失败：{error}")
            return

    if set_user_role(username, "admin"):
        print(f"管理员账号已准备好：{username}")
    else:
        print("没有找到这个用户。")


if __name__ == "__main__":
    main()
