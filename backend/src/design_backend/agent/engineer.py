"""Engineer agent: one LLM call per interview turn, deterministic patching around it."""

from __future__ import annotations

import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from ..documents import document_inputs
from ..web_sources import source_context
from ..catalog import catalog_for_prompt
from ..manufacturing import profile_for_prompt
from ..review import review, review_for_prompt, transition_problems
from ..llm import LLMError, LLMProvider, LLMRequest
from ..patching import apply_concept_patch, apply_spec_patch, diff_concepts, validate_concept
from ..schemas import AgentTurn, ConceptGraph, DesignPlan, DesignSpec, Selection
from ..store import Store

PROMPTS = Path(__file__).parent / "prompts"
ENGINEER_SYSTEM = (
    (PROMPTS / "engineer.md").read_text(encoding="utf-8")
    .replace("{catalog}", catalog_for_prompt())
    .replace("{profile}", profile_for_prompt())
)
PLAN_SYSTEM = (PROMPTS / "plan.md").read_text(encoding="utf-8")

InputKind = Literal["initial", "reponse", "remarque", "checkpoint_continuer", "checkpoint_modifier"]


class AgentError(RuntimeError):
    pass


class TransitionError(AgentError):
    pass


def _extract_json(text: str) -> Any:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("aucun objet JSON dans la réponse")
    return json.loads(text[start : end + 1])


def _transcript(store: Store, pid: str, lineage: list[dict]) -> tuple[str, int]:
    """Readable interview history along the current branch + number of questions asked."""
    lines: list[str] = []
    questions = 0
    for m in store.messages_for(pid, [v["id"] for v in lineage]):
        payload = m.get("payload") or {}
        if m["role"] == "user":
            if payload.get("web_sources"):
                lines.append(payload["web_sources"])
            if m["kind"] == "initial":
                continue
            sel = payload.get("selection")
            where = f" [sélection : {sel.get('label') or sel['component_id']} / {sel.get('zone') or '-'}]" if sel else ""
            lines.append(f"UTILISATEUR ({m['kind']}){where} : {m['text']}")
        elif m["role"] == "assistant":
            lines.append(f"MAQUETTE : {m['text']}")
            nxt = payload.get("next") or {}
            if nxt.get("kind") == "question" and nxt.get("question"):
                q = nxt["question"]
                opts = " | ".join(o["label"] for o in q.get("options", []))
                lines.append(f"INGÉNIEUR (question) : {q['text']}  [options : {opts}]")
                questions += 1
            elif nxt.get("kind") == "checkpoint":
                lines.append("INGÉNIEUR (checkpoint) : proposition de valider la direction du concept")
        elif m["role"] == "event":
            lines.append(f"ÉVÉNEMENT : {m['text']}")
    return "\n".join(lines) or "(aucun échange pour l'instant)", questions


@dataclass
class _Stats:
    turn_id: str | None = None
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    models: list[str] = field(default_factory=list)


@dataclass
class _Context:
    project: dict
    head: dict | None
    spec: DesignSpec
    concept: ConceptGraph
    user: str
    sources: str = ""


