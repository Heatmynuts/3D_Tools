"""Scripted provider for offline UI development (no API key, no cost).

It ignores the actual answers and replays a fixed "screen stand" scenario so the
whole loop (versions, diff, checkpoint, plan) can be exercised end to end.
"""

from __future__ import annotations

import json
import re
import time

from .base import LLMRequest, LLMResult

SCREEN = {
    "id": "ecran", "type": "ref_box", "label": "Écran (cotes démo)", "role": "reference",
    "params": {"size": [360, 22, 120], "tilt_deg": 0, "display_bezel": 6},
}
FRAME = {
    "id": "cadre", "type": "frame", "label": "Cadre de protection", "part": "cadre", "wraps": "ecran",
    "params": {"wall": 2.5, "front_lip": 3, "back_lip": 4, "mode": "coins", "corner_length": 30},
}
STAND = {
    "id": "support", "type": "stand", "label": "Support arrière", "part": "support", "supports": "ecran",
    "params": {"style": "cale", "width_ratio": 0.5, "support_height": 0.55},
}
SCREWS = [
    {"id": f"vis_{s}", "type": "fastener", "label": f"Vis {s}", "role": "assemblage", "parent": "ecran",
     "position": [x, 18, 60], "rotation": [-90, 0, 0], "params": {"d": 3, "length": 10}}
    for s, x in (("g", -60), ("d", 60))
]
CLIPS = [
    {"id": f"clip_{s}", "type": "clip", "label": f"Clip {s}", "role": "assemblage", "part": "support",
     "parent": "ecran", "position": [x, 13, 50], "rotation": [0, 0, 180], "params": {"length": 14, "width": 10}}
    for s, x in (("g", -60), ("d", 60))
]


def _turn(spec_patch: dict, concept_patch: dict, summary: str, nxt: dict) -> dict:
    return {"spec_patch": spec_patch, "concept_patch": concept_patch, "change_summary": summary, "next": nxt}


def _question(text: str, options: list[tuple[str, str]], why: str, target: str) -> dict:
    return {"kind": "question", "question": {
        "text": text, "why": why, "allow_other": True, "targets_unknown": target,
        "options": [{"id": i, "label": label} for i, label in options]}}


SCRIPT = [
    _turn(
        {"set": {"title": "Support protecteur d'écran", "function": "Protéger les bords d'un écran et le tenir incliné sur un bureau",
                 "context": "Bureau, usage quotidien"},
         "upsert": {
             "requirements": [{"id": "r1", "text": "Protéger les bords de l'écran"}, {"id": "r2", "text": "Tenir l'écran incliné"}],
             "parameters": [{"id": "ecran_l", "label": "Largeur écran", "value": 360, "status": "estime"}],
             "unknowns": [{"id": "u1", "topic": "Étendue de la protection", "impact": "fort", "affects": ["geometrie"]},
                          {"id": "u2", "topic": "Démontabilité", "impact": "fort", "affects": ["assemblage"]},
                          {"id": "u3", "topic": "Angle d'inclinaison", "impact": "moyen", "affects": ["geometrie"]}],
             "orientations": [{"id": "cadre", "up": "-Y", "rationale": "face avant sur le plateau : lèvres sans supports"},
                              {"id": "support", "up": "+X", "rationale": "cale imprimée sur le flanc"}],
             "positioning": [{"id": "mip_ecran", "object": "ecran", "relative_to": "cadre",
                              "liaisons": [{"type": "appui_plan", "surface": "dos de l'écran sur la lèvre arrière"},
                                           {"type": "lineaire_rectiligne", "surface": "tranche inférieure sur la paroi basse"},
                                           {"type": "ponctuelle", "surface": "tranche gauche"}],
                              "maintien": "lèvres avant et arrière du cadre, gravité"}],
             "loads": [{"id": "l1", "description": "Poids de l'écran", "target": "support", "direction": "-Z"}]}},
        {"upsert_references": [SCREEN], "upsert_components": [FRAME, STAND, *SCREWS]},
        "Première esquisse : l'écran en fantôme, quatre protège-coins et une cale arrière vissée.",
        _question("Le support doit-il protéger seulement les coins ou tout le périmètre ?",
                  [("coins", "Seulement les coins"), ("perimetre", "Tout le périmètre"), ("perimetre_dos", "Périmètre + dos")],
                  "Change la forme principale du cadre.", "u1"),
    ),
    _turn(
        {"upsert": {"decisions": [{"id": "d1", "topic": "Protection", "choice": "Tout le périmètre",
                                   "consequence": "Cadre continu sur les 4 côtés"}]},
         "remove": {"unknowns": ["u1"]}},
        {"upsert_components": [{**FRAME, "params": {**FRAME["params"], "mode": "perimetre"}}]},
        "Le cadre enveloppe maintenant les quatre côtés de l'écran au lieu des seuls coins.",
        _question("Le support doit-il pouvoir être démonté sans outil ?",
                  [("oui", "Oui, sans outil"), ("non", "Non, vissé c'est bien"), ("indiff", "Peu importe")],
                  "Détermine le principe d'assemblage cadre/support.", "u2"),
    ),
    _turn(
        {"upsert": {"decisions": [{"id": "d2", "topic": "Assemblage", "choice": "Démontable sans outil",
                                   "consequence": "Clips à la place des vis"}]},
         "remove": {"unknowns": ["u2"]}},
        {"upsert_components": CLIPS, "remove": ["vis_g", "vis_d"]},
        "Les deux vis visibles ont été remplacées par deux clips : le support se retire sans outil.",
        _question("Quelle inclinaison veux-tu pour l'écran ?",
                  [("10", "Légère (≈10°)"), ("20", "Moyenne (≈20°)"), ("30", "Forte (≈30°)")],
                  "Fixe la géométrie de la cale.", "u3"),
    ),
    _turn(
        {"upsert": {"decisions": [{"id": "d3", "topic": "Inclinaison", "choice": "≈20°"}],
                    "parameters": [{"id": "tilt", "label": "Inclinaison", "value": 20, "unit": "°", "status": "connu",
                                    "source": "utilisateur"}]},
         "remove": {"unknowns": ["u3"]}},
        {"upsert_references": [{**SCREEN, "params": {**SCREEN["params"], "tilt_deg": 20}}]},
        "L'écran est incliné à 20° et la cale s'est adaptée à ce nouvel angle.",
        {"kind": "checkpoint", "checkpoint": {
            "text": "Est-ce que cette direction correspond maintenant à ce que tu veux fabriquer ?",
            "summary": ["Cadre périphérique complet", "Support arrière démontable par clips", "Inclinaison 20°"]}},
    ),
]

