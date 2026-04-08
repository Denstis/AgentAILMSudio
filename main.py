#!/usr/bin/env python3
"""
LM Agent - Main Entry Point

Точка входа для запуска LM Agent с модульной архитектурой.
Поддерживает режимы: GUI, CLI, проверка системы
"""

import sys
import argparse
from pathlib import Path


def check_system():
    """Проверить систему и зависимости."""
    print("=" * 60)
    print("LM Agent - Проверка системы")
    print("=" * 60)
    
    # Проверка Python версии
    print(f"\n[✓] Python версия: {sys.version}")
    
    # Проверка импортов модулей
    try:
        from lm_agent import __version__
        print(f"[✓] LM Agent версия: {__version__}")
    except ImportError as e:
        print(f"[✗] Ошибка импорта lm_agent: {e}")
        return False
    
    # Проверка core модулей
    try:
        from lm_agent.core import AgentConfig, ModelInfo
        print("[✓] Core модули загружены")
    except ImportError as e:
        print(f"[✗] Ошибка импорта core: {e}")
        return False
    
    # Проверка tools модулей
    try:
        from lm_agent.tools import BaseTool, FileSearchTool
        print("[✓] Tools модули загружены")
    except ImportError as e:
        print(f"[✗] Ошибка импорта tools: {e}")
        return False
    
    # Проверка sandbox модулей
    try:
        from lm_agent.sandbox import ValidationResult, safe_path
        print("[✓] Sandbox модули загружены")
    except ImportError as e:
        print(f"[✗] Ошибка импорта sandbox: {e}")
        return False
    
    # Проверка utils модулей
    try:
        from lm_agent.utils.logging import setup_logging
        print("[✓] Utils модули загружены")
    except ImportError as e:
        print(f"[✗] Ошибка импорта utils: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("Все проверки пройдены успешно!")
    print("=" * 60)
    return True


def run_cli_mode():
    """Запустить в CLI режиме."""
    from lm_agent.utils.logging import setup_logging
    
    logger = setup_logging()
    logger.info("Запуск LM Agent в CLI режиме")
    
    print("\n" + "=" * 60)
    print("LM Agent - CLI Режим")
    print("=" * 60)
    print("\nВведите задачу для агента (или 'exit' для выхода):")
    
    while True:
        try:
            task = input("\n> ").strip()
            if task.lower() in ('exit', 'quit', 'q'):
                print("Выход из LM Agent")
                break
            
            if not task:
                continue
            
            logger.info(f"Получена задача: {task}")
            print("\n[INFO] Задача принята. Обработка...")
            # Здесь будет интеграция с агентом
            print("[TODO] Интеграция с LLM агентом в разработке")
            
        except KeyboardInterrupt:
            print("\n\nПрервано пользователем")
            break
        except EOFError:
            break


def run_gui_mode():
    """Запустить в GUI режиме."""
    print("\n" + "=" * 60)
    print("LM Agent - GUI Режим")
    print("=" * 60)
    
    try:
        import tkinter as tk
        print("[✓] Tkinter доступен")
    except ImportError:
        print("[✗] Tkinter не доступен. Установите python3-tk")
        return False
    
    # Запуск полноценного GUI
    from lm_agent.gui.app import run_gui
    run_gui()
    
    return True


def main():
    """Основная функция запуска."""
    parser = argparse.ArgumentParser(
        description="LM Agent - Интеллектуальный агент для генерации кода",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python main.py --check     Проверка системы и зависимостей
  python main.py --cli       Запуск в CLI режиме
  python main.py --gui       Запуск в GUI режиме (по умолчанию)
        """
    )
    
    parser.add_argument(
        '--check',
        action='store_true',
        help='Проверить систему и зависимости'
    )
    
    parser.add_argument(
        '--cli',
        action='store_true',
        help='Запустить в CLI режиме'
    )
    
    parser.add_argument(
        '--gui',
        action='store_true',
        help='Запустить в GUI режиме'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'LM Agent v{__import__("lm_agent").__version__}'
    )
    
    args = parser.parse_args()
    
    # Если аргументы не указаны, показать справку
    if len(sys.argv) == 1:
        parser.print_help()
        print("\n" + "=" * 60)
        print("Рекомендуется запустить с --check для проверки системы")
        print("=" * 60)
        return 0
    
    if args.check:
        success = check_system()
        return 0 if success else 1
    
    if args.cli:
        run_cli_mode()
        return 0
    
    if args.gui:
        success = run_gui_mode()
        return 0 if success else 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
