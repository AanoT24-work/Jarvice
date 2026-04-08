'''# Стандартная библиотека
import asyncio
import json
import logging
from collections import deque
from typing import AsyncGenerator
from typing import Dict, List, Optional

# Сторонние библиотеки
import psutil
from PyLibreHardwareMonitor import Computer

logger = logging.getLogger(__name__)


class SystemMonitor:
    def __init__(self, name: str, interval: Optional[float], history_size: Optional[int] = None):
        self.name = name
        self.interval = interval
        self.history = deque(maxlen=history_size) if history_size is not None else None

    async def measure(self) -> Optional[dict]:
        raise NotImplementedError("Метод measure должен быть реализован")

    def get_history(self) -> Optional[List[float]]:
        return None if self.history is None else list(self.history)

    def get_stats(self) -> Optional[Dict[str, float]]:
        if not self.history:
            return None
        return {
            'current': self.history[-1],
            'avg': sum(self.history) / len(self.history),
            'max': max(self.history),
            'min': min(self.history)
        }

    async def stream(self) -> AsyncGenerator[str, None]:
        while True:
            try:
                value = await self.measure()
                data = {self.name: value}

                if self.history is not None and value is not None:
                    # Для истории берем первое числовое значение из словаря
                    if isinstance(value, dict):
                        for v in value.values():
                            if isinstance(v, (int, float)):
                                self.history.append(v)
                                break
                    else:
                        self.history.append(value)

                    data['history'] = self.get_history()

                    stats = self.get_stats()
                    if stats:
                        data['stats'] = stats

                yield f"data: {json.dumps(data)}\n\n"

            except Exception as e:
                logger.error(f"Ошибка в stream для {self.name}: {e}")
                data = {self.name: None, 'error': str(e)}

                if self.history is not None:
                    data['history'] = self.get_history()

                yield f"data: {json.dumps(data)}\n\n"

            if self.interval:
                await asyncio.sleep(self.interval)

class CPUMonitor(SystemMonitor):
    def __init__(self, interval: Optional[float] = 3, history_size: Optional[int] = 10):
        super().__init__('cpu', interval, history_size)
        self.flag = False
        self.computer = None
        self.cache_cpu_name = None

    async def measure(self) -> Optional[dict]:
        try:
            cpu = await asyncio.wait_for(asyncio.to_thread(psutil.cpu_percent, interval=1), timeout=5)
            cpu_result = round(cpu, 2) if cpu is not None else None
            logger.debug(f'CPUMonitor.measure(): {cpu_result}')
            return {'cpu': cpu_result}
        except Exception as e:
            logger.error(f'Ошибка CPUMonitor.measure(): {e}%')
            return None

    async def init_library(self) -> None:
        try:
            if not self.flag or self.computer is None:
                self.computer = await asyncio.wait_for(
                    asyncio.to_thread(Computer),
                    timeout=5
                )
                self.flag = True
        except asyncio.TimeoutError:
            logger.error(f'Ограничение времени CPUMonitor.init_library()')
        except Exception as e:
            logger.error(f'Ошибка CPUMonitor.init_library(): {e}%')

    async def detailed_info(self) -> Optional[dict]:
        try:
            await self.init_library()
            if not self.flag and self.computer is None:
                logger.error(f'Ошибка получения данных от CPUMonitor.init_library()')
                return None

            cpu_data = self.computer.cpu
            if not cpu_data:
                logger.error('Нет данных CPU')
                return None

            cpu_name = next(iter(cpu_data))

            if self.cache_cpu_name is None and cpu_name is not None:
                self.cache_cpu_name = cpu_name

            if not cpu_data or not self.cache_cpu_name:
                logger.error(f'Ошибка получения данных от CPUMonitor.init_library()')
                return None

            cpu_temp_route = cpu_data[self.cache_cpu_name]["Temperature"]

            priority_sensors = [
                "CCD1 (Tdie)",      # AMD Ryzen CCD1
                "CCD2 (Tdie)",      # AMD Ryzen CCD2 (если есть)
                "Tdie",              # AMD общий
                "Core Max",          # Intel максимальная по ядрам
                "Core Average",      # Intel средняя по ядрам
                "CPU Core",          # Стандартный
                "Core (Tdie)",       # Некоторые версии
                "CPU Package",       # Общая температура пакета (на крайний случай)
            ]

            used_sensor = None
            cpu_temp = None

            for sensor in priority_sensors:
                if sensor in cpu_temp_route:
                    used_sensor = sensor
                    cpu_temp = cpu_temp_route[sensor]
                    logger.debug(f'Найден приоритетный сенсор: {sensor}')
                    break

            if cpu_temp is None:
                exclude_patterns = ['tctl', 'control', 'offset']
                candidates = []

                for sensor_name, sensor_value in cpu_temp_route.items():
                    sensor_lower = sensor_name.lower()
                    if any(pattern in sensor_lower for pattern in exclude_patterns):
                        continue
                    candidates.append((sensor_name, sensor_value))

                if candidates:
                    used_sensor, cpu_temp = candidates[0]
                    logger.debug(f'Использую сенсор (исключая Tctl): {used_sensor}')
                else:
                    used_sensor = next(iter(cpu_temp_route))
                    cpu_temp = cpu_temp_route[used_sensor]
                    logger.debug(f'Использую первый доступный сенсор: {used_sensor}')

            results = {
                'cpu_name': self.cache_cpu_name,
                'cpu_temp': round(float(cpu_temp), 1),
                'sensor_used': used_sensor
            }

            logger.info(f'Результат: {results}')
            return results

        except Exception as e:
            logger.error(f'Ошибка CPUMonitor.detailed_info() - {e}')
            return None

class RAMMonitor(SystemMonitor):
    def __init__(
        self,
        cpu_monitor: CPUMonitor,
        interval: Optional[float] = 3,
        history_size: Optional[int] = 10
    ):
        super().__init__('ram', interval, history_size)
        self.cache_ram_total = None
        self.cache_ram_name = None
        self.cpu_monitor = cpu_monitor

    async def measure(self) -> Optional[dict]:
        try:
            ram = await asyncio.wait_for(asyncio.to_thread(psutil.virtual_memory), timeout=5)
            if ram is None:
                logger.error(f'Нет данных о RAM в RAMMonitor.measure()')
                return None

            if self.cache_ram_total is None and ram is not None:
                self.cache_ram_total = ram.total

            results = {
                'ram_used': round(ram.used / (1024 ** 3), 1) if ram is not None else None,
                'ram_total': round(ram.total / (1024 ** 3), 1) if ram is not None else None,
                'ram_percent': round(ram.percent, 1) if ram is not None else None
            }
            logger.info(f'Результат: {results}')
            return results

        except asyncio.TimeoutError:
            logger.error('Таймаут RAMMonitor.measure()')
            return None
        except Exception as e:
            logger.error(f'Ошибка RAMMonitor.measure(): {e}')
            return None

    async def detailed_info(self) -> Optional[dict]:
        try:
            await asyncio.wait_for(
                self.cpu_monitor.init_library(),
                timeout=5
            )

            if not self.cpu_monitor.flag and self.cpu_monitor.computer is None:
                logger.error(f'Ошибка получения данных от CPUMonitor.init_library()')
                return None

            computer = self.cpu_monitor.computer
            ram_data = computer.memory
            if not ram_data:
                logger.error('Нет данных RAM')
                return None

            ram_name = next(iter(ram_data))
            if self.cache_ram_name is None and ram_name is not None:
                self.cache_ram_name = ram_name

            results = {
                'ram_name': self.cache_ram_name
            }
            return results
        except Exception as e:
            logger.error(f'Ошибка RAMMonitor.detailed_info() - {e}')
            return None

class StorageMonitor(SystemMonitor):
    def __init__(
        self,
        cpu_monitor: CPUMonitor,
        interval: Optional[float] = 3,
        history_size: Optional[int] = 10
    ):
        super().__init__('ram', interval, history_size)
        self.cache_storage_total = None
        self.cache_storage_name = None
        self.cpu_monitor = cpu_monitor

    async def measure(self) -> Optional[dict]:
        try:
            import string
            from pathlib import Path

            drives = []
            # Проверяем все буквы от C до Z
            for letter in string.ascii_uppercase:
                drive_path = f"{letter}:\\"
                if Path(drive_path).exists():
                    drives.append(drive_path)

            disks_info = {}

            for drive in drives:
                try:
                    usage = await asyncio.wait_for(
                        asyncio.to_thread(psutil.disk_usage, drive),
                        timeout=3
                    )

                    disk_name = drive.replace('\\', '')

                    disks_info[disk_name] = {
                        'drive_letter': drive[0],
                        'total_gb': round(usage.total / (1024**3), 2),
                        'free_gb': round(usage.free / (1024**3), 2),
                        'used_gb': round(usage.used / (1024**3), 2),
                        'percent_used': round(usage.percent, 1)
                    }

                except Exception as e:
                    logger.warning(f"Не удалось получить инфо для диска {drive}: {e}")
                    continue

            disks_info = dict(sorted(disks_info.items()))

            results = {
                'drives': disks_info,
                'total_drives': len(disks_info)
            }
            logger.info(f'Информация по дискам: {results}')
            return results

        except Exception as e:
            logger.error(f'Ошибка StorageMonitor.measure_windows() - {e}')
            return None'''