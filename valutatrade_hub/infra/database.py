"""Singleton-менеджер JSON-хранилищ приложения."""

import json
import os

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.infra.settings import get_settings

USERS_FILE = "users.json"
PORTFOLIOS_FILE = "portfolios.json"
RATES_FILE = "rates.json"
HISTORY_FILE = "exchange_rates.json"

EMPTY_RATES = {"pairs": {}, "last_refresh": None}


class DatabaseManager:
    """Абстракция над JSON-файлами каталога data/."""

    _instance = None

    def __new__(cls):
        # __new__ выбран за простоту: один синглтон на процесс.
        if cls._instance is None:
            instance = super().__new__(cls)
            instance.settings = get_settings()
            cls._instance = instance
        return cls._instance

    def _path(self, filename):
        """Возвращает полный путь к файлу хранилища."""
        return self.settings.data_dir / filename

    def ensure_storage(self):
        """Создаёт каталог data/ и пустые файлы, если их ещё нет."""
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        defaults = {
            USERS_FILE: [],
            PORTFOLIOS_FILE: [],
            RATES_FILE: dict(EMPTY_RATES),
            HISTORY_FILE: [],
        }
        for filename, content in defaults.items():
            path = self._path(filename)
            if not path.exists():
                self._write(path, content)

    def _read(self, filename, fallback):
        """Читает JSON-файл, при сбое возвращает значение по умолчанию."""
        path = self._path(filename)
        try:
            with open(path, encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError):
            return fallback

    def _write(self, path, content):
        """Атомарно записывает JSON: временный файл -> os.replace."""
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as file:
            json.dump(content, file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)

    def load_users(self):
        """Возвращает список пользователей."""
        self.ensure_storage()
        return self._read(USERS_FILE, [])

    def save_users(self, users):
        """Сохраняет список пользователей."""
        self.ensure_storage()
        self._write(self._path(USERS_FILE), users)

    def load_portfolios(self):
        """Возвращает список портфелей."""
        self.ensure_storage()
        return self._read(PORTFOLIOS_FILE, [])

    def save_portfolios(self, portfolios):
        """Сохраняет список портфелей."""
        self.ensure_storage()
        self._write(self._path(PORTFOLIOS_FILE), portfolios)

    def load_rates(self):
        """Возвращает кэш текущих курсов."""
        self.ensure_storage()
        return self._read(RATES_FILE, dict(EMPTY_RATES))

    def save_rates(self, rates):
        """Сохраняет кэш текущих курсов."""
        self.ensure_storage()
        self._write(self._path(RATES_FILE), rates)

    def load_history(self):
        """Возвращает историю измерений курсов."""
        self.ensure_storage()
        return self._read(HISTORY_FILE, [])

    def append_history(self, records):
        """Добавляет новые записи в историю курсов."""
        self.ensure_storage()
        history = self._read(HISTORY_FILE, [])
        history.extend(records)
        self._write(self._path(HISTORY_FILE), history)

    def next_user_id(self):
        """Генерирует следующий идентификатор пользователя."""
        users = self.load_users()
        if not users:
            return 1
        return max(int(user["user_id"]) for user in users) + 1


def get_database():
    """Возвращает общий экземпляр DatabaseManager."""
    return DatabaseManager()


def read_rates_or_raise():
    """Читает кэш курсов, пустой кэш считается ошибкой API."""
    rates = get_database().load_rates()
    if not rates.get("pairs"):
        raise ApiRequestError("локальный кэш курсов пуст")
    return rates
