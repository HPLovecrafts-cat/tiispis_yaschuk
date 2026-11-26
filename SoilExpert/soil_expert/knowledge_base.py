"""Модуль «База знаний»: загрузка OWL-онтологии и SPARQL-запросы (rdflib)."""
from __future__ import annotations

from pathlib import Path

from rdflib import Graph, Namespace

from .models import Cause, SoilCondition, Species, Symptom

NS = Namespace("http://www.semanticweb.org/soil_monitoring#")
PREFIX = "PREFIX : <http://www.semanticweb.org/soil_monitoring#>\n"


def _local(uri) -> str:
    return str(uri).split("#", 1)[1]


class KnowledgeBase:
    """Менеджер онтологии: загружает .owl в память и отдаёт объекты приложения."""

    def __init__(self, owl_path: str | Path):
        self.path = Path(owl_path)
        if not self.path.exists():
            raise FileNotFoundError(f"Файл базы знаний не найден: {self.path}")
        self.graph = Graph()
        self.graph.parse(self.path, format="xml")          # RDF/XML, сохранённый Protégé
        self.symptoms = self._load_symptoms()
        self.species = self._load_species()
        self.causes = self._load_causes()

    # ---------- загрузка справочников ----------
    def query(self, sparql: str, **bindings):
        return self.graph.query(PREFIX + sparql, initBindings=bindings or None)

    def _load_symptoms(self) -> dict[str, Symptom]:
        rows = self.query("""
            SELECT ?s ?name ?sev WHERE {
                ?s a :ПризнакРастения ; :названиеПризнака ?name .
                OPTIONAL { ?s :степеньВыраженности ?sev }
            }""")
        items = [Symptom(_local(r.s), str(r.name), str(r.sev or "")) for r in rows]
        return {s.id: s for s in sorted(items, key=lambda s: s.name)}

    def _load_species(self) -> dict[str, Species]:
        rows = self.query("""
            SELECT ?v ?name ?hmin ?hmax ?pmin ?pmax ?tmin ?tmax WHERE {
                ?v a :ВидРастения ; :названиеВида ?name ;
                   :влажностьМин ?hmin ; :влажностьМакс ?hmax ;
                   :pHМин ?pmin ; :pHМакс ?pmax ;
                   :температураМин ?tmin ; :температураМакс ?tmax .
            } ORDER BY ?name""")
        return {_local(r.v): Species(_local(r.v), str(r.name), float(r.hmin), float(r.hmax),
                                     float(r.pmin), float(r.pmax), float(r.tmin), float(r.tmax))
                for r in rows}

    def _load_causes(self) -> dict[str, Cause]:
        causes: dict[str, Cause] = {}
        for r in self.query("""
            SELECT ?c ?name ?rec ?chronic WHERE {
                ?c a :ПричинаОтклонения ; :названиеПричины ?name ; :рекомендация ?rec .
                OPTIONAL { ?c :хроническая ?chronic }
            } ORDER BY ?name"""):
            causes[_local(r.c)] = Cause(_local(r.c), str(r.name), str(r.rec),
                                        bool(r.chronic.toPython()) if r.chronic is not None else False)
        # характерные признаки (ключевойПризнак — подсвойство характеризуетсяПризнаком)
        for r in self.query("""
            SELECT ?c ?s ?key WHERE {
                ?c :характеризуетсяПризнаком ?s .
                BIND (EXISTS { ?c :ключевойПризнак ?s } AS ?key)
            }"""):
            cause = causes.get(_local(r.c))
            if cause:
                cause.symptoms.add(_local(r.s))
                if r.key.toPython():
                    cause.key_symptoms.add(_local(r.s))
        # условия по показателям почвы
        for r in self.query("""
            SELECT ?c ?u ?ind ?rel ?val ?desc WHERE {
                ?c :имеетУсловие ?u .
                ?u :показатель ?ind ; :отношение ?rel ; :описаниеУсловия ?desc .
                OPTIONAL { ?u :значение ?val }
            } ORDER BY ?u"""):
            cause = causes.get(_local(r.c))
            if cause:
                cause.conditions.append(SoilCondition(_local(r.u), str(r.ind), str(r.rel),
                                                      str(r.val or ""), str(r.desc)))
        return causes

    # ---------- основной запрос к БЗ ----------
    def candidate_causes(self, symptom_ids: set[str]) -> dict[str, int]:
        """SPARQL: причины, у которых есть хотя бы один из наблюдаемых признаков,
        и число совпавших признаков для каждой из них."""
        if not symptom_ids:
            return {}
        values = " ".join(f":{s}" for s in sorted(symptom_ids) if s in self.symptoms)
        if not values:
            return {}
        rows = self.query(f"""
            SELECT ?c (COUNT(DISTINCT ?s) AS ?n) WHERE {{
                VALUES ?s {{ {values} }}
                ?c a :ПричинаОтклонения ; :характеризуетсяПризнаком ?s .
            }} GROUP BY ?c""")
        return {_local(r.c): int(r.n) for r in rows}

    def stats(self) -> str:
        return (f"причин: {len(self.causes)}, признаков: {len(self.symptoms)}, "
                f"видов растений: {len(self.species)}, триплетов: {len(self.graph)}")
