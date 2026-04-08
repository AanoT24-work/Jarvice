"""Файл для получения данных с датчиков для Linux"""
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
        self.oc_flag = oc_flag

        self.cpu_temp = None
        self.cache_cpu_name = None
        self.cache_amd_flag = False
        self.cache_intel_flag = False
        self._cpu_info_cache = None

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
                logger.warning("CPU name not found")
                return None

            if self.cache_cpu_name is None:
                self.cache_cpu_name = cpu_name

        except asyncio.TimeoutError:
            logger.error("CPU info timeout (5s)")
            return None
        except Exception as e:
            logger.error(f"CPU info failed: {e}")
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
            logger.debug("Not a Linux system")
            return None
        if not await self.init_cpu():
            return None
        return {'cpu_name': self.cache_cpu_name}

    async def detailed_info(self) -> Optional[dict]:
        if not await self.init_oc():
            logger.debug("Not a Linux system")
            return None
        if not await self.init_cpu():
            return None

        try:
            cpu_gz = self._cpu_info_cache.get('hz_advertised_friendly')

            temp_sensor = await asyncio.wait_for(
                asyncio.to_thread(psutil.sensors_temperatures), timeout=5
            )

            if self.cache_amd_flag:
                sensor_key = 'k10temp'
            elif self.cache_intel_flag:
                sensor_key = 'coretemp'
            else:
                sensor_key = None
                logger.debug(f"Unknown CPU vendor: {self.cache_cpu_name}")

            if sensor_key:
                sensor_data = temp_sensor.get(sensor_key)
                if sensor_data and len(sensor_data) > 0:
                    self.cpu_temp = sensor_data[0][1]
                    logger.debug(f"Temp {self.cpu_temp}°C from {sensor_key}")

            return {
                'cpu_temp': self.cpu_temp,
                'cpu_GZ': cpu_gz
            }

        except asyncio.TimeoutError:
            logger.error("Temperature read timeout (5s)")
            return None
        except Exception as e:
            logger.error(f"Detailed info failed: {e}")
            return None


class StorageMonitor_Linux(SystemMonitor):
    def __init__(self, oc: CPUMonitor_Linux, interval: Optional[float] = 3, history_size: Optional[int] = 10):
        super().__init__('storage_linux', interval, history_size)
        self.oc_flag = oc
        self.cache_storage_total = None

    async def measure(self) -> Optional[dict]:
        result_storage = {}

        try:
            partitions = await asyncio.wait_for(
                asyncio.to_thread(psutil.disk_partitions),
                timeout=5.0
            )

            for part in partitions:
                if (
                        part.device and
                        part.device.startswith('/dev/') and
                        'loop' not in part.device and
                        part.fstype and
                        part.fstype not in ['squashfs', 'tmpfs']
                ):
                    try:
                        usage = await asyncio.wait_for(
                            asyncio.to_thread(psutil.disk_usage, part.mountpoint),
                            timeout=5
                        )

                        device_name = part.device.split('/')[-1]

                        result_storage[device_name] = {
                            'mountpoint': part.mountpoint,
                            'used_gb': round(usage.used / (1024 ** 3), 2),
                            'free_gb': round(usage.free / (1024 ** 3), 2),
                            'total_gb': round(usage.total / (1024 ** 3), 2),
                            'used_percent': usage.percent,
                        }

                    except Exception as e:
                        logger.warning(f"Skip {part.device}: {e}")

        except asyncio.TimeoutError:
            logger.error("Disk read timeout (5s)")
            return None
        except Exception as e:
            logger.error(f"Disk scan failed: {e}")
            return None

        disk_count = len(result_storage)
        if disk_count:
            logger.debug(f"Found {disk_count} physical disks")
            return {
                'disks': result_storage,
                'total_disks': disk_count,
            }

        logger.warning("No physical disks found")
        return None