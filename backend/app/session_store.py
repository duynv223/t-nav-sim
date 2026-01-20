from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
import shutil
import uuid


@dataclass(frozen=True)
class SessionInfo:
    session_id: str
    root: Path
    created_at: datetime
    name: Optional[str] = None


class SessionStore:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._sessions: Dict[str, SessionInfo] = {}
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def create(self, name: Optional[str] = None) -> SessionInfo:
        session_id = uuid.uuid4().hex
        root = self._base_dir / session_id
        root.mkdir(parents=True, exist_ok=True)
        info = SessionInfo(
            session_id=session_id,
            root=root,
            created_at=datetime.now(timezone.utc),
            name=name,
        )
        self._sessions[session_id] = info
        return info

    def get(self, session_id: str) -> Optional[SessionInfo]:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        info = self._sessions.pop(session_id, None)
        if not info:
            return False
        shutil.rmtree(info.root, ignore_errors=True)
        return True
