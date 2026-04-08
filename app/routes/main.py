import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

from app.base_monitor import SystemMonitorFacade

monitor_facade = SystemMonitorFacade()


@router.get("/")
async def index():
    return HTMLResponse(content="<script>window.location.href='/main.html';</script>", status_code=200)


@router.get("/main.html")
async def main_page(request: Request):
    return templates.TemplateResponse("main.html", {"request": request, "current_time": datetime.now()})


@router.get("/test")
async def test():
    return {"status": "ok", "message": "FastAPI работает"}


@router.get("/debug")
async def debug():
    """Проверка, что мониторы работают"""
    data = {
        'measurements': {},
        'detailed_info': {}
    }

    for name, monitor in monitor_facade.monitors.items():
        try:
            measure_result = await monitor.measure()
            data['measurements'][name] = {
                'value': measure_result,
                'status': 'ok'
            }

            if hasattr(monitor, 'detailed_info'):
                detailed_result = await monitor.detailed_info()
                data['detailed_info'][name] = {
                    'value': detailed_result,
                    'status': 'ok'
                }

        except Exception as e:
            data['measurements'][name] = {
                'error': str(e),
                'status': 'error'
            }

    return data


async def event_stream(generator_func):
    """Генератор SSE событий"""
    async for chunk in generator_func:
        yield chunk


@router.get("/cpu")
async def cpu_stream():
    async def generate():
        async for chunk in monitor_facade.monitors['cpu'].stream():
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )


@router.get("/ram")
async def ram_stream():
    async def generate():
        async for chunk in monitor_facade.monitors['ram'].stream():
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )


@router.get("/gpu")
async def gpu_stream():
    async def generate():
        gpu_monitor = monitor_facade.monitors['gpu']
        while True:
            try:
                value = await gpu_monitor.measure()
                details = await gpu_monitor.detailed_info()
                data = {
                    'gpu': value,
                    'details': details
                }
                yield f"data: {json.dumps(data)}\n\n"
            except Exception as e:
                error_data = {'gpu': 0, 'error': str(e)}
                yield f"data: {json.dumps(error_data)}\n\n"
            await asyncio.sleep(gpu_monitor.interval)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )


@router.get("/network")
async def network_stream():
    network_key = None
    for key in monitor_facade.monitors.keys():
        if 'network' in key.lower():
            network_key = key
            break

    if network_key is None:
        async def error_generate():
            yield f"data: {json.dumps({'error': 'Network monitor not found'})}\n\n"

        return StreamingResponse(
            error_generate(),
            media_type="text/event-stream",
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )

    async def generate():
        async for chunk in monitor_facade.monitors[network_key].stream():
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )