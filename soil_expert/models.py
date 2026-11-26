"""Модели данных экспертной системы «Мониторинг состояния почвы и растений»."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


class InputError(ValueError):
    """Ошибка входных данных, которую нужно показать пользователю."""


@dataclass(frozen=True)
class Symptom:
    id: str
    name: str
    severity: str


@dataclass(frozen=True)
class Species:
    id: str
    name: str
    humidity_min: float
    humidity_max: float
    ph_min: float
    ph_max: float
    temp_min: float
    temp_max: float


@dataclass(frozen=True)
class SoilCondition:
    id: str
    indicator: str      # влажность | pH | температура | подкормки
    relation: str       # нижеНормы | вышеНормы | входитВ
    value: str          # для «входитВ»: допустимые значения через «;»
    description: str


@dataclass
class Cause:
    id: str
    name: str
    recommendation: str
    chronic: bool
    key_symptoms: set[str] = field(default_factory=set)
    symptoms: set[str] = field(default_factory=set)        # все характерные (включая ключевые)
    conditions: list[SoilCondition] = field(default_factory=list)


@dataclass
class Observation:
    """Данные, введённые пользователем на форме."""
    species_id: str
    symptoms: set[str]
    humidity: Optional[float] = None
    ph: Optional[float] = None
    temperature: Optional[float] = None
    feeding: Optional[str] = None
    days: int = 0


@dataclass
class ConditionCheck:
    condition: SoilCondition
    status: Optional[bool]   # True — выполнено, False — не выполнено, None — показатель не задан
    text: str


@dataclass
class CauseAssessment:
    cause: Cause
    score: float
    verdict: str
    matched: list[str]
    missing: list[str]
    missing_key: list[str]
    checks: list[ConditionCheck]
    fired_rules: list[str]


@dataclass
class DiagnosticResult:
    observation: Observation
    assessments: list[CauseAssessment]
    warnings: list[str]
    elapsed_ms: float

    @property
    def best(self) -> Optional[CauseAssessment]:
        return self.assessments[0] if self.assessments and self.assessments[0].score > 0 else None


def parse_number(text: str, title: str, lo: float, hi: float) -> Optional[float]:
    """Преобразует текст поля в число. Пустое поле — показатель не задан (None)."""
    text = (text or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        raise InputError(f"Ошибка: поле «{title}» должно содержать число, введено: «{text}».") from None
    if not lo <= value <= hi:
        raise InputError(f"Ошибка: поле «{title}»: значение {value:g} вне допустимого диапазона {lo:g}…{hi:g}.")
    return value
