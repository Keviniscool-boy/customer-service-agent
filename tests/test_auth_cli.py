import unittest
from unittest.mock import patch

from agent.auth_cli import login_or_register, read_password


class AuthCLITest(unittest.TestCase):
    def test_password_prompt_is_short(self):
        with patch("agent.auth_cli.getpass", return_value="secret123") as prompt:
            self.assertEqual(read_password(), "secret123")
        prompt.assert_called_once_with("密码：")

    def test_registration_logs_user_in_automatically(self):
        inputs = iter(["2", "test-user"])
        with patch("builtins.input", side_effect=inputs):
            with patch("agent.auth_cli.getpass", side_effect=["secret123", "secret123"]):
                with patch(
                    "agent.auth_cli.register_user",
                    return_value={"id": "user-1", "username": "test-user"},
                ):
                    user = login_or_register()

        self.assertEqual(user["id"], "user-1")


if __name__ == "__main__":
    unittest.main()
