import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from config.settings import settings


DB_PATH = Path(settings.database_path)
DATABASE_BACKEND = settings.database_backend

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - only needed for PostgreSQL mode
    psycopg = None
    dict_row = None


class DatabaseConnection:
    """让现有业务 SQL 同时适配 SQLite 和 PostgreSQL。"""

    def __init__(self, connection, backend: str):
        self._connection = connection
        self.backend = backend

    def execute(self, query: str, params=()):
        if self.backend == "postgres":
            query = query.replace("?", "%s")
        return self._connection.execute(query, params)

    def executemany(self, query: str, params):
        if self.backend == "postgres":
            query = query.replace("?", "%s")
        return self._connection.executemany(query, params)

    def commit(self):
        self._connection.commit()

    def close(self):
        self._connection.close()

ORDER_STATUS_TRANSITIONS = {
    "待发货": {"已发货", "已取消"},
    "已发货": {"运输中"},
    "运输中": {"已送达"},
    "已送达": set(),
    "已取消": set(),
}


def get_connection():
    if DATABASE_BACKEND == "postgres":
        if psycopg is None:
            raise RuntimeError("PostgreSQL 模式需要安装 psycopg[binary]")
        if not settings.postgres_dsn.strip():
            raise RuntimeError("PostgreSQL 模式没有配置 POSTGRES_DSN")
        return DatabaseConnection(
            psycopg.connect(settings.postgres_dsn, row_factory=dict_row),
            "postgres",
        )

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return DatabaseConnection(connection, "sqlite")


def _table_columns(connection: DatabaseConnection, table_name: str) -> set[str]:
    if DATABASE_BACKEND == "postgres":
        rows = connection.execute(
            """
            SELECT column_name AS name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = ?
            """,
            (table_name,),
        ).fetchall()
    else:
        rows = connection.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    return {row["name"] for row in rows}

def init_db():
    connection = get_connection()
    connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            agent_id TEXT NOT NULL DEFAULT 'ecom-default',
            title TEXT,
            summary TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
            """
        )
    message_id = (
        "BIGSERIAL PRIMARY KEY"
        if DATABASE_BACKEND == "postgres"
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS messages (
            id {message_id},
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            message_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    user_columns = _table_columns(connection, "users")
    if "role" not in user_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
        )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id TEXT,
            product_name TEXT NOT NULL,
            status TEXT NOT NULL,
            amount REAL NOT NULL,
            tracking_number TEXT,
            shipping_address TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS refunds (
            refund_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            user_id TEXT,
            amount REAL NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            stock INTEGER NOT NULL,
            description TEXT NOT NULL
        )
        """
    )
    audit_id = (
        "BIGSERIAL PRIMARY KEY"
        if DATABASE_BACKEND == "postgres"
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS tool_audits (
            id {audit_id},
            user_id TEXT,
            session_id TEXT,
            agent_id TEXT,
            tool_name TEXT NOT NULL,
            arguments_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    session_columns = _table_columns(connection, "sessions")
    if "agent_id" not in session_columns:
        connection.execute(
            "ALTER TABLE sessions ADD COLUMN agent_id TEXT NOT NULL DEFAULT 'ecom-default'"
        )
    if "title" not in session_columns:
        connection.execute("ALTER TABLE sessions ADD COLUMN title TEXT")

    columns = _table_columns(connection, "messages")
    if "message_json" not in columns:
        connection.execute("ALTER TABLE messages ADD COLUMN message_json TEXT")
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sessions_user_agent_updated
        ON sessions (user_id, agent_id, updated_at DESC)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_messages_session_id
        ON messages (session_id, id)
        """
    )
    order_count = connection.execute(
        "SELECT COUNT(*) AS count FROM orders"
    ).fetchone()["count"]
    order_columns = _table_columns(connection, "orders")
    if "user_id" not in order_columns:
        connection.execute("ALTER TABLE orders ADD COLUMN user_id TEXT")
    if order_count == 0:
        from agent.tools.mock_data import ORDERS

        connection.executemany(
            """
            INSERT INTO orders (
                order_id,
                product_name,
                status,
                amount,
                tracking_number,
                shipping_address
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    order["order_id"],
                    order["product_name"],
                    order["status"],
                    order["amount"],
                    order["tracking_number"],
                    order["shipping_address"],
                )
                for order in ORDERS.values()
            ],
        )
    product_count = connection.execute(
        "SELECT COUNT(*) AS count FROM products"
    ).fetchone()["count"]
    if product_count == 0:
        from agent.tools.mock_data import PRODUCTS

        connection.executemany(
            """
            INSERT INTO products (
                product_id, name, price, category, stock, description
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    product["product_id"],
                    product["name"],
                    product["price"],
                    product["category"],
                    product["stock"],
                    product["description"],
                )
                for product in PRODUCTS.values()
            ],
        )
    connection.commit()
    connection.close()


def create_user(
    username: str,
    password_hash: str,
    role: str = "user",
) -> str:
    user_id = str(uuid4())
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO users (id, username, password_hash, role)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, username, password_hash, role),
    )
    connection.commit()
    connection.close()
    return user_id


def get_user_by_username(username: str) -> dict | None:
    connection = get_connection()
    row = connection.execute(
        """
        SELECT id, username, password_hash, role
        FROM users
        WHERE username = ?
        """,
        (username,),
    ).fetchone()
    connection.close()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    connection = get_connection()
    row = connection.execute(
        """
        SELECT id, username, role
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    connection.close()
    return dict(row) if row else None


def set_user_role(username: str, role: str) -> bool:
    if role not in {"user", "admin"}:
        raise ValueError("角色只能是 user 或 admin")

    connection = get_connection()
    cursor = connection.execute(
        "UPDATE users SET role = ? WHERE username = ?",
        (role, username),
    )
    connection.commit()
    connection.close()
    return cursor.rowcount > 0


def update_user_password(username: str, password_hash: str) -> bool:
    connection = get_connection()
    cursor = connection.execute(
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (password_hash, username),
    )
    connection.commit()
    connection.close()
    return cursor.rowcount > 0


def get_order(order_id: str) -> dict | None:
    return get_order_for_user(order_id)


def get_order_for_user(order_id: str, user_id: str | None = None) -> dict | None:
    init_db()
    connection = get_connection()
    query = """
        SELECT order_id, product_name, status, amount,
               tracking_number, shipping_address
        FROM orders
        WHERE order_id = ?
    """
    params: tuple[str, ...] = (order_id,)
    if user_id:
        query += " AND (user_id IS NULL OR user_id = ?)"
        params += (user_id,)
    row = connection.execute(query, params).fetchone()
    connection.close()
    return dict(row) if row else None


def create_order(
    user_id: str,
    order_id: str | None,
    product_name: str,
    status: str,
    amount: float,
    tracking_number: str | None = None,
    shipping_address: str | None = None,
) -> str:
    order_id = order_id or f"ORD-{uuid4().hex[:8].upper()}"
    init_db()
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO orders (
            order_id, user_id, product_name, status, amount,
            tracking_number, shipping_address
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            user_id,
            product_name,
            status,
            amount,
            tracking_number,
            shipping_address,
        ),
    )
    connection.commit()
    connection.close()
    return order_id


