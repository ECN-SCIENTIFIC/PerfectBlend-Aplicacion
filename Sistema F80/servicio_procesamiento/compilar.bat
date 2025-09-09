@echo off
setlocal

echo Limpiando builds anteriores...
if exist "%~dp0dist" rmdir /s /q "%~dp0dist"
if exist "%~dp0build" rmdir /s /q "%~dp0build"

echo.
echo =======================================================
echo     Construyendo el ejecutable universal...
echo =======================================================
echo.

pyinstaller --noconfirm build.spec

echo.
echo =======================================================
echo          Proceso de compilacion completado.
echo =======================================================
echo.
echo La carpeta 'dist/proyecto_output' esta lista para ser desplegada.
echo Contiene el ejecutable: F80_service.exe
echo.

endlocal
pause