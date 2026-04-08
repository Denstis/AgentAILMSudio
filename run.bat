@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo LM Agent - Модульная система v0.2.0
echo ============================================
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Python не найден! Установите Python 3.8 или выше.
    echo Скачайте с: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python найден
python --version
echo.

REM Создание виртуального окружения (если отсутствует)
if not exist "venv" (
    echo [INFO] Создание виртуального окружения...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ОШИБКА] Не удалось создать виртуальное окружение
        pause
        exit /b 1
    )
    echo [OK] Виртуальное окружение создано
) else (
    echo [OK] Виртуальное окружение уже существует
)
echo.

REM Активация виртуального окружения
echo [INFO] Активация виртуального окружения...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось активировать виртуальное окружение
    pause
    exit /b 1
)
echo [OK] Виртуальное окружение активировано
echo.

REM Обновление pip
echo [INFO] Обновление pip...
python -m pip install --upgrade pip --quiet
echo [OK] pip обновлён
echo.

REM Установка зависимостей
echo [INFO] Установка зависимостей из requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось установить зависимости
    pause
    exit /b 1
)
echo [OK] Зависимости установлены
echo.

REM Запуск тестов (опционально)
echo [INFO] Запуск юнит-тестов...
python -m pytest lm_agent/tests/ -v
if %errorlevel% neq 0 (
    echo [ПРЕДУПРЕЖДЕНИЕ] Некоторые тесты не прошли
    echo Продолжаем запуск...
) else (
    echo [OK] Все тесты пройдены
)
echo.

REM Запуск основного приложения
echo ============================================
echo Запуск LM Agent...
echo ============================================
echo.
python main.py --gui

pause
