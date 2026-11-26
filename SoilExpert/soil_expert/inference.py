"""Модуль «Машина вывода»: сопоставление наблюдений с профилями причин.

Правила (из ЛР2, формализованы в ЛР3–ЛР5):
  R1  все ключевые признаки причины присутствуют            → +20 %
  R2  за долю совпавших характерных признаков                → до 50 % (до 80 %, если у причины нет условий почвы)
  R3  условие по показателю почвы выполнено                  → +30 % (делится между условиями причины)
  R4  условие по показателю почвы задано, но не выполнено     → −10 %
  R5  причина хроническая и признаки наблюдаются ≥ 14 дней    → +10 %
  R6  отсутствует ключевой признак причины                   → −30 %
  R7  нет ни одного признака причины                         → 0 %
  R8–R10  ≥ 80 % «Высокая», 50–79 % «Средняя», < 50 % «Низкая» вероятность
  R11 массовое поражение (увядание + опадание листьев или ≥ 6 признаков) → «Обратитесь к агроному»
  R12 есть пятна на листьях                                  → проверить на вредителей и болезни
  R13 итог < 30 %                                            → «Маловероятно»
"""
from __future__ import annotations

import time

from .knowledge_base import KnowledgeBase
from .models import (Cause, CauseAssessment, ConditionCheck, DiagnosticResult,
                     InputError, Observation)

HIGH, MEDIUM, LOW, UNLIKELY = ("Высокая вероятность", "Средняя вероятность",
                               "Низкая вероятность", "Маловероятно")
CHRONIC_DAYS = 14


def verdict_for(score: float) -> str:
    if score >= 80:
        return HIGH
    if score >= 50:
        return MEDIUM
    if score >= 30:
        return LOW
    return UNLIKELY


