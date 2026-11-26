"""Точка входа: ЭС «Мониторинг состояния почвы и растений».

Запуск:  python main.py
"""
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from soil_expert.gui import MainWindow
from soil_expert.inference import InferenceEngine
from soil_expert.knowledge_base import KnowledgeBase


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))   # поддержка PyInstaller
    return base / "resources" / name


def main():
    root = tk.Tk()
    try:
        kb = KnowledgeBase(resource_path("knowledge_base.owl"))
    except Exception as err:                       # файл БЗ отсутствует или повреждён
        root.withdraw()
        messagebox.showerror("Ошибка загрузки базы знаний", str(err))
        return 1
    MainWindow(root, InferenceEngine(kb))
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