def list_orders_for_user(user_id: str) -> list[dict]:
    init_db()
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT order_id, product_name, status, amount,
               tracking_number, shipping_address
        FROM orders
        WHERE user_id = ?
        ORDER BY order_id DESC
        """,
        (user_id,),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def search_products(keyword: str = "") -> list[dict]:
    init_db()
    connection = get_connection()
    keyword = keyword.strip().lower()
    rows = connection.execute(
        """
        SELECT product_id, name, price, category, stock, description
        FROM products
        WHERE lower(name) LIKE ?
           OR lower(category) LIKE ?
           OR lower(description) LIKE ?
        ORDER BY product_id
        """,
        (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def find_active_refund(order_id: str, user_id: str | None = None) -> dict | None:
    init_db()
    connection = get_connection()
    query = """
        SELECT refund_id, order_id, user_id, amount, reason, status,
               created_at, updated_at
        FROM refunds
        WHERE order_id = ? AND status IN ('approved', 'pending_human')
    """
    params: tuple[str, ...] = (order_id,)
    if user_id:
        query += " AND (user_id IS NULL OR user_id = ?)"
        params += (user_id,)
    row = connection.execute(query, params).fetchone()
    connection.close()
    return dict(row) if row else None


def create_refund(
    order_id: str,
    user_id: str | None,
    amount: float,
    reason: str,
    status: str,
) -> dict:
    refund_id = f"REF-{uuid4().hex[:8].upper()}"
    init_db()
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO refunds (
            refund_id, order_id, user_id, amount, reason, status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (refund_id, order_id, user_id, amount, reason, status),
    )
    connection.commit()
    row = connection.execute(
        """
        SELECT refund_id, order_id, user_id, amount, reason, status,
               created_at, updated_at
        FROM refunds
        WHERE refund_id = ?
        """,
        (refund_id,),
    ).fetchone()
    connection.close()
    return dict(row)


def list_refunds_for_user(user_id: str) -> list[dict]:
    init_db()
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT refund_id, order_id, amount, reason, status,
               created_at, updated_at
        FROM refunds
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def transition_order_status(
    order_id: str,
    user_id: str,
    new_status: str,
) -> dict | None:
    init_db()
    connection = get_connection()
    row = connection.execute(
        "SELECT status FROM orders WHERE order_id = ? AND user_id = ?",
        (order_id, user_id),
    ).fetchone()
    if row is None:
        connection.close()
        return None

    current_status = row["status"]
    if new_status not in ORDER_STATUS_TRANSITIONS.get(current_status, set()):
        connection.close()
        raise ValueError(
            f"订单 {order_id} 不能从“{current_status}”变为“{new_status}”"
        )

    connection.execute(
        "UPDATE orders SET status = ? WHERE order_id = ? AND user_id = ?",
        (new_status, order_id, user_id),
    )
    connection.commit()
    connection.close()
    return get_order_for_user(order_id, user_id)


def create_session(
    user_id: str,
    title: str | None = None,
    agent_id: str = "ecom-default",
) -> str:
    session_id = str(uuid4())
    connection = get_connection()
    connection.execute(
        "INSERT INTO sessions (id, user_id, agent_id, title) VALUES (?, ?, ?, ?)",
        (session_id, user_id, agent_id, title),
    )
    connection.commit()
    connection.close()
    return session_id


def get_latest_session_id(
    user_id: str,
    agent_id: str = "ecom-default",
) -> str | None:
    connection = get_connection()
    row = connection.execute(
        """
        SELECT id
        FROM sessions
        WHERE user_id = ? AND agent_id = ?
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 1
        """,
        (user_id, agent_id),
    ).fetchone()
    connection.close()
    return row["id"] if row else None


def session_belongs_to_user(
    session_id: str,
    user_id: str,
    agent_id: str | None = None,
) -> bool:
    connection = get_connection()
    query = "SELECT 1 FROM sessions WHERE id = ? AND user_id = ?"
    params: tuple[str, ...] = (session_id, user_id)
    if agent_id is not None:
        query += " AND agent_id = ?"
        params += (agent_id,)
    row = connection.execute(query, params).fetchone()
    connection.close()
    return row is not None


def load_summary(session_id: str) -> str | None:
    connection = get_connection()
    row = connection.execute(
        "SELECT summary FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    connection.close()
    return row["summary"] if row else None

def save_message(session_id: str, message: dict) -> None:
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO messages (session_id, role, content, message_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            session_id,
            message["role"],
            message.get("content") or "",
            json.dumps(message, ensure_ascii=False),
        ),
    )
    connection.execute(
        "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (session_id,),
    )
    connection.commit()
    connection.close()


def load_messages(session_id: str) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT role, content, message_json
        FROM messages
        WHERE session_id = ?
        ORDER BY id ASC
        """,
        (session_id,),
    ).fetchall()
    connection.close()

    messages = []
    for row in rows:
        if row["message_json"]:
            messages.append(json.loads(row["message_json"]))
        else:
            messages.append(
                {"role": row["role"], "content": row["content"]}
            )
    return messages


