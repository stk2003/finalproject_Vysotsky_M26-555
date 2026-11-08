"""Командный интерфейс ValutaTrade Hub."""

import argparse
import json
import shlex
import sys

from prettytable import PrettyTable

from valutatrade_hub.core import usecases
from valutatrade_hub.core.currencies import supported_codes
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    ValutaTradeError,
)
from valutatrade_hub.logging_config import set_console_level
from valutatrade_hub.parser_service.api_clients import build_clients
from valutatrade_hub.parser_service.updater import RatesUpdater

SESSION = None
SESSION_FILE = "session.json"
BANNER = "*** ValutaTrade Hub ***"


def _session_path():
    """Путь к файлу с текущей сессией."""
    from valutatrade_hub.infra.settings import get_settings

    return get_settings().data_dir / SESSION_FILE


def _load_session():
    """Восстанавливает сессию из data/session.json."""
    try:
        with open(_session_path(), encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "user_id" not in data:
        return None
    return data


def _save_session(info):
    """Сохраняет сессию, чтобы команды работали в разных процессах."""
    path = _session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(info, file, ensure_ascii=False)


def _clear_session():
    """Удаляет файл сессии."""
    try:
        _session_path().unlink()
    except OSError:
        pass


def _fmt_amount(value):
    """Форматирует сумму: целые с двумя знаками, дробные с четырьмя."""
    if value is None:
        return "-"
    if abs(value) >= 1:
        return f"{value:,.2f}"
    return f"{value:,.4f}"


def _fmt_money(value):
    """Форматирует денежную сумму с разделителем тысяч."""
    if value is None:
        return "-"
    return f"{value:,.2f}"


def _fmt_rate(value):
    """Форматирует курс: мелкие значения — восемь знаков, крупные — два."""
    if value is None:
        return "-"
    if 0 < abs(value) < 0.01:
        return f"{value:.8f}"
    if abs(value) < 1000:
        return f"{value:.4f}"
    return f"{value:,.2f}"


def _fmt_time(value):
    """Приводит ISO-время к виду 2025-10-09 00:03:22."""
    if not value:
        return "-"
    return str(value).replace("T", " ").split("+")[0].replace("Z", "")


def _require_login():
    """Проверяет, что пользователь вошёл в систему."""
    if SESSION is None:
        print("Сначала выполните login")
        return None
    return SESSION


def cmd_register(args):
    """Регистрирует нового пользователя."""
    info = usecases.register(args.username, args.password)
    print(
        f"Пользователь '{info['username']}' зарегистрирован "
        f"(id={info['user_id']}). "
        f"Войдите: login --username {info['username']} --password ****"
    )
    return 0


def cmd_login(args):
    """Выполняет вход и запоминает сессию."""
    global SESSION
    info = usecases.login(args.username, args.password)
    SESSION = info
    _save_session(info)
    print(f"Вы вошли как '{info['username']}'")
    return 0


def cmd_logout(_args):
    """Завершает текущую сессию."""
    global SESSION
    if SESSION is None:
        print("Вы ещё не вошли в систему")
        return 1
    name = SESSION["username"]
    SESSION = None
    _clear_session()
    print(f"Вы вышли из аккаунта '{name}'")
    return 0


def cmd_show_portfolio(args):
    """Показывает кошельки и итоговую стоимость портфеля."""
    session = _require_login()
    if session is None:
        return 1

    report = usecases.portfolio_report(session["user_id"], args.base)
    if report["empty"]:
        print("У вас пока нет кошельков. Купите валюту командой buy.")
        return 0

    base = report["base"]
    print(f"Портфель пользователя '{report['username']}' (база: {base}):")

    table = PrettyTable()
    table.field_names = ["Валюта", "Баланс", f"Стоимость, {base}"]
    table.align = "r"
    for row in report["rows"]:
        table.add_row(
            [
                row["currency_code"],
                _fmt_amount(row["balance"]),
                _fmt_money(row["value"]),
            ]
        )
    print(table)
    print("-" * 40)
    print(f"ИТОГО: {_fmt_money(report['total'])} {base}")
    return 0


def cmd_buy(args):
    """Покупает указанную валюту."""
    session = _require_login()
    if session is None:
        return 1

    result = usecases.buy(
        session["user_id"], args.currency, args.amount, username=session["username"]
    )
    print(
        f"Покупка выполнена: {_fmt_amount(result['amount'])} {result['currency_code']} "
        f"по курсу {_fmt_money(result['rate'])} {result['base']}/"
        f"{result['currency_code']}"
    )
    print("Изменения в портфеле:")
    print(
        f"- {result['currency_code']}: было {_fmt_amount(result['before'])} "
        f"→ стало {_fmt_amount(result['after'])}"
    )
    print(f"Оценочная стоимость покупки: {_fmt_money(result['cost'])} {result['base']}")
    return 0


def cmd_sell(args):
    """Продаёт указанную валюту."""
    session = _require_login()
    if session is None:
        return 1

    result = usecases.sell(
        session["user_id"], args.currency, args.amount, username=session["username"]
    )
    print(
        f"Продажа выполнена: {_fmt_amount(result['amount'])} {result['currency_code']} "
        f"по курсу {_fmt_money(result['rate'])} {result['base']}/"
        f"{result['currency_code']}"
    )
    print("Изменения в портфеле:")
    print(
        f"- {result['currency_code']}: было {_fmt_amount(result['before'])} "
        f"→ стало {_fmt_amount(result['after'])}"
    )
    print(f"Оценочная выручка: {_fmt_money(result['proceeds'])} {result['base']}")
    return 0


def cmd_get_rate(args):
    """Показывает курс одной валюты к другой."""
    result = usecases.get_rate(args.source, args.target)
    print(
        f"Курс {result['from_currency']}→{result['to_currency']}: "
        f"{_fmt_rate(result['rate'])} (обновлено: "
        f"{_fmt_time(result['updated_at'])}, источник: {result['source']})"
    )
    if result["reverse_rate"] is not None:
        print(
            f"Обратный курс {result['to_currency']}→{result['from_currency']}: "
            f"{_fmt_rate(result['reverse_rate'])}"
        )
    if result["stale"]:
        print("Курсы устарели, выполните 'update-rates' для обновления.")
    return 0


def cmd_update_rates(args):
    """Запускает немедленное обновление курсов."""
    set_console_level("INFO")
    try:
        sources = [args.source] if args.source else None
        if sources:
            build_clients(sources)
        result = RatesUpdater().run_update(sources)
    finally:
        set_console_level("WARNING")

    total = result["updated"]
    stamp = result["last_refresh"]
    if result["errors"]:
        print("Update completed with errors. Check logs/actions.log for details.")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        return 0 if total else 1
    print(f"Update successful. Total rates updated: {total}. Last refresh: {stamp}")
    return 0


def cmd_show_rates(args):
    """Показывает курсы из локального кэша с фильтрами."""
    from valutatrade_hub.core.utils import get_rate_value
    from valutatrade_hub.infra.database import get_database

    rates = get_database().load_rates()
    pairs = rates.get("pairs", {})
    if not pairs:
        print(
            "Локальный кеш курсов пуст. Выполните 'update-rates', "
            "чтобы загрузить данные."
        )
        return 1

    base = (args.base or "USD").upper()
    wanted = args.currency.upper() if args.currency else None
    rows = []
    for pair, meta in pairs.items():
        from_code, _, _to = pair.partition("_")
        if wanted and wanted not in pair.split("_"):
            continue
        try:
            value, _ = get_rate_value(from_code, base, rates)
        except ApiRequestError:
            continue
        rows.append((f"{from_code}_{base}", value, meta.get("source")))

    if wanted and not rows:
        print(f"Курс для '{wanted}' не найден в кеше.")
        return 1
    if not rows:
        print(
            "Локальный кеш курсов пуст. Выполните 'update-rates', "
            "чтобы загрузить данные."
        )
        return 1

    rows.sort(key=lambda item: item[1], reverse=True)
    if args.top:
        rows = rows[: max(int(args.top), 0)]

    print(f"Rates from cache (updated at {rates.get('last_refresh')}):")
    table = PrettyTable()
    table.field_names = ["Пара", "Курс", "Источник"]
    table.align = "r"
    for pair, value, source in rows:
        table.add_row([pair, _fmt_rate(value), source])
    print(table)
    return 0


def cmd_help(_args):
    """Показывает список доступных команд."""
    print("Доступные команды:")
    print("  register --username <имя> --password <пароль>")
    print("  login --username <имя> --password <пароль>")
    print("  logout")
    print("  show-portfolio [--base <валюта>]")
    print("  buy --currency <код> --amount <сумма>")
    print("  sell --currency <код> --amount <сумма>")
    print("  get-rate --from <код> --to <код>")
    print("  update-rates [--source coingecko|exchangerate]")
    print("  show-rates [--currency <код>] [--top N] [--base <валюта>]")
    print("  currencies")
    print("  help, exit")
    return 0


def cmd_currencies(_args):
    """Показывает поддерживаемые валюты."""
    from valutatrade_hub.core.currencies import get_currency

    for code in supported_codes():
        print(get_currency(code).get_display_info())
    return 0


def build_parser():
    """Создаёт аргументный парсер всех команд CLI."""
    parser = argparse.ArgumentParser(
        prog="valutatrade-hub",
        description="ValutaTrade Hub — консольный кошелёк",
        add_help=False,
    )
    subparsers = parser.add_subparsers(dest="command")

    register = subparsers.add_parser("register", add_help=False)
    register.add_argument("--username", required=True)
    register.add_argument("--password", required=True)
    register.set_defaults(handler=cmd_register)

    login = subparsers.add_parser("login", add_help=False)
    login.add_argument("--username", required=True)
    login.add_argument("--password", required=True)
    login.set_defaults(handler=cmd_login)

    logout = subparsers.add_parser("logout", add_help=False)
    logout.set_defaults(handler=cmd_logout)

    show = subparsers.add_parser("show-portfolio", add_help=False)
    show.add_argument("--base", default=None)
    show.set_defaults(handler=cmd_show_portfolio)

    buy = subparsers.add_parser("buy", add_help=False)
    buy.add_argument("--currency", required=True)
    buy.add_argument("--amount", type=float, required=True)
    buy.set_defaults(handler=cmd_buy)

    sell = subparsers.add_parser("sell", add_help=False)
    sell.add_argument("--currency", required=True)
    sell.add_argument("--amount", type=float, required=True)
    sell.set_defaults(handler=cmd_sell)

    rate = subparsers.add_parser("get-rate", add_help=False)
    rate.add_argument("--from", dest="source", required=True)
    rate.add_argument("--to", dest="target", required=True)
    rate.set_defaults(handler=cmd_get_rate)

    update = subparsers.add_parser("update-rates", add_help=False)
    update.add_argument("--source", default=None)
    update.set_defaults(handler=cmd_update_rates)

    show_rates = subparsers.add_parser("show-rates", add_help=False)
    show_rates.add_argument("--currency", default=None)
    show_rates.add_argument("--top", type=int, default=None)
    show_rates.add_argument("--base", default=None)
    show_rates.set_defaults(handler=cmd_show_rates)

    help_cmd = subparsers.add_parser("help", add_help=False)
    help_cmd.set_defaults(handler=cmd_help)

    currencies = subparsers.add_parser("currencies", add_help=False)
    currencies.set_defaults(handler=cmd_currencies)

    return parser


def _print_error(error):
    """Выводит сообщение доменного исключения."""
    if isinstance(error, CurrencyNotFoundError):
        print(str(error))
        print(f"Поддерживаемые коды: {', '.join(supported_codes())}")
        return
    print(str(error))


def execute(argv):
    """Разбирает и выполняет одну команду, возвращает код возврата."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    if not getattr(args, "command", None):
        print("Команда не указана. Наберите 'help' для списка команд.")
        return 2

    try:
        return args.handler(args)
    except (
        ValutaTradeError,
        ValueError,
    ) as error:
        _print_error(error)
        return 1


def main(argv=None):
    """Точка входа: однокомандный запуск или интерактивный режим."""
    from valutatrade_hub.logging_config import setup_logging

    global SESSION
    setup_logging()
    SESSION = _load_session()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        return execute(arguments)

    print(BANNER)
    print("Наберите 'help' для списка команд, 'exit' для выхода.")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not line:
            continue
        lowered = line.lower()
        if lowered in {"exit", "quit"}:
            return 0
        try:
            tokens = shlex.split(line)
        except ValueError as error:
            print(f"Некорректная команда: {error}")
            continue
        execute(tokens)


if __name__ == "__main__":
    raise SystemExit(main())
