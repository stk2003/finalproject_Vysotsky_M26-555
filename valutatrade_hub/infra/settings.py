"""Singleton-загрузчик конфигурации проекта."""

import tomllib
from pathlib import Path

PYPROJECT_PATH = "pyproject.toml"


def find_project_root():
    """Ищет корень проекта по файлу pyproject.toml."""
    for start in (Path.cwd(), Path(__file__).resolve()):
        for parent in (start, *start.parents):
            if (parent / PYPROJECT_PATH).exists():
                return parent
    return Path.cwd()


PROJECT_ROOT = find_project_root()
PYPROJECT_FILE = PROJECT_ROOT / PYPROJECT_PATH

DEFAULTS = {
    "data_dir": "data",
    "rates_ttl_seconds": 300,
    "default_base_currency": "USD",
    "log_dir": "logs",
    "log_level": "INFO",
}


class SettingsLoader:
    """Единственный в приложении источник настроек проекта."""

    _instance = None

    def __new__(cls):
        # Выбран __new__, а не метакласс: способ проще и читабельнее,
        # а для одного синглтона этого достаточно.
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._config = dict(DEFAULTS)
            instance.reload()
            cls._instance = instance
        return cls._instance

    def reload(self):
        """Перечитывает секцию [tool.valutatrade] из pyproject.toml."""
        try:
            with open(PYPROJECT_FILE, "rb") as file:
                data = tomllib.load(file)
        except (OSError, tomllib.TOMLDecodeError):
            return dict(self._config)
        section = data.get("tool", {}).get("valutatrade", {})
        self._config.update(section)
        return dict(self._config)

    def get(self, key, default=None):
        """Возвращает значение настройки или значение по умолчанию."""
        return self._config.get(key, default)

    @property
    def data_dir(self):
        """Абсолютный путь к каталогу с JSON-хранилищем."""
        return PROJECT_ROOT / self.get("data_dir", DEFAULTS["data_dir"])

    @property
    def log_dir(self):
        """Абсолютный путь к каталогу с логами."""
        return PROJECT_ROOT / self.get("log_dir", DEFAULTS["log_dir"])

    @property
    def rates_ttl(self):
        """Срок годности кэша курсов в секундах."""
        return int(self.get("rates_ttl_seconds", DEFAULTS["rates_ttl_seconds"]))

    @property
    def base_currency(self):
        """Базовая валюта по умолчанию."""
        return str(self.get("default_base_currency", "USD")).upper()


def get_settings():
    """Возвращает общий экземпляр SettingsLoader."""
    return SettingsLoader()
