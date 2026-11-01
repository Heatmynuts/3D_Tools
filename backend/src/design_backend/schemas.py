"""Structured state shared by the engineer agent, the store and the frontend.

The LLM never produces geometry: it emits patches on DesignSpec and ConceptGraph.
The frontend ConceptBuilder turns ConceptGraph into geometry deterministically.
"""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field, field_validator

Source = Literal["utilisateur", "document", "hypothese", "deduit"]
PrintIntent = Literal[
    "prototype_rapide",
    "test_dimensionnel",
    "test_assemblage",
    "piece_finale",
    "priorite_finition",
    "priorite_resistance",
    "priorite_temps",
]

# ---------------------------------------------------------------- DesignSpec


class Requirement(BaseModel):
    id: str
    text: str
    priority: Literal["obligatoire", "souhaitable", "optionnel"] = "obligatoire"


class Constraint(BaseModel):
    id: str
    kind: str = Field(description="dimension, materiau, assemblage, impression, environnement, esthetique…")
    text: str
    source: Source = "utilisateur"


class Decision(BaseModel):
    id: str
    topic: str
    choice: str
    consequence: str = ""


class Parameter(BaseModel):
    id: str
    label: str
    value: float | None = None
    unit: str = "mm"
    status: Literal["connu", "estime", "a_determiner"] = "a_determiner"
    source: Source = "hypothese"


class Unknown(BaseModel):
    id: str
    topic: str
    impact: Literal["fort", "moyen", "faible"] = "moyen"
    affects: list[str] = Field(default_factory=list)


Axis = Literal["+X", "-X", "+Y", "-Y", "+Z", "-Z"]

# Standard mechanical joints (NF EN ISO 3952) and the degrees of freedom each removes.
LIAISON_DOF: dict[str, int] = {
    "ponctuelle": 1,
    "lineaire_rectiligne": 2,
    "lineaire_annulaire": 2,
    "appui_plan": 3,
    "rotule": 3,
    "pivot_glissant": 4,
    "pivot": 5,
    "glissiere": 5,
    "helicoidale": 5,
    "encastrement": 6,
}
LiaisonType = Literal[
    "ponctuelle", "lineaire_rectiligne", "lineaire_annulaire", "appui_plan", "rotule",
    "pivot_glissant", "pivot", "glissiere", "helicoidale", "encastrement",
]


class PartOrientation(BaseModel):
    """How a printed part sits on the build plate: `up` is the part/world axis that
    points up during printing (layers are stacked along it)."""

    id: str = Field(description="nom de la pièce imprimée (valeur de `part`, ou id du composant)")
    up: Axis
    rationale: str = ""

    @field_validator("up", mode="before")
    @classmethod
    def _norm_axis(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip().upper()
            return v if v[:1] in "+-" else "+" + v
        return v


class LoadCase(BaseModel):
    id: str
    description: str
    target: str | None = None
    direction: str = ""
    magnitude: float | None = None
    unit: str = "N"
    source: Source = "hypothese"


def _slug(v: object) -> object:
    if not isinstance(v, str):
        return v
    import unicodedata

    s = unicodedata.normalize("NFKD", v).encode("ascii", "ignore").decode().lower().strip()
    return s.replace(" ", "_").replace("-", "_")


class Liaison(BaseModel):
    type: LiaisonType
    surface: str = ""

    @field_validator("type", mode="before")
    @classmethod
    def _norm(cls, v: object) -> object:
        return _slug(v)


class Positioning(BaseModel):
    """Mise en position (liaisons) + maintien en position of one object relative to another."""

    id: str
    object: str
    relative_to: str
    liaisons: list[Liaison] = Field(default_factory=list)
    maintien: str = ""
    note: str = ""


class DesignSpec(BaseModel):
    title: str = ""
    function: str = ""
    context: str = ""
    print_intent: PrintIntent | None = None
    requirements: list[Requirement] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
    unknowns: list[Unknown] = Field(default_factory=list)
    orientations: list[PartOrientation] = Field(default_factory=list)
    loads: list[LoadCase] = Field(default_factory=list)
    positioning: list[Positioning] = Field(default_factory=list)


# ---------------------------------------------------------------- ConceptGraph

ParamValue = Union[float, int, str, bool, list[float], list[str]]


class Component(BaseModel):
    id: str
    type: str
    label: str = ""
    role: Literal["reference", "fonctionnel", "esthetique", "assemblage"] = "fonctionnel"
    part: str | None = None
    params: dict[str, ParamValue] = Field(default_factory=dict)
    position: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    parent: str | None = None
    wraps: str | None = None
    supports: str | None = None
    target: str | None = None
    note: str | None = None

    @field_validator("role", mode="before")
    @classmethod
    def _lenient_role(cls, v: object) -> object:
        # Unknown roles are not worth a repair round-trip.
        return v if v in ("reference", "fonctionnel", "esthetique", "assemblage") else "fonctionnel"


class ConceptGraph(BaseModel):
    references: list[Component] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)