class InferenceEngine:
    """«Мост» между интерфейсом и базой знаний. GUI вызывает только run_diagnosis()."""

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    # ---------- публичный метод ----------
    def run_diagnosis(self, obs: Observation) -> DiagnosticResult:
        started = time.perf_counter()
        self._validate(obs)
        candidates = self.kb.candidate_causes(obs.symptoms)        # SPARQL-запрос к онтологии
        assessments = [self._assess(cause, obs, cause.id in candidates)
                       for cause in self.kb.causes.values()]
        assessments.sort(key=lambda a: (-a.score, a.cause.name))
        warnings = self._global_rules(obs, assessments)
        elapsed = (time.perf_counter() - started) * 1000
        return DiagnosticResult(obs, assessments, warnings, elapsed)

    # ---------- проверка ввода ----------
    def _validate(self, obs: Observation) -> None:
        if obs.species_id not in self.kb.species:
            raise InputError("Ошибка: выберите вид растения из списка.")
        if not obs.symptoms:
            raise InputError("Ошибка: выберите хотя бы один внешний признак растения.")
        unknown = obs.symptoms - set(self.kb.symptoms)
        if unknown:
            raise InputError(f"Ошибка: неизвестные признаки: {', '.join(sorted(unknown))}.")
        if obs.days < 0 or obs.days > 365:
            raise InputError("Ошибка: давность признаков должна быть от 0 до 365 дней.")

    # ---------- оценка одной причины ----------
    def _assess(self, cause: Cause, obs: Observation, is_candidate: bool) -> CauseAssessment:
        name = lambda ids: [self.kb.symptoms[i].name for i in sorted(ids)]
        matched = cause.symptoms & obs.symptoms
        missing = cause.symptoms - obs.symptoms
        missing_key = cause.key_symptoms - obs.symptoms
        checks = [self._check(c, obs) for c in cause.conditions]
        rules: list[str] = []

        if not is_candidate or not matched:
            rules.append("R7: ни один характерный признак не наблюдается → 0 %")
            return CauseAssessment(cause, 0.0, UNLIKELY, [], name(missing), name(missing_key), checks, rules)

        weight = 50.0 if cause.conditions else 80.0
        score = weight * len(matched) / len(cause.symptoms)
        rules.append(f"R2: совпало {len(matched)} из {len(cause.symptoms)} признаков → +{score:.0f} %")

        if missing_key:
            score -= 30
            rules.append("R6: отсутствует ключевой признак → −30 %")
        else:
            score += 20
            rules.append("R1: все ключевые признаки присутствуют → +20 %")

        if cause.conditions:
            part = 30.0 / len(cause.conditions)
            for chk in checks:
                if chk.status is True:
                    score += part
                    rules.append(f"R3: {chk.condition.description} → +{part:.0f} %")
                elif chk.status is False:
                    score -= 10
                    rules.append(f"R4: не выполнено условие «{chk.condition.description}» → −10 %")

        if cause.chronic and obs.days >= CHRONIC_DAYS:
            score += 10
            rules.append(f"R5: хроническая причина, признаки {obs.days} дн. → +10 %")

        score = max(0.0, min(100.0, round(score, 1)))
        verdict = verdict_for(score)
        rules.append(f"Итог: {score:.0f} % — {verdict}")
        return CauseAssessment(cause, score, verdict, name(matched), name(missing), name(missing_key), checks, rules)

    def _check(self, cond, obs: Observation) -> ConditionCheck:
        sp = self.kb.species[obs.species_id]
        ranges = {"влажность": (obs.humidity, sp.humidity_min, sp.humidity_max, "%"),
                  "pH": (obs.ph, sp.ph_min, sp.ph_max, ""),
                  "температура": (obs.temperature, sp.temp_min, sp.temp_max, " °C")}
        if cond.indicator == "подкормки":
            if not obs.feeding:
                return ConditionCheck(cond, None, "подкормки не указаны")
            allowed = [v for v in cond.value.split(";") if v]
            ok = obs.feeding in allowed
            return ConditionCheck(cond, ok, f"подкормки: {obs.feeding}")
        value, lo, hi, unit = ranges[cond.indicator]
        if value is None:
            return ConditionCheck(cond, None, f"{cond.indicator}: не задано")
        ok = value < lo if cond.relation == "нижеНормы" else value > hi
        return ConditionCheck(cond, ok, f"{cond.indicator} = {value:g}{unit} (норма {lo:g}–{hi:g}{unit})")

    # ---------- общие правила ----------
    def _global_rules(self, obs: Observation, assessments: list[CauseAssessment]) -> list[str]:
        w: list[str] = []
        s = obs.symptoms
        if ({"Увядание", "Опадание_листьев"} <= s) or len(s) >= 6:
            w.append("R11: признаки массового поражения растения — рекомендуется обратиться к агроному.")
        if "Пятна_на_листьях" in s:
            w.append("R12: на листьях есть пятна — осмотрите растение на вредителей и болезни "
                     "(особенно нижнюю сторону листьев).")
        if not assessments or assessments[0].score < 30:
            w.append("R13: однозначная причина не установлена (все причины маловероятны). "
                     "Уточните признаки и показатели почвы.")
        sp = self.kb.species[obs.species_id]
        out = []
        if obs.humidity is not None and not sp.humidity_min <= obs.humidity <= sp.humidity_max:
            out.append(f"влажность {obs.humidity:g}% (норма {sp.humidity_min:g}–{sp.humidity_max:g}%)")
        if obs.ph is not None and not sp.ph_min <= obs.ph <= sp.ph_max:
            out.append(f"pH {obs.ph:g} (норма {sp.ph_min:g}–{sp.ph_max:g})")
        if obs.temperature is not None and not sp.temp_min <= obs.temperature <= sp.temp_max:
            out.append(f"температура {obs.temperature:g} °C (норма {sp.temp_min:g}–{sp.temp_max:g} °C)")
        if out:
            w.append(f"Показатели вне нормы для вида «{sp.name}»: " + "; ".join(out) + ".")
        return w
