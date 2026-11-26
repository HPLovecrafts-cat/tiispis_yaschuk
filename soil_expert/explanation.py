"""Подсистема объяснения: превращает результат вывода в понятный пользователю текст."""
from __future__ import annotations

from datetime import datetime

from .models import CauseAssessment, DiagnosticResult


def explain(a: CauseAssessment) -> str:
    lines = [f"{a.cause.name}: {a.score:.0f} % — {a.verdict}", ""]
    lines.append("Совпавшие признаки: " + (", ".join(a.matched) if a.matched else "нет"))
    if a.missing:
        lines.append("Не наблюдаются (характерны для причины): " + ", ".join(a.missing))
    if a.missing_key:
        lines.append("Отсутствует ключевой признак: " + ", ".join(a.missing_key))
    if a.checks:
        lines.append("")
        lines.append("Проверка показателей почвы:")
        mark = {True: "✔ выполнено", False: "✘ не выполнено", None: "— не проверено"}
        for c in a.checks:
            lines.append(f"  • {c.condition.description}: {mark[c.status]} ({c.text})")
    lines.append("")
    lines.append("Сработавшие правила:")
    lines += [f"  {r}" for r in a.fired_rules]
    lines.append("")
    lines.append("Рекомендация: " + a.cause.recommendation)
    return "\n".join(lines)


def full_report(result: DiagnosticResult, species_name: str, symptom_names: list[str]) -> str:
    o = result.observation
    fmt = lambda v, u="": "не задано" if v is None else f"{v:g}{u}"
    lines = [
        "ЗАКЛЮЧЕНИЕ ЭКСПЕРТНОЙ СИСТЕМЫ «МОНИТОРИНГ СОСТОЯНИЯ ПОЧВЫ И РАСТЕНИЙ»",
        f"Дата: {datetime.now():%d.%m.%Y %H:%M}",
        "",
        f"Вид растения: {species_name}",
        "Признаки: " + ", ".join(symptom_names),
        f"Влажность почвы: {fmt(o.humidity, ' %')}; pH: {fmt(o.ph)}; "
        f"температура: {fmt(o.temperature, ' °C')}; подкормки: {o.feeding or 'не указаны'}; "
        f"давность признаков: {o.days} дн.",
        "",
        "РАНЖИРОВАННЫЙ СПИСОК ПРИЧИН:",
    ]
    for i, a in enumerate(result.assessments, 1):
        lines.append(f"{i:2}. {a.cause.name:<40} {a.score:5.0f} %  {a.verdict}")
    if result.warnings:
        lines += ["", "ПРЕДУПРЕЖДЕНИЯ:"] + [f"  • {w}" for w in result.warnings]
    best = result.best
    if best:
        lines += ["", "ОБЪЯСНЕНИЕ НАИБОЛЕЕ ВЕРОЯТНОЙ ПРИЧИНЫ:", explain(best)]
    return "\n".join(lines) + "\n"
