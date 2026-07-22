from __future__ import annotations

from typing import Dict, List, Optional
from uuid import uuid4

from .identity import CarlIdentity
from .memory import SQLiteMemoryStore
from .models import ConversationTurn, MemoryRecord, SessionState


class ConversationEngine:
    def __init__(
        self,
        memory_store: SQLiteMemoryStore,
        identity: Optional[CarlIdentity] = None,
    ) -> None:
        self.memory_store = memory_store
        self.identity = identity or CarlIdentity()
        self._sessions: Dict[str, SessionState] = {}

    def start_session(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> SessionState:
        if not user_id.strip():
            raise ValueError("user_id cannot be empty.")

        session = SessionState(
            session_id=session_id or str(uuid4()),
            user_id=user_id,
        )

        self._sessions[session.session_id] = session
        return session

    def get_session(
        self,
        session_id: str,
    ) -> SessionState:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError(
                f"Unknown session_id: {session_id}"
            ) from exc

    def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> ConversationTurn:
        session = self.get_session(session_id)

        turn = ConversationTurn(
            role=role,
            content=content,
        )

        session.add_turn(turn)
        return turn

    def remember(
        self,
        session_id: str,
        content: str,
        *,
        kind: str = "episodic",
        importance: float = 0.5,
        source: str = "conversation",
        metadata: Optional[dict] = None,
    ) -> MemoryRecord:
        session = self.get_session(session_id)

        record = MemoryRecord(
            content=content,
            kind=kind,
            importance=importance,
            source=source,
            metadata=metadata or {},
        )

        return self.memory_store.remember(
            session.user_id,
            record,
        )

    def retrieve_memories(
        self,
        session_id: str,
        query: str,
        *,
        limit: int = 6,
    ) -> List[MemoryRecord]:
        session = self.get_session(session_id)

        return self.memory_store.search(
            session.user_id,
            query,
            limit=limit,
        )

    def build_context(
        self,
        session_id: str,
        current_message: str,
        *,
        memory_limit: int = 6,
        turn_limit: int = 12,
    ) -> List[dict]:
        session = self.get_session(session_id)

        memories = self.retrieve_memories(
            session_id,
            current_message,
            limit=memory_limit,
        )

        context: List[dict] = [
            {
                "role": "system",
                "content": self.identity.system_prompt(),
            }
        ]

        if memories:
            memory_text = "\n".join(
                f"- [{memory.kind}] {memory.content}"
                for memory in memories
            )

            context.append(
                {
                    "role": "system",
                    "content": (
                        "Relevant persistent memory:\n"
                        f"{memory_text}\n\n"
                        "Use only when relevant. "
                        "Do not invent memories."
                    ),
                }
            )

        context.extend(
            turn.to_dict()
            for turn in session.turns[-turn_limit:]
        )

        context.append(
            {
                "role": "user",
                "content": current_message,
            }
        )

        return context

    def opening_message(
        self,
        session_id: str,
    ) -> str:
        session = self.get_session(session_id)

        memories = self.memory_store.recent(
            session.user_id,
            limit=3,
        )

        if not memories:
            return (
                "Morning. I’m here, and I’m ready to build. "
                "What are we working on?"
            )

        strongest = memories[0].content.rstrip(".!?")

        return (
            "Morning. I remember where we left off: "
            f"{strongest}. Ready to build?"
        )
