# app/__init__.py (исправленный)
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os


# Ленивый импорт Config
def create_app(config_class=None):
    if config_class is None:
        from app.config import Config
        config_class = Config

    app = FastAPI(
        title="System Monitor API",
        description="API для мониторинга системы",
        version="1.0.0"
    )

    app.config = config_class

    # Подключаем статические файлы
    static_path = Path(__file__).parent / 'static'
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # Подключаем роутеры
    from app.routes.main import router as main_router
    app.include_router(main_router)

    return app