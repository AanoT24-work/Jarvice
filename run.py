import logging
import os
import sys
import uvicorn
from app import create_app

print("=== НАСТРОЙКА ЛОГГЕРА В run.py ===")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Убираем шум от библиотек
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('uvicorn').setLevel(logging.INFO)
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
logging.getLogger('playwright').setLevel(logging.WARNING)

# Твои мониторы
logging.getLogger('app.system').setLevel(logging.DEBUG)

app = create_app()

if __name__ == '__main__':
    print("=== ЗАПУСК UVICORN ===")
    uvicorn.run(
        "run:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )