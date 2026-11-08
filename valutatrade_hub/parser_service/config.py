"""Конфигурация Parser Service: ключи, эндпоинты, списки валют."""

import os
from dataclasses import dataclass, field

from valutatrade_hub.infra.settings import find_project_root

PROJECT_ROOT = find_project_root()


@dataclass
class ParserConfig:
    """Параметры запросов к внешним API и пути к файлам."""

    exchangerate_api_key: str = field(
        default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY", "")
    )
    coingecko_url: str = "https://api.coingecko.com/api/v3/simple/price"
    exchangerate_api_url: str = "https://v6.exchangerate-api.com/v6"

    base_currency: str = "USD"
    fiat_currencies: tuple = ("EUR", "GBP", "RUB")
    crypto_currencies: tuple = ("BTC", "ETH", "SOL")
    crypto_id_map: dict = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )

    data_dir: str = "data"
    rates_file: str = "rates.json"
    history_file: str = "exchange_rates.json"
    request_timeout: int = 10

    @property
    def rates_path(self):
        """Полный путь к файлу текущих курсов."""
        return PROJECT_ROOT / self.data_dir / self.rates_file

    @property
    def history_path(self):
        """Полный путь к файлу истории курсов."""
        return PROJECT_ROOT / self.data_dir / self.history_file
