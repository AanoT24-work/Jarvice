// Ждем загрузки страницы
document.addEventListener('DOMContentLoaded', function() {
    const canvas = document.getElementById('cityCanvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();
    
    // Кэшируем для производительности
    let cachedImageData = null;
    let cachedCanvasSize = null;
    
    // Загружаем изображение города
    img.src = '/static/photo/Preset/City.png';
    img.crossOrigin = 'anonymous';
    
    img.onload = function() {
        renderCity();
        // Ресайз с троттлингом для производительности
        let resizeTimeout;
        window.addEventListener('resize', function() {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(renderCity, 100);
        });
    };
    
    function renderCity() {
        const container = canvas.parentElement;
        const width = container.clientWidth;
        const height = container.clientHeight;
        
        // Проверяем, изменился ли размер
        if (cachedCanvasSize && cachedCanvasSize.width === width && cachedCanvasSize.height === height && cachedImageData) {
            // Используем кэшированное изображение
            ctx.putImageData(cachedImageData, 0, 0);
            return;
        }
        
        // Устанавливаем размеры canvas
        canvas.width = width;
        canvas.height = height;
        
        // Рассчитываем размеры для background-size: contain
        const imgRatio = img.width / img.height;
        const canvasRatio = width / height;
        
        let drawWidth, drawHeight, offsetX, offsetY;
        
        if (imgRatio > canvasRatio) {
            // Изображение шире, чем контейнер
            drawWidth = width;
            drawHeight = width / imgRatio;
            offsetX = 0;
            offsetY = (height - drawHeight) / 2;
        } else {
            // Изображение выше, чем контейнер
            drawHeight = height;
            drawWidth = height * imgRatio;
            offsetX = (width - drawWidth) / 2;
            offsetY = 0;
        }
        
        // Очищаем canvas
        ctx.clearRect(0, 0, width, height);

        // Рисуем изображение
        ctx.drawImage(img, offsetX, offsetY, drawWidth, drawHeight);

        // Создаем вертикальный линейный градиент
        const vertical_gradient = ctx.createLinearGradient(
            0, offsetY,                 
            0, offsetY + drawHeight       
        );      
        vertical_gradient.addColorStop(0, 'rgba(0, 0, 0, 0)');
        vertical_gradient.addColorStop(0.1, 'rgba(0, 0, 0, 0.5)');
        vertical_gradient.addColorStop(0.2, 'rgba(0, 0, 0, 1)');
        vertical_gradient.addColorStop(0.8, 'rgba(0, 0, 0, 1)');
        vertical_gradient.addColorStop(0.9, 'rgba(0, 0, 0, 0.5)');
        vertical_gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.globalCompositeOperation = 'destination-in';
        ctx.fillStyle = vertical_gradient;
        ctx.fillRect(offsetX, offsetY, drawWidth, drawHeight);

        // Создаем горизонтальный градиент (исправлено!)
        const horizontal_gradient = ctx.createLinearGradient(
            offsetX, 0,                   
            offsetX + drawWidth, 0       
        );
        horizontal_gradient.addColorStop(0, 'rgba(0, 0, 0, 0)');
        horizontal_gradient.addColorStop(0.1, 'rgba(0, 0, 0, 0.5)');  
        horizontal_gradient.addColorStop(0.2, 'rgba(0, 0, 0, 1)');    
        horizontal_gradient.addColorStop(0.8, 'rgba(0, 0, 0, 1)');    
        horizontal_gradient.addColorStop(0.9, 'rgba(0, 0, 0, 0.5)');  
        horizontal_gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = horizontal_gradient;
        ctx.fillRect(offsetX, offsetY, drawWidth, drawHeight);

        // Возвращаем режим композиции
        ctx.globalCompositeOperation = 'source-over';
        
        // Кэшируем результат
        cachedImageData = ctx.getImageData(0, 0, width, height);
        cachedCanvasSize = { width, height };
    }
    
    // Анимация для плавного появления
    let opacity = 0;
    function fadeIn() {
        if (opacity < 1) {
            opacity += 0.05;
            canvas.style.opacity = opacity;
            requestAnimationFrame(fadeIn);
        }
    }
    
    // Запускаем fade-in после загрузки
    setTimeout(fadeIn, 100);
});