def delete_messages(session_id: str) -> None:
    connection = get_connection()
    connection.execute(
        "DELETE FROM messages WHERE session_id = ?",
        (session_id,),
    )
    connection.commit()
    connection.close()


def replace_messages(session_id: str, messages: list[dict]) -> None:
    connection = get_connection()
    connection.execute(
        "DELETE FROM messages WHERE session_id = ?",
        (session_id,),
    )
    connection.executemany(
        """
        INSERT INTO messages (session_id, role, content, message_json)
        VALUES (?, ?, ?, ?)
        """,
        [
            (
                session_id,
                message["role"],
                message.get("content") or "",
                json.dumps(message, ensure_ascii=False),
            )
            for message in messages
        ],
    )
    connection.execute(
        "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (session_id,),
    )
    connection.commit()
    connection.close()


def update_summary(session_id: str, summary: str | None) -> None:
    connection = get_connection()

    connection.execute(
        """
        UPDATE sessions
        SET summary = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (summary, session_id),
    )

    connection.commit()
    connection.close()


def record_tool_audit(
    *,
    user_id: str | None,
    session_id: str | None,
    agent_id: str | None,
    tool_name: str,
    arguments: dict,
    result: object,
    status: str,
) -> None:
    """保存一次工具调用记录，供学习版管理员查看。"""

    connection = get_connection()
    connection.execute(
        """
        INSERT INTO tool_audits (
            user_id, session_id, agent_id, tool_name,
            arguments_json, result_json, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            session_id,
            agent_id,
            tool_name,
            json.dumps(arguments, ensure_ascii=False),
            result if isinstance(result, str) else json.dumps(
                result,
                ensure_ascii=False,
            ),
            status,
        ),
    )
    connection.commit()
    connection.close()


def list_tool_audits(limit: int = 100) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT tool_audits.id, tool_audits.user_id, tool_audits.session_id,
               tool_audits.agent_id, tool_audits.tool_name,
               tool_audits.arguments_json, tool_audits.result_json,
               tool_audits.status, tool_audits.created_at, users.username
        FROM tool_audits
        LEFT JOIN users ON users.id = tool_audits.user_id
        ORDER BY tool_audits.id DESC
        LIMIT ?
        """,
        (max(1, min(limit, 500)),),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def delete_session(session_id: str) -> None:
    connection = get_connection()

    connection.execute(
        "DELETE FROM messages WHERE session_id = ?",
        (session_id,),
    )
    connection.execute(
        "DELETE FROM sessions WHERE id = ?",
        (session_id,),
    )

    connection.commit()
    connection.close()
