""" Файл для получения данных с датчиков для linux """
import asyncio
import logging
from typing import Optional

import cpuinfo
import psutil

from Options.system_all import SystemMonitor, OperationSystemMonitor

logger = logging.getLogger(__name__)


class CPUMonitor_Linux(SystemMonitor):
    def __init__(self, oc_flag: OperationSystemMonitor, interval: Optional[float] = 3, history_size: Optional[int] = 10):
        super().__init__('cpu_linux', interval, history_size)
        # Внешние зависимости
        self.oc_flag = oc_flag  # Ссылка на объект-флаг ОС (нужен для проверки, что мы в Linux)

        # Публичные атрибуты (доступны из других классов)
        self.cpu_temp = None  # Последняя измеренная температура CPU (градусы Цельсия), обновляется в detailed_info()

        # Приватные атрибуты кэша (используются только внутри класса)
        self.cache_cpu_name = None  # Имя модели процессора (например "AMD Ryzen 5 5500U"), берется из cpuinfo
        self.cache_amd_flag = False  # True если процессор AMD, False если Intel или другой
        self.cache_intel_flag = False  # True если процессор Intel, False если AMD или другой
        self._cpu_info_cache = None  # Полный словарь данных от cpuinfo

    async def init_oc(self) -> bool:
        await self.oc_flag.measure()
        return self.oc_flag.linux_flag

    @staticmethod
    async def cpu_stat():
        return await asyncio.wait_for(
            asyncio.to_thread(cpuinfo.get_cpu_info), timeout=5
        )

    async def init_cpu(self) -> Optional[dict]:
        try:
            if self._cpu_info_cache is None:
                self._cpu_info_cache = await self.cpu_stat()

            cpu_name = self._cpu_info_cache.get('brand_raw')
            if cpu_name is None:
                logger.error('Нет данных об имени процессора')
                return None

            if self.cache_cpu_name is None:
                self.cache_cpu_name = cpu_name

        except asyncio.TimeoutError:
            logger.error('Таймаут получения данных о процессоре')
            return None
        except Exception as e:
            logger.error(f"Ошибка получения данных о CPU - {e}")
            return None

        if self.cache_cpu_name:
            cpu_name_lower = self.cache_cpu_name.lower()
            self.cache_intel_flag = cpu_name_lower.startswith('intel')
            self.cache_amd_flag = cpu_name_lower.startswith('amd')

        return {
            'cpu_name': self.cache_cpu_name,
            'intel_flag': self.cache_intel_flag,
            'amd_flag': self.cache_amd_flag
        }

    async def measure(self) -> Optional[dict]:
        if not await self.init_oc():
            logger.warning('Система не является Linux системой')
            return None
        if not await self.init_cpu():
            logger.error('Нет данных о имени CPU для Linux')
            return None
        return {'cpu_name': self.cache_cpu_name}

    async def detailed_info(self) -> Optional[dict]:
        if not await self.init_oc():
            logger.warning('Система не является Linux системой')
            return None
        if not await self.init_cpu():
            logger.error('Нет данных о имени CPU для Linux')
            return None

        try:
            # Используем кэш, не дергаем cpu_stat повторно
            cpu_gz = self._cpu_info_cache.get('hz_advertised_friendly')
            if cpu_gz is None:
                logger.debug('Нет данных о частоте процессора')

            temp_sensor = await asyncio.wait_for(
                asyncio.to_thread(psutil.sensors_temperatures), timeout=5
            )

            if self.cache_amd_flag:
                sensor_key = 'k10temp'
            elif self.cache_intel_flag:
                sensor_key = 'coretemp'
            else:
                sensor_key = None
                logger.warning('Неизвестный производитель CPU')

            if sensor_key:
                sensor_data = temp_sensor.get(sensor_key)
                if sensor_data and len(sensor_data) > 0:
                    self.cpu_temp = sensor_data[0][1]

            return {
                'cpu_temp': self.cpu_temp,
                'cpu_GZ': cpu_gz
            }

        except asyncio.TimeoutError:
            logger.error('Таймаут получения данных о процессоре')
            return None
        except Exception as e:
            logger.error(f'Ошибка получения данных: {e}')
            return None


class StorageMonitor_Linux(SystemMonitor):
    def __init__(self, oc: CPUMonitor_Linux, interval: Optional[float] = 3,
                 history_size: Optional[int] = 10):
        super().__init__('cpu_linux', interval, history_size)
        # Внешние зависимости
        self.oc_flag = oc # Ссылка на объект-флаг ОС (нужен для проверки, что мы в Linux)

        self.cache_storage_total = None
    async def measure(self) -> Optional[dict]:
        try:
            storage_data = await asyncio.wait_for()
        except asyncio.TimeoutError:
            logger.error(f'')
            return None
        except Exception as e:
            logger.error(f'')
            return None