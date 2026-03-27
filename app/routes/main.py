import time
import asyncio
import json
from datetime import datetime
from flask import Blueprint, Response, redirect, render_template, jsonify

main = Blueprint('main', __name__)

from app.base_monitor import SystemMonitorFacade
monitor_facade = SystemMonitorFacade()

@main.route('/')
def index():
    return redirect('/main.html')

@main.route('/main.html')
def main_page():
    return render_template('main.html', current_time=datetime.now())

@main.route('/test')
def test():
    """Тестовый маршрут для проверки работы"""
    return jsonify({"status": "ok", "message": "Flask работает"})

# ОТЛАДОЧНЫЙ МАРШРУТ
@main.route('/debug')
async def debug():
    """Проверка, что мониторы работают"""
    data = {
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
            data['measurements'][name] = {
                'error': str(e),
                'status': 'error'
            }
            
    return jsonify(data)

# Вспомогательная функция для запуска асинхронного генератора в синхронном контексте
def run_async_generator(async_gen):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        while True:
            try:
                chunk = loop.run_until_complete(async_gen.__anext__())
                yield chunk
            except StopAsyncIteration:
                break
    finally:
        loop.close()

# SSE потоки - ВСЕ должны быть синхронными функциями
@main.route('/cpu')
def cpu_stream():
    async def generate():
        async for chunk in monitor_facade.monitors['cpu'].stream():
            yield chunk
    
    return Response(
        run_async_generator(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )

@main.route('/ram')
def ram_stream():
    async def generate():
        async for chunk in monitor_facade.monitors['ram'].stream():
            yield chunk
    
    return Response(
        run_async_generator(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )

@main.route('/gpu')
def gpu_stream():
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
    
    return Response(
        run_async_generator(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )

@main.route('/network')
def network_stream():
    # Проверяем, какой ключ используется для сетевого монитора
    network_key = None
    for key in monitor_facade.monitors.keys():
        if 'network' in key.lower():
            network_key = key
            break
    
    if network_key is None:
        # Если сетевой монитор не найден, возвращаем ошибку
        def error_generate():
            yield f"data: {json.dumps({'error': 'Network monitor not found'})}\n\n"
        return Response(
            error_generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )
    
    async def generate():
        async for chunk in monitor_facade.monitors[network_key].stream():
            yield chunk
    
    return Response(
        run_async_generator(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )