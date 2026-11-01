"""Version-linked CAD artifacts and explicit H2D slicing. Never sends a print."""
from __future__ import annotations
from .web_sources import source_context
import ast
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pydantic import BaseModel, Field
from .agent.engineer import AgentError, EngineerAgent, TransitionError, _Stats
from .manufacturing import PROFILES_DIR, DEFAULT_BAMBU
from .review import transition_problems
from .schemas import DesignSpec, ConceptGraph

BAMBU = Path(os.getenv('BAMBU_STUDIO_BIN', str(DEFAULT_BAMBU / 'Contents/MacOS/BambuStudio')))
CAD_PROMPT = '''Tu conçois en CadQuery une géométrie paramétrique à partir du plan validé fourni.
Réponds uniquement en JSON : {"summary": "...", "code": "...", "params": {"nom": nombre}, "assumptions": ["..."]}.
Le code définit uniquement def build(PARAMS), qui retourne un dictionnaire {identifiant_de_piece: cq.Workplane}.
cq (cadquery) et math sont préchargés. Aucun import, fichier, réseau, affichage, export, sous-processus ni attribut privé.
Utilise PARAMS pour les dimensions modifiables. Unités mm, repère monde de ConceptGraph.
Les clés des pièces doivent correspondre exactement aux orientations déclarées dans DesignSpec.
Les références fantômes et la visserie achetée ne sont pas des pièces à fabriquer.
Produis les détails fonctionnels du concept : interfaces, évidements, clips, nervures et fixations demandées.
N'utilise pas une boîte simplifiée à la place de la conception. Déclare toute dimension illustrative ou hypothèse.
Aucune donnée matériau inventée. Une validité géométrique ne démontre pas la résistance mécanique.'''

class CadProposal(BaseModel):
    summary: str
    code: str
    params: dict[str, float] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)


def validate_code(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [str(e)]
    problems = []
    if len(code) > 50000:
        problems.append('Code trop long.')
    if not tree.body or any(not isinstance(n, ast.FunctionDef) or n.name != 'build' or n.decorator_list for n in tree.body) or len(tree.body) != 1:
        problems.append('Définir uniquement la fonction build(PARAMS).')
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.ClassDef, ast.AsyncFunctionDef)):
            problems.append('Import ou déclaration interdite.')
        if isinstance(n, ast.Attribute) and n.attr.startswith('_') or isinstance(n, ast.Name) and n.id.startswith('__'):
            problems.append('Attribut privé interdit.')
        if isinstance(n, ast.Name) and n.id in {'open', 'eval', 'exec', 'compile', 'getattr', 'setattr', '__import__', 'input', 'breakpoint'}:
            problems.append('Appel système interdit.')
    return list(dict.fromkeys(problems))


