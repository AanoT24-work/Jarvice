import logging
import uvicorn
from app import create_app

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Убираем шум от библиотек
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.INFO)  # Если остался от Flask
logging.getLogger('uvicorn').setLevel(logging.INFO)
logging.getLogger('playwright').setLevel(logging.WARNING)

# Ваши мониторы
logging.getLogger('app.system').setLevel(logging.DEBUG)

if __name__ == '__main__':
    print("=== ЗАПУСК FASTAPI через Uvicorn ===")
    uvicorn.run(
        "run:create_app",  # Изменено: вызываем create_app, а не app
        host="127.0.0.1",
        port=5000,
        reload=True,
        log_level="debug"
    )