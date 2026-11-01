"""Regression checks for local-only builds and verified-output reuse."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/page-mascot/scripts/mascot.py'
spec = importlib.util.spec_from_file_location('mascot_pipeline', SCRIPT)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def sheet(path, size=90):
    im = Image.new('RGBA', (size, size))
    draw = ImageDraw.Draw(im)
    tile = size//3
    for row in range(3):
        for col in range(3):
            x, y = col*tile, row*tile
            draw.rectangle((x+6, y+6, x+tile-6, y+tile-6), fill='orange')
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sources = [self.root/'characters'/'fox'/f'{k}.png' for k in ('directions', 'reactions')]
        for p in self.sources:
            sheet(p)
        self.outputs = [self.root/f'fox-{k}.webp' for k in ('directions', 'reactions')]
        for p in self.outputs:
            p.write_bytes(b'verified output')
        self.cache = self.root/'cache.json'

    def test_cache_detects_source_settings_and_output_changes(self):
        inputs = pipeline.fingerprint(self.sources)
        pipeline.save_cache(self.cache, inputs, self.outputs)
        self.assertTrue(pipeline.cache_matches(self.cache, inputs, self.outputs))
        # Content, not timestamps, determines freshness.
        self.sources[0].write_bytes(self.sources[0].read_bytes()+b'changed')
        self.assertFalse(pipeline.cache_matches(self.cache, pipeline.fingerprint(self.sources), self.outputs))
        with patch.dict(os.environ, {'FADE_DEPTH': '0.2'}):
            self.assertNotEqual(inputs, pipeline.fingerprint(self.sources))
        self.outputs[0].write_bytes(b'corrupt')
        self.assertFalse(pipeline.cache_matches(self.cache, inputs, self.outputs))
        self.outputs[0].unlink()
        self.assertFalse(pipeline.cache_matches(self.cache, inputs, self.outputs))

    def test_implementation_and_dependency_changes_invalidate(self):
        inputs = pipeline.fingerprint(self.sources)
        with patch.object(pipeline, 'version', return_value='future-version'):
            self.assertNotEqual(inputs, pipeline.fingerprint(self.sources))
        helper = self.root/'helpers'
        helper.mkdir()
        (helper/'requirements.txt').write_text('pillow')
        code = helper/'build.py'
        code.write_text('old implementation')
        with patch.object(pipeline, 'HERE', helper):
            before = pipeline.fingerprint(self.sources)
            code.write_text('new implementation')
            self.assertNotEqual(before, pipeline.fingerprint(self.sources))

    def test_bad_cache_is_a_miss(self):
        inputs = pipeline.fingerprint(self.sources)
        for content in ('broken json', 'null', '{}', '[]'):
            self.cache.write_text(content)
            self.assertFalse(pipeline.cache_matches(self.cache, inputs, self.outputs))

    def test_sources_validate_geometry_and_cells(self):
        pipeline.validate_sources(self.sources)
        sheet(self.sources[1], 120)
        with self.assertRaisesRegex(ValueError, 'same pixel dimensions'):
            pipeline.validate_sources(self.sources)
        Image.new('RGBA', (90, 90)).save(self.sources[1])
        with self.assertRaisesRegex(ValueError, 'empty cell'):
            pipeline.validate_sources(self.sources)
        Image.new('RGBA', (90, 60), 'orange').save(self.sources[1])
        with self.assertRaisesRegex(ValueError, 'square PNG'):
            pipeline.validate_sources(self.sources)

    def test_missing_sources_and_path_names_fail_without_generation(self):
        for name, message in [('missing', 'Generate them with Codex native'), ('../escape', 'must be a slug')]:
            result = subprocess.run([sys.executable, str(SCRIPT), name], cwd=self.root,
                                    env={**os.environ, 'MASCOT_ROOT': str(self.root), 'MASCOT_SRC': str(self.root/'characters')},
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(message, result.stderr)
        self.assertFalse((self.root/'public').exists())

    def run_pipeline(self, *, metrics=(0, .7, .01), force=False):
        called = []
        def local_run(script, *args, env):
            called.append(script)
            if script == 'build.py':
                for output in self.outputs:
                    (Path(env['MASCOT_DEST'])/output.name).write_bytes(b'new verified atlas')
            return ''
        argv = ['mascot.py', 'fox', '--dest', str(self.root)] + (['--force'] if force else [])
        with patch.dict(os.environ, {'MASCOT_ROOT': str(self.root), 'MASCOT_SRC': str(self.root/'characters')}), \
             patch.object(sys, 'argv', argv), patch.object(pipeline, 'screen'), \
             patch.object(pipeline, 'run', side_effect=local_run), \
             patch.object(pipeline, 'measure', return_value=metrics):
            pipeline.main()
        return called

    def test_failed_verification_preserves_live_outputs_and_no_cache(self):
        with self.assertRaises(SystemExit) as raised:
            self.run_pipeline(metrics=(3, .7, .01))
        self.assertEqual(raised.exception.code, 1)
        self.assertTrue(all(p.read_bytes() == b'verified output' for p in self.outputs))
        self.assertFalse((self.root/'.cache').exists())
        self.assertEqual(list(self.root.glob('.fox-*')), [])

    def test_success_cache_hit_force_and_corruption_rebuild(self):
        self.assertEqual(self.run_pipeline(), ['build.py'])
        self.assertTrue(all(p.read_bytes() == b'new verified atlas' for p in self.outputs))
        self.assertEqual(self.run_pipeline(), [])
        self.assertEqual(self.run_pipeline(force=True), ['build.py'])
        self.outputs[0].write_bytes(b'corrupt')
        self.assertEqual(self.run_pipeline(), ['build.py'])
        self.assertEqual(list(self.root.glob('.fox-*')), [])


if __name__ == '__main__':
    unittest.main()
