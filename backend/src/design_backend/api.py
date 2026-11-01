"""HTTP API. Endpoints are plain `def`: FastAPI runs them in a thread pool, so
the blocking LLM calls do not freeze the server."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / "backend" / ".env")

from .agent.engineer import AgentError, EngineerAgent, TransitionError  # noqa: E402
from .catalog import CATALOG  # noqa: E402
from .credits import credits as credit_report  # noqa: E402
from .manufacturing import process_profile  # noqa: E402
from .review import review, review_coverage, transition_problems  # noqa: E402
from .llm import (  # noqa: E402
    LLMError, b_available, default_b_model, get_provider_a, get_provider_b, model_label, openrouter_models,
)
from .schemas import ConceptGraph, DesignSpec, Selection  # noqa: E402
from .pipeline import Pipeline, profile_options
from .store import Store  # noqa: E402

store = Store(Path(os.getenv("DATA_DIR", ROOT / "data")) / "projects.sqlite3")
provider = get_provider_a()
agent = EngineerAgent(store, provider)
pipeline = Pipeline(store, agent, Path(os.getenv("DATA_DIR", ROOT / "data")) / "artifacts")

app = FastAPI(title="3D_Tool — conception mécanique assistée")


def _phase(head: dict | None) -> str:
    if head is None:
        return "vide"
    if head["kind"] == "plan":
        return "plan_valide" if head["validated"] else "plan_revue"
    nxt = head.get("next") or {}
    return "checkpoint" if nxt.get("kind") == "checkpoint" else "entretien"


def _review(version: dict | None) -> list[dict]:
    if version is None:
        return []
    findings = review(DesignSpec.model_validate(version["spec"]), ConceptGraph.model_validate(version["concept"]))
    return [f.model_dump() for f in findings]


def _track_view(pid: str, track: dict) -> dict[str, Any]:
    """An open parallel thread with what the UI needs: its head, the parent (for the
    diff), the answers given on this thread since the fork, and its review."""
    head = store.get_version(track["head_version_id"])
    parent = store.get_version(head["parent_id"]) if head and head["parent_id"] else None
    lineage = store.lineage(head["id"]) if head else []
    fork_idx = next((i for i, v in enumerate(lineage) if v["id"] == track["fork_version_id"]), -1)
    since_fork = [v["id"] for v in lineage[fork_idx + 1:]]
    answers = [m for m in store.messages_for(pid, since_fork) if m["role"] == "user"]
    return {**track, "head": head, "parent_concept": parent["concept"] if parent else None,
            "answers": answers, "review": _review(head), "turns": len(since_fork)}


def _state(pid: str) -> dict[str, Any]:
    project = store.get_project(pid)
    if project is None:
        raise HTTPException(404, "Projet introuvable")
    head = store.get_version(project["head_version_id"]) if project["head_version_id"] else None
    lineage = store.lineage(head["id"]) if head else []
    return {
        "project": project,
        "phase": _phase(head),
        "head": head,
        "lineage": [v["id"] for v in lineage],
        "versions": store.list_versions(pid),
        "messages": store.messages_for(pid, [v["id"] for v in lineage]),
        "pending": store.pending_batch(pid, head["id"] if head else None),
        "cad_runs": pipeline.list(pid),
        "review": _review(head),
        "review_coverage": review_coverage(DesignSpec.model_validate(head["spec"]), ConceptGraph.model_validate(head["concept"])) if head else [],
        "tracks": [_track_view(pid, t) for t in store.open_tracks(pid)],
        "ab_stats": {"project": store.ab_stats(pid), "global": store.ab_stats(),
                     "threads_project": store.track_stats(pid), "threads_global": store.track_stats()},
    }


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except TransitionError as e:
        raise HTTPException(409, str(e)) from e
    except (AgentError, LLMError) as e:
        raise HTTPException(502, str(e)) from e


def _provider_b(b_model: str | None):
    """Model B for this request, or None when the user did not ask for a comparison."""
    if not b_model:
        return None
    return _guard(get_provider_b, b_model, model_label(b_model))


# ---------------------------------------------------------------- meta


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    return {
        "provider": provider.name, "model": provider.model, "label": provider.label,
        "b": {"available": b_available(), "default_model": default_b_model()},
        "profile": process_profile(),
        "catalog": CATALOG,
    }


@app.get("/api/models")
def models() -> list[dict[str, Any]]:
    """OpenRouter catalogue for the model-B picker."""
    if os.getenv("B_PROVIDER") == "mock":
        return [{"id": "scenario-demo-b", "name": "Démo B", "context_length": None, "prompt_per_m": 0, "completion_per_m": 0, "vision": False}]
    return _guard(openrouter_models)


# ---------------------------------------------------------------- projects


class NewProject(BaseModel):
    prompt: str
    b_model: str | None = None


@app.get("/api/projects")
def list_projects() -> list[dict[str, Any]]:
    return store.list_projects()


@app.post("/api/projects")
def create_project(body: NewProject) -> dict[str, Any]:
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(400, "Décris ce que tu veux fabriquer.")
    b = _provider_b(body.b_model)
    pid = store.create_project(prompt[:60], prompt)
    try:
        if b:
            agent.run_ab(pid, b, "initial", prompt)
        else:
            agent.run_turn(pid, "initial", prompt)
    except AgentError as e:
        store.delete_project(pid)
        raise HTTPException(502, str(e)) from e
    return _state(pid)


@app.get("/api/projects/{pid}")
def get_project(pid: str) -> dict[str, Any]:
    return _state(pid)


@app.delete("/api/projects/{pid}")
def delete_project(pid: str) -> dict[str, str]:
    store.delete_project(pid)
    return {"ok": "supprimé"}


@app.get("/api/projects/{pid}/versions/{vid}")
def get_version(pid: str, vid: str) -> dict[str, Any]:
    v = store.get_version(vid)
    if v is None or v["project_id"] != pid:
        raise HTTPException(404, "Version introuvable")
    return {**v, "review": _review(v), "review_coverage": review_coverage(DesignSpec.model_validate(v["spec"]), ConceptGraph.model_validate(v["concept"]))}


@app.get("/api/projects/{pid}/usage")
def usage(pid: str) -> dict[str, Any]:
    return store.usage(pid)


@app.get("/api/credits")
def credits() -> dict[str, Any]:
    if provider.name == "mock":
        return {"openrouter": None, "anthropic": None, "app": {}}
    return credit_report(store)


# ---------------------------------------------------------------- interview


class Answer(BaseModel):
    kind: Literal["reponse", "remarque", "checkpoint_continuer", "checkpoint_modifier"] = "reponse"
    text: str
    option_id: str | None = None
    selection: Selection | None = None
    b_model: str | None = None


@app.post("/api/projects/{pid}/answer")
def answer(pid: str, body: Answer) -> dict[str, Any]:
    if not body.text.strip():
        raise HTTPException(400, "Réponse vide.")
    b = _provider_b(body.b_model)
    if b:
        _guard(agent.run_ab, pid, b, body.kind, body.text.strip(), body.selection, body.option_id)
    else:
        _guard(agent.run_turn, pid, body.kind, body.text.strip(), body.selection, body.option_id)
    return _state(pid)


@app.post("/api/projects/{pid}/documents")
async def upload_document(pid: str, file: UploadFile = File(...)):
    from .documents import decode_document, MAX_DOCUMENT_BYTES
    if not store.get_project(pid): raise HTTPException(404, "Projet introuvable.")
    raw = await file.read(MAX_DOCUMENT_BYTES + 1)
    await file.close()
    try:
        from starlette.concurrency import run_in_threadpool
        metadata = await run_in_threadpool(decode_document, raw, file.filename or "Document")
    except Exception as exc:
        raise HTTPException(400, str(exc)[:240]) from exc
    return {"reference": "[document:" + metadata['id'] + "]", **metadata}


class Choice(BaseModel):
    candidate_id: str


@app.post("/api/projects/{pid}/choose")
def choose(pid: str, body: Choice) -> dict[str, Any]:
    _guard(agent.choose, pid, body.candidate_id)
    return _state(pid)


class Discard(BaseModel):
    batch_id: str


@app.post("/api/projects/{pid}/discard")
def discard(pid: str, body: Discard) -> dict[str, Any]:
    store.discard_batch(body.batch_id)
    return _state(pid)


# ---------------------------------------------------------------- parallel threads


class StartParallel(BaseModel):
    batch_id: str


@app.post("/api/projects/{pid}/parallel/start")
def start_parallel(pid: str, body: StartParallel) -> dict[str, Any]:
    _guard(agent.start_parallel, pid, body.batch_id)
    return _state(pid)


@app.post("/api/projects/{pid}/tracks/{tid}/answer")
def track_answer(pid: str, tid: str, body: Answer) -> dict[str, Any]:
    track = store.get_track(tid)
    if track is None or track["project_id"] != pid:
        raise HTTPException(404, "Fil introuvable")
    if not body.text.strip():
        raise HTTPException(400, "Réponse vide.")
    prov = provider if track["slot"] == "A" else _guard(get_provider_b, track["model"], track["label"])
    _guard(agent.track_turn, pid, tid, prov, body.kind, body.text.strip(), body.selection, body.option_id)
    return _state(pid)


@app.post("/api/projects/{pid}/tracks/{tid}/choose")
def track_choose(pid: str, tid: str) -> dict[str, Any]:
    _guard(agent.choose_track, pid, tid)
    return _state(pid)


# ---------------------------------------------------------------- plan


class PlanRequest(BaseModel):
    remarks: str | None = None
    b_model: str | None = None


@app.post("/api/projects/{pid}/plan")
def make_plan(pid: str, body: PlanRequest) -> dict[str, Any]:
    _guard(agent.generate_plan, pid, body.remarks, _provider_b(body.b_model))
    return _state(pid)


@app.post("/api/projects/{pid}/plan/validate")
def validate_plan(pid: str) -> dict[str, Any]:
    project = store.get_project(pid)
    if project is None:
        raise HTTPException(404, "Projet introuvable")
    head = store.get_version(project["head_version_id"])
    if head is None or head["kind"] != "plan":
        raise HTTPException(409, "Aucun plan à valider.")
    problems = transition_problems(DesignSpec.model_validate(head["spec"]), ConceptGraph.model_validate(head["concept"]))
    if problems:
        raise HTTPException(409, "Plan bloqué : " + "; ".join(problems))
    store.set_validated(head["id"])
    store.add_message(pid, head["id"], "event", "plan_valide", "Plan de conception validé")
    return _state(pid)


# ---------------------------------------------------------------- versions


class Checkout(BaseModel):
    version_id: str
    branch: str | None = None


@app.post("/api/projects/{pid}/head")
def checkout(pid: str, body: Checkout) -> dict[str, Any]:
    v = store.get_version(body.version_id)
    if v is None or v["project_id"] != pid:
        raise HTTPException(404, "Version introuvable")
    fields: dict[str, Any] = {"head_version_id": v["id"]}
    if body.branch:
        fields["branch"] = body.branch.strip()[:40]
    store.update_project(pid, **fields)
    return _state(pid)


@app.post("/api/projects/{pid}/duplicate")
def duplicate(pid: str, body: Checkout) -> dict[str, Any]:
    v = store.get_version(body.version_id)
    if v is None or v["project_id"] != pid:
        raise HTTPException(404, "Version introuvable")
    return _state(store.duplicate(pid, v["id"]))


# ---------------------------------------------------------------- CAD and fabrication: explicit actions only

class CadRequest(BaseModel):
    remarks: str = ""
    parent_id: str | None = None
    params: dict[str, float] | None = None

class SliceRequest(BaseModel):
    bed_type: Literal["Cool Plate", "Engineering Plate", "High Temp Plate", "Textured PEI Plate", "Supertack Plate"]
    machine: str
    process: str
    filament: str

@app.get("/api/fabrication/profiles")
def fabrication_profiles():
    return _guard(profile_options)

@app.post("/api/projects/{pid}/cad")
def generate_cad(pid: str, body: CadRequest):
    _guard(pipeline.generate, pid, body.remarks, body.parent_id, body.params)
    return _state(pid)

@app.post("/api/projects/{pid}/cad/{rid}/validate")
def validate_cad(pid: str, rid: str):
    _guard(pipeline.validate, pid, rid)
    return _state(pid)

@app.post("/api/projects/{pid}/cad/{rid}/slice")
def slice_cad(pid: str, rid: str, body: SliceRequest):
    _guard(pipeline.slice, pid, rid, body.machine, body.process, body.filament, body.bed_type)
    return _state(pid)

@app.post("/api/projects/{pid}/cad/{rid}/slices/{sid}/validate")
def validate_slice(pid: str, rid: str, sid: str):
    run = _guard(pipeline.get, pid, rid)
    head = _guard(pipeline.head, pid)
    if not run['validated'] or run['plan_version_id'] != head['id']:
        raise HTTPException(409, "La CAO validée doit correspondre au plan courant.")
    sliced = next((s for s in run['slices'] if s['id'] == sid), None)
    if not sliced:
        raise HTTPException(404, "Slicing introuvable.")
    sliced['validated'] = True
    pipeline.save(pid, run)
    return _state(pid)

@app.get("/api/projects/{pid}/cad/{rid}/files/{name}")
def cad_file(pid: str, rid: str, name: str):
    run = _guard(pipeline.get, pid, rid)
    names = {'model.py', 'input.json', 'metrics.json'}
    for m in run['metrics']:
        names.update({f"part-{m['index']}.step", f"part-{m['index']}.stl", f"print-{m['index']}.stl"})
    if name not in names:
        raise HTTPException(404, "Fichier introuvable.")
    return FileResponse(pipeline.folder(pid, rid) / name, filename=name)

@app.get("/api/projects/{pid}/cad/{rid}/slices/{sid}/file")
def slice_file(pid: str, rid: str, sid: str):
    run = _guard(pipeline.get, pid, rid)
    if not any(s['id'] == sid for s in run['slices']):
        raise HTTPException(404, "Slicing introuvable.")
    return FileResponse(pipeline.folder(pid, rid) / sid / 'sliced.gcode.3mf', filename='sliced.gcode.3mf')

# ---------------------------------------------------------------- frontend (production build)

DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        candidate = DIST / path
        return FileResponse(candidate if path and candidate.is_file() else DIST / "index.html")
