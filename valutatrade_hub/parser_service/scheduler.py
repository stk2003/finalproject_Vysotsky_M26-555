"""Планировщик периодического обновления курсов."""

import threading

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import get_logger
from valutatrade_hub.parser_service.updater import RatesUpdater

logger = get_logger("scheduler")

DEFAULT_INTERVAL = 900


class RatesScheduler:
    """Периодически запускает обновление курсов в фоновом потоке."""

    def __init__(self, updater=None, interval=DEFAULT_INTERVAL):
        """Задаёт интервал в секундах и экземпляр Updater."""
        self.updater = updater or RatesUpdater()
        self.interval = int(interval)
        self._stop = threading.Event()
        self._thread = None

    def run_once(self):
        """Выполняет одно обновление, возвращает результат или None."""
        try:
            return self.updater.run_update()
        except ApiRequestError as error:
            logger.error("Scheduled update failed: %s", error)
            return None

    def _loop(self):
        """Фоновый цикл ожидания между обновлениями."""
        while not self._stop.wait(self.interval):
            self.run_once()

    def start(self):
        """Запускает поток планировщика, если он ещё не запущен."""
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self, timeout=2):
        """Останавливает планировщик и ждёт завершения потока."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._thread = None
