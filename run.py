import logging
import os
import sys
from app import create_app

print("=== НАСТРОЙКА ЛОГГЕРА В run.py ===")  # Метка

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Убираем шум от библиотек
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.INFO)
logging.getLogger('hypercorn').setLevel(logging.WARNING)
logging.getLogger('playwright').setLevel(logging.WARNING)

# Твои мониторы
logging.getLogger('app.system').setLevel(logging.DEBUG)

app = create_app()

if __name__ == '__main__':
    print("=== ЗАПУСК APP.RUN ===")
    app.run(debug=True, use_reloader=False)