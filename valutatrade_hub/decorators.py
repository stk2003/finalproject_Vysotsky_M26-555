"""Декораторы для логирования доменных операций."""

import functools

from valutatrade_hub.logging_config import get_logger

logger = get_logger("actions")


def _extract(args, kwargs, name, position=None, default=None):
    """Достаёт аргумент функции по имени либо по позиции."""
    if name in kwargs:
        return kwargs[name]
    if position is not None and len(args) > position:
        return args[position]
    return default


def log_action(action=None, verbose=False):
    """Логирует операцию BUY/SELL/REGISTER/LOGIN и не глотает исключения.

    Можно использовать и как @log_action, и как @log_action(verbose=True).
    """

    def decorator(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            name = action or function.__name__.upper()
            user = _extract(args, kwargs, "username", 0)
            if user is None:
                user = _extract(args, kwargs, "user_id", 0, "-")
            currency = _extract(
                args, kwargs, "currency_code", 1, kwargs.get("code", "-")
            )
            amount = _extract(args, kwargs, "amount", 2, "-")
            base = _extract(args, kwargs, "base_currency", default="USD")

            try:
                result = function(*args, **kwargs)
            except Exception as error:
                logger.info(
                    "%s user=%r currency=%r amount=%s result=ERROR "
                    "error_type=%s error_message=%s",
                    name,
                    user,
                    currency,
                    amount,
                    type(error).__name__,
                    error,
                )
                raise

            extra = ""
            if verbose and isinstance(result, dict):
                extra = f" before={result.get('before')} after={result.get('after')}"
            logger.info(
                "%s user=%r currency=%r amount=%s base=%r result=OK%s",
                name,
                user,
                currency,
                amount,
                base,
                extra,
            )
            return result

        return wrapper

    if callable(action):
        function = action
        action = None
        return decorator(function)
    return decorator
