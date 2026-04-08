from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path


def create_app():
    app = FastAPI(title="Jarvice Monitor", debug=True)

    # Настройка статики и шаблонов
    static_path = Path("app/static")
    templates_path = Path("app/templates")

    if static_path.exists():
        app.mount("/static", StaticFiles(directory=static_path), name="static")

    # Импорт роутеров
    from .routes.main import router
    app.include_router(router)

    return app