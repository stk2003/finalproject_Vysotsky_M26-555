"""Бизнес-логика: регистрация, вход, сделки и запросы курсов."""

from datetime import datetime, timezone

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    AuthenticationError,
    WalletNotFoundError,
)
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import (
    convert_amount,
    get_rate_value,
    rate_key,
    validate_amount,
    validate_currency_code,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import get_database
from valutatrade_hub.infra.settings import get_settings


def _now_iso():
    """Текущее время в ISO-формате без микросекунд."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _user_to_dict(user):
    """Сериализует пользователя для users.json."""
    return {
        "user_id": user.user_id,
        "username": user.username,
        "hashed_password": user.hashed_password,
        "salt": user.salt,
        "registration_date": user.registration_date,
    }


def _user_from_dict(data):
    """Восстанавливает пользователя из users.json."""
    return User(
        data["user_id"],
        data["username"],
        data["hashed_password"],
        data["salt"],
        data["registration_date"],
    )


def find_user(username):
    """Возвращает объект User по имени или None."""
    wanted = str(username).strip().lower()
    for data in get_database().load_users():
        if str(data["username"]).lower() == wanted:
            return _user_from_dict(data)
    return None


def get_portfolio(user_id):
    """Загружает портфель пользователя и подставляет объект User."""
    user = None
    for data in get_database().load_users():
        if int(data["user_id"]) == int(user_id):
            user = _user_from_dict(data)
            break

    for data in get_database().load_portfolios():
        if int(data["user_id"]) == int(user_id):
            raw_wallets = data.get("wallets", {})
            wallets = {
                code: value["balance"] if isinstance(value, dict) else value
                for code, value in raw_wallets.items()
            }
            return Portfolio(user_id, wallets, user)
    return Portfolio(user_id, user=user)


def _save_portfolio(portfolio):
    """Сохраняет портфель в portfolios.json."""
    db = get_database()
    records = db.load_portfolios()
    payload = {
        "user_id": portfolio.user_id,
        "wallets": {
            code: {"balance": wallet.balance}
            for code, wallet in portfolio.wallets.items()
        },
    }
    records = [r for r in records if int(r["user_id"]) != portfolio.user_id]
    records.append(payload)
    db.save_portfolios(records)


def _current_rates():
    """Возвращает кэш курсов, пустой кэш допустим для покупки."""
    return get_database().load_rates()


def _rates_are_stale(meta, ttl):
    """Проверяет, старше ли записи порога TTL."""
    updated_at = (meta or {}).get("updated_at")
    if not updated_at:
        return True
    try:
        moment = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
    except ValueError:
        return True
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - moment).total_seconds()
    return age > ttl


def _try_refresh_rates():
    """Пытается обновить курсы через Parser Service."""
    from valutatrade_hub.parser_service.updater import update_rates

    return update_rates()


@log_action("REGISTER", verbose=True)
def register(username, password):
    """Регистрирует нового пользователя и создаёт пустой портфель."""
    db = get_database()
    users = db.load_users()
    cleaned = str(username or "").strip()
    if any(str(u["username"]).lower() == cleaned.lower() for u in users):
        raise AuthenticationError(f"Имя пользователя '{cleaned}' уже занято")

    user = User.create(db.next_user_id(), cleaned, password)
    users.append(_user_to_dict(user))
    db.save_users(users)

    records = db.load_portfolios()
    records.append({"user_id": user.user_id, "wallets": {}})
    db.save_portfolios(records)
    return user.get_user_info()


@log_action("LOGIN")
def login(username, password):
    """Проверяет учётные данные и возвращает открытые данные пользователя."""
    user = find_user(username)
    if user is None:
        raise AuthenticationError(f"Пользователь '{username}' не найден")
    if not user.verify_password(password):
        raise AuthenticationError("Неверный пароль")
    return user.get_user_info()


def portfolio_report(user_id, base_currency=None):
    """Собирает данные для команды show-portfolio."""
    settings = get_settings()
    base = (base_currency or settings.base_currency).strip().upper()
    get_currency(base)

    portfolio = get_portfolio(user_id)
    rates = _current_rates()
    rows = []
    total = 0.0
    for code, wallet in sorted(portfolio.wallets.items()):
        value = None
        try:
            value = convert_amount(wallet.balance, code, base, rates)
            total += value
        except ApiRequestError:
            value = None
        rows.append({"currency_code": code, "balance": wallet.balance, "value": value})
    username = portfolio.user.username if portfolio.user else "-"
    return {
        "username": username,
        "base": base,
        "rows": rows,
        "total": total,
        "empty": not rows,
    }


@log_action(verbose=True)
def buy(user_id, currency_code, amount, username=None):
    """Покупает валюту: создаёт кошелёк и пополняет его."""
    value = validate_amount(amount)
    code = validate_currency_code(currency_code)
    base = get_settings().base_currency

    rates = _current_rates()
    try:
        rate, _ = get_rate_value(code, base, rates)
    except ApiRequestError as error:
        raise ApiRequestError(f"Не удалось получить курс для {code}->{base}") from error

    portfolio = get_portfolio(user_id)
    wallet = portfolio.add_currency(code)
    before = wallet.balance
    wallet.deposit(value)
    _save_portfolio(portfolio)

    return {
        "currency_code": code,
        "amount": value,
        "before": before,
        "after": wallet.balance,
        "rate": rate,
        "cost": value * rate,
        "base": base,
    }


@log_action(verbose=True)
def sell(user_id, currency_code, amount, username=None):
    """Продаёт валюту: списывает её и зачисляет эквивалент в USD."""
    value = validate_amount(amount)
    code = validate_currency_code(currency_code)
    base = get_settings().base_currency

    portfolio = get_portfolio(user_id)
    if not portfolio.has_wallet(code):
        raise WalletNotFoundError(code)

    rates = _current_rates()
    try:
        rate, _ = get_rate_value(code, base, rates)
    except ApiRequestError as error:
        raise ApiRequestError(f"Не удалось получить курс для {code}->{base}") from error

    wallet = portfolio.get_wallet(code)
    before = wallet.balance
    wallet.withdraw(value)

    proceeds = value * rate
    if code != "USD":
        portfolio.add_currency("USD").deposit(proceeds)
    _save_portfolio(portfolio)

    return {
        "currency_code": code,
        "amount": value,
        "before": before,
        "after": wallet.balance,
        "rate": rate,
        "proceeds": proceeds,
        "base": base,
    }


def get_rate(from_code, to_code):
    """Возвращает курс пары с учётом TTL кэша."""
    source = validate_currency_code(from_code)
    target = validate_currency_code(to_code)
    settings = get_settings()
    db = get_database()

    rates = db.load_rates()
    if not rates.get("pairs"):
        try:
            _try_refresh_rates()
        except ApiRequestError:
            pass
        rates = db.load_rates()
    if not rates.get("pairs"):
        raise ApiRequestError(f"курс {source}->{target} недоступен")

    try:
        rate, meta = get_rate_value(source, target, rates)
    except ApiRequestError as error:
        raise ApiRequestError(
            f"Курс {source}->{target} недоступен. Повторите попытку позже."
        ) from error

    stale = _rates_are_stale(meta, settings.rates_ttl)
    if stale:
        try:
            _try_refresh_rates()
            rates = db.load_rates()
            rate, meta = get_rate_value(source, target, rates)
            stale = _rates_are_stale(meta, settings.rates_ttl)
        except ApiRequestError:
            stale = True

    reverse = None
    try:
        reverse, _ = get_rate_value(target, source, rates)
    except ApiRequestError:
        reverse = None

    return {
        "from_currency": source,
        "to_currency": target,
        "rate": rate,
        "updated_at": (meta or {}).get("updated_at"),
        "source": (meta or {}).get("source"),
        "reverse_rate": reverse,
        "stale": stale,
        "pair": rate_key(source, target),
    }