PLAN = {
    "title": "Support protecteur d'écran",
    "fonction": "Protéger les quatre bords de l'écran et le maintenir incliné à 20° sur un bureau.",
    "geometrie_generale": "Cadre périphérique en U autour de l'écran, cale arrière clipsée.",
    "dimensions_connues": [{"text": "Inclinaison 20°", "status": "connu"}],
    "dimensions_a_determiner": [{"text": "Cotes exactes de l'écran (L × H × ép.)", "status": "a_determiner"}],
    "interfaces": [{"text": "Tranche et bords avant/arrière de l'écran"}],
    "materiau": "PETG envisagé (hypothèse démo)",
    "assemblages": [{"text": "2 clips entre cadre et cale"}],
    "tolerances": [{"text": "Jeu écran/cadre 0,3 mm", "status": "hypothese"}],
    "zones_fonctionnelles": [{"text": "Lèvres avant et arrière"}],
    "zones_esthetiques": [{"text": "Face avant du cadre"}],
    "contraintes_impression": [{"text": "Cadre imprimé à plat, lèvres sans supports si possible"}],
    "hypotheses": [{"text": "Scénario de démonstration : réponses non prises en compte", "status": "hypothese"}],
}


class MockProvider:
    name = "mock"
    label = ""
    model = "scenario-demo"

    def __init__(self, variant: str = "") -> None:
        # A second mock ("B") gives slightly different wording, to exercise the A/B screen offline.
        self.variant = variant
        if variant:
            self.model = f"scenario-demo-{variant.lower()}"

    def complete(self, request: LLMRequest) -> LLMResult:
        time.sleep(0.4)
        if request.kind == "plan":
            payload = PLAN
        else:
            m = re.search(r"Questions déjà posées : (\d+)", request.user)
            n = int(m.group(1)) if m else 0
            payload = SCRIPT[min(n, len(SCRIPT) - 1)]
            if self.variant:
                payload = json.loads(json.dumps(payload))
                payload["change_summary"] = "Variante : " + payload["change_summary"][0].lower() + payload["change_summary"][1:]
                q = payload["next"].get("question")
                if q:
                    q["options"] = list(reversed(q["options"]))
        return LLMResult(text=json.dumps(payload, ensure_ascii=False), model=self.model, latency_ms=400)
