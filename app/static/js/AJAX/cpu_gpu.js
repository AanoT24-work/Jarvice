
function startMonitoring() {
    // Если уже есть активные источники - не создаем новые
    if (window.monitoringSources.cpu && window.monitoringSources.cpu.readyState === EventSource.OPEN) {
        console.log('Sources already exist, reusing...');
        return;
    }
    
    console.log('Starting monitoring...');
    
    // CPU Monitoring
    if (!window.monitoringSources.cpu) {
        console.log('Creating CPU source');
        window.monitoringSources.cpu = new EventSource('/cpu');
        const cpuElement = document.getElementById('cpu-load');
        
        window.monitoringSources.cpu.onmessage = function(event) {
            console.log('CPU data:', event.data);
            try {
                const data = JSON.parse(event.data);
                if (cpuElement) {
                    cpuElement.textContent = `${data.cpu?.toFixed(1) || 0}%`;
                }
            } catch (error) {
                console.error('Error parsing CPU data:', error);
            }
        };
        
        window.monitoringSources.cpu.onerror = function() {
            console.log('CPU connection error, will reconnect...');
            setTimeout(() => {
                window.monitoringSources.cpu.close();
                window.monitoringSources.cpu = null;
                window.monitoringSources.initialized = false;
            }, 3000);
        };
    }
    
    // GPU Monitoring
    if (!window.monitoringSources.gpu) {
        console.log('Creating GPU source');
        window.monitoringSources.gpu = new EventSource('/gpu');
        const gpuLoad = document.getElementById('gpu-load');

        window.monitoringSources.gpu.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);   
                if (gpuLoad) {
                    if (data.details && data.details.used_gb !== undefined) {
                        gpuLoad.textContent = `${data.details.used_gb.toFixed(1)} GB`;
                    } else {
                        gpuLoad.textContent = 'N/A';
                    }
                }
            } catch(error) {
                console.error('Не удалось получить данные о GPU', error);
            }    
        };
        
        window.monitoringSources.gpu.onerror = function() {
            console.log('GPU connection error, will reconnect...');
            setTimeout(() => {
                window.monitoringSources.gpu.close();
                window.monitoringSources.gpu = null;
                window.monitoringSources.initialized = false;
            }, 3000);
        };
    }

    // Network Monitoring
    if (!window.monitoringSources.network) {
        console.log('Creating Network source');
        window.monitoringSources.network = new EventSource('/network');
        const networSpeed = document.getElementById('network');

        window.monitoringSources.network.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                if (networSpeed) {
                    networSpeed.textContent = `${data.network_system?.load_download?.toFixed(1) || 0} Mbit/s`;
                }
            }catch (error) {
                console.error('Error parsing network data:', error);
            }
        };
        
        window.monitoringSources.network.onerror = function() {
            console.log('Network connection error, will reconnect...');
            setTimeout(() => {
                window.monitoringSources.network.close();
                window.monitoringSources.network = null;
                window.monitoringSources.initialized = false;
            }, 3000);
        };
    }

    // Закрываем соединения при закрытии страницы
    window.addEventListener('beforeunload', function() {
        if (window.monitoringSources.cpu) {
            window.monitoringSources.cpu.close();
        }
        if (window.monitoringSources.gpu) {
            window.monitoringSources.gpu.close();
        }
        if (window.monitoringSources.network) {
            window.monitoringSources.network.close();
        }
        console.log('All SSE connections closed');
    });
}