class EngineerAgent:
    """Model A is the reference agent; an optional model B (OpenRouter) can answer
    the very same prompt in parallel so the user can compare and keep one."""

    def __init__(self, store: Store, provider_a: LLMProvider) -> None:
        self.store = store
        self.provider_a = provider_a

    # ------------------------------------------------------------ LLM plumbing

    def _call(self, pid: str, provider: LLMProvider, kind: str, system: str, user: str, stats: _Stats) -> str:
        document_text, images = document_inputs(user)
        try:
            result = provider.complete(LLMRequest(kind=kind, system=system + "\nRéponds avec un JSON compact. Évite de recopier les données inchangées dans les patches. Limite le résumé à trois phrases et pose une seule question utile.", user=user + document_text, images=images))  # type: ignore[arg-type]
        except LLMError as e:
            self.store.log_llm_call(pid, kind, provider.name, provider.model, ok=False, error=str(e),
                                    turn_id=stats.turn_id)
            raise AgentError(str(e)) from e
        self.store.log_llm_call(
            pid, kind, provider.name, result.model, ok=True, latency_ms=result.latency_ms,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens, response_text=result.text,
            turn_id=stats.turn_id, cost_usd=result.cost_usd, cost_is_estimate=result.cost_is_estimate,
            cache_read_tokens=result.cache_read_tokens, cache_write_tokens=result.cache_write_tokens,
        )
        stats.latency_ms += result.latency_ms
        stats.input_tokens += result.input_tokens or 0
        stats.output_tokens += result.output_tokens or 0
        stats.models.append(result.model)
        return result.text

    def _structured(self, pid: str, provider: LLMProvider, kind: str, system: str, user: str,
                    model: type[BaseModel], stats: _Stats, check=None):
        """Call, parse, validate; on failure send the errors back once for repair."""
        text = self._call(pid, provider, kind, system, user, stats)
        for attempt in range(2):
            try:
                obj = model.model_validate(_extract_json(text))
                problems = check(obj) if check else []
                if not problems:
                    return obj
                error = "; ".join(problems)
            except (ValueError, ValidationError) as e:
                error = str(e)[:2000]
            if attempt == 1:
                raise AgentError(f"Réponse de {provider.label} inexploitable après réparation : {error[:300]}")
            repair = (
                f"{user}\n\n# CORRECTION REQUISE\nTa réponse précédente était invalide :\n{error}\n\n"
                f"Réponse précédente :\n{text}\n\nRenvoie l'objet JSON complet corrigé, sans texte autour."
            )
            text = self._call(pid, provider, "repair", system, repair, stats)
        raise AssertionError("unreachable")

    # ------------------------------------------------------------ interview turn

    def _context(self, pid: str, input_kind: InputKind, text: str, selection: Selection | None,
                 head_id: str | None = None) -> _Context:
        project = self.store.get_project(pid)
        if project is None:
            raise AgentError("projet introuvable")
        head_id = head_id or project["head_version_id"]
        head = self.store.get_version(head_id) if head_id else None
        lineage = self.store.lineage(head["id"]) if head else []
        spec = DesignSpec.model_validate(head["spec"]) if head else DesignSpec()
        concept = ConceptGraph.model_validate(head["concept"]) if head else ConceptGraph()
        history, n_questions = _transcript(self.store, pid, lineage)
        sel_text = "aucune"
        if selection:
            sel_text = (f"composant `{selection.component_id}` ({selection.label or ''}), zone `{selection.zone or '-'}`"
                        + (f", point {[round(v, 1) for v in selection.point]}" if selection.point else ""))
        user = "\n\n".join([
            f"# Demande initiale\n{project['initial_prompt']}",
            f"# Historique de l'entretien\n{history}",
            f"# DesignSpec actuel\n{spec.model_dump_json(indent=1)}",
            f"# ConceptGraph actuel ({head['label'] if head else 'vide — crée la V0'})\n{concept.model_dump_json(indent=1, exclude_none=True)}",
            f"# Revue technique automatique ({head['label'] if head else 'aucune version'})\n"
            + (review_for_prompt(review(spec, concept)) if head else "Pas encore de maquette."),
            f"# Nouvelle entrée\ntype : {input_kind}\ntexte : {text}\nsélection : {sel_text}",
            f"# Compteur\nQuestions déjà posées : {n_questions}",
        ])
        sources = source_context(text + '\n' + project['initial_prompt'] + '\n' + history)
        user += sources
        return _Context(project, head, spec, concept, user, sources)

    def _propose(self, pid: str, ctx: _Context, provider: LLMProvider, turn_id: str) -> dict:
        """One model's answer to the turn, fully validated, nothing persisted."""
        def check(turn: AgentTurn) -> list[str]:
            new_concept = apply_concept_patch(ctx.concept, turn.concept_patch)
            new_spec = apply_spec_patch(ctx.spec, turn.spec_patch)
            problems = validate_concept(new_concept)
            if turn.next.kind == "checkpoint":
                problems.extend(transition_problems(new_spec, new_concept))
            if turn.next.kind == "question":
                q = turn.next.question
                if q is None:
                    problems.append("next.kind = question mais next.question absent")
                elif not 2 <= len(q.options) <= 5:
                    problems.append("une question doit proposer 2 à 5 options")
            elif turn.next.checkpoint is None:
                problems.append("next.kind = checkpoint mais next.checkpoint absent")
            if not new_concept.components:
                problems.append("la maquette doit contenir au moins un composant de conception")
            return problems

        stats = _Stats(turn_id=turn_id)
        turn: AgentTurn = self._structured(pid, provider, "interview", ENGINEER_SYSTEM, ctx.user, AgentTurn, stats, check)
        new_spec = apply_spec_patch(ctx.spec, turn.spec_patch)
        new_concept = apply_concept_patch(ctx.concept, turn.concept_patch)
        return {
            "turn": turn.model_dump(),
            "spec": new_spec.model_dump(),
            "concept": new_concept.model_dump(),
            "diff": diff_concepts(ctx.concept if ctx.head else None, new_concept),
            "model": stats.models[-1] if stats.models else provider.model,
            "latency_ms": stats.latency_ms,
            "input_tokens": stats.input_tokens,
            "output_tokens": stats.output_tokens,
        }

    def _commit(self, pid: str, ctx: _Context, cand: dict, author: str, input_kind: str, text: str,
                selection: Selection | None, option_id: str | None, turn_id: str,
                move_head: bool = True, branch: str | None = None) -> dict:
        turn = AgentTurn.model_validate(cand["turn"])
        if turn.next.kind == "checkpoint":
            problems = transition_problems(DesignSpec.model_validate(cand["spec"]), ConceptGraph.model_validate(cand["concept"]))
            if problems:
                raise TransitionError("Validation du concept impossible : " + "; ".join(problems))
        version = self.store.add_version(
            pid, ctx.head["id"] if ctx.head else None, "concept", cand["spec"], cand["concept"],
            change_summary=turn.change_summary, next_step=turn.next.model_dump(), diff=cand["diff"], author=author,
            turn_id=turn_id, move_head=move_head, branch=branch,
        )
        title = cand["spec"].get("title")
        if title and title != ctx.project["title"]:
            self.store.update_project(pid, title=title)
        user_payload: dict[str, Any] = {}
        if ctx.sources:
            user_payload["web_sources"] = ctx.sources
        if selection:
            user_payload["selection"] = selection.model_dump()
        if option_id:
            user_payload["option_id"] = option_id
        self.store.add_message(pid, version["id"], "user", input_kind, text, user_payload or None)
        self.store.add_message(pid, version["id"], "assistant", "turn", turn.change_summary,
                               {"next": turn.next.model_dump(), "author": author})
        return version

    def run_turn(self, pid: str, input_kind: InputKind, text: str,
                 selection: Selection | None = None, option_id: str | None = None) -> dict:
        ctx = self._context(pid, input_kind, text, selection)
        turn_id = uuid.uuid4().hex[:12]
        cand = self._propose(pid, ctx, self.provider_a, turn_id)
        return self._commit(pid, ctx, cand, self.provider_a.label, input_kind, text, selection, option_id, turn_id)

    # ------------------------------------------------------------ A/B comparison

    def run_ab(self, pid: str, provider_b: LLMProvider, input_kind: InputKind, text: str,
               selection: Selection | None = None, option_id: str | None = None) -> str:
        """Both models answer the same context in parallel; results are stored as a
        pending batch until the user keeps one. Returns the batch id."""
        ctx = self._context(pid, input_kind, text, selection)
        batch_id = uuid.uuid4().hex[:12]
        slots = [("A", self.provider_a), ("B", provider_b)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self._propose, pid, ctx, p, batch_id) for _, p in slots]
        results: list[dict | AgentError] = []
        for f in futures:
            try:
                results.append(f.result())
            except AgentError as e:
                results.append(e)
        if all(isinstance(r, AgentError) for r in results):
            raise AgentError(" · ".join(f"{p.label} : {r}" for (_, p), r in zip(slots, results)))
        payload = {"kind": input_kind, "text": text, "option_id": option_id,
                   "selection": selection.model_dump() if selection else None}
        for pos, ((slot, provider), res) in enumerate(zip(slots, results)):
            ok = not isinstance(res, AgentError)
            self.store.add_candidate(
                id=uuid.uuid4().hex[:12], batch_id=batch_id, project_id=pid,
                parent_version_id=ctx.head["id"] if ctx.head else None,
                slot=slot, label=provider.label, model=res["model"] if ok else provider.model, position=pos,
                ok=int(ok), error=None if ok else str(res),
                turn=res["turn"] if ok else None, spec=res["spec"] if ok else None,
                concept=res["concept"] if ok else None, diff=res["diff"] if ok else None,
                input=payload, requested_model=provider.model,
                latency_ms=res["latency_ms"] if ok else None,
                input_tokens=res["input_tokens"] if ok else None,
                output_tokens=res["output_tokens"] if ok else None,
            )
        return batch_id

    def choose(self, pid: str, candidate_id: str) -> dict:
        cand = self.store.get_candidate(candidate_id)
        if cand is None or cand["project_id"] != pid:
            raise AgentError("proposition introuvable")
        if not cand["ok"]:
            raise AgentError("cette proposition a échoué, elle ne peut pas être retenue")
        project = self.store.get_project(pid)
        if project is None or project["head_version_id"] != cand["parent_version_id"]:
            raise AgentError("la version courante a changé depuis ces propositions")
        inp = cand["input"]
        selection = Selection.model_validate(inp["selection"]) if inp.get("selection") else None
        ctx = self._context(pid, inp["kind"], inp["text"], selection)
        version = self._commit(pid, ctx, cand, cand["label"], inp["kind"], inp["text"], selection, inp.get("option_id"),
                               cand["batch_id"])
        self.store.mark_chosen(candidate_id)
        return version

    # ------------------------------------------------------------ parallel threads

    def start_parallel(self, pid: str, batch_id: str) -> list[dict]:
        """Both proposals of an A/B turn become versions on their own branch and each
        model then follows its own thread. Returns the created tracks."""
        batch = [c for c in self.store.pending_batch(pid, self.store.get_project(pid)["head_version_id"])
                 if c["batch_id"] == batch_id]
        if len(batch) < 2 or not all(c["ok"] for c in batch):
            raise AgentError("les deux propositions doivent être valides pour les poursuivre en parallèle")
        if self.store.open_tracks(pid):
            raise AgentError("une comparaison en parallèle est déjà en cours")
        tracks = []
        for cand in batch:
            inp = cand["input"]
            selection = Selection.model_validate(inp["selection"]) if inp.get("selection") else None
            ctx = self._context(pid, inp["kind"], inp["text"], selection, head_id=cand["parent_version_id"])
            version = self._commit(pid, ctx, cand, cand["label"], inp["kind"], inp["text"], selection,
                                   inp.get("option_id"), batch_id, move_head=False, branch=cand["label"])
            tid = self.store.add_track(pid, cand["slot"], cand["label"], cand.get("requested_model") or cand["model"],
                                       cand["parent_version_id"], version["id"])
            tracks.append(self.store.get_track(tid))
        self.store.mark_batch_parallel(batch_id)
        return tracks

    def track_turn(self, pid: str, track_id: str, provider: LLMProvider, input_kind: InputKind, text: str,
                   selection: Selection | None = None, option_id: str | None = None) -> dict:
        track = self.store.get_track(track_id)
        if track is None or track["project_id"] != pid or track["status"] != "open":
            raise AgentError("fil de conception introuvable ou terminé")
        ctx = self._context(pid, input_kind, text, selection, head_id=track["head_version_id"])
        turn_id = uuid.uuid4().hex[:12]
        cand = self._propose(pid, ctx, provider, turn_id)
        version = self._commit(pid, ctx, cand, track["label"], input_kind, text, selection, option_id, turn_id,
                               move_head=False, branch=track["label"])
        self.store.set_track_head(track_id, version["id"])
        return version

    def choose_track(self, pid: str, track_id: str) -> None:
        track = self.store.get_track(track_id)
        if track is None or track["project_id"] != pid or track["status"] != "open":
            raise AgentError("fil de conception introuvable ou terminé")
        self.store.update_project(pid, head_version_id=track["head_version_id"], branch=track["label"])
        self.store.close_tracks(pid, track_id)
        self.store.add_message(pid, track["head_version_id"], "event", "fil_retenu",
                               f"Concept de {track['label']} retenu ; l'entretien continue avec lui")

    # ------------------------------------------------------------ design plan

    def generate_plan(self, pid: str, remarks: str | None = None, provider: LLMProvider | None = None) -> dict:
        provider = provider or self.provider_a
        project = self.store.get_project(pid)
        if project is None:
            raise AgentError("projet introuvable")
        head = self.store.get_version(project["head_version_id"])
        if head is None:
            raise AgentError("aucune version de concept")
        if head["kind"] != "plan" and (head.get("next") or {}).get("kind") != "checkpoint":
            raise TransitionError("Valide d’abord la direction du concept au checkpoint.")
        problems = transition_problems(DesignSpec.model_validate(head["spec"]), ConceptGraph.model_validate(head["concept"]))
        if problems:
            raise TransitionError("Plan bloqué : " + "; ".join(problems))
        lineage = self.store.lineage(head["id"])
        history, _ = _transcript(self.store, pid, lineage)
        concept = ConceptGraph.model_validate(head["concept"])
        parts = [
            f"# Demande initiale\n{project['initial_prompt']}",
            f"# Historique de l'entretien\n{history}",
            f"# DesignSpec\n{DesignSpec.model_validate(head['spec']).model_dump_json(indent=1)}",
            f"# ConceptGraph ({head['label']})\n{concept.model_dump_json(indent=1, exclude_none=True)}",
            f"# Revue technique automatique\n{review_for_prompt(review(DesignSpec.model_validate(head['spec']), concept))}",
        ]
        if head["kind"] == "plan" and head["plan"]:
            parts.append(f"# Plan précédent\n{json.dumps(head['plan'], ensure_ascii=False, indent=1)}")
        if remarks:
            parts.append(f"# Remarques de l'utilisateur sur le plan\n{remarks}" + source_context(remarks))
        turn_id = uuid.uuid4().hex[:12]
        plan: DesignPlan = self._structured(pid, provider, "plan", PLAN_SYSTEM, "\n\n".join(parts), DesignPlan,
                                            _Stats(turn_id=turn_id))
        version = self.store.add_version(
            pid, head["id"], "plan", head["spec"], head["concept"],
            change_summary="Plan de conception rédigé" if not remarks else "Plan de conception révisé",
            diff={"added": [], "removed": [], "modified": []}, plan=plan.model_dump(), author=provider.label,
            turn_id=turn_id,
        )
        self.store.add_message(pid, version["id"], "user", "plan_demande", remarks or "Oui, passer à la conception")
        self.store.add_message(pid, version["id"], "assistant", "plan", version["change_summary"],
                               {"author": provider.label})
        return version
