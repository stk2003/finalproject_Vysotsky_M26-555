"""Клиенты внешних API курсов с единым интерфейсом."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


def _now_iso():
    """Текущее время в ISO-формате с меткой UTC."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class BaseApiClient(ABC):
    """Абстрактный клиент, возвращающий курсы в общем формате."""

    source = "unknown"

    @abstractmethod
    def fetch_rates(self):
        """Возвращает словарь вида {'BTC_USD': 59337.21, ...}."""


class CoinGeckoClient(BaseApiClient):
    """Клиент криптовалют через публичный API CoinGecko."""

    source = "CoinGecko"

    def __init__(self, config=None):
        """Хранит конфигурацию запроса."""
        self.config = config or ParserConfig()

    def fetch_rates(self):
        """Запрашивает цены криптовалют в USD."""
        config = self.config
        coins = ",".join(
            config.crypto_id_map[code] for code in config.crypto_currencies
        )
        params = {"ids": coins, "vs_currencies": config.base_currency.lower()}
        try:
            response = requests.get(
                config.coingecko_url,
                params=params,
                timeout=config.request_timeout,
            )
        except requests.exceptions.RequestException as error:
            raise ApiRequestError(f"Network error ({self.source}): {error}") from error

        if response.status_code == 429:
            raise ApiRequestError(f"{self.source}: превышен лимит запросов (429)")
        if response.status_code != 200:
            raise ApiRequestError(f"{self.source}: HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as error:
            raise ApiRequestError(f"{self.source}: некорректный JSON") from error

        rates = {}
        for code in config.crypto_currencies:
            coin_id = config.crypto_id_map[code]
            price = payload.get(coin_id, {}).get(config.base_currency.lower())
            if isinstance(price, (int, float)):
                rates[f"{code}_{config.base_currency}"] = float(price)
        if not rates:
            raise ApiRequestError(f"{self.source}: пустой ответ")
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Клиент фиатных валют через ExchangeRate-API."""

    source = "ExchangeRate-API"

    def __init__(self, config=None):
        """Хранит конфигурацию и ключ из переменной окружения."""
        self.config = config or ParserConfig()

    def fetch_rates(self):
        """Запрашивает курсы фиатных валют относительно базовой."""
        config = self.config
        if not config.exchangerate_api_key:
            raise ApiRequestError("не задан EXCHANGERATE_API_KEY для ExchangeRate-API")

        url = (
            f"{config.exchangerate_api_url}/{config.exchangerate_api_key}"
            f"/latest/{config.base_currency}"
        )
        try:
            response = requests.get(url, timeout=config.request_timeout)
        except requests.exceptions.RequestException as error:
            raise ApiRequestError(f"Network error ({self.source}): {error}") from error

        if response.status_code == 429:
            raise ApiRequestError(f"{self.source}: превышен лимит запросов (429)")
        if response.status_code == 401:
            raise ApiRequestError(f"{self.source}: неверный API-ключ (401)")
        if response.status_code != 200:
            raise ApiRequestError(f"{self.source}: HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as error:
            raise ApiRequestError(f"{self.source}: некорректный JSON") from error

        if payload.get("result") != "success":
            reason = payload.get("error-type", "неизвестная ошибка")
            raise ApiRequestError(f"{self.source}: {reason}")

        rates = {}
        for code in config.fiat_currencies:
            # API отдаёт, сколько единиц валюты за 1 базовую.
            # Храним канонический вид X_USD: 1 единица валюты в базовых.
            value = payload.get("rates", {}).get(code)
            if isinstance(value, (int, float)) and value:
                rates[f"{code}_{config.base_currency}"] = 1.0 / float(value)
        if not rates:
            raise ApiRequestError(f"{self.source}: пустой ответ")
        return rates


def build_clients(sources=None):
    """Создаёт нужный набор клиентов по списку имён источников."""
    available = {
        "coingecko": CoinGeckoClient,
        "exchangerate": ExchangeRateApiClient,
    }
    if not sources:
        return [cls() for cls in available.values()]
    clients = []
    for name in sources:
        key = str(name).strip().lower()
        if key not in available:
            raise ApiRequestError(f"неизвестный источник '{name}'")
        clients.append(available[key]())
    return clients


__all__ = [
    "ApiRequestError",
    "BaseApiClient",
    "CoinGeckoClient",
    "ExchangeRateApiClient",
    "ParserConfig",
    "build_clients",
]
