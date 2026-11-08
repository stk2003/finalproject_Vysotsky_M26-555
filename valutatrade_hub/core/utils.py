"""Вспомогательные функции: валидации и конвертация валют."""

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InvalidAmountError,
)


def validate_amount(amount):
    """Проверяет, что сумма — положительное число, и возвращает float."""
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        raise InvalidAmountError("'amount' должен быть положительным числом")
    return float(amount)


def validate_currency_code(code):
    """Нормализует код валюты и проверяет его по реестру."""
    if not isinstance(code, str) or not code.strip():
        raise CurrencyNotFoundError(str(code))
    normalized = code.strip().upper()
    get_currency(normalized)
    return normalized


def rate_key(from_code, to_code):
    """Собирает ключ пары курса вида BTC_USD."""
    return f"{from_code}_{to_code}"


def _invert(rate):
    """Возвращает обратный курс."""
    if not rate:
        raise ApiRequestError("нулевой курс")
    return 1.0 / rate


def get_rate_value(from_code, to_code, rates):
    """Достаёт курс пары из кэша, при необходимости — через USD."""
    if from_code == to_code:
        return 1.0, {"rate": 1.0, "source": "identity"}
    pairs = (rates or {}).get("pairs", {})
    direct = pairs.get(rate_key(from_code, to_code))
    if direct is not None:
        return float(direct["rate"]), direct

    via_usd_from = pairs.get(rate_key(from_code, "USD"))
    via_usd_to = pairs.get(rate_key(to_code, "USD"))
    if via_usd_from is not None and via_usd_to is not None:
        rate = float(via_usd_from["rate"]) * _invert(float(via_usd_to["rate"]))
        return rate, via_usd_from

    if from_code == "USD" and via_usd_to is not None:
        return _invert(float(via_usd_to["rate"])), via_usd_to
    if to_code == "USD" and via_usd_from is not None:
        return float(via_usd_from["rate"]), via_usd_from

    raise ApiRequestError(f"курс {from_code}->{to_code} отсутствует в кэше")


def convert_amount(amount, from_code, to_code, rates):
    """Конвертирует сумму между валютами по данным кэша."""
    from_code = from_code.strip().upper()
    to_code = to_code.strip().upper()
    if from_code == to_code:
        return float(amount)
    rate, _ = get_rate_value(from_code, to_code, rates)
    return float(amount) * rate