def run_bounded(command: list[str], folder: Path, timeout: int, env: dict | None = None):
    log = folder / 'execution.log'
    with log.open('w') as stream:
        process = subprocess.Popen(command, cwd=folder, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    code = process.wait(timeout=0.5)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= deadline:
                        raise
                    memory = subprocess.run(['/bin/ps', '-o', 'rss=', '-p', str(process.pid)], capture_output=True, text=True).stdout.strip()
                    if memory.isdigit() and int(memory) > 2 * 1024 * 1024:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        raise AgentError('Budget mémoire de 2 Gio dépassé.')
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise AgentError(f'Délai maximal de {timeout} secondes dépassé.')
    if code:
        raise AgentError(f'Exécution interrompue ({code}) : ' + log.read_text(errors='replace')[-2500:])


def flatten_profile(kind: str, name: str, stack: tuple[str, ...] = ()) -> dict:
    if name in stack or Path(name).name != name:
        raise AgentError('Profil cyclique ou nom invalide.')
    path = PROFILES_DIR / kind / (name + '.json')
    if not path.is_file():
        raise AgentError(f'Profil officiel introuvable : {name}')
    raw = json.loads(path.read_text())
    data = flatten_profile(kind, raw['inherits'], stack + (name,)) if raw.get('inherits') else {}
    for include in raw.get('include', []):
        data.update(flatten_profile(kind, include, stack + (name,)))
    data.update({k: v for k, v in raw.items() if k not in ('inherits', 'include')})
    return data


def profile_options():
    return {kind: sorted(p.stem for p in (PROFILES_DIR / kind).glob('*.json')
                        if 'H2D' in p.stem and 'H2DP' not in p.stem and 'Pro' not in p.stem and 'template' not in p.stem
                        and json.loads(p.read_text()).get('instantiation') == 'true')
            for kind in ('machine', 'process', 'filament')}


class Pipeline:
    def __init__(self, store, agent: EngineerAgent, root: Path):
        self.store, self.agent, self.root = store, agent, root
        root.mkdir(parents=True, exist_ok=True)

    def folder(self, pid: str, rid: str) -> Path:
        if not pid.isalnum() or not rid.isalnum():
            raise AgentError('Identifiant invalide.')
        return self.root / pid / rid

    def get(self, pid: str, rid: str) -> dict:
        p = self.folder(pid, rid) / 'manifest.json'
        if not p.is_file():
            raise AgentError('Version CAO introuvable.')
        return json.loads(p.read_text())

    def list(self, pid: str):
        if not pid.isalnum():
            return []
        return sorted([json.loads(p.read_text()) for p in (self.root / pid).glob('*/manifest.json')], key=lambda x: x['created_at'])

    def save(self, pid, run):
        p = self.folder(pid, run['id']) / 'manifest.json'
        temp = p.with_suffix('.tmp')
        temp.write_text(json.dumps(run, ensure_ascii=False, indent=2))
        temp.replace(p)

    def head(self, pid):
        project = self.store.get_project(pid)
        head = self.store.get_version(project['head_version_id']) if project and project['head_version_id'] else None
        if not head or head['kind'] != 'plan' or not head['validated']:
            raise TransitionError('Valide le plan avant de générer la CAO.')
        problems = transition_problems(DesignSpec.model_validate(head['spec']), ConceptGraph.model_validate(head['concept']))
        if problems:
            raise TransitionError('; '.join(problems))
        head["spec"] = DesignSpec.model_validate(head["spec"]).model_dump()
        head["concept"] = ConceptGraph.model_validate(head["concept"]).model_dump()
        return head

    def generate(self, pid, remarks='', parent=None, params=None):
        head = self.head(pid)
        cad_stats = _Stats(turn_id=uuid.uuid4().hex[:12])
        previous = self.get(pid, parent) if parent else None
        if previous and previous['plan_version_id'] != head['id']:
            raise TransitionError('Cette CAO appartient à un autre plan ; reviens sur ce plan pour la modifier.')
        if params is not None:
            if any(not math.isfinite(v) or abs(v) > 3000 for v in params.values()):
                raise TransitionError("Paramètres numériques hors limites (valeurs finies, amplitude ≤ 3000).")
            if not previous or set(params) - set(previous['params']):
                raise TransitionError('Paramètre inconnu ; demander une nouvelle conception.')
            proposal = CadProposal(code=previous['code'], summary='Paramètres modifiés', params={**previous['params'], **params}, assumptions=previous['assumptions'])
        elif self.agent.provider_a.name == 'mock':
            # Explicit pipeline fixture, not a pretended reconstruction of the screen concept.
            proposal = CadProposal(summary='Éprouvette de démonstration pour tester la chaîne CAO et slicing',
                code="def build(PARAMS):\n    return {'cadre': cq.Workplane('XY').box(PARAMS['largeur'], PARAMS['profondeur'], PARAMS['epaisseur'])}\n",
                params={'largeur': 30, 'profondeur': 20, 'epaisseur': 4}, assumptions=['Éprouvette illustrative : ne représente pas le support écran du scénario d’entretien.'])
        else:
            context = json.dumps({'plan': head['plan'], 'spec': head['spec'], 'concept': head['concept'], 'remarks': remarks + source_context(remarks),
                                  'previous': previous}, ensure_ascii=False)
            proposal = self.agent._structured(pid, self.agent.provider_a, 'cad', CAD_PROMPT, context, CadProposal,
                                               cad_stats, lambda p: validate_code(p.code))
        errors = validate_code(proposal.code)
        if errors:
            raise AgentError('; '.join(errors))
        rid = uuid.uuid4().hex[:12]
        folder = self.folder(pid, rid)
        folder.mkdir(parents=True)
        if any(not math.isfinite(v) or abs(v) > 3000 for v in proposal.params.values()):
            raise AgentError('Paramètres CAO non finis ou hors limites.')
        input_data = {**proposal.model_dump(), 'expected_parts': [] if self.agent.provider_a.name == 'mock' else sorted({c.get('part') or c['id'] for c in head['concept']['components'] if c['type'] not in ('fastener', 'cutout')}), 'orientations': {o['id']: o['up'] for o in head['spec']['orientations']}}
        (folder/'input.json').write_text(json.dumps(input_data))
        (folder/'model.py').write_text(proposal.code)
        shutil.copyfile(Path(__file__).with_name('cad_worker.py'), folder/'worker.py')
        if sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').is_file():
            raise AgentError('Isolation macOS indisponible : le code généré ne sera pas exécuté.')
        allowed = [str(folder.resolve()), str(Path(sys.prefix).resolve()), str(Path(sys.base_prefix).resolve()),
                   str(Path.home()/'.cache/uv/archive-v0'), str(Path.home()/'.local/share/uv/python')]
        rules = ['(version 1)', '(allow default)', '(deny network*)', '(deny process-fork)', '(deny file-read* (subpath "/Users"))', '(deny file-write*)', '(allow file-read-metadata)']
        rules += [f'(allow file-read* (subpath {json.dumps(p)}))' for p in allowed]
        rules += [f'(allow file-write* (subpath {json.dumps(str(folder.resolve()))}))', '(allow file-write* (literal "/dev/null"))']
        profile = folder/'sandbox.sb'; profile.write_text('\n'.join(rules))
        environment = {'PATH': '/usr/bin:/bin', 'HOME': str(folder), 'TMPDIR': str(folder), 'PYTHONDONTWRITEBYTECODE': '1', 'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2'}
        started = time.monotonic()
        command = ['/usr/bin/sandbox-exec', '-f', str(profile), sys.executable, '-I', str(folder/'worker.py')]
        repairs = 0
        try:
            run_bounded(command, folder, 120, environment)
        except AgentError as error:
            if self.agent.provider_a.name == 'mock' or params is not None:
                raise
            shutil.copyfile(folder/'execution.log', folder/'execution-attempt1.log')
            repair_context = context + '\nCode précédent :\n' + proposal.code + '\nErreur d’exécution :\n' + str(error) + '\nCorrige uniquement les erreurs, conserve les exigences et identifiants de pièces.'
            proposal = self.agent._structured(pid, self.agent.provider_a, 'repair', CAD_PROMPT, repair_context, CadProposal,
                                               cad_stats, lambda p: validate_code(p.code))
            if any(not math.isfinite(v) or abs(v) > 3000 for v in proposal.params.values()):
                raise AgentError('Paramètres de réparation hors limites.')
            input_data.update(proposal.model_dump())
            (folder/'input.json').write_text(json.dumps(input_data))
            (folder/'model.py').write_text(proposal.code)
            run_bounded(command, folder, 120, environment)
            repairs = 1
        metrics = json.loads((folder/'metrics.json').read_text())
        for parameter in head['spec']['parameters']:
            if parameter['status'] != 'connu':
                note = f"Donnée à confirmer : {parameter['label']} ({parameter['status']})."
                if note not in proposal.assumptions:
                    proposal.assumptions.append(note)
        run = {'id': rid, 'plan_version_id': head['id'], 'parent_id': parent, 'created_at': time.time(), **proposal.model_dump(),
               'metrics': metrics, 'generation_seconds': round(time.monotonic()-started, 2), 'validated': False,
               'engine': 'CadQuery', 'slices': [], 'repairs': repairs, 'turn_id': cad_stats.turn_id, 'demo': self.agent.provider_a.name == 'mock'}
        self.save(pid, run)
        return run

    def validate(self, pid, rid):
        run = self.get(pid, rid)
        head = self.head(pid)
        if run['plan_version_id'] != head['id']:
            raise TransitionError('Le plan a changé : valider une CAO du plan courant.')
        run['validated'] = True
        run['validation_note'] = 'Géométrie acceptée pour préparer le slicing ; résistance et essais physiques non validés.'
        self.save(pid, run)
        return run

    def slice(self, pid, rid, machine, process, filament, bed_type):
        run = self.get(pid, rid)
        head = self.head(pid)
        if run['plan_version_id'] != head['id'] or not run['validated']:
            raise TransitionError('Valide une CAO du plan courant avant le slicing.')
        if bed_type not in ('Cool Plate', 'Engineering Plate', 'High Temp Plate', 'Textured PEI Plate', 'Supertack Plate'):
            raise TransitionError('Choisis le plateau réellement utilisé.')
        options = profile_options()
        for kind, name in [('machine', machine), ('process', process), ('filament', filament)]:
            if name not in options[kind]:
                raise TransitionError(f'Profil non disponible : {name}')
        resolved = {kind: flatten_profile(kind, name) for kind, name in [('machine', machine), ('process', process), ('filament', filament)]}
        cli_adjustments = []
        machine_config = resolved['machine']
        if 'nozzle_volume_type' not in machine_config and machine_config.get('default_nozzle_volume_type'):
            machine_config['nozzle_volume_type'] = machine_config['default_nozzle_volume_type']
            cli_adjustments.append({'key': 'nozzle_volume_type', 'value': machine_config['nozzle_volume_type'], 'source': 'default_nozzle_volume_type du profil officiel machine', 'reason': 'Résolution du défaut officiel pour le CLI Bambu Studio'})
        for kind in ('process', 'filament'):
            compatible = resolved[kind].get('compatible_printers', [])
            if compatible and machine not in compatible:
                raise TransitionError(f'Profil {kind} incompatible avec {machine}.')
        if not BAMBU.is_file():
            raise AgentError('Bambu Studio introuvable.')
        sid = uuid.uuid4().hex[:12]
        folder = self.folder(pid, rid)/sid; folder.mkdir()
        for kind, data in resolved.items():
            (folder/f'{kind}.json').write_text(json.dumps(data))
        source = self.folder(pid, rid)
        command = (["/usr/bin/arch", "-x86_64"] if os.getenv('BAMBU_CLI_ARCH') == 'x86_64' else []) + [str(BAMBU), '--debug', '2', '--load-settings', str(folder/'machine.json')+';'+str(folder/'process.json'),
                   '--load-filaments', str(folder/'filament.json'), '--orient', '0', '--arrange', '1', '--ensure-on-bed', '--slice', '0',
                   '--curr-bed-type', bed_type, '--mstpp', '180', '--outputdir', str(folder), '--export-3mf', 'sliced.gcode.3mf']
        command.extend(['--nozzle-volume-type', ','.join(machine_config['nozzle_volume_type'])])
        command.extend(str(source/f"print-{m['index']}.stl") for m in run['metrics'])
        started = time.monotonic()
        run_bounded(command, folder, 240)
        artifact = folder/'sliced.gcode.3mf'
        if not artifact.is_file():
            raise AgentError('Le slicer n’a pas produit de 3MF.')
        with zipfile.ZipFile(artifact) as z:
            gcodes = [n for n in z.namelist() if n.endswith('.gcode')]
            if not gcodes:
                raise AgentError('3MF sans G-code : slicing non confirmé.')
            data = z.read('Metadata/slice_info.config').decode() if 'Metadata/slice_info.config' in z.namelist() else ''
            statistics = [{**el.attrib} for el in ET.fromstring(data).iter() if el.attrib] if data else []
        sliced = {'id': sid, 'created_at': time.time(), 'machine': machine, 'process': process, 'filament': filament, 'bed_type': bed_type,
                  'seconds': round(time.monotonic()-started, 2), 'gcode_files': gcodes, 'statistics': statistics,
                  'validated': False, 'profile_modifications': [], 'cli_adjustments': cli_adjustments, 'orientation': 'Reprise des orientations du cahier des charges ; arrangement uniquement.'}
        run['slices'].append(sliced)
        self.save(pid, run)
        return run
