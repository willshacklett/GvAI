from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    content: str
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant"}:
            raise ValueError(f"Unsupported role: {self.role}")

        if not self.content.strip():
            raise ValueError("Conversation content cannot be empty.")

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryRecord:
    content: str
    kind: str = "episodic"
    importance: float = 0.5
    source: str = "conversation"
    memory_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("Memory content cannot be empty.")

        if not 0.0 <= self.importance <= 1.0:
            raise ValueError("Memory importance must be between 0 and 1.")


@dataclass
class SessionState:
    session_id: str
    user_id: str
    turns: List[ConversationTurn] = field(default_factory=list)
    started_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def add_turn(self, turn: ConversationTurn) -> None:
        self.turns.append(turn)
        self.updated_at = utc_now_iso()
