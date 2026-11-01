"""Local integration fixtures: real CAD kernel and slicer, no paid provider."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from design_backend.agent.engineer import EngineerAgent, TransitionError
from design_backend.llm.base import LLMResult
from design_backend.pipeline import BAMBU, Pipeline
from design_backend.store import Store


class FixtureProvider:
    name = 'fixture'
    label = 'Fixture locale'
    model = 'fixture'
    def complete(self, request):
        return LLMResult(text=json.dumps(self.proposal), model='fixture', latency_ms=0, cost_usd=0)


@unittest.skipUnless(sys.platform == 'darwin', 'Sandbox macOS requis')
class PipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'projects.sqlite3')
        self.provider = FixtureProvider()
        self.pipeline = Pipeline(self.store, EngineerAgent(self.store, self.provider), Path(self.tmp.name) / 'artifacts')
        self.pid = self.store.create_project('Fixture', 'Pièce de test')
        version = self.store.add_version(self.pid, None, 'plan',
            {'orientations': [{'id': 'piece', 'up': '+Z'}]},
            {'components': [{'id': 'piece', 'type': 'block'}]},
            plan={'title': 'Fixture', 'fonction': 'Test', 'geometrie_generale': 'Test'},
)
        self.store.set_validated(version['id'])

    def tearDown(self):
        self.tmp.cleanup()

    def generate(self, code, params=None):
        self.provider.proposal = {'summary': 'Fixture', 'code': 'def build(PARAMS):\n    return {"piece": '+code+'}\n', 'params': params or {}, 'assumptions': ['Fixture de validation logicielle']}
        return self.pipeline.generate(self.pid)

    def test_four_geometry_scenarios(self):
        cases = [
            ("cq.Workplane('XY').box(30,20,4)", [30,20,4], 2400),
            ("cq.Workplane('XY').box(30,20,4).faces('>Z').workplane().hole(6)", [30,20,4], None),
            ("cq.Workplane('XY').box(30,20,15).faces('>Z').shell(-2)", [30,20,15], None),
            ("cq.Workplane('XY').box(30,4,15).union(cq.Workplane('XY').box(30,20,4).translate((0,8,-5.5)))", [30,20,15], None),
        ]
        for code, dims, volume in cases:
            with self.subTest(code=code):
                run = self.generate(code)
                m = run['metrics'][0]
                for actual, expected in zip(m['dimensions_mm'], dims):
                    self.assertAlmostEqual(actual, expected, places=5)
                self.assertTrue(m['valid'])
                self.assertTrue((self.pipeline.folder(self.pid,run['id'])/'part-0.step').is_file())
                if volume: self.assertAlmostEqual(m['volume_mm3'], volume)

    def test_parametric_rebuild_is_new_unvalidated_version(self):
        run = self.generate("cq.Workplane('XY').box(PARAMS['width'],20,4)", {'width':30})
        self.pipeline.validate(self.pid,run['id'])
        rebuilt = self.pipeline.generate(self.pid,parent=run['id'],params={'width':35})
        self.assertNotEqual(rebuilt['id'],run['id'])
        self.assertFalse(rebuilt['validated'])
        self.assertEqual(rebuilt['metrics'][0]['dimensions_mm'][0],35)
        self.assertEqual(self.pipeline.get(self.pid,run['id'])['params']['width'],30)

    @unittest.skipUnless(BAMBU.is_file(), 'Bambu Studio requis')
    def test_h2d_slicing_gates_and_gcode(self):
        run=self.generate("cq.Workplane('XY').box(20,20,4)")
        args=(self.pid,run['id'],'Bambu Lab H2D 0.4 nozzle','0.20mm Standard @BBL H2D','Bambu PLA Basic @BBL H2D','Textured PEI Plate')
        with self.assertRaises(TransitionError): self.pipeline.slice(*args)
        self.pipeline.validate(self.pid,run['id'])
        result=self.pipeline.slice(*args)
        sliced=result['slices'][-1]
        self.assertFalse(sliced['validated'])
        self.assertTrue(sliced['gcode_files'])
        self.assertTrue(sliced['statistics'])
        self.assertEqual(sliced['bed_type'],'Textured PEI Plate')

    def test_sandbox_denies_user_files_and_network(self):
        import subprocess
        run=self.generate("cq.Workplane('XY').box(10,10,2)")
        folder=self.pipeline.folder(self.pid,run['id'])
        sentinel=Path(self.tmp.name)/'private.txt'
        sentinel.write_text('private fixture')
        # Place the private fixture under the user home to exercise the same rule as .env.
        with tempfile.TemporaryDirectory(dir=Path.home()) as home_temp:
            sentinel=Path(home_temp)/'private.txt';sentinel.write_text('private fixture')
            script = "import socket\nfrom pathlib import Path\ndenied=0\ntry:\n Path("+repr(str(sentinel))+ ").read_text()\nexcept PermissionError:\n denied+=1\ntry:\n socket.create_connection(('127.0.0.1',8000),timeout=1)\nexcept PermissionError:\n denied+=1\nassert denied == 2, denied\nprint('Fichier privé et réseau interdits')\n"
            (folder/'isolation.py').write_text(script)
            result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(folder/'sandbox.sb'),sys.executable,'-I',str(folder/'isolation.py')],capture_output=True,text=True,env={'PATH':'/usr/bin:/bin','HOME':str(folder)},timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
