from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Dict, Optional
import secrets
import shutil


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
        self._load_existing_sessions()

    def create(self, name: Optional[str] = None) -> SessionInfo:
        session_id = self._next_id()
        root = self._base_dir / session_id
        root.mkdir(parents=True, exist_ok=True)
        info = SessionInfo(
            session_id=session_id,
            root=root,
            created_at=datetime.now(timezone.utc),
            name=name,
        )
        self._sessions[session_id] = info
        _write_meta(info)
        return info

    def _next_id(self) -> str:
        for _ in range(10):
            candidate = secrets.token_hex(4)
            if candidate not in self._sessions:
                return candidate
        raise RuntimeError("Failed to allocate session id")

    def get(self, session_id: str) -> Optional[SessionInfo]:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        info = self._sessions.pop(session_id, None)
        if not info:
            return False
        shutil.rmtree(info.root, ignore_errors=True)
        return True

    def _load_existing_sessions(self) -> None:
        for entry in self._base_dir.iterdir():
            if not entry.is_dir():
                continue
            session_id = entry.name
            info = _read_meta(entry, session_id)
            self._sessions[session_id] = info
        if self._sessions:
            logger.info("session.restore count=%d", len(self._sessions))


logger = logging.getLogger("sim.sessions")
_META_FILE = "session.json"


def _read_meta(root: Path, session_id: str) -> SessionInfo:
    meta_path = root / _META_FILE
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            created_at = _parse_created_at(data.get("created_at")) or _mtime(root)
            name = data.get("name") if isinstance(data.get("name"), str) else None
            return SessionInfo(
                session_id=session_id,
                root=root,
                created_at=created_at,
                name=name,
            )
        except Exception:
            logger.exception("session.meta.read_failed path=%s", meta_path)
    return SessionInfo(
        session_id=session_id,
        root=root,
        created_at=_mtime(root),
        name=None,
    )


def _write_meta(info: SessionInfo) -> None:
    payload = {
        "session_id": info.session_id,
        "created_at": info.created_at.isoformat(),
        "name": info.name,
    }
    path = info.root / _META_FILE
    try:
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("session.meta.write_failed path=%s", path)


def _parse_created_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _mtime(root: Path) -> datetime:
    return datetime.fromtimestamp(root.stat().st_mtime, tz=timezone.utc)
