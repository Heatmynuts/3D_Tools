import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from design_backend.agent.engineer import AgentError, EngineerAgent, TransitionError
from design_backend.llm.base import LLMResult
from design_backend.llm.mock_provider import MockProvider
from design_backend.patching import apply_concept_patch, apply_spec_patch
from design_backend.review import review, review_coverage, transition_problems
from design_backend.schemas import Component, ConceptGraph, DesignSpec, Unknown, PartOrientation
from design_backend.store import Store


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'test.sqlite3')
        self.agent = EngineerAgent(self.store, MockProvider())
        self.pid = self.store.create_project('Démo', 'Support écran')
        self.sleep = patch('design_backend.llm.mock_provider.time.sleep')
        self.sleep.start()

    def tearDown(self):
        self.sleep.stop()
        self.tmp.cleanup()

    def checkpoint(self):
        v = self.agent.run_turn(self.pid, 'initial', 'Support écran')
        for answer in ['Tout le périmètre', 'Sans outil', '20 degrés']:
            v = self.agent.run_turn(self.pid, 'reponse', answer)
        return v

    def test_demo_to_plan(self):
        v = self.checkpoint()
        self.assertEqual(v['next']['kind'], 'checkpoint')
        plan = self.agent.generate_plan(self.pid)
        self.assertEqual(plan['kind'], 'plan')
        self.assertFalse(plan['validated'])
        self.assertEqual(len(self.store.list_versions(self.pid)), 5)

    def test_plan_refused_before_checkpoint(self):
        self.agent.run_turn(self.pid, 'initial', 'Support écran')
        with self.assertRaises(TransitionError):
            self.agent.generate_plan(self.pid)

    def test_checkpoint_checks_new_geometry_and_preserves_head(self):
        original = self.agent.run_turn(self.pid, 'initial', 'Support écran')
        payload = {'spec_patch': {'remove': {'unknowns': ['u1', 'u2', 'u3']}},
                   'concept_patch': {'upsert_components': [{'id': 'bad', 'type': 'clip', 'part': 'bad', 'params': {'thickness': 0.01}}]},
                   'change_summary': 'Clip trop fin', 'next': {'kind': 'checkpoint', 'checkpoint': {'text': 'Valider ?', 'summary': []}}}
        with patch.object(self.agent.provider_a, 'complete', return_value=LLMResult(text=json.dumps(payload), model='test', latency_ms=0)):
            with self.assertRaises(AgentError):
                self.agent.run_turn(self.pid, 'reponse', 'Ajouter un clip')
        self.assertEqual(self.store.get_project(self.pid)['head_version_id'], original['id'])

    def test_strong_unknown_blocks_transition(self):
        spec = DesignSpec(unknowns=[Unknown(id='u', topic='Fixation', impact='fort')])
        self.assertTrue(transition_problems(spec, ConceptGraph()))

    def test_functional_loads_checked_for_prototype(self):
        findings = review(DesignSpec(print_intent='prototype_rapide'), ConceptGraph(components=[Component(id='b', type='block')]))
        self.assertTrue(any(f.rule == 'charges' for f in findings))

    def test_missing_orientation_is_reported_in_coverage(self):
        coverage = review_coverage(DesignSpec(), ConceptGraph(components=[Component(id='c', type='clip')]))
        self.assertEqual(next(c['status'] for c in coverage if c['rule'] == 'couches'), 'donnees_manquantes')
        self.assertEqual(next(c['status'] for c in coverage if c['rule'] == 'resistance'), 'non_disponible')

    def test_documentary_update_preserves_geometry(self):
        from design_backend.schemas import ConceptPatch, SpecPatch
        graph = ConceptGraph(components=[Component(id='b', type='block')])
        self.assertEqual(apply_concept_patch(graph, ConceptPatch()), graph)
        spec = apply_spec_patch(DesignSpec(), SpecPatch.model_validate({'upsert': {'parameters': [{'id': 'width', 'label': 'Largeur', 'value': 40, 'status': 'connu', 'source': 'utilisateur'}]}}))
        self.assertEqual(spec.parameters[0].value, 40)

    def test_clip_insertion_assumption_explicit(self):
        graph = ConceptGraph(components=[Component(id='c', type='clip')])
        self.assertTrue(any(f.rule == 'clip_hypothese' for f in review(DesignSpec(), graph)))
        graph.components[0].params['insertion_deflection'] = 0.5
        self.assertFalse(any(f.rule == 'clip_hypothese' for f in review(DesignSpec(), graph)))

    def test_ab_proposals_share_parent(self):
        batch = self.agent.run_ab(self.pid, MockProvider('B'), 'initial', 'Support écran')
        candidates = self.store.pending_batch(self.pid, None)
        self.assertEqual(len(candidates), 2)
        self.assertTrue(all(c['batch_id'] == batch and c['ok'] for c in candidates))
        selected = self.agent.choose(self.pid, candidates[0]['id'])
        self.assertEqual(self.store.get_project(self.pid)['head_version_id'], selected['id'])


if __name__ == '__main__':
    unittest.main()

class CadContractTests(unittest.TestCase):
    def test_rejects_system_code(self):
        from design_backend.pipeline import validate_code
        for code in ['import os\ndef build(PARAMS):\n return {}',
                     'def build(PARAMS):\n return open("secret")',
                     'def build(PARAMS):\n return cq.__dict__',
                     'def build(PARAMS):\n return {}\nopen("file")']:
            self.assertTrue(validate_code(code), code)

    def test_allows_parametric_factory(self):
        from design_backend.pipeline import validate_code
        self.assertFalse(validate_code("def build(PARAMS):\n return {'piece': cq.Workplane('XY').box(PARAMS['largeur'],20,4)}"))

    def test_official_profiles_flatten_includes(self):
        from design_backend.pipeline import flatten_profile
        p = flatten_profile('machine', 'Bambu Lab H2D 0.4 nozzle')
        self.assertNotIn('inherits', p)
        self.assertNotIn('include', p)
        self.assertIn('machine_start_gcode', p)
        self.assertEqual(p['printer_model'], 'Bambu Lab H2D')
