"""Автоматизированные тест-кейсы ПМИ (ЛР7): база знаний и машина вывода.

Запуск:  python -m unittest discover -s tests -v
"""
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from soil_expert.inference import HIGH, InferenceEngine  # noqa: E402
from soil_expert.knowledge_base import KnowledgeBase  # noqa: E402
from soil_expert.models import InputError, Observation, parse_number  # noqa: E402

KB = KnowledgeBase(ROOT / "resources" / "knowledge_base.owl")
ENGINE = InferenceEngine(KB)


def run(species, symptoms, hum=None, ph=None, t=None, feed=None, days=0):
    return ENGINE.run_diagnosis(Observation(species, set(symptoms), hum, ph, t, feed, days))


class EngineTests(unittest.TestCase):
    def test_tc01_water_deficit(self):
        """TC-01: Фиалка, увядание + пожелтение + сухие кончики, влажность 25 % → Дефицит влаги (высокая)."""
        r = run("Вид_Фиалка", ["Увядание", "Пожелтение_листьев", "Сухие_кончики_листьев"], 25, 6.2, 23, "регулярные", 3)
        self.assertEqual(r.best.cause.id, "Дефицит_влаги")
        self.assertEqual(r.best.verdict, HIGH)

    def test_tc02_overwatering(self):
        """TC-02: Томат, загнивание корней + пожелтение + плесень + увядание, влажность 88 % → Переувлажнение."""
        r = run("Вид_Томат", ["Загнивание_корней", "Пожелтение_листьев", "Плесень_на_почве", "Увядание"], 88, 6.4, 21, "регулярные", 5)
        self.assertEqual(r.best.cause.id, "Переувлажнение")
        self.assertEqual(r.best.verdict, HIGH)

    def test_tc03_nutrition_chronic(self):
        """TC-03: Огурец, замедление роста + пожелтение + мелкие листья, без подкормок 20 дн. → Дефицит питания, R5."""
        r = run("Вид_Огурец", ["Замедление_роста", "Пожелтение_листьев", "Мелкие_листья"], 75, 6.5, 22, "отсутствуют", 20)
        self.assertEqual(r.best.cause.id, "Дефицит_питания")
        self.assertTrue(any(x.startswith("R5") for x in r.best.fired_rules))

    def test_tc04_acidity_species_norm(self):
        """TC-04: Голубика (pH 4–5.5), межжилковый хлороз…, pH 3.6 → Повышенная кислотность."""
        r = run("Вид_Голубика", ["Межжилковый_хлороз", "Пожелтение_листьев", "Замедление_роста"], 65, 3.6, 18, "регулярные", 21)
        self.assertEqual(r.best.cause.id, "Повышенная_кислотность")
        self.assertGreaterEqual(r.best.score, 80)

    def test_tc05_pests_without_soil(self):
        """TC-05: Роза, насекомые + паутина + пятна + деформация, без показателей почвы → Вредители, R12."""
        r = run("Вид_Роза", ["Насекомые_на_растении", "Паутина_на_листьях", "Пятна_на_листьях", "Деформация_листьев"], days=4)
        self.assertEqual(r.best.cause.id, "Поражение_вредителями")
        self.assertTrue(any(w.startswith("R12") for w in r.warnings))

    def test_tc06_species_dependence(self):
        """TC-06: одинаковый pH 5.0 оценивается по-разному для томата (норма 6–7) и голубики (4–5.5)."""
        sy = ["Межжилковый_хлороз", "Пожелтение_листьев"]
        tomato = next(a for a in run("Вид_Томат", sy, ph=5.0).assessments if a.cause.id == "Повышенная_кислотность")
        blue = next(a for a in run("Вид_Голубика", sy, ph=5.0).assessments if a.cause.id == "Повышенная_кислотность")
        self.assertGreater(tomato.score, blue.score)

    def test_tc07_no_symptoms(self):
        """TC-07: ни один признак не выбран → InputError «выберите хотя бы один…»."""
        with self.assertRaises(InputError) as cm:
            run("Вид_Фиалка", [])
        self.assertIn("хотя бы один", str(cm.exception))

    def test_tc08_not_a_number(self):
        """TC-08: в поле влажности введён текст «abc» → InputError."""
        with self.assertRaises(InputError):
            parse_number("abc", "Влажность почвы", 0, 100)

    def test_tc09_boundaries(self):
        """TC-09: 150 % → ошибка диапазона; 0, 100, «6,5» (запятая) — допустимы; пусто → не задано."""
        with self.assertRaises(InputError):
            parse_number("150", "Влажность почвы", 0, 100)
        self.assertEqual(parse_number("0", "В", 0, 100), 0)
        self.assertEqual(parse_number("100", "В", 0, 100), 100)
        self.assertEqual(parse_number("6,5", "pH", 0, 14), 6.5)
        self.assertIsNone(parse_number("  ", "pH", 0, 14))

    def test_tc10_missing_key_symptom(self):
        """TC-10: только неспецифичный признак (пожелтение) → нет высокой вероятности, предупреждение R13."""
        r = run("Вид_Фикус", ["Пожелтение_листьев"])
        self.assertTrue(all(a.score < 50 for a in r.assessments))
        self.assertTrue(any(w.startswith("R13") for w in r.warnings))

    def test_tc11_alarm(self):
        """TC-11: 6 признаков, включая увядание и опадание листьев → предупреждение R11 (обратиться к агроному)."""
        r = run("Вид_Фиалка", ["Увядание", "Пожелтение_листьев", "Пятна_на_листьях", "Опадание_листьев",
                               "Замедление_роста", "Потемнение_листьев"], 55, 6, 20, "регулярные", 7)
        self.assertTrue(any(w.startswith("R11") for w in r.warnings))

    def test_tc14_performance(self):
        """TC-14: время вывода не более 1 с (проверка на 100 запусках)."""
        t0 = time.perf_counter()
        for _ in range(100):
            r = run("Вид_Томат", ["Загнивание_корней", "Пожелтение_листьев"], 88, 6.4, 21, "регулярные", 5)
        worst = (time.perf_counter() - t0) / 100
        self.assertLess(worst, 1.0)
        self.assertLess(r.elapsed_ms, 1000)

    def test_tc15_kb_loading(self):
        """TC-15: БЗ загружена полностью (10 причин, 20 признаков, 10 видов); отсутствие файла → FileNotFoundError."""
        self.assertEqual((len(KB.causes), len(KB.symptoms), len(KB.species)), (10, 20, 10))
        with self.assertRaises(FileNotFoundError):
            KnowledgeBase(ROOT / "resources" / "missing.owl")


if __name__ == "__main__":
    unittest.main(verbosity=2)
