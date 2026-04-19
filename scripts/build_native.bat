@echo off
setlocal
echo ============================================================
echo [VULCAN FOUNDRY] Iniciando Compilacao de Motores Nativos
echo ============================================================

:: Verifica se o GCC está instalado
where gcc >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Compilador GCC nao encontrado no PATH.
    echo Instale o MinGW-w64 para continuar.
    exit /b 1
)

:: Define caminhos relativos a partir da raiz do projeto
set NATIVE_DIR=engine\native

echo [1/3] Compilando Shredder (vulcan_cleaner)...
gcc -shared -o %NATIVE_DIR%\vulcan_cleaner.dll %NATIVE_DIR%\vulcan_cleaner.c -lkernel32
if %errorlevel% equ 0 (echo   [OK] vulcan_cleaner.dll) else (echo   [FALHA])

echo [2/3] Compilando RAM Engine (vulcan_ram)...
gcc -shared -o %NATIVE_DIR%\vulcan_ram.dll %NATIVE_DIR%\vulcan_ram.c -lpsapi
if %errorlevel% equ 0 (echo   [OK] vulcan_ram.dll) else (echo   [FALHA])

echo [3/3] Compilando Backup Engine (vulcan_dox_v3)...
gcc -shared -o %NATIVE_DIR%\vulcan_dox_v3.dll %NATIVE_DIR%\dox_packer.c -lkernel32
if %errorlevel% equ 0 (echo   [OK] vulcan_dox_v3.dll) else (echo   [FALHA])

echo.
echo [CONCLUIDO] Todos os binarios foram processados.
echo ============================================================
endlocal