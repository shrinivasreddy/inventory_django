@echo off
REM ============================================================
REM Installs Inventory Web (Django) as a Windows Service using NSSM,
REM so it behaves like Tomcat: starts automatically on server boot,
REM keeps running in the background, restarts if it crashes.
REM ============================================================
REM
REM SETUP (one-time):
REM   1. Download NSSM from https://nssm.cc/download and extract it.
REM   2. Copy nssm.exe into this "deploy" folder (or edit NSSM_PATH below).
REM   3. Edit APP_DIR below to match where you deployed this project.
REM   4. Make sure you've already run once, manually:
REM        pip install -r requirements.txt
REM        python manage.py migrate
REM        python manage.py collectstatic --noinput
REM   5. Run this script as Administrator.

setlocal

REM ---- EDIT THESE TWO LINES FOR YOUR SERVER ----
set APP_DIR=D:\BLUEDOME\web\inventory_django
set NSSM_PATH=%~dp0nssm.exe
REM ------------------------------------------------

set SERVICE_NAME=InventoryWebDjango
set PYTHON_EXE=python.exe

echo Installing "%SERVICE_NAME%" as a Windows Service...
echo App directory: %APP_DIR%
echo.

"%NSSM_PATH%" install %SERVICE_NAME% %PYTHON_EXE% "%APP_DIR%\serve.py"
"%NSSM_PATH%" set %SERVICE_NAME% AppDirectory "%APP_DIR%"
"%NSSM_PATH%" set %SERVICE_NAME% AppStdout "%APP_DIR%\deploy\service_stdout.log"
"%NSSM_PATH%" set %SERVICE_NAME% AppStderr "%APP_DIR%\deploy\service_stderr.log"
"%NSSM_PATH%" set %SERVICE_NAME% AppRotateFiles 1
"%NSSM_PATH%" set %SERVICE_NAME% AppRotateBytes 5242880
"%NSSM_PATH%" set %SERVICE_NAME% Start SERVICE_AUTO_START
"%NSSM_PATH%" set %SERVICE_NAME% AppRestartDelay 5000

echo.
echo Starting the service...
"%NSSM_PATH%" start %SERVICE_NAME%

echo.
echo Done. Check status with:  nssm status %SERVICE_NAME%
echo Stop it with:             nssm stop %SERVICE_NAME%
echo Uninstall it with:        nssm remove %SERVICE_NAME% confirm
echo Logs are in:              %APP_DIR%\deploy\service_stdout.log / service_stderr.log
echo.
pause
