''' Файл для получения данных с датчиков для windows '''

from typing import Optional

from Options.system_all import SystemMonitor, OperationSystemMonitor


class CPUMonitor_Windows(SystemMonitor):
    def __init__(self, oc_flag: OperationSystemMonitor, interval: Optional[float] = 3,
                 history_size: Optional[int] = 10):
        super().__init__('cpu_windows', interval, history_size)
        self.oc_flag = oc_flag

    async def init_oc(self) -> bool:
        await self.oc_flag.measure()
        return self.oc_flag.windows_flag

    async def measure(self) -> Optional[dict]:
        if not await self.init_oc():
            return {}


