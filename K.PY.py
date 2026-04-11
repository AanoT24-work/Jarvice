
async def init_monitors():
    """Асинхронная инициализация мониторов"""
    global _initialized
    if not _initialized:
        logger.info("=== ИНИЦИАЛИЗАЦИЯ МОНИТОРОВ В MAIN ===")
        result = await monitor_facade.add_oc_monitor()
        _initialized = True
        logger.info(f"Мониторы инициализированы: {list(monitor_facade.monitors.keys())}")
        return result
    return True


async def async_generator_to_sse(generator: AsyncGenerator, event_name: str = "message"):
    """Конвертирует асинхронный генератор в SSE формат"""
    async for chunk in generator:
        yield f"event: {event_name}\n{chunk}"


@router.get("/", include_in_schema=False)
async def index():
    return RedirectResponse(url="/main.html")


@router.get("/main.html", response_class=HTMLResponse)
async def main_page(request: Request):


    return templates.TemplateResponse(
        "main.html",
        {
            "request": request,
            "current_time": datetime.now()
        }
    )


@router.get("/test")
async def test():
    """Тестовый маршрут для проверки работы"""
    return {"status": "ok", "message": "FastAPI работает"}


@router.get("/init")
async def init():
    """Ручная инициализация мониторов"""
    try:
        result = await init_monitors()
        return {
            'status': 'success',
            'initialized': _initialized,
            'monitors': list(monitor_facade.monitors.keys()),
            'result': result
        }
    except Exception as e:
        logger.error(f"Ошибка инициализации: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={'status': 'error', 'error': str(e)}
        )


@router.get("/debug")
async def debug():
    """Проверка, что мониторы работают"""
    global _initialized

    # Инициализируем, если еще не
    if not _initialized:
        await init_monitors()

    data = {
        'initialized': _initialized,
        'monitors': list(monitor_facade.monitors.keys()),
        'measurements': {},
        'detailed_info': {}
    }

    for name, monitor in monitor_facade.monitors.items():
        try:
            # measure
            measure_result = await monitor.measure()
            data['measurements'][name] = {
                'value': measure_result,
                'status': 'ok'
            }

            # detailed_info
            if hasattr(monitor, 'detailed_info'):
                detailed_result = await monitor.detailed_info()
                data['detailed_info'][name] = {
                    'value': detailed_result,
                    'status': 'ok'
                }

        except Exception as e:
            logger.error(f"Ошибка для {name}: {e}")
            data['measurements'][name] = {
                'error': str(e),
                'status': 'error'
            }

    return data


@router.get("/all_data")
async def all_data():
    """Получить все данные сразу"""
    global _initialized

    if not _initialized:
        await init_monitors()

    try:
        data = await monitor_facade.get_all_data()
        return data
    except Exception as e:
        logger.error(f"Ошибка получения данных: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={'error': str(e)}
        )


@router.get("/stream/all")
async def stream_all():
    """SSE поток всех данных"""
    global _initialized

    if not _initialized:
        await init_monitors()

    async def generate():
        async for chunk in monitor_facade.stream_all():
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'X-Accel-Buffering': 'no'
        }
    )


@router.get("/stream/{monitor_name}")
async def stream_monitor(monitor_name: str):
    """SSE поток конкретного монитора"""
    global _initialized

    if not _initialized:
        await init_monitors()

    # Ищем монитор
    monitor = None
    for key, mon in monitor_facade.monitors.items():
        if monitor_name.lower() in key.lower():
            monitor = mon
            break

    if monitor is None:
        async def error_stream():
            yield f"data: {json.dumps({'error': f'Monitor {monitor_name} not found'})}\n\n"

        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={'Access-Control-Allow-Origin': '*'}
        )

    async def generate():
        async for chunk in monitor.stream():
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


# Упрощенные маршруты для конкретных мониторов
@router.get("/cpu")
async def cpu_stream():
    return await stream_monitor('cpu')


@router.get("/ram")
async def ram_stream():
    return await stream_monitor('ram')


@router.get("/network")
async def network_stream():
    return await stream_monitor('network')


@router.get("/storage")
async def storage_stream():
    return await stream_monitor('storage')


# Дополнительный эндпоинт для получения конкретного монитора
@router.get("/monitor/{monitor_name}")
async def get_monitor_data(monitor_name: str):
    """Получить данные конкретного монитора"""
    global _initialized

    if not _initialized:
        await init_monitors()

    monitor = None
    for key, mon in monitor_facade.monitors.items():
        if monitor_name.lower() in key.lower():
            monitor = mon
            break

    if monitor is None:
        return JSONResponse(
            status_code=404,
            content={'error': f'Monitor {monitor_name} not found'}
        )

    try:
        value = await monitor.measure()
        result = {'name': monitor_name, 'value': value}

        if hasattr(monitor, 'history'):
            result['history'] = monitor.get_history()
            stats = monitor.get_stats()
            if stats:
                result['stats'] = stats

        if hasattr(monitor, 'detailed_info'):
            details = await monitor.detailed_info()
            if details:
                result['details'] = details

        return result
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={'error': str(e)}
        )