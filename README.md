# SoilExpert — ЭС «Мониторинг состояния почвы и растений»

Прототип экспертной системы диагностики причин отклонения состояния растений
(ЛР4–ЛР7 по дисциплине «Технологии и инструментальные средства проектирования ИС»).

## Запуск

Нужен Python 3.10+ (на Windows Tkinter входит в стандартный установщик).

```
pip install -r requirements.txt
python main.py
```

На Windows можно просто запустить `run.bat`.

## Структура

| Файл | Назначение |
|---|---|
| `main.py` | точка входа, загрузка БЗ, создание окна |
| `soil_expert/knowledge_base.py` | менеджер онтологии: rdflib + SPARQL |
| `soil_expert/inference.py` | машина вывода (правила R1–R13), метод `run_diagnosis()` |
| `soil_expert/explanation.py` | подсистема объяснения, текст заключения |
| `soil_expert/gui.py` | интерфейс Tkinter: главное окно, окно базы знаний |
| `soil_expert/models.py` | классы данных и проверка ввода |
| `resources/knowledge_base.owl` | база знаний (OWL, открывается в Protégé) |
| `tests/` | автоматические тест-кейсы ПМИ (ЛР7) |

## Тесты

```
python -m unittest discover -s tests -v
```

## Сборка .exe (по желанию, на Windows)

```
pip install pyinstaller
pyinstaller --noconsole --onefile --name SoilExpert --add-data "resources;resources" main.py
```
