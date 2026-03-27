from asyncio.log import logger
import json
import asyncio  # Добавляем asyncio
from typing import AsyncGenerator  # Меняем тип
from Options.system import CPUMonitor, RAMMonitor, StorageMonitor


class SystemMonitorFacade:
    def __init__(self):
        self.cpu_monitor = CPUMonitor(interval=1, history_size=10)
        
        self.monitors = {
            'cpu': self.cpu_monitor,
            'ram': RAMMonitor(cpu_monitor=self.cpu_monitor, interval=1, history_size=10),
            'storage': StorageMonitor(cpu_monitor=self.cpu_monitor, interval=1, history_size=10)

        }
    
    async def get_all_data(self) -> dict:  
        data = {}
        for name, monitor in self.monitors.items():
            try:
                # Измеряем асинхронно
                value = await monitor.measure()
                
                # Базовая структура данных
                monitor_data = {'current': value}
                
                # Добавляем историю, если она есть (она автоматически обновляется в monitor.measure)
                if monitor.history is not None:
                    monitor_data['history'] = monitor.get_history()
                    stats = monitor.get_stats()
                    if stats:
                        monitor_data['stats'] = stats
                
                # Добавляем детальную информацию для определенных типов
                if name in ['ram', 'gpu']:
                    try:
                        details = await monitor.detailed_info()
                        if details:
                            monitor_data['details'] = details
                    except Exception as e:
                        logger.error(f"Ошибка получения детальной информации для {name}: {e}")
                        monitor_data['details'] = {'error': str(e)}
                
                data[name] = monitor_data
                
            except Exception as e:
                logger.error(f"Ошибка получения данных для {name}: {e}")
                data[name] = {'error': str(e)}
                
        return data

    async def stream_all(self) -> AsyncGenerator[str, None]:  # Асинхронный генератор
        while True:
            try:
                data = await self.get_all_data()
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error(f"Ошибка в stream_all: {e}")
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            
            await asyncio.sleep(1)  # Асинхронная задержка

    # Добавляем метод для запуска всех стримов
    async def start_streaming(self):
        """Запускает все мониторы в отдельных задачах"""
        tasks = []
        for name, monitor in self.monitors.items():
            # Запускаем каждый монитор как отдельную задачу
            task = asyncio.create_task(
                self._run_monitor_stream(name, monitor),
                name=f"monitor_{name}"
            )
            tasks.append(task)
        
        # Ждем завершения всех задач (они будут работать бесконечно)
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _run_monitor_stream(self, name: str, monitor):
        """Запускает стрим конкретного монитора"""
        try:
            async for data in monitor.stream():
                # Здесь можно обрабатывать данные каждого монитора отдельно
                # Например, отправлять в вебсокет или сохранять в БД
                logger.debug(f"Монитор {name}: {data}")
        except Exception as e:
            logger.error(f"Ошибка в стриме монитора {name}: {e}")