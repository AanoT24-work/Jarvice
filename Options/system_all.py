"""Файл для определения ОС и кроссплатформенных функций"""
import os
import sys
import json
import asyncio
import logging
import platform
from unittest import result

import pythonping

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
        raise NotImplementedError("Subclass must implement measure()")

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
                logger.error(f"Stream error [{self.name}]: {e}")
                data = {self.name: None, 'error': str(e)}
                if self.history is not None:
                    data['history'] = self.get_history()
                yield f"data: {json.dumps(data)}\n\n"

            if self.interval:
                await asyncio.sleep(self.interval)


class OperationSystemMonitor(SystemMonitor):
    def __init__(self, interval: Optional[float] = 3, history_size: Optional[int] = 0):
        super().__init__(name='operation_system', interval=interval, history_size=history_size)
        self.cache_oc_name = None
        self.cache_oc_version = None

    async def measure(self) -> Optional[dict]:
        if self.cache_oc_name is not None:
            return {'OC': f"{self.cache_oc_name}:{self.cache_oc_version}"}
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

        logger.debug(f"OS: {self.cache_oc_name} {self.cache_oc_version}")
        return {'OC': f"{self.cache_oc_name}:{self.cache_oc_version}"}

class CPUMonitor_All(SystemMonitor):
    def __init__(self, interval: Optional[float] = 3, history_size: Optional[int] = 10):
        super().__init__('cpu_all', interval, history_size)

    async def measure(self) -> Optional[dict]:
        try:
            cpu_percent = await asyncio.wait_for(
                asyncio.to_thread(psutil.cpu_percent, interval=1), timeout=5
            )
            result = round(cpu_percent, 2) if cpu_percent is not None else None
            logger.debug(f"CPU usage: {result}%")
            return {'cpu': result}

        except asyncio.TimeoutError:
            logger.error("CPU load timeout (5s)")
            return None
        except Exception as e:
            logger.error(f"CPU load failed: {e}")
            return None


class RAMMonitor_All(SystemMonitor):
    def __init__(self, interval: Optional[float] = 3, history_size: Optional[int] = 10):
        super().__init__('ram', interval, history_size)
        self.cache_ram_total = None
        self.ram = None

    async def init_ram(self):
        try:
            self.ram = await asyncio.wait_for(
                asyncio.to_thread(psutil.virtual_memory), timeout=5
            )
            if self.ram is None:
                logger.warning("No RAM data received")
                return None
            return self.ram

        except asyncio.TimeoutError:
            logger.error("RAM read timeout (5s)")
            return None
        except Exception as e:
            logger.error(f"RAM read failed: {e}")
            return None

    async def measure(self) -> Optional[dict]:
        try:
            ram = await self.init_ram()
            if ram is None:
                return None

            if self.cache_ram_total is None:
                self.cache_ram_total = ram.total
                logger.debug(f"RAM total: {ram.total / (1024 ** 3):.1f} GB")

            results = {
                'ram_used': round(ram.used / (1024 ** 3), 1),
                'ram_total': round(ram.total / (1024 ** 3), 1),
                'ram_percent': round(ram.percent, 1)
            }

            logger.debug(f"RAM: {results['ram_used']}/{results['ram_total']} GB ({results['ram_percent']}%)")
            return results

        except asyncio.TimeoutError:
            logger.error("RAM measure timeout (5s)")
            return None
        except Exception as e:
            logger.error(f"RAM measure failed: {e}")
            return None

class Network_system_All(SystemMonitor):
    def __init__(self, interval: Optional[float] = 20, history_size: Optional[int] = 10):
        super().__init__('network_system', interval, history_size)

    async def measure(self) -> Optional[dict]:
        net_data = lambda: asyncio.wait_for(asyncio.to_thread(psutil.net_io_counters), timeout=5)
        mbytes_sent = 0
        mbytes_recv = 0
        delta_time = 5
        delta_bytes = 100000
        try:
            net_data_first = await net_data()
            if net_data_first is None:
                logger.error("Network system data received")
                return None

            first_mbytes_sent = net_data_first.bytes_sent
            first_mbytes_recv = net_data_first.bytes_recv
            first_pack_sent = net_data_first.packets_sent
            first_pack_recv = net_data_first.packets_recv

            await asyncio.sleep(delta_time)

            net_data_second = await net_data()
            if net_data_second is None:
                logger.error("Network system data received")
                return None
            second_mbytes_sent = net_data_second.bytes_sent
            second_mbytes_recv = net_data_second.bytes_recv
            second_pack_sent = net_data_second.packets_sent
            second_pack_recv = net_data_second.packets_recv

            if second_mbytes_sent - first_mbytes_sent >= delta_bytes:
                mbytes_sent = round((second_mbytes_sent - first_mbytes_sent) / (1024 ** 2) / delta_time, 2)
            elif second_mbytes_sent - first_mbytes_sent < delta_bytes:
                mbytes_sent = round((second_mbytes_sent - first_mbytes_sent) / (1024 ** 2) / delta_time, 4)
            if second_mbytes_recv - first_mbytes_recv >= delta_bytes:
                mbytes_recv = round((second_mbytes_recv - first_mbytes_recv)/(1024**2)/delta_time, 2)
            elif second_mbytes_recv - first_mbytes_recv < delta_bytes:
                mbytes_recv = round((second_mbytes_recv - first_mbytes_recv) / (1024 ** 2) / delta_time, 4)

            result = {
                'mbytes_sent': mbytes_sent,
                'mbytes_recv': mbytes_recv,
                'pack_sent': round((second_pack_sent - first_pack_sent)/delta_time),
                'pack_recv': round((second_pack_recv - first_pack_recv)/delta_time)
            }
            logger.debug(f"NETWORK DATA: {result}")
            return result
        except asyncio.TimeoutError:
            logger.error(f'Network_system measure timeout (5s)')
            return None
        except Exception as e:
            logger.error(f'Network system measure failed: {e}')
            return None

