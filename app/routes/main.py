import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.base_monitor import OC, SystemMonitorFacade, Location

logger = logging.getLogger(__name__)
router = APIRouter()

# Конфигурация
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(['html', 'xml']),
    enable_async=True
)

# Глобальное состояние
monitor_facade = None
is_initialized = False


async def init_monitors():
    """Инициализация мониторов"""
    global monitor_facade, is_initialized

    if is_initialized:
        return True

    logger.info("Инициализация мониторов...")
    try:
        monitor_facade = SystemMonitorFacade(oc_monitor=OC())
        result = await monitor_facade.add_oc_monitor()

        if result is not None:
            is_initialized = True
            logger.info(f"Мониторы готовы: {list(monitor_facade.monitors.keys())}")
            return True
        else:
            logger.warning("ОС-специфичные мониторы не активированы, но базовые работают")
            is_initialized = True
            return True
    except Exception as e:
        logger.error(f"Ошибка инициализации: {e}")
        return False


# ============ ЭНДПОИНТЫ ============

@router.get("/")
async def index():
    """Перенаправление на дашборд"""
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Главная страница"""
    template = jinja_env.get_template("main.html")

    def url_for(name: str, **kwargs):
        return request.url_for(name, **kwargs)

    html = await template.render_async(
        request=request,
        current_time=datetime.now(),
        url_for=url_for
    )
    return HTMLResponse(content=html)


@router.get("/health")
async def health():
    """Проверка работоспособности"""
    return {
        "status": "ok" if is_initialized else "initializing",
        "initialized": is_initialized,
        "time": datetime.now().isoformat()
    }


# Добавьте в существующий main.py

@router.get("/myip")
async def get_my_ip():
    """Получить реальный IP выхода в интернет"""
    if not is_initialized:
        await init_monitors()

    location_data = await monitor_facade.location.get_location()
    return JSONResponse(content={
        "ip": location_data.get("ip"),
        "country": location_data.get("country"),
        "vpn_detected": location_data.get("wpn_flag", False),
        "details": location_data
    })

@router.get("/all_data")
async def get_all_data(request: Request):
    """Получить все данные разом (включая геолокацию)"""
    if not is_initialized:
        await init_monitors()

    try:
        data = await monitor_facade.get_all_data(request)
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/location")
async def get_location(request: Request):
    """Получить информацию о местоположении"""
    if not is_initialized:
        await init_monitors()

    try:
        location_data = await monitor_facade.get_location_data(request)
        return JSONResponse(content=location_data)
    except Exception as e:
        logger.error(f"Ошибка получения геолокации: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream/all")
async def stream_all(request: Request):
    """Поток всех данных (Server-Sent Events)"""
    if not is_initialized:
        await init_monitors()

    async def generate():
        try:
            while True:
                data = await monitor_facade.get_all_data(request)
                yield f"data: {json.dumps(data, default=str)}\n\n"
                await asyncio.sleep(1)  # Обновление каждую секунду
        except Exception as e:
            logger.error(f"Ошибка в стриме: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@router.get("/stream/{monitor_name}")
async def stream_single(monitor_name: str):
    """Поток данных от конкретного монитора"""
    if not is_initialized:
        await init_monitors()

    # Ищем монитор (без учета регистра)
    monitor = None
    for name, mon in monitor_facade.monitors.items():
        if monitor_name.lower() in name.lower():
            monitor = mon
            break

    if not monitor:
        available = list(monitor_facade.monitors.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Монитор '{monitor_name}' не найден. Доступны: {available}"
        )

    async def generate():
        try:
            async for chunk in monitor.stream():
                yield chunk
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@router.post("/init")
async def force_init():
    """Принудительная инициализация"""
    result = await init_monitors()
    return {
        "success": result,
        "initialized": is_initialized,
        "monitors": list(monitor_facade.monitors.keys()) if monitor_facade else []
    }


@router.get("/debug")
async def debug(request: Request):
    """Отладочная информация"""
    if not is_initialized:
        await init_monitors()

    result = {
        "initialized": is_initialized,
        "monitors": list(monitor_facade.monitors.keys()) if monitor_facade else [],
        "data": {}
    }

    for name, monitor in monitor_facade.monitors.items():
        try:
            value = await monitor.measure()
            result["data"][name] = value
        except Exception as e:
            result["data"][name] = f"Ошибка: {e}"

    # Добавляем геоданные в debug
    try:
        location_data = await monitor_facade.get_location_data(request)
        result["location"] = location_data
    except Exception as e:
        result["location"] = {"error": str(e)}

    return result