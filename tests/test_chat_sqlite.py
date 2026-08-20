import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import database
from agent.chat import EcomAgent
from config.agent_config import AgentConfig


class ChatSQLiteTest(unittest.TestCase):
    @staticmethod
    def make_config(agent_id: str) -> AgentConfig:
        return AgentConfig(
            agent_id=agent_id,
            name=agent_id,
            role="通用助手",
            welcome_message="你好",
            tone="简洁",
            service_scope=["咨询"],
            knowledge_base_path="knowledge",
        )

    def test_agent_restores_messages_from_sqlite(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with patch("agent.chat.MCPClient.connect", return_value=[]):
                    first = EcomAgent(user_id="sqlite-test-user")
                    first.messages.extend(
                        [
                            {"role": "user", "content": "remember this"},
                            {"role": "assistant", "content": "saved"},
                        ]
                    )
                    first._save_to_database()

                    second = EcomAgent(
                        user_id="sqlite-test-user",
                        session_id=first.session_id,
                    )

                self.assertEqual(second.messages[-2:], first.messages[-2:])
            finally:
                database.DB_PATH = original_path

    def test_agent_rejects_another_users_session(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                database.init_db()
                session_id = database.create_session("user-a")
                with patch("agent.chat.MCPClient.connect", return_value=[]):
                    with self.assertRaises(ValueError):
                        EcomAgent(user_id="user-b", session_id=session_id)
            finally:
                database.DB_PATH = original_path

    def test_same_user_has_separate_sessions_per_agent(self):
        original_path = database.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "app.db"
            try:
                with patch("agent.chat.MCPClient.connect", return_value=[]):
                    first = EcomAgent(
                        user_id="multi-agent-user",
                        agent_config=self.make_config("agent-one"),
                    )
                    second = EcomAgent(
                        user_id="multi-agent-user",
                        agent_config=self.make_config("agent-two"),
                    )

                    with self.assertRaises(ValueError):
                        EcomAgent(
                            user_id="multi-agent-user",
                            session_id=first.session_id,
                            agent_config=self.make_config("agent-two"),
                        )

                self.assertNotEqual(first.session_id, second.session_id)
                self.assertEqual(
                    database.get_latest_session_id(
                        "multi-agent-user",
                        "agent-one",
                    ),
                    first.session_id,
                )
            finally:
                database.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
