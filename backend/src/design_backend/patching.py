"""Deterministic application and validation of agent patches."""

from __future__ import annotations

import math

from .catalog import CATALOG
from .schemas import ConceptGraph, ConceptPatch, DesignSpec, SpecPatch

SPEC_LISTS = ("requirements", "constraints", "decisions", "parameters", "unknowns", "orientations", "loads", "positioning")
MAX_DIM_MM = 3000


def apply_spec_patch(spec: DesignSpec, patch: SpecPatch) -> DesignSpec:
    data = spec.model_dump()
    for key, value in patch.set.model_dump().items():
        if value is not None:
            data[key] = value
    for key in SPEC_LISTS:
        removed = set(getattr(patch.remove, key))
        items = {item["id"]: item for item in data[key] if item["id"] not in removed}
        for item in getattr(patch.upsert, key):
            items[item.id] = item.model_dump()
        data[key] = list(items.values())
    return DesignSpec.model_validate(data)


def apply_concept_patch(concept: ConceptGraph, patch: ConceptPatch) -> ConceptGraph:
    removed = set(patch.remove)
    refs = {c.id: c for c in concept.references if c.id not in removed}
    comps = {c.id: c for c in concept.components if c.id not in removed}
    # Route by catalog category, whichever list the model put the component in.
    for c in [*patch.upsert_references, *patch.upsert_components]:
        is_ref = CATALOG.get(c.type, {}).get("category") == "reference"
        if is_ref:
            refs[c.id] = c.model_copy(update={"role": "reference"})
            comps.pop(c.id, None)
        else:
            comps[c.id] = c
            refs.pop(c.id, None)
    return ConceptGraph(references=list(refs.values()), components=list(comps.values()))


def validate_concept(concept: ConceptGraph) -> list[str]:
    """Return a list of human-readable problems (empty = valid)."""
    errors: list[str] = []
    ids = [c.id for c in concept.references + concept.components]
    known = set(ids)
    if len(known) != len(ids):
        errors.append("identifiants de composants dupliqués")

    for c in concept.references + concept.components:
        spec = CATALOG.get(c.type)
        if spec is None:
            errors.append(f"{c.id}: type inconnu '{c.type}' (types permis : {', '.join(CATALOG)})")
            continue
        is_ref = spec["category"] == "reference"
        if is_ref != (c in concept.references):
            errors.append(f"{c.id}: un '{c.type}' doit être dans {'references' if is_ref else 'components'}")
        for field in ("parent", "wraps", "supports", "target"):
            ref = getattr(c, field)
            if ref is not None and ref not in known:
                errors.append(f"{c.id}.{field} → '{ref}' n'existe pas")
            if ref == c.id:
                errors.append(f"{c.id}.{field} pointe sur lui-même")
        if len(c.position) != 3 or len(c.rotation) != 3:
            errors.append(f"{c.id}: position et rotation doivent avoir 3 valeurs")
        for pname, value in c.params.items():
            values = value if isinstance(value, list) else [value]
            for v in values:
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if not math.isfinite(v) or abs(v) > MAX_DIM_MM:
                        errors.append(f"{c.id}.{pname} = {v} hors limites")
        if c.type in ("frame",) and c.wraps is None:
            errors.append(f"{c.id}: un 'frame' doit envelopper un ref_box via 'wraps'")
        if c.type == "stand" and c.supports is None:
            errors.append(f"{c.id}: un 'stand' doit indiquer l'objet porté via 'supports'")
        if c.type == "cutout" and c.target is None:
            errors.append(f"{c.id}: une 'cutout' doit indiquer le composant découpé via 'target'")

    # parent cycles
    parents = {c.id: c.parent for c in concept.references + concept.components}
    for start in parents:
        seen: set[str] = set()
        node: str | None = start
        while node is not None:
            if node in seen:
                errors.append(f"cycle de parenté autour de '{start}'")
                break
            seen.add(node)
            node = parents.get(node)
    return errors


def diff_concepts(before: ConceptGraph | None, after: ConceptGraph) -> dict[str, list[str]]:
    old = {c.id: c.model_dump() for c in (before.references + before.components)} if before else {}
    new = {c.id: c.model_dump() for c in after.references + after.components}
    return {
        "added": [i for i in new if i not in old],
        "removed": [i for i in old if i not in new],
        "modified": [i for i in new if i in old and new[i] != old[i]],
    }
