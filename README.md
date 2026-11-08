# ValutaTrade Hub

Учебный итоговый проект: консольный кошелёк для фиатных и криптовалют.
Пользователь регистрируется, входит в систему, покупает и продаёт валюту,
смотрит портфель и курсы. Курсы можно обновлять из внешних API через
отдельный Parser Service.

## Возможности

- регистрация и вход с хешированием пароля (`hashlib.sha256` + соль);
- портфель из кошельков `Wallet` с проверкой баланса;
- команды `buy`, `sell`, `show-portfolio`, `get-rate`;
- команды Parser Service: `update-rates`, `show-rates`;
- кэш курсов `data/rates.json` с TTL и историей `data/exchange_rates.json`;
- Singleton-настройки и Singleton-хранилище;
- декоратор `@log_action` и ротация логов в `logs/actions.log`;
- PrettyTable для вывода таблиц.

## Структура проекта

```text
finalproject_Vysotsky_M26-555/
├── data/
│   ├── users.json
│   ├── portfolios.json
│   ├── rates.json
│   └── exchange_rates.json
├── valutatrade_hub/
│   ├── __init__.py
│   ├── logging_config.py
│   ├── decorators.py
│   ├── core/
│   │   ├── currencies.py
│   │   ├── exceptions.py
│   │   ├── models.py
│   │   ├── usecases.py
│   │   └── utils.py
│   ├── infra/
│   │   ├── settings.py
│   │   └── database.py
│   ├── parser_service/
│   │   ├── config.py
│   │   ├── api_clients.py
│   │   ├── updater.py
│   │   ├── storage.py
│   │   └── scheduler.py
│   └── cli/
│       └── interface.py
├── main.py
├── pyproject.toml
├── uv.lock
├── README.md
└── .gitignore
```

## Установка

```bash
uv sync
```

или:

```bash
make install
```

## Запуск

Интерактивный режим:

```bash
uv run valutatrade-hub
```

Однократная команда:

```bash
uv run valutatrade-hub register --username alice --password 1234
```

Также можно запускать через `main.py`:

```bash
uv run python main.py
```

Сессия сохраняется в `data/session.json`, поэтому команды можно выполнять
по одной в разных вызовах CLI.

## Команды

```text
register --username <имя> --password <пароль>
login --username <имя> --password <пароль>
logout
show-portfolio [--base <валюта>]
buy --currency <код> --amount <сумма>
sell --currency <код> --amount <сумма>
get-rate --from <код> --to <код>
update-rates [--source coingecko|exchangerate]
show-rates [--currency <код>] [--top N] [--base <валюта>]
currencies
help, exit
```

Поддерживаемые валюты: `USD`, `EUR`, `GBP`, `RUB`, `BTC`, `ETH`, `SOL`.

## Пример работы

```text
> register --username alice --password 1234
Пользователь 'alice' зарегистрирован (id=1). Войдите: login --username alice --password ****

> login --username alice --password 1234
Вы вошли как 'alice'

> buy --currency BTC --amount 0.05
Покупка выполнена: 0.0500 BTC по курсу 59,337.21 USD/BTC
Изменения в портфеле:
- BTC: было 0.00 → стало 0.0500
Оценочная стоимость покупки: 2,966.86 USD

> buy --currency USD --amount 150
Покупка выполнена: 150.00 USD по курсу 1.00 USD/USD
Изменения в портфеле:
- USD: было 0.00 → стало 150.00
Оценочная стоимость покупки: 150.00 USD

> show-portfolio
Портфель пользователя 'alice' (база: USD):
+--------+--------+----------------+
| Валюта | Баланс | Стоимость, USD |
+--------+--------+----------------+
|    BTC | 0.0500 |       2,966.86 |
|    USD | 150.00 |         150.00 |
+--------+--------+----------------+
----------------------------------------
ИТОГО: 3,116.86 USD

> get-rate --from EUR --to USD
Курс EUR→USD: 1.0786 (обновлено: 2026-11-08 20:25:49, источник: stub)
Обратный курс USD→EUR: 0.9271
Курсы устарели, выполните 'update-rates' для обновления.

> sell --currency BTC --amount 0.02
Продажа выполнена: 0.0200 BTC по курсу 59,337.21 USD/BTC
Изменения в портфеле:
- BTC: было 0.0500 → стало 0.0300
Оценочная выручка: 1,186.74 USD

> update-rates
INFO ... Fetching from CoinGecko... OK (3 rates)
Update completed with errors. Check logs/actions.log for details.
ERROR: ... не задан EXCHANGERATE_API_KEY для ExchangeRate-API

> show-rates --top 3
Rates from cache (updated at ...):
+---------+-----------+-----------+
|    Пара |      Курс |  Источник |
+---------+-----------+-----------+
| BTC_USD | 75,796.00 | CoinGecko |
| ETH_USD |  2,227.23 | CoinGecko |
| SOL_USD |     89.35 | CoinGecko |
+---------+-----------+-----------+
```

## Parser Service и курсы

Parser Service опрашивает два источника:

- CoinGecko — криптовалюты, работает без ключа;
- ExchangeRate-API — фиатные валюты, нужен ключ.

Ключ ExchangeRate-API берётся из переменной окружения и не хранится в коде:

```bash
export EXCHANGERATE_API_KEY="ваш_ключ"
```

Без ключа обновление продолжает работать для криптовалют, а фиатные курсы
остаются из локального кэша или заглушки.

Текущие курсы лежат в `data/rates.json`, история измерений — в
`data/exchange_rates.json`. Срок годности кэша задаётся в `pyproject.toml`:

```toml
[tool.valutatrade]
data_dir = "data"
rates_ttl_seconds = 300
default_base_currency = "USD"
log_dir = "logs"
log_level = "INFO"
```

Если кэш устарел, `get-rate` пытается обновить его и предупреждает:
`Курсы устарели, выполните 'update-rates' для обновления.`

## Логирование

Все операции `REGISTER`, `LOGIN`, `BUY`, `SELL` пишутся в `logs/actions.log`
через декоратор `@log_action`. Файл ротируется по размеру (1 МБ, 3 копии).

## Демонстрация

[![asciinema](https://asciinema.org/a/hohUkk9FKKcfk3iH.svg)](https://asciinema.org/a/hohUkk9FKKcfk3iH)

## Автор

Высоцкий М26-555
