""" Файл для определения ОС перед началом всех работ и функций, которые подходят и для windows и linux """
import os
import sys
import json
import asyncio
import logging
import platform

from collections import deque
from typing import AsyncGenerator, Dict, List, Optional

import psutil

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

class OperationSystemMonitor(SystemMonitor):
    def __init__(self, interval: Optional[float] = 3, history_size: Optional[int] = 0):
        super().__init__(name='operation_system', interval=interval, history_size=history_size)
        self.cache_oc_name = None          # Кэш значение операционной системы
        self.cache_oc_version = None       # Кэш значение версии операционной системы
        self.linux_flag = False            # Кэш значение, является ли ОС - linux
        self.windows_flag = False          # Кэш значение, является ли ОС - windows

    async def measure(self) -> Optional[dict]:
        if self.cache_oc_name is not None:
            return {
                'OC': f"{self.cache_oc_name}:{self.cache_oc_version}",
                'linux_flag': self.linux_flag,
                'windows_flag': self.windows_flag
            }

        win_marker = "windows"
        lin_marker = "linux"

        try:
            oc_name = await asyncio.wait_for(asyncio.to_thread(platform.system), timeout=5)
            if self.cache_oc_name is None and oc_name is not None:
                self.cache_oc_name = oc_name
            oc_version = await asyncio.wait_for(asyncio.to_thread(platform.release), timeout=5)
            if self.cache_oc_version is None and oc_version is not None:
                self.cache_oc_version = oc_version
        except asyncio.TimeoutError:
            logger.error(f"Превышено время ожидания определения ОС")
            return None
        except Exception as e:
            logger.error(f"Ошибка определения ОС: {e}")
            return None

        if self.cache_oc_name is not None:
            oc_name_lower = self.cache_oc_name.lower()
            self.windows_flag = oc_name_lower.startswith(win_marker)
            self.linux_flag = oc_name_lower.startswith(lin_marker)
        result = {
            'OC': f"{self.cache_oc_name}:{self.cache_oc_version}",
            'linux_flag': self.linux_flag,
            'windows_flag': self.windows_flag
            }
        logger.debug(f'{self.cache_oc_name}')
        return result


class CPUMonitor_All(SystemMonitor):
    def __init__(self, interval: Optional[float] = 3, history_size: Optional[int] = 10):
        super().__init__('cpu_all', interval, history_size)

    async def measure(self) -> Optional[dict]:
        try:
            cpu_percent = await asyncio.wait_for(asyncio.to_thread(psutil.cpu_percent, interval=1), timeout=5)
            result = round(cpu_percent, 2) if cpu_percent is not None else None
            logger.debug(f'CPUMonitor.measure(): {result}')
            return {'cpu': result}
        except asyncio.TimeoutError:
            logger.error(f"Превышено время ожидания определения нагрузки CPU")
            return None
        except Exception as e:
            logger.error(f'Ошибка CPUMonitor.measure(): {e}%')
            return None

class RAMMonitor_All(SystemMonitor):
    def __init__(self, interval: Optional[float] = 3, history_size: Optional[int] = 10):
        super().__init__('ram', interval, history_size)
        self.cache_ram_total = None

        self.ram = None

    async def init_ram(self):
        try:
            self.ram = await asyncio.wait_for(asyncio.to_thread(psutil.virtual_memory), timeout=5)
            if self.ram is None:
                logger.error(f'Нет данных о RAM в RAMMonitor.measure()')
                return None
            return self.ram

        except asyncio.TimeoutError:
            logger.error('Таймаут RAMMonitor.measure()')
            return None
        except Exception as e:
            logger.error(f'Ошибка RAMMonitor.measure(): {e}')
            return None

    async def measure(self) -> Optional[dict]:
        try:
            ram = await self.init_ram()

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

