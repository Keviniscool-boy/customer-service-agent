import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from agent import database


class DatabaseTest(unittest.TestCase):
    def test_postgres_executemany_uses_cursor(self):
        raw_connection = MagicMock()
        cursor = raw_connection.cursor.return_value.__enter__.return_value
        connection = database.DatabaseConnection(raw_connection, "postgres")
        rows = [("one", 1), ("two", 2)]

        connection.executemany(
            "INSERT INTO examples (name, value) VALUES (?, ?)",
            rows,
        )

        cursor.executemany.assert_called_once_with(
            "INSERT INTO examples (name, value) VALUES (%s, %s)",
            rows,
        )

    def test_connection_enables_sqlite_reliability_options(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                database.init_db()
                connection = database.get_connection()
                foreign_keys = connection.execute(
                    "PRAGMA foreign_keys"
                ).fetchone()[0]
                journal_mode = connection.execute(
                    "PRAGMA journal_mode"
                ).fetchone()[0]
                connection.close()

                self.assertEqual(foreign_keys, 1)
                self.assertEqual(str(journal_mode).lower(), "wal")
            finally:
                database.DB_PATH = original_path

    def test_save_and_load_full_messages(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                database.init_db()
                session_id = database.create_session("test-user")
                messages = [
                    {"role": "user", "content": "你好"},
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {"id": "call-1", "type": "function"}
                        ],
                    },
                ]

                for message in messages:
                    database.save_message(session_id, message)

                self.assertEqual(database.load_messages(session_id), messages)
            finally:
                database.DB_PATH = original_path

    def test_session_ownership(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                database.init_db()
                session_id = database.create_session("user-a")
                self.assertTrue(
                    database.session_belongs_to_user(session_id, "user-a")
                )
                self.assertFalse(
                    database.session_belongs_to_user(session_id, "user-b")
                )
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
