import asyncio
import logging
import platform
import traceback
from typing import Optional, Dict, Any
import aiohttp
from fastapi import Request

from Options.system_all import CPUMonitor_All, RAMMonitor_All, Network_system_All
from Options.system_linux import CPUMonitor_Linux, StorageMonitor_Linux
from Options.system_windows import CPUMonitor_Windows, StorageMonitor_Windows

logger = logging.getLogger(__name__)


class OC:
    def __init__(self):
        self.linux_flag = False
        self.windows_flag = False

    async def init_oc(self) -> Optional[dict]:
        try:
            oc_name = await asyncio.wait_for(asyncio.to_thread(platform.system), timeout=5)
            if oc_name is None:
                logger.error(f'There is no information about the name CPU')
                return None

        except asyncio.TimeoutError:
            logger.error("OS detection timeout (5s)")
            return None
        except Exception as e:
            logger.error(f"OS detection failed: {e}")
            return None

        oc_name_lower = oc_name.lower()
        if 'windows' in oc_name_lower:
            self.windows_flag = True
        elif 'linux' in oc_name_lower:
            self.linux_flag = True
        return {"linux_flag": self.linux_flag, "windows_flag": self.windows_flag}


class Location:
    """Класс для получения реального публичного IP и геолокации"""

    def __init__(self):
        self.main_position = ["russia", "россия"]
        self.wpn_flag = False

    async def get_location(self, request: Request = None) -> Dict[str, Any]:
        """Получить реальный публичный IP и геолокацию"""
        try:
            public_ip = await self._get_public_ip()

            if not public_ip:
                return {
                    "error": "Не удалось определить публичный IP",
                    "country": "Unknown",
                    "ip": None,
                    "wpn_flag": None
                }

            geo_data = await self._get_geo_data(public_ip)
            country = geo_data.get('country', 'Unknown') if geo_data else 'Unknown'

            self.wpn_flag = country.lower() not in [p.lower() for p in self.main_position]

            result = {
                "ip": public_ip,
                "country": country,
                "wpn_flag": self.wpn_flag,
                "status": "success"
            }

            if geo_data:
                result.update({
                    "city": geo_data.get("city"),
                    "region": geo_data.get("regionName"),
                    "isp": geo_data.get("isp"),
                    "lat": geo_data.get("lat"),
                    "lon": geo_data.get("lon")
                })

            logger.info(f"Public IP: {public_ip}, Country: {country}, VPN: {self.wpn_flag}")
            return result

        except Exception as e:
            logger.error(f"Location error: {e}")
            return {
                "error": str(e),
                "country": "Unknown",
                "ip": None,
                "wpn_flag": None,
                "status": "error"
            }

    async def _get_public_ip(self) -> Optional[str]:
        """Получить реальный публичный IP"""
        try:
            async with aiohttp.ClientSession() as session:
                services = [
                    'https://api.ipify.org?format=json',
                    'https://icanhazip.com',
                    'https://checkip.amazonaws.com',
                ]

                for service in services:
                    try:
                        async with session.get(service, timeout=5) as response:
                            if response.status == 200:
                                if 'ipify' in service:
                                    data = await response.json()
                                    return data.get('ip')
                                else:
                                    text = await response.text()
                                    return text.strip()
                    except:
                        continue
        except Exception as e:
            logger.error(f"Error getting public IP: {e}")

        return None

    async def _get_geo_data(self, ip: str) -> Optional[Dict]:
        """Получить геоданные по IP"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f'http://ip-api.com/json/{ip}?fields=status,country,city,regionName,isp,lat,lon'
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == 'success':
                            return data
        except Exception as e:
            logger.error(f"Error getting geo data: {e}")

        return None


class SystemMonitorFacade:
    def __init__(self, oc_monitor: OC):
        self.oc_monitor = oc_monitor
        self.location = Location()

        self.common_cpu = CPUMonitor_All(interval=3, history_size=10)
        self.common_ram = RAMMonitor_All(interval=3, history_size=10)
        self.common_network_system = Network_system_All(interval=20, history_size=10)

        self.linux_cpu = CPUMonitor_Linux(interval=3, history_size=10)
        self.linux_storage = StorageMonitor_Linux(interval=3, history_size=10)

        self.windows_cpu = CPUMonitor_Windows(interval=3, history_size=10)
        self.windows_storage = StorageMonitor_Windows(interval=3, history_size=10)

        self.monitor_all = {
            'common_cpu': self.common_cpu,
            'common_ram': self.common_ram,
            'common_network_system': self.common_network_system,
        }
        self.oc_monitors = {}
        self.monitors = {}

    async def add_oc_monitor(self):
        """Активирует ОС-специфичные мониторы"""
        try:
            oc_flag = await self.oc_monitor.init_oc()
            if oc_flag is None:
                logger.error('Нет информации об ОС (oc_flag is None)')
                return None

            if oc_flag.get("linux_flag"):
                logger.info("Обнаружена ОС: Linux")
                self.oc_monitors = {
                    'linux_cpu': self.linux_cpu,
                    'linux_storage': self.linux_storage,
                }
            elif oc_flag.get("windows_flag"):
                logger.info("Обнаружена ОС: Windows")
                self.oc_monitors = {
                    'windows_cpu': self.windows_cpu,
                    'windows_storage': self.windows_storage,
                }
            else:
                logger.warning("ОС не определена как Linux или Windows")

            self.monitors = {**self.monitor_all, **self.oc_monitors}
            return self.oc_monitors

        except Exception as e:
            logger.error(f"Ошибка при активации ОС-мониторов: {e}")
            logger.error(traceback.format_exc())
            return None

    # ДОБАВЛЕННЫЙ МЕТОД:
    async def get_location_data(self, request: Request = None) -> dict:
        """Получить данные о местоположении"""
        return await self.location.get_location(request)

    async def get_all_data(self, request: Request = None) -> dict:
        """Получить данные со всех мониторов включая геолокацию"""

        if not self.monitors:
            logger.warning("Мониторы не инициализированы, вызываем add_oc_monitor()")
            await self.add_oc_monitor()

        if not self.monitors:
            logger.error("Мониторы все еще не инициализированы")
            return {"error": "No monitors initialized"}

        data = {}

        for name, monitor in self.monitors.items():
            if monitor is None:
                continue
            try:
                value = await monitor.measure()
                if value is None:
                    data[name] = {'error': 'No data'}
                    continue

                monitor_data = {'current': value}

                if hasattr(monitor, 'history') and monitor.history is not None:
                    monitor_data['history'] = monitor.get_history()
                    stats = monitor.get_stats()
                    if stats:
                        monitor_data['stats'] = stats

                if name in ['common_ram', 'linux_cpu', 'windows_cpu']:
                    if hasattr(monitor, 'detailed_info'):
                        try:
                            details = await monitor.detailed_info()
                            if details:
                                monitor_data['details'] = details
                        except Exception as e:
                            logger.debug(f"Detailed info not available for {name}: {e}")

                data[name] = monitor_data
            except Exception as e:
                logger.error(f"Ошибка при получении данных для {name}: {e}")
                data[name] = {'error': str(e)}

        # Добавляем геолокацию
        try:
            location_data = await self.get_location_data(request)
            data['location'] = location_data
        except Exception as e:
            data['location'] = {'error': str(e)}

        return data


async def test_facade():
    logging.basicConfig(level=logging.INFO)
    oc = OC()
    facade = SystemMonitorFacade(oc)
    await facade.add_oc_monitor()
    data = await facade.get_all_data()

    import json
    print(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(test_facade())