@echo off
setlocal

:: =================================================================
:: Script de DEPURACIÓN para el pipeline (usando python run.py)
:: =================================================================
:: Este script ejecuta cada servicio en ESTA MISMA VENTANA y
:: hace una pausa si uno de ellos falla, permitiéndote ver el error.
:: Para pasar al siguiente servicio, cierra el actual con Ctrl+C.

echo.
echo Iniciando pipeline en modo de depuracion...
echo Asegurate de que tu entorno virtual (conda o venv) este activado.
echo.
pause
echo.

:: --- Paso 1: API de la Camara ---
echo [1/5] Iniciando API de la Camara... Presiona Ctrl+C para detenerla y continuar.
python run.py camera
echo API de Camara detenida.
echo.

:: --- Paso 2: Worker de la Cola de Camaras ---
echo [2/5] Iniciando Worker de Camaras...
python run.py worker camaras_queue 1
echo Worker de Camaras crasheo o fue detenido.
pause
echo.

:: --- Paso 3: Worker de la Cola de Inferencia ---
echo [3/5] Iniciando Worker de Inferencia...
python run.py worker inference_queue 4
echo Worker de Inferencia crasheo o fue detenido.
pause
echo.

:: --- Paso 4: Worker de la Cola de Procesamiento ---
echo [4/5] Iniciando Worker de Procesamiento...
python run.py worker processing_queue 2
echo Worker de Procesamiento crasheo o fue detenido.
pause
echo.

:: --- Paso 5: Celery Beat ---
echo [5/5] Iniciando Celery Beat...
python run.py beat
echo Celery Beat crasheo o fue detenido.
pause
echo.

echo =================================================================
echo Depuracion finalizada.
echo =================================================================
echo.

endlocal
pause