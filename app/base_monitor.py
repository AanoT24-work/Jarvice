import asyncio
import json
import logging
import platform
from typing import AsyncGenerator

from Options.system_all import CPUMonitor_All, OperationSystemMonitor,RAMMonitor_All, Network_system_All
from Options.system_linux import CPUMonitor_Linux, StorageMonitor_Linux
from Options.system_windows import CPUMonitor_Windows, StorageMonitor_Windows

logger = logging.getLogger(__name__)


class SystemMonitorFacade:
    def __init__(self):
        self.linux_flag = False
        self.windows_flag = False
        self.cache_oc_name = None
        self.cache_oc_version = None

        self.os_monitor = OperationSystemMonitor(interval=3)

        self.common_cpu = CPUMonitor_All(interval=3, history_size=10)
        self.common_ram = RAMMonitor_All(interval=3, history_size=10)
        self.common_network_system = Network_system_All(interval=20, history_size=10)
        self.linux_cpu = CPUMonitor_Linux(interval=3, history_size=10)
        self.linux_storage = StorageMonitor_Linux(interval=3, history_size=10)
        self.windows_cpu = CPUMonitor_Windows(interval=3, history_size=10)
        self.windows_storage = StorageMonitor_Windows(interval=3, history_size=10)

        # Базовые мониторы
        self.monitors = {
            'oc': self.os_monitor,
            'common_cpu': self.common_cpu,
            'common_ram': self.common_ram,
            'common_network_system': self.common_network_system,
        }

    async def os(self) -> dict:
        """Определение операционной системы"""
        try:
            oc_name = await asyncio.wait_for(asyncio.to_thread(platform.system), timeout=5)
            if self.cache_oc_name is None and oc_name is not None:
                self.cache_oc_name = oc_name

            oc_version = await asyncio.wait_for(asyncio.to_thread(platform.release), timeout=5)
            if self.cache_oc_version is None and oc_version is not None:
                self.cache_oc_version = oc_version

        except asyncio.TimeoutError:
            logger.error("OS detection timeout (5s)")
            return None
        except Exception as e:
            logger.error(f"OS detection failed: {e}")
            return None

        if self.cache_oc_name is not None:
            oc_name_lower = self.cache_oc_name.lower()
            self.windows_flag = oc_name_lower.startswith("windows")
            self.linux_flag = oc_name_lower.startswith("linux")

        return {
            'linux_flag': self.linux_flag,
            'windows_flag': self.windows_flag,
        }

    async def monitor(self):
        """Добавляем ОС-специфичные мониторы после определения ОС"""
        os_info = await self.os()
        if os_info is None:
            logger.error("Cannot detect OS, using only common monitors")
            return

        # Добавляем Linux мониторы
        if os_info.get('linux_flag'):
            self.monitors['linux_cpu'] = self.linux_cpu
            self.monitors['linux_storage'] = self.linux_storage
            logger.info("Linux monitors activated")

        # Добавляем Windows мониторы
        if os_info.get('windows_flag'):
            self.monitors['cpu_windows'] = self.windows_cpu
            self.monitors['storage_windows'] = self.windows_storage
            logger.info("Windows monitors activated")

    async def get_all_data(self) -> dict:
        """Получить данные со всех мониторов"""
        data = {}
        for name, monitor in self.monitors.items():
            if monitor is None:
                continue

            try:
                value = await monitor.measure()
                if value is None:
                    continue

                monitor_data = {'current': value}

                # История и статистика (если есть)
                if hasattr(monitor, 'history') and monitor.history is not None:
                    monitor_data['history'] = monitor.get_history()
                    stats = monitor.get_stats()
                    if stats:
                        monitor_data['stats'] = stats

                # Детальная информация (для CPU, RAM)
                if name in ['common_ram', 'linux_cpu', 'windows_cpu'] and hasattr(monitor, 'detailed_info'):
                    try:
                        details = await monitor.detailed_info()
                        if details:
                            monitor_data['details'] = details
                    except Exception as e:
                        logger.debug(f"Detailed info not available for {name}: {e}")

                data[name] = monitor_data

            except Exception as e:
                logger.error(f"Error getting data for {name}: {e}")
                data[name] = {'error': str(e)}

        return data

    async def stream_all(self) -> AsyncGenerator[str, None]:
        """Асинхронный генератор всех данных"""
        while True:
            try:
                data = await self.get_all_data()
                if data:
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error(f"Error in stream_all: {e}")
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

            await asyncio.sleep(1)

    async def start_streaming(self):
        """Запускает все мониторы в отдельных задачах"""
        await self.monitor()
        tasks = []
        for name, monitor in self.monitors.items():
            if monitor is not None:
                task = asyncio.create_task(
                    self._run_monitor_stream(name, monitor),
                    name=f"monitor_{name}"
                )
                tasks.append(task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_monitor_stream(self, name: str, monitor):
        """Запускает стрим конкретного монитора"""
        try:
            async for data in monitor.stream():
                logger.debug(f"Monitor {name}: {data[:100]}...")
        except Exception as e:
            logger.error(f"Error in monitor stream {name}: {e}")