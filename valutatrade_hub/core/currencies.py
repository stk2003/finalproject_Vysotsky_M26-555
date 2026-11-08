"""Иерархия валют и реестр поддерживаемых кодов."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Абстрактное представление любой валюты."""

    def __init__(self, name, code):
        """Создаёт валюту с человекочитаемым именем и кодом."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым")
        normalized = code.strip().upper() if isinstance(code, str) else ""
        if not 2 <= len(normalized) <= 5 or not normalized.isalnum():
            raise ValueError(f"Некорректный код валюты: {code}")
        self.name = name.strip()
        self.code = normalized

    def __str__(self):
        """Возвращает код валюты."""
        return self.code

    @abstractmethod
    def get_display_info(self):
        """Строковое представление валюты для CLI и логов."""


class FiatCurrency(Currency):
    """Фиатная валюта с указанием эмитента."""

    def __init__(self, name, code, issuing_country):
        """Добавляет к базовой валюте страну или зону эмиссии."""
        super().__init__(name, code)
        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("Страна эмиссии не может быть пустой")
        self.issuing_country = issuing_country.strip()

    def get_display_info(self):
        """Формирует строку вида [FIAT] USD — US Dollar (Issuing: ...)."""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом и капитализацией."""

    def __init__(self, name, code, algorithm, market_cap):
        """Задаёт алгоритм майнинга и последнюю капитализацию."""
        super().__init__(name, code)
        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("Алгоритм не может быть пустым")
        if not isinstance(market_cap, (int, float)) or market_cap < 0:
            raise ValueError("Капитализация должна быть положительным числом")
        self.algorithm = algorithm.strip()
        self.market_cap = float(market_cap)

    def get_display_info(self):
        """Формирует строку вида [CRYPTO] BTC — Bitcoin (Algo: ..., MCAP: ...)."""
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})".Replace("e+", "e")
        )


_CURRENCIES = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("British Pound", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.4e11),
    "SOL": CryptoCurrency("Solana", "SOL", "Proof of History", 7.5e10),
}

SUPPORTED_CODES = tuple(_CURRENCIES)


def get_currency(code):
    """Возвращает объект валюты по коду или бросает CurrencyNotFoundError."""
    if not isinstance(code, str):
        raise CurrencyNotFoundError(str(code))
    currency = _CURRENCIES.get(code.strip().upper())
    if currency is None:
        raise CurrencyNotFoundError(code.strip().upper())
    return currency


def supported_codes():
    """Возвращает отсортированный список поддерживаемых кодов."""
    return sorted(_CURRENCIES)
