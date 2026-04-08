"""
GUI модуль для LM Agent.

Предоставляет графический интерфейс на базе Tkinter
для управления всеми возможностями системы.
"""

from lm_agent.gui.app import LMAgentGUI, run_gui
from lm_agent.gui.components import (
    ModelSettingsFrame,
    SandboxConfigFrame,
    ToolsPanelFrame,
    TaskManagerFrame,
    ConsoleOutputFrame
)

__all__ = [
    'LMAgentGUI',
    'run_gui',
    'ModelSettingsFrame',
    'SandboxConfigFrame',
    'ToolsPanelFrame',
    'TaskManagerFrame',
    'ConsoleOutputFrame'
]
