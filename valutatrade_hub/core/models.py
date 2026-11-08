"""Модели предметной области: пользователь, кошелёк, портфель."""

import hashlib
import secrets
from datetime import datetime, timezone

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    AuthenticationError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    InvalidAmountError,
)
from valutatrade_hub.core.utils import convert_amount

MIN_PASSWORD_LENGTH = 4


def _is_positive_number(amount):
    """Проверяет, что значение — положительное число (bool не считается)."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return False
    return amount > 0


class User:
    """Пользователь системы с хешированным паролем и солью."""

    def __init__(self, user_id, username, hashed_password, salt, registration_date):
        """Создаёт пользователя из уже готовых учётных данных."""
        self._user_id = int(user_id)
        self._salt = salt
        self._hashed_password = hashed_password
        self._registration_date = registration_date
        self._username = ""
        self.username = username

    @classmethod
    def create(cls, user_id, username, password):
        """Генерирует соль и хеш пароля для нового пользователя."""
        if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
            raise AuthenticationError(
                f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов"
            )
        salt = secrets.token_hex(4)
        hashed = hashlib.sha256((password + salt).encode()).hexdigest()
        created = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        return cls(user_id, username, hashed, salt, created)

    @property
    def user_id(self):
        """Уникальный идентификатор пользователя."""
        return self._user_id

    @property
    def username(self):
        """Имя пользователя."""
        return self._username

    @username.setter
    def username(self, value):
        """Проверяет, что имя не пустое."""
        if not isinstance(value, str) or not value.strip():
            raise AuthenticationError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self):
        """Хеш пароля пользователя."""
        return self._hashed_password

    @property
    def salt(self):
        """Соль пользователя."""
        return self._salt

    @property
    def registration_date(self):
        """Дата регистрации в формате ISO."""
        return self._registration_date

    def _make_hash(self, password):
        """Считает SHA-256 от пароля и текущей соли."""
        return hashlib.sha256((password + self._salt).encode()).hexdigest()

    def verify_password(self, password):
        """Проверяет, совпадает ли пароль с сохранённым хешем."""
        if not isinstance(password, str):
            return False
        return secrets.compare_digest(self._make_hash(password), self._hashed_password)

    def change_password(self, new_password):
        """Перехеширует пароль с новой солью."""
        if not isinstance(new_password, str) or len(new_password) < MIN_PASSWORD_LENGTH:
            raise AuthenticationError(
                f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов"
            )
        self._salt = secrets.token_hex(4)
        self._hashed_password = self._make_hash(new_password)

    def get_user_info(self):
        """Возвращает открытые данные пользователя без пароля и соли."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date,
        }


class Wallet:
    """Кошелёк пользователя для одной валюты."""

    def __init__(self, currency_code, balance=0.0):
        """Создаёт кошелёк указанной валюты с нулевым балансом по умолчанию."""
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")
        self.currency_code = currency_code.strip().upper()
        self._balance = 0.0
        self.balance = balance

    @property
    def balance(self):
        """Текущий баланс кошелька."""
        return self._balance

    @balance.setter
    def balance(self, value):
        """Запрещает отрицательные значения и нечисловые типы."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidAmountError("Баланс должен быть положительным числом")
        if value < 0:
            raise InvalidAmountError("Баланс не может быть отрицательным")
        self._balance = round(float(value), 8)

    def deposit(self, amount):
        """Пополняет кошелёк на положительную сумму."""
        if not _is_positive_number(amount):
            raise InvalidAmountError("'amount' должен быть положительным числом")
        self.balance = self._balance + float(amount)
        return self._balance

    def withdraw(self, amount):
        """Снимает средства, если баланс это позволяет."""
        if not _is_positive_number(amount):
            raise InvalidAmountError("'amount' должен быть положительным числом")
        if amount > self._balance:
            raise InsufficientFundsError(
                f"{self._balance:.4f}", f"{amount:.4f}", self.currency_code
            )
        self.balance = self._balance - float(amount)
        return self._balance

    def get_balance_info(self):
        """Возвращает краткую информацию о балансе."""
        return {"currency_code": self.currency_code, "balance": self._balance}


class Portfolio:
    """Набор кошельков одного пользователя."""

    def __init__(self, user_id, wallets=None, user=None):
        """Создаёт портфель, при необходимости загружая готовые кошельки."""
        self._user_id = int(user_id)
        self._user = user
        self._wallets = {}
        for code, wallet in (wallets or {}).items():
            if isinstance(wallet, Wallet):
                self._wallets[wallet.currency_code.upper()] = wallet
            else:
                self._wallets[code.upper()] = Wallet(code, wallet)

    @property
    def user_id(self):
        """Идентификатор владельца портфеля."""
        return self._user_id

    @property
    def user(self):
        """Объект пользователя без возможности перезаписи."""
        return self._user

    @property
    def wallets(self):
        """Копия словаря кошельков."""
        return dict(self._wallets)

    def add_currency(self, currency_code):
        """Добавляет новый кошелёк, если такого кода ещё нет."""
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")
        code = currency_code.strip().upper()
        get_currency(code)
        if code not in self._wallets:
            self._wallets[code] = Wallet(code)
        return self._wallets[code]

    def get_wallet(self, currency_code):
        """Возвращает кошелёк по коду валюты."""
        code = str(currency_code).strip().upper()
        wallet = self._wallets.get(code)
        if wallet is None:
            raise CurrencyNotFoundError(code)
        return wallet

    def has_wallet(self, currency_code):
        """Проверяет наличие кошелька с указанным кодом."""
        return str(currency_code).strip().upper() in self._wallets

    def get_total_value(self, base_currency="USD", rates=None):
        """Считает суммарную стоимость всех кошельков в базовой валюте."""
        base = str(base_currency).strip().upper()
        get_currency(base)
        total = 0.0
        for wallet in self._wallets.values():
            if wallet.balance:
                total += convert_amount(
                    wallet.balance, wallet.currency_code, base, rates
                )
        return total
