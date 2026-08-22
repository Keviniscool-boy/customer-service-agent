"""给隔离压测数据库批量预置用户、会话和 JWT。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

from api.auth import create_access_token, password_hash
from agent.database import get_connection


def seed_users(count: int, output_path: Path) -> None:
    if count < 1:
        raise ValueError("预置用户数必须大于 0")

    shared_password_hash = password_hash.hash("loadtest123")
    users = []
    sessions = []
    accounts = []

    for index in range(count):
        user_id = str(uuid4())
        session_id = str(uuid4())
        username = f"seed-load-user-{index:05d}"
        user = {
            "id": user_id,
            "username": username,
            "role": "user",
        }
        users.append((user_id, username, shared_password_hash, "user"))
        sessions.append(
            (
                session_id,
                user_id,
                "ecom-default",
                "隔离压测预置会话",
            )
        )
        accounts.append(
            {
                "username": username,
                "token": create_access_token(user),
                "session_id": session_id,
            }
        )

    connection = get_connection()
    try:
        connection.executemany(
            """
            INSERT INTO users (id, username, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            users,
        )
        connection.executemany(
            """
            INSERT INTO sessions (id, user_id, agent_id, title)
            VALUES (?, ?, ?, ?)
            """,
            sessions,
        )
        connection.commit()
    finally:
        connection.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {"count": count, "accounts": accounts},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"已预置 {count} 个隔离压测用户")


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("用法：seed_users.py <count> <output.json>")
    seed_users(int(sys.argv[1]), Path(sys.argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
