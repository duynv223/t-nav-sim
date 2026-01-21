from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
from typing import Any

import yaml

from app.app_settings import AppSettings

logger = logging.getLogger("sim.settings")


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = Lock()
        self._settings = self._load()

    def get(self) -> AppSettings:
        with self._lock:
            return self._settings.model_copy(deep=True)

    def update(self, payload: AppSettings | dict[str, Any]) -> AppSettings:
        if isinstance(payload, AppSettings):
            settings = payload
        else:
            settings = AppSettings.model_validate(payload)
        with self._lock:
            self._settings = settings
            self._save(settings)
            logger.info("settings.update path=%s", self._path)
            return settings.model_copy(deep=True)

    def _load(self) -> AppSettings:
        if not self._path.exists():
            settings = AppSettings()
            self._save(settings)
            logger.info("settings.create_default path=%s", self._path)
            return settings
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw) or {}
            settings = AppSettings.model_validate(data)
            logger.info("settings.load path=%s", self._path)
            return settings
        except Exception:
            logger.exception("Failed to load settings at %s, using defaults.", self._path)
            return AppSettings()

    def _save(self, settings: AppSettings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = settings.model_dump()
        content = yaml.safe_dump(payload, sort_keys=False)
        self._path.write_text(content, encoding="utf-8")
        logger.info("settings.save path=%s", self._path)
