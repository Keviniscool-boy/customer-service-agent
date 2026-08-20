import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def create_handoff(
    reason: str,
    ticket_path: str | Path = "sessions/handoff_tickets.json",
) -> dict:
    """创建一个学习版人工客服工单。"""
    path = Path(ticket_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tickets = []
        if path.exists():
            tickets = json.loads(path.read_text(encoding="utf-8"))

        ticket = {
            "ticket_id": f"HUMAN-{uuid.uuid4().hex[:8].upper()}",
            "status": "pending_human",
            "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        tickets.append(ticket)
        path.write_text(
            json.dumps(tickets, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {"success": True, **ticket}
    except Exception as error:
        return {
            "success": False,
            "message": "人工工单创建失败",
            "error": type(error).__name__,
        }
