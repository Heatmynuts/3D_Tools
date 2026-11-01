"""Trusted runner executed inside a macOS filesystem/network sandbox."""
import json
import resource
from pathlib import Path

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
resource.setrlimit(resource.RLIMIT_FSIZE, (200 * 1024 * 1024, 200 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))

import cadquery as cq
import math

job = json.loads(Path('input.json').read_text())
safe = {k: __builtins__[k] for k in ('abs', 'min', 'max', 'range', 'len', 'float', 'int', 'round', 'enumerate', 'zip', 'list', 'dict', 'tuple', 'sum', 'ValueError')} if isinstance(__builtins__, dict) else {k: getattr(__builtins__, k) for k in ('abs', 'min', 'max', 'range', 'len', 'float', 'int', 'round', 'enumerate', 'zip', 'list', 'dict', 'tuple', 'sum', 'ValueError')}
namespace = {'__builtins__': safe, 'cq': cq, 'math': math}
exec(compile(job['code'], 'model.py', 'exec'), namespace)
parts = namespace['build'](job['params'])
if not isinstance(parts, dict) or not parts or len(parts) > 30:
    raise ValueError('build(PARAMS) doit renvoyer 1 à 30 pièces nommées.')
if job.get('expected_parts') and set(parts) != set(job['expected_parts']):
    raise ValueError('Les pièces produites ne correspondent pas aux pièces imprimées du concept : ' + str(job['expected_parts']))
metrics = []
rotations = {'+Z': ((1, 0, 0), 0), '-Z': ((1, 0, 0), 180), '+X': ((0, 1, 0), -90), '-X': ((0, 1, 0), 90), '+Y': ((1, 0, 0), 90), '-Y': ((1, 0, 0), -90)}
for i, (name, part) in enumerate(parts.items()):
    if not isinstance(part, cq.Workplane):
        raise ValueError('Chaque pièce doit être un cq.Workplane.')
    solids = part.solids().vals()
    if not solids or any(not s.isValid() or s.Volume() <= 0 for s in solids):
        raise ValueError(f'Pièce {name} invalide ou sans volume positif.')
    shape = cq.Compound.makeCompound(solids)
    bb = shape.BoundingBox()
    cq.exporters.export(shape, f'part-{i}.step')
    cq.exporters.export(shape, f'part-{i}.stl', tolerance=0.08, angularTolerance=0.15)
    axis = job['orientations'].get(name)
    if axis not in rotations:
        raise ValueError(f'Orientation absente pour la pièce {name}. Utiliser les identifiants de pièces du cahier des charges.')
    vector, angle = rotations[axis]
    oriented = shape.rotate((0, 0, 0), vector, angle)
    pb = oriented.BoundingBox()
    oriented = oriented.translate((-pb.xmin, -pb.ymin, -pb.zmin))
    cq.exporters.export(oriented, f'print-{i}.stl', tolerance=0.08, angularTolerance=0.15)
    # Reload saved STEP to check the actual artifact, rather than only the in-memory shape.
    saved = cq.importers.importStep(f'part-{i}.step').val()
    if not saved.isValid():
        raise ValueError('STEP exporté invalide.')
    metrics.append({'name': name, 'index': i, 'dimensions_mm': [bb.xlen, bb.ylen, bb.zlen],
                    'print_dimensions_mm': [pb.xlen, pb.ylen, pb.zlen], 'volume_mm3': shape.Volume(),
                    'surface_mm2': shape.Area(), 'solids': len(solids), 'valid': True, 'orientation': axis})
Path('metrics.json').write_text(json.dumps(metrics))
