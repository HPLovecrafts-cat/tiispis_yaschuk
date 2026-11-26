"""Тест-кейсы ПМИ (ЛР7) для пользовательского интерфейса. Требуют графического дисплея."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tkinter as tk  # noqa: E402

from soil_expert.gui import MainWindow  # noqa: E402
from soil_expert.inference import InferenceEngine  # noqa: E402
from soil_expert.knowledge_base import KnowledgeBase  # noqa: E402

try:
    _probe = tk.Tk(); _probe.destroy(); HAS_DISPLAY = True
except tk.TclError:
    HAS_DISPLAY = False


@unittest.skipUnless(HAS_DISPLAY, "нет графического дисплея")
class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.kb = KnowledgeBase(ROOT / "resources" / "knowledge_base.owl")
        self.w = MainWindow(self.root, InferenceEngine(self.kb))

    def tearDown(self):
        self.root.destroy()

    def test_tc07_gui_error_message(self):
        """TC-07 (GUI): без признаков нажать «Диагностировать» → сообщение об ошибке, приложение работает."""
        self.w.diagnose()
        self.assertIn("хотя бы один", self.w.text.get("1.0", "end"))
        self.assertEqual(self.w.tree.get_children(), ())

    def test_tc08_gui_not_a_number(self):
        """TC-08 (GUI): влажность «abc» → сообщение «должно содержать число»."""
        self.w.symptom_vars["Увядание"].set(True)
        self.w.hum_var.set("abc")
        self.w.diagnose()
        self.assertIn("должно содержать число", self.w.status.cget("text"))

    def test_tc12_clear(self):
        """TC-12: выбрать 3 признака, выполнить диагностику, нажать «Очистить» → всё сброшено."""
        self.w.fill_example()
        self.w.diagnose()
        self.assertEqual(len(self.w.tree.get_children()), 10)
        self.w.clear()
        self.assertFalse(any(v.get() for v in self.w.symptom_vars.values()))
        self.assertEqual((self.w.hum_var.get(), self.w.ph_var.get(), self.w.temp_var.get()), ("", "", ""))
        self.assertEqual(self.w.tree.get_children(), ())
        self.assertEqual(self.w.text.get("1.0", "end").strip(), "")

    def test_tc13_explanation(self):
        """TC-13: выбор строки таблицы показывает объяснение: совпавшие признаки, правила, рекомендацию."""
        self.w.fill_example()
        self.w.diagnose()
        self.w.tree.selection_set("Дефицит_влаги")
        self.root.update()
        txt = self.w.text.get("1.0", "end")
        for part in ("Совпавшие признаки", "Сработавшие правила", "Рекомендация", "Увядание"):
            self.assertIn(part, txt)

    def test_tc16_save_report(self):
        """TC-16: сохранение заключения в файл .txt."""
        self.w.fill_example()
        self.w.diagnose()
        path = os.path.join(tempfile.mkdtemp(), "заключение.txt")
        self.w.save_report(path)
        content = Path(path).read_text(encoding="utf-8")
        self.assertIn("ЗАКЛЮЧЕНИЕ", content)
        self.assertIn("Дефицит влаги", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