# ---------------------------------------------------------------- Agent I/O


class SpecSet(BaseModel):
    title: str | None = None
    function: str | None = None
    context: str | None = None
    print_intent: PrintIntent | None = None


class SpecUpsert(BaseModel):
    requirements: list[Requirement] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
    unknowns: list[Unknown] = Field(default_factory=list)
    orientations: list[PartOrientation] = Field(default_factory=list)
    loads: list[LoadCase] = Field(default_factory=list)
    positioning: list[Positioning] = Field(default_factory=list)


class SpecRemove(BaseModel):
    requirements: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    orientations: list[str] = Field(default_factory=list)
    loads: list[str] = Field(default_factory=list)
    positioning: list[str] = Field(default_factory=list)


class SpecPatch(BaseModel):
    set: SpecSet = Field(default_factory=SpecSet)
    upsert: SpecUpsert = Field(default_factory=SpecUpsert)
    remove: SpecRemove = Field(default_factory=SpecRemove)


class ConceptPatch(BaseModel):
    upsert_references: list[Component] = Field(default_factory=list)
    upsert_components: list[Component] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)


class Option(BaseModel):
    id: str
    label: str
    hint: str = ""


class Question(BaseModel):
    text: str
    why: str = ""
    options: list[Option] = Field(default_factory=list)
    allow_other: bool = True
    targets_unknown: str | None = None


class Checkpoint(BaseModel):
    text: str
    summary: list[str] = Field(default_factory=list)


class NextStep(BaseModel):
    kind: Literal["question", "checkpoint"]
    question: Question | None = None
    checkpoint: Checkpoint | None = None


class AgentTurn(BaseModel):
    spec_patch: SpecPatch = Field(default_factory=SpecPatch)
    concept_patch: ConceptPatch = Field(default_factory=ConceptPatch)
    change_summary: str
    next: NextStep


class Selection(BaseModel):
    component_id: str
    zone: str | None = None
    label: str | None = None
    point: list[float] | None = None


# ---------------------------------------------------------------- Design plan


class PlanItem(BaseModel):
    text: str
    status: Literal["connu", "estime", "a_determiner", "hypothese"] | None = None


class DesignPlan(BaseModel):
    title: str
    fonction: str
    geometrie_generale: str
    dimensions_connues: list[PlanItem] = Field(default_factory=list)
    dimensions_a_determiner: list[PlanItem] = Field(default_factory=list)
    interfaces: list[PlanItem] = Field(default_factory=list)
    materiau: str = ""
    contraintes: list[PlanItem] = Field(default_factory=list)
    assemblages: list[PlanItem] = Field(default_factory=list)
    tolerances: list[PlanItem] = Field(default_factory=list)
    zones_fonctionnelles: list[PlanItem] = Field(default_factory=list)
    zones_esthetiques: list[PlanItem] = Field(default_factory=list)
    contraintes_impression: list[PlanItem] = Field(default_factory=list)
    hypotheses: list[PlanItem] = Field(default_factory=list)
    orientation_impression: list[PlanItem] = Field(default_factory=list)
    cas_de_charge: list[PlanItem] = Field(default_factory=list)
    mise_en_position: list[PlanItem] = Field(default_factory=list)
    points_de_vigilance: list[PlanItem] = Field(default_factory=list)
    intention_impression: PrintIntent | None = None
