from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .conversation import ConversationEngine
from .memory import SQLiteMemoryStore


class CarlRuntime:
    """
    Main Carl OS entry point for GvAI.

    The FastAPI server will call this runtime instead of managing
    conversation sessions and persistent memory directly.
    """

    def __init__(
        self,
        database_path: str | Path = "data/carl_memory.sqlite3",
    ) -> None:
        self.memory_store = SQLiteMemoryStore(database_path)
        self.conversation = ConversationEngine(self.memory_store)
        self._user_sessions: Dict[str, str] = {}

    def get_or_create_session(
        self,
        user_id: str,
    ) -> str:
        if not user_id.strip():
            raise ValueError("user_id cannot be empty.")

        existing = self._user_sessions.get(user_id)

        if existing:
            return existing

        session = self.conversation.start_session(user_id)
        self._user_sessions[user_id] = session.session_id

        return session.session_id

    def build_chat_context(
        self,
        user_id: str,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> List[dict]:
        session_id = self.get_or_create_session(user_id)
        session = self.conversation.get_session(session_id)

        if history and not session.turns:
            for item in history:
                role = str(item.get("role", "")).strip()
                content = str(item.get("content", "")).strip()

                if role in {"user", "assistant", "system"} and content:
                    self.conversation.add_turn(
                        session_id,
                        role,
                        content,
                    )

        return self.conversation.build_context(
            session_id,
            message,
        )

    def record_exchange(
        self,
        user_id: str,
        user_message: str,
        assistant_reply: str,
    ) -> None:
        session_id = self.get_or_create_session(user_id)

        self.conversation.add_turn(
            session_id,
            "user",
            user_message,
        )

        self.conversation.add_turn(
            session_id,
            "assistant",
            assistant_reply,
        )

    def remember(
        self,
        user_id: str,
        content: str,
        *,
        importance: float = 0.5,
        kind: str = "episodic",
    ) -> str:
        session_id = self.get_or_create_session(user_id)

        memory = self.conversation.remember(
            session_id,
            content,
            importance=importance,
            kind=kind,
        )

        return memory.memory_id

    def opening_message(
        self,
        user_id: str,
    ) -> str:
        session_id = self.get_or_create_session(user_id)

        return self.conversation.opening_message(
            session_id
        )
