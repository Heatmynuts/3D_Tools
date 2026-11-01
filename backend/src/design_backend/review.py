"""Deterministic design review of a concept version.

The LLM declares intentions (orientation, loads, joints); these rules check them
against geometry and the official printing profile. No LLM involved here.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel

from .catalog import CATALOG
from .manufacturing import process_profile
from .schemas import LIAISON_DOF, Component, ConceptGraph, DesignSpec

Level = Literal["bloquant", "attention", "info"]

# Parameters that are material thicknesses (mm) in the catalogue.
THICKNESS_PARAMS = {
    "frame": ("wall",),
    "shell": ("wall", "floor", "lid_thickness"),
    "stand": ("thickness",),
    "rib": ("thickness",),
    "clip": ("thickness",),
    "rail_clip": ("thickness",),
}
AXES = {"+X": (1, 0, 0), "-X": (-1, 0, 0), "+Y": (0, 1, 0), "-Y": (0, -1, 0), "+Z": (0, 0, 1), "-Z": (0, 0, -1)}


class Finding(BaseModel):
    id: str
    level: Level
    rule: str
    message: str
    component: str | None = None


# ------------------------------------------------------------------ small rotation maths


def _mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _rx(t: float) -> list[list[float]]:
    c, s = math.cos(t), math.sin(t)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def _ry(t: float) -> list[list[float]]:
    c, s = math.cos(t), math.sin(t)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def _rz(t: float) -> list[list[float]]:
    c, s = math.cos(t), math.sin(t)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def _params(c: Component) -> dict:
    spec = CATALOG.get(c.type, {"params": {}})
    return {**{k: p["default"] for k, p in spec["params"].items()}, **c.params}


def _num(v: object, default: float = 0.0) -> float:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else default


class _Frames:
    """World rotation of each component, same conventions as the frontend builder
    (Euler XYZ as in three.js, ref_box tilt = lean back around X)."""

    def __init__(self, concept: ConceptGraph) -> None:
        self.by_id = {c.id: c for c in concept.references + concept.components}
        self.cache: dict[str, list[list[float]]] = {}

    def rot(self, cid: str, stack: frozenset = frozenset()) -> list[list[float]]:
        if cid in self.cache:
            return self.cache[cid]
        c = self.by_id.get(cid)
        ident = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        if c is None or cid in stack:
            return ident
        anchor = c.wraps or c.parent
        base = self.rot(anchor, stack | {cid}) if anchor and anchor in self.by_id else ident
        rx, ry, rz = (math.radians(v) for v in (c.rotation + [0, 0, 0])[:3])
        r = _mul(base, _mul(_rx(rx), _mul(_ry(ry), _rz(rz))))
        if c.type == "ref_box":
            r = _mul(r, _rx(-math.radians(_num(_params(c).get("tilt_deg")))))
        self.cache[cid] = r
        return r

    def axis(self, cid: str, local: tuple[float, float, float]) -> tuple[float, float, float]:
        r = self.rot(cid)
        return tuple(sum(r[i][j] * local[j] for j in range(3)) for i in range(3))  # type: ignore[return-value]


# ------------------------------------------------------------------ review


def review(spec: DesignSpec, concept: ConceptGraph) -> list[Finding]:
    out: list[Finding] = []
    prof = process_profile()
    pv = prof["values"]
    single = pv.get("outer_wall_line_width")
    double = prof.get("two_perimeters_mm")
    printed = [c for c in concept.components if c.type not in ("fastener", "cutout")]
    parts = sorted({c.part or c.id for c in printed})
    orientation = {o.id: o for o in spec.orientations}
    frames = _Frames(concept)

    def add(level: Level, rule: str, message: str, component: str | None = None) -> None:
        out.append(Finding(id=f"{rule}:{component or len(out)}", level=level, rule=rule, message=message,
                           component=component))

    # 1. Thicknesses vs line widths of the official profile.
    if single and double:
        for c in printed:
            p = _params(c)
            for name in THICKNESS_PARAMS.get(c.type, ()):
                t = _num(p.get(name))
                if 0 < t < single:
                    add("bloquant", "epaisseur",
                        f"{c.label or c.id} : {name} = {t} mm, inférieur à une largeur de ligne ({single} mm) — non imprimable.",
                        c.id)
                elif 0 < t < double:
                    add("attention", "epaisseur",
                        f"{c.label or c.id} : {name} = {t} mm, moins de deux lignes ({double} mm) — paroi d'une seule ligne, fragile.",
                        c.id)

    # 2. Orientation declared for every printed part.
    for part in parts:
        if part not in orientation:
            add("attention", "orientation",
                f"Pièce « {part} » : orientation d'impression non définie (elle conditionne la résistance entre couches et les supports).")

    # 3. Snap-fit clips: strain and layer direction.
    for c in concept.components:
        if c.type != "clip":
            continue
        p = _params(c)
        t, y, L = _num(p.get("thickness"), 1.6), _num(p.get("insertion_deflection"), _num(p.get("hook"), 1.2)), _num(p.get("length"), 12)
        if "insertion_deflection" not in c.params:
            add("attention", "clip_hypothese", "Déplacement d’insertion inconnu : la hauteur du crochet sert uniquement d’hypothèse illustrative au calcul.", c.id)
        if L > 0:
            strain = 1.5 * t * y / (L * L) * 100
            limit = next((prm.value for prm in spec.parameters
                          if prm.id in ("deformation_admissible", "allongement_admissible") and prm.value is not None and prm.value > 0 and prm.unit == "%" and prm.status == "connu" and prm.source in ("document", "utilisateur", "deduit")), None)
            msg = (f"{c.label or c.id} : déformation en flexion ε = 1,5·t·y/L² = {strain:.1f} % "
                   f"(t = {t} mm, crochet y = {y} mm, lame L = {L} mm ; poutre encastrée à section constante).")
            if limit is None:
                add("info", "clip_deformation", msg + " Déformation admissible du matériau non renseignée : à comparer.", c.id)
            elif strain > limit:
                add("bloquant", "clip_deformation", msg + f" Supérieure à l'admissible déclaré ({limit} %).", c.id)
        part = c.part or c.id
        o = orientation.get(part)
        if o:
            blade = frames.axis(c.id, (0, 0, 1))
            up = AXES[o.up]
            cos = abs(sum(a * b for a, b in zip(blade, up)))
            if cos > math.cos(math.radians(30)):
                add("bloquant", "couches",
                    f"{c.label or c.id} : la lame est imprimée verticalement (pièce « {part} », haut = {o.up}). "
                    "En flexion, elle travaillerait perpendiculairement aux couches, là où l'adhésion inter-couches est la plus faible. "
                    "Réoriente la pièce ou le clip pour que la lame soit dans le plan des couches.", c.id)

    # 4. Positioning: degrees of freedom and holding.
    held = {c.wraps or c.supports for c in concept.components if c.wraps or c.supports}
    declared = {pos.object for pos in spec.positioning}
    for ref in concept.references:
        if ref.id in held and ref.id not in declared:
            add("attention", "mise_en_position",
                f"{ref.label or ref.id} : mise en position par rapport à la pièce non définie (liaisons et maintien).", ref.id)
    for pos in spec.positioning:
        dof = sum(LIAISON_DOF[l.type] for l in pos.liaisons)
        detail = " + ".join(f"{l.type.replace('_', ' ')} ({LIAISON_DOF[l.type]})" for l in pos.liaisons) or "aucune liaison"
        if dof > 6:
            add("attention", "isostatisme",
                f"Mise en position de « {pos.object} » : {detail} = {dof} contraintes déclarées > 6 — redondance possible, à examiner. "
                "Les liaisons redondantes imposent des jeux ou des tolérances serrées, sinon montage forcé.", pos.object)
        elif dof < 6:
            add("attention", "isostatisme",
                f"Mise en position de « {pos.object} » : {detail} = {dof} contraintes déclarées < 6 — "
                "immobilisation non démontrée ; préciser les mobilités voulues et les appuis. Le maintien seul ne prouve pas la mise en position.", pos.object)
        if not pos.maintien.strip():
            add("attention", "maintien",
                f"« {pos.object} » : maintien en position non défini (qu'est-ce qui empêche l'objet de quitter ses appuis ?).",
                pos.object)

    # 5. Loads for functional parts.
    if any(c.role == "fonctionnel" for c in printed) and not spec.loads:
        add("attention", "charges", "Pièce fonctionnelle sans cas de charge déclaré : les efforts ne peuvent pas être vérifiés.")

    # 6. Fits built on unconfirmed dimensions.
    estimated = [prm.label for prm in spec.parameters if prm.status in ("estime", "a_determiner")]
    if estimated and any(c.wraps or c.supports for c in concept.components):
        add("attention", "cotes",
            "Ajustements construits sur des cotes non confirmées : " + ", ".join(estimated[:6])
            + ". À mesurer avant impression finale.")
    return out


def review_for_prompt(findings: list[Finding]) -> str:
    if not findings:
        return "Aucun point relevé."
    return "\n".join(f"- [{f.level.upper()}] ({f.rule}) {f.message}" for f in findings)


def transition_problems(spec: DesignSpec, concept: ConceptGraph) -> list[str]:
    """Enforced independently of model wording, on the proposed state."""
    problems = [f.message for f in review(spec, concept) if f.level == "bloquant"]
    problems.extend(f"Inconnue forte à résoudre : {u.topic}" for u in spec.unknowns if u.impact == "fort")
    return problems


def review_coverage(spec: DesignSpec, concept: ConceptGraph) -> list[dict[str, str]]:
    """Explicit coverage; 'executed' means a check ran, not mechanical approval."""
    profile = process_profile()
    thickness = any(c.type in THICKNESS_PARAMS for c in concept.components)
    clips = [c for c in concept.components if c.type == "clip"]
    oriented = {o.id for o in spec.orientations}
    def item(rule, label, status, detail):
        return {"rule": rule, "label": label, "status": status, "detail": detail}
    return [
        item("epaisseur", "Épaisseurs déclarées", "non_applicable" if not thickness else
             "execute" if profile.get("two_perimeters_mm") and profile["values"].get("outer_wall_line_width") else "donnees_manquantes",
             "Comparaison au profil installé ; aucune mesure de géométrie CAO."),
        item("orientation", "Orientations déclarées", "execute" if concept.components else "non_applicable", "Présence des orientations par pièce."),
        item("couches", "Orientation des clips", "non_applicable" if not clips else
             "execute" if all((c.part or c.id) in oriented for c in clips) else "donnees_manquantes", "Règle limitée aux clips du catalogue."),
        item("clip_deformation", "Déformation des clips", "execute" if clips else "non_applicable", "Estimation conditionnelle ; hypothèse d’insertion signalée si absente."),
        item("mise_en_position", "Appuis et maintien déclarés", "execute" if spec.positioning or concept.references else "non_applicable", "Somme déclarative ; indépendance spatiale non vérifiée."),
        item("charges", "Présence de cas de charge", "execute" if concept.components else "non_applicable", "Aucun dimensionnement en résistance."),
        item("cotes", "Cotes à confirmer", "execute", "Statuts du cahier des charges ; pas de mesure physique."),
        item("resistance", "Résistance, fatigue et essais", "non_disponible", "À valider avec données matériau, calculs adaptés et essais."),
        item("contacts", "Contacts, collisions et indépendance des appuis", "non_disponible", "Non démontrés par le contrôle déclaratif."),
    ]
