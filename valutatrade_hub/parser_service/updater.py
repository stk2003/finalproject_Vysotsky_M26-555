"""Координатор обновления курсов: опрос клиентов и сохранение."""

from datetime import datetime, timezone

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import get_logger
from valutatrade_hub.parser_service.api_clients import build_clients
from valutatrade_hub.parser_service.storage import RatesStorage

logger = get_logger("parser")


def _utc_stamp():
    """Момент времени в формате 2025-10-10T12:00:00Z."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class RatesUpdater:
    """Точка входа логики парсинга курсов."""

    def __init__(self, clients=None, storage=None):
        """Принимает готовые клиенты и хранилище (или создаёт свои)."""
        self.clients = clients if clients is not None else build_clients()
        self.storage = storage or RatesStorage()

    def run_update(self, sources=None):
        """Опрашивает все источники и сохраняет объединённый результат."""
        clients = self.clients if sources is None else build_clients(sources)
        snapshot = {}
        history = []
        errors = []
        per_client = {}

        logger.info("Starting rates update...")
        for client in clients:
            try:
                rates = client.fetch_rates()
            except ApiRequestError as error:
                errors.append(str(error))
                per_client[client.source] = 0
                logger.error("Failed to fetch from %s: %s", client.source, error)
                continue

            stamp = _utc_stamp()
            for pair, rate in rates.items():
                snapshot[pair] = {
                    "rate": round(float(rate), 8),
                    "updated_at": stamp,
                    "source": client.source,
                }
                from_code, _, to_code = pair.partition("_")
                history.append(
                    {
                        "id": f"{pair}_{stamp}",
                        "from_currency": from_code,
                        "to_currency": to_code,
                        "rate": round(float(rate), 8),
                        "timestamp": stamp,
                        "source": client.source,
                        "meta": {
                            "request_ms": None,
                            "status_code": 200,
                        },
                    }
                )
            per_client[client.source] = len(rates)
            logger.info("Fetching from %s... OK (%d rates)", client.source, len(rates))

        if not snapshot:
            logger.error("Update failed: no rates received")
            raise ApiRequestError("не удалось получить ни один источник курсов")

        payload = self.storage.save_snapshot(snapshot)
        added = self.storage.append_history(history)
        logger.info("Writing %d rates... done, history +%d", len(snapshot), added)
        return {
            "updated": len(snapshot),
            "history_added": added,
            "last_refresh": payload.get("last_refresh"),
            "per_client": per_client,
            "errors": errors,
        }


def update_rates(sources=None):
    """Быстрый запуск обновления без явного создания Updater."""
    return RatesUpdater().run_update(sources)
