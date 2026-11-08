"""Чтение и атомарная запись файлов курсов."""

import json
import os
from datetime import datetime, timezone

from valutatrade_hub.parser_service.config import ParserConfig


def _write_json(path, payload):
    """Атомарно записывает JSON: временный файл -> os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _read_json(path, fallback):
    """Читает JSON, при сбое возвращает значение по умолчанию."""
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return fallback


class RatesStorage:
    """Хранит текущий снимок курсов и историю измерений."""

    def __init__(self, config=None):
        """Запоминает пути к файлам хранилища."""
        self.config = config or ParserConfig()

    def load_rates(self):
        """Возвращает текущий кэш курсов."""
        return _read_json(self.config.rates_path, {"pairs": {}, "last_refresh": None})

    def save_snapshot(self, pairs):
        """Сохраняет снимок текущих курсов и время обновления."""
        existing = self.load_rates()
        current = existing.get("pairs", {})
        for key, value in pairs.items():
            if key not in current or value["updated_at"] >= current[key]["updated_at"]:
                current[key] = value

        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        payload = {"pairs": current, "last_refresh": now}
        _write_json(self.config.rates_path, payload)
        return payload

    def append_history(self, records):
        """Добавляет новые измерения в историю exchange_rates.json."""
        if not records:
            return 0
        history = _read_json(self.config.history_path, [])
        known = {item.get("id") for item in history}
        added = 0
        for record in records:
            if record["id"] in known:
                continue
            history.append(record)
            known.add(record["id"])
            added += 1
        _write_json(self.config.history_path, history)
        return added
