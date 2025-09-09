@echo off
setlocal


echo.
echo Iniciando todos los servicios del pipeline en orden...
echo.

:: --- Paso 1: Iniciar la API de la Camara ---
echo [1/5] Iniciando API de la Camara...
start "Camera API" F80_service.exe camera
timeout /t 5 /nobreak >nul

:: --- Paso 2: Iniciar el Worker de la Cola de Camaras ---
echo [2/5] Iniciando Worker de Camaras (cola: camaras_queue, concurrencia: 1)...
start "Camera Worker" F80_service.exe worker camaras_queue 1
timeout /t 5 /nobreak >nul

:: --- Paso 3: Iniciar el Worker de la Cola de Inferencia ---
:: Usando concurrencia 4 como un valor razonable. Ajusta si es necesario.
echo [3/5] Iniciando Worker de Inferencia (cola: inference_queue, concurrencia: 4)...
start "Inference Worker" F80_service.exe worker inference_queue 4
timeout /t 5 /nobreak >nul

:: --- Paso 4: Iniciar el Worker de la Cola de Procesamiento ---
echo [4/5] Iniciando Worker de Procesamiento (cola: processing_queue, concurrencia: 2)...
start "Processing Worker" F80_service.exe worker processing_queue 2
timeout /t 5 /nobreak >nul

:: --- Paso 5: Iniciar Celery Beat (El orquestador) ---
echo [5/5] Iniciando Celery Beat...
start "Celery Beat" F80_service.exe beat

echo.
echo =================================================================
echo Pipeline iniciado. Revisa las nuevas ventanas para ver los logs.
echo =================================================================
echo.

endlocal
pause