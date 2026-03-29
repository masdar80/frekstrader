@echo off
setlocal
:menu
cls
echo ==========================================
echo       ForeksTrader - Docker Control Center
echo ==========================================
echo  1. START (Run Containers & Build)
echo  2. STOP  (Shut Down All Services)
echo  3. RESTART (Fast Refresh web only)
echo  4. LOGS  (View Live Output)
echo  5. STATUS (Check All Services)
echo  6. EXIT
echo ==========================================
set /p choice="Choose an option (1-6): "

if "%choice%"=="1" (
    echo [STARTING] Rebuilding and launching containers...
    docker-compose up -d --build
    pause
    goto menu
)
if "%choice%"=="2" (
    echo [STOPPING] Shutting down all services safely...
    docker-compose down
    pause
    goto menu
)
if "%choice%"=="3" (
    echo [RESTARTING] Quick reboot of web service...
    docker-compose restart web
    pause
    goto menu
)
if "%choice%"=="4" (
    echo [LOGS] Press Ctrl+C to stop viewing logs.
    docker-compose logs -f web
    goto menu
)
if "%choice%"=="5" (
    echo [STATUS] Checking container health...
    docker-compose ps
    pause
    goto menu
)
if "%choice%"=="6" (
    exit
)

echo Invalid choice. Please try again.
pause
goto menu