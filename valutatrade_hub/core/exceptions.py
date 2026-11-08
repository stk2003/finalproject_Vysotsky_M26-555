"""Пользовательские исключения ValutaTrade Hub."""


class ValutaTradeError(Exception):
    """Базовое исключение приложения."""


class InsufficientFundsError(ValutaTradeError):
    """Недостаточно средств на кошельке."""

    def __init__(self, available, required, code):
        """Формирует сообщение о нехватке средств."""
        super().__init__(
            f"Недостаточно средств: доступно {available} {code}, "
            f"требуется {required} {code}"
        )
        self.available = available
        self.required = required
        self.code = code


class CurrencyNotFoundError(ValutaTradeError):
    """Запрошенная валюта отсутствует в реестре."""

    def __init__(self, code):
        """Формирует сообщение о неизвестной валюте."""
        super().__init__(f"Неизвестная валюта '{code}'")
        self.code = code


class ApiRequestError(ValutaTradeError):
    """Сбой обращения к внешнему API курсов."""

    def __init__(self, reason):
        """Формирует сообщение о недоступности API."""
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")
        self.reason = reason


class WalletNotFoundError(ValutaTradeError):
    """У пользователя нет кошелька с такой валютой."""

    def __init__(self, code):
        """Формирует подсказку, что кошелёк создаётся при покупке."""
        super().__init__(
            f"У вас нет кошелька '{code}'. Добавьте валюту: "
            "она создаётся автоматически при первой покупке."
        )
        self.code = code


class AuthenticationError(ValutaTradeError):
    """Ошибка входа или регистрации пользователя."""


class InvalidAmountError(ValutaTradeError):
    """Сумма операции не является положительным числом."""
