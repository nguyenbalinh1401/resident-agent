"""File-backed operations store for sessions, handoffs, knowledge base, and secrets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask_secret(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return ""
    if len(trimmed) <= 8:
        return "*" * len(trimmed)
    return f"{trimmed[:4]}{'*' * max(4, len(trimmed) - 8)}{trimmed[-4:]}"


@dataclass
class OpsStore:
    root_dir: Path

    @classmethod
    def create(cls) -> "OpsStore":
        root_dir = Path(__file__).resolve().parents[3]
        return cls(root_dir=root_dir)

    @property
    def data_dir(self) -> Path:
        path = self.root_dir / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def sessions_path(self) -> Path:
        return self.data_dir / "sessions.json"

    @property
    def handoffs_path(self) -> Path:
        return self.data_dir / "handoffs.json"

    @property
    def knowledge_base_path(self) -> Path:
        return self.root_dir / "configs" / "knowledge_base.md"

    @property
    def env_path(self) -> Path:
        return self.root_dir / ".env"

    def _read_json_list(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        try:
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                return []
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
        except Exception:
            return []
        return []

    def _write_json_list(self, path: Path, data: List[Dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_env(self) -> Dict[str, str]:
        if not self.env_path.exists():
            return {}
        values: Dict[str, str] = {}
        for raw_line in self.env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        return values

    def _write_env(self, values: Dict[str, str]) -> None:
        lines = [f"{key}={value}" for key, value in sorted(values.items())]
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def ensure_knowledge_base(self) -> None:
        if self.knowledge_base_path.exists():
            return
        self.knowledge_base_path.parent.mkdir(parents=True, exist_ok=True)
        self.knowledge_base_path.write_text(
            "# Pulse AI Knowledge Base\n\n"
            "- Building handbook snippets\n"
            "- Policy notes and escalation rules\n"
            "- Payment and amenity FAQs\n",
            encoding="utf-8",
        )

    def list_sessions_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        sessions = self._read_json_list(self.sessions_path)
        filtered = [item for item in sessions if item.get("user_id") == user_id]
        return sorted(filtered, key=lambda item: item.get("updated_at", ""), reverse=True)

    def upsert_session(
        self,
        user: Dict[str, Any],
        session_id: str,
        user_message: str,
        assistant_message: str,
    ) -> Dict[str, Any]:
        sessions = self._read_json_list(self.sessions_path)
        existing = next((item for item in sessions if item.get("id") == session_id), None)
        now = _utc_now_iso()

        if existing is None:
            existing = {
                "id": session_id,
                "user_id": user.get("sub"),
                "user_name": user.get("name"),
                "phone_number": user.get("phone_number"),
                "created_at": now,
                "handoff_count": 0,
                "status": "Active",
            }
            sessions.append(existing)

        existing["title"] = (user_message.strip() or "Resident chat")[:80]
        existing["last_user_message"] = user_message.strip()
        existing["last_assistant_message"] = assistant_message.strip()
        existing["last_preview"] = (assistant_message.strip() or user_message.strip())[:160]
        existing["updated_at"] = now
        self._write_json_list(self.sessions_path, sessions)
        return existing

    def create_handoff(
        self,
        user: Dict[str, Any],
        session_id: Optional[str],
        topic: str,
        summary: str,
        priority: str,
        requested_team: Optional[str],
    ) -> Dict[str, Any]:
        handoffs = self._read_json_list(self.handoffs_path)
        sessions = self._read_json_list(self.sessions_path)
        now = _utc_now_iso()
        handoff = {
            "id": f"handoff-{uuid.uuid4().hex[:10]}",
            "session_id": session_id,
            "resident_id": user.get("sub"),
            "resident_name": user.get("name"),
            "phone_number": user.get("phone_number"),
            "topic": topic.strip(),
            "summary": summary.strip(),
            "priority": priority,
            "requested_team": requested_team,
            "assigned_to": None,
            "status": "Open",
            "created_at": now,
            "updated_at": now,
            "resolution_note": None,
        }
        handoffs.append(handoff)
        self._write_json_list(self.handoffs_path, handoffs)

        if session_id:
            session = next((item for item in sessions if item.get("id") == session_id), None)
            if session:
                session["handoff_count"] = int(session.get("handoff_count", 0)) + 1
                session["status"] = "Escalated"
                session["updated_at"] = now
                self._write_json_list(self.sessions_path, sessions)

        return handoff

    def list_handoffs(self, resident_id: Optional[str] = None) -> List[Dict[str, Any]]:
        handoffs = self._read_json_list(self.handoffs_path)
        if resident_id:
            handoffs = [item for item in handoffs if item.get("resident_id") == resident_id]
        return sorted(handoffs, key=lambda item: item.get("updated_at", ""), reverse=True)

    def update_handoff(
        self,
        handoff_id: str,
        *,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        resolution_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        handoffs = self._read_json_list(self.handoffs_path)
        handoff = next((item for item in handoffs if item.get("id") == handoff_id), None)
        if handoff is None:
            raise KeyError(handoff_id)

        if status is not None:
            handoff["status"] = status
        if assigned_to is not None:
            handoff["assigned_to"] = assigned_to
        if resolution_note is not None:
            handoff["resolution_note"] = resolution_note
        handoff["updated_at"] = _utc_now_iso()
        self._write_json_list(self.handoffs_path, handoffs)
        return handoff

    def get_knowledge_base(self) -> Dict[str, Any]:
        self.ensure_knowledge_base()
        content = self.knowledge_base_path.read_text(encoding="utf-8")
        return {
            "path": str(self.knowledge_base_path.relative_to(self.root_dir)),
            "content": content,
            "updated_at": datetime.fromtimestamp(
                self.knowledge_base_path.stat().st_mtime,
                tz=timezone.utc,
            ).isoformat(),
        }

    def save_knowledge_base(self, content: str) -> Dict[str, Any]:
        self.ensure_knowledge_base()
        self.knowledge_base_path.write_text(content, encoding="utf-8")
        return self.get_knowledge_base()

    def list_api_keys(self) -> List[Dict[str, Any]]:
        env_values = self._read_env()
        definitions = [
            ("OPENAI_API_KEY", "OpenAI", "Used by resident_agent.core.config"),
            ("JWT_SECRET_KEY", "JWT", "Resident Agent auth signing secret"),
            ("PULSE_BACKEND_URL", "Pulse Backend", "Resident Agent upstream backend URL"),
        ]
        keys: List[Dict[str, Any]] = []
        for env_name, provider, description in definitions:
            raw_value = env_values.get(env_name, "")
            keys.append(
                {
                    "id": env_name.lower(),
                    "env_name": env_name,
                    "provider": provider,
                    "description": description,
                    "status": "Configured" if raw_value else "Missing",
                    "masked_value": _mask_secret(raw_value),
                    "updated_at": datetime.fromtimestamp(
                        self.env_path.stat().st_mtime,
                        tz=timezone.utc,
                    ).isoformat()
                    if self.env_path.exists()
                    else None,
                }
            )
        return keys

    def update_api_key(self, env_name: str, value: str) -> Dict[str, Any]:
        allowed = {"OPENAI_API_KEY", "JWT_SECRET_KEY", "PULSE_BACKEND_URL"}
        if env_name not in allowed:
            raise KeyError(env_name)
        env_values = self._read_env()
        env_values[env_name] = value.strip()
        self._write_env(env_values)
        updated = next(
            item for item in self.list_api_keys() if item.get("env_name") == env_name
        )
        return updated

    def generate_summary(self, days: int = 1) -> Dict[str, Any]:
        handoffs = self._read_json_list(self.handoffs_path)
        sessions = self._read_json_list(self.sessions_path)
        threshold = datetime.now(timezone.utc) - timedelta(days=max(1, days))

        def _is_recent(raw: Any) -> bool:
            if not isinstance(raw, str):
                return False
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return False
            return parsed >= threshold

        recent_sessions = [item for item in sessions if _is_recent(item.get("updated_at"))]
        recent_handoffs = [item for item in handoffs if _is_recent(item.get("created_at"))]
        open_handoffs = [item for item in handoffs if item.get("status") in {"Open", "InProgress"}]

        lines = [
            f"Window: last {max(1, days)} day(s)",
            f"- Sessions active: {len(recent_sessions)}",
            f"- New handoffs: {len(recent_handoffs)}",
            f"- Open handoffs: {len(open_handoffs)}",
        ]

        if recent_handoffs:
            lines.append("")
            lines.append("Recent handoffs:")
            for handoff in recent_handoffs[:5]:
                topic = handoff.get("topic") or "Untitled"
                resident_name = handoff.get("resident_name") or "Resident"
                status = handoff.get("status") or "Open"
                lines.append(f"- {resident_name}: {topic} ({status})")

        return {
            "days": max(1, days),
            "generated_at": _utc_now_iso(),
            "metrics": {
                "sessions_active": len(recent_sessions),
                "handoffs_created": len(recent_handoffs),
                "handoffs_open": len(open_handoffs),
            },
            "summary": "\n".join(lines),
        }
