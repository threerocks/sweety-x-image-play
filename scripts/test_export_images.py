#!/usr/bin/env python3
"""Mechanical image fixtures verify export behavior; they are not artwork."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

module_spec = importlib.util.spec_from_file_location('export_images', Path(__file__).with_name('export_images.py'))
exporter = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(exporter)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def make_image(self, name, size='40x1920', color='red'):
        path = self.root / name
        exporter.magick('-size', size, f'xc:{color}', '-strip', path)
        return path

    def build_set(self, plan, name='output'):
        plan_path = self.root / f'{name}.json'
        exporter.write_json(plan_path, plan)
        destination = self.root / name
        exporter.build(plan_path, destination)
        return destination

    def independent(self):
        source = self.make_image('red.png')
        return self.build_set({'mode': 'independent', 'count': 4, 'width': 40,
                               'height': 1920, 'assets': [str(source)] * 4})

    def test_four_files_and_zip_are_exact_size(self):
        destination = self.independent()
        report = exporter.audit(destination)
        self.assertEqual((report['count'], report['width'], report['height']), (4, 40, 1920))
        self.assertFalse(report['privacy_workflow_complete'])
        self.assertFalse(report['x_client_verified'])
        with zipfile.ZipFile(destination / 'images.zip') as archive:
            self.assertEqual(archive.namelist(), ['01.png', '02.png', '03.png', '04.png'])

    def test_twenty_slices_reconstruct_gradient(self):
        source = self.root / 'master.png'
        exporter.magick('-size', '740x128', 'gradient:red-blue', '-rotate', '180', '-strip', source)
        destination = self.build_set({'mode': 'panorama', 'count': 20, 'width': 37,
                                      'height': 128, 'source': str(source)})
        manifest = exporter.load_json(destination / 'manifest.json')
        self.assertTrue(manifest['panorama_reconstruction_matches'])
        joined = self.root / 'joined.png'
        exporter.magick(*sorted((destination / 'images').glob('*.png')), '+append', '-strip', joined)
        self.assertEqual(exporter.pixel_digest(source), exporter.pixel_digest(joined))

    def test_reveal_keeps_endpoints_and_repeats_only_bridge(self):
        head = self.make_image('head.png', '78x120', 'red')
        bridge = self.make_image('bridge.png', '78x120', 'green')
        tail = self.make_image('tail.png', '78x120', 'blue')
        destination = self.build_set({'mode': 'reveal', 'count': 20, 'width': 78, 'height': 120,
                                      'head': str(head), 'bridge': str(bridge), 'tail': str(tail)})
        frames = exporter.load_json(destination / 'manifest.json')['frames']
        self.assertEqual(frames[0]['pixels_sha256'], exporter.pixel_digest(head))
        self.assertEqual(frames[-1]['pixels_sha256'], exporter.pixel_digest(tail))
        self.assertTrue(all(frame['pixels_sha256'] == exporter.pixel_digest(bridge) for frame in frames[1:-1]))

    def test_stretch_band_preserves_endpoint_shape(self):
        source = self.root / 'band.png'
        exporter.magick('-size', '20x100', 'xc:green', '-fill', 'red', '-draw', 'rectangle 0,0 19,19',
                       '-fill', 'blue', '-draw', 'rectangle 0,80 19,99', '-strip', source)
        destination = self.build_set({'mode': 'independent', 'count': 2, 'width': 40, 'height': 1920,
                                      'assets': [{'source': str(source), 'stretch_band': [20, 80]}] * 2})
        exported = destination / 'images/01.png'
        top = exporter.magick(exported, '-crop', '40x40+0+0', '+repage', '-depth', '8', 'rgb:-')
        bottom = exporter.magick(exported, '-crop', '40x40+0+1880', '+repage', '-depth', '8', 'rgb:-')
        self.assertEqual(top, bytes([255, 0, 0]) * 1600)
        self.assertEqual(bottom, bytes([0, 0, 255]) * 1600)

    def test_wrong_source_size_fails_without_publishing_partial_set(self):
        source = self.make_image('wide.png', '800x1920')
        with self.assertRaises(ValueError):
            self.build_set({'mode': 'independent', 'count': 2, 'width': 40,
                            'height': 1920, 'assets': [str(source)] * 2})
        self.assertFalse((self.root / 'output').exists())

    def test_explicit_cover_produces_requested_size(self):
        source = self.make_image('wide.png', '800x1200')
        destination = self.build_set({'mode': 'independent', 'count': 2, 'width': 40,
                                      'height': 1920, 'fit': 'cover', 'assets': [str(source)] * 2})
        self.assertEqual(exporter.dimensions(destination / 'images/01.png'), (40, 1920))

    def test_existing_output_is_not_overwritten(self):
        destination = self.independent()
        before = (destination / 'images/01.png').read_bytes()
        with self.assertRaises(ValueError):
            exporter.build(self.root / 'output.json', destination)
        self.assertEqual(before, (destination / 'images/01.png').read_bytes())

    def test_extra_image_is_rejected(self):
        destination = self.independent()
        (destination / 'images/extra.png').write_bytes((destination / 'images/01.png').read_bytes())
        with self.assertRaises(ValueError):
            exporter.audit(destination)

    def test_tampered_image_cannot_be_hidden_by_finalize(self):
        destination = self.independent()
        exporter.magick('-size', '40x1920', 'xc:blue', '-strip', destination / 'images/01.png')
        with self.assertRaises(ValueError):
            exporter.finalize(destination, privacy_unavailable=True)

    def test_zip_with_wrong_image_is_rejected(self):
        destination = self.independent()
        with zipfile.ZipFile(destination / 'images.zip', 'w') as archive:
            for index in range(1, 5):
                archive.writestr(f'{index:02}.png', b'not an image')
        with self.assertRaises(ValueError):
            exporter.audit(destination)

    def test_privacy_report_must_cover_this_set(self):
        destination = self.independent()
        report = self.root / 'privacy.json'
        exporter.write_json(report, [{'output': '/wrong/location.png', 'privacy': {
            'gpsPresent': False, 'sourceExifPresent': False, 'requiredMacSourceXattrsPresent': []}}] * 4)
        with self.assertRaises(ValueError):
            exporter.finalize(destination, privacy_report=report)

    def test_metadata_stripping_and_unavailable_status(self):
        destination = self.independent()
        path = destination / 'images/01.png'
        temporary = self.root / 'metadata.png'
        exporter.magick(path, '-set', 'comment', 'test-source-marker', temporary)
        path.write_bytes(temporary.read_bytes())
        with self.assertRaises(ValueError):
            exporter.audit(destination)
        report = exporter.finalize(destination, privacy_unavailable=True)
        self.assertTrue(report['file_checks_passed'])
        self.assertFalse(report['privacy_workflow_complete'])
        self.assertEqual(exporter.png_metadata_chunks(path.read_bytes()), [])

    def test_crop_bounds_and_image_limit_are_rejected(self):
        source = self.make_image('source.png')
        with self.assertRaises(ValueError):
            self.build_set({'mode': 'independent', 'count': 2, 'width': 40, 'height': 1920,
                            'assets': [{'source': str(source), 'crop': [0, 0, 41, 1920]}] * 2})
        with self.assertRaises(ValueError):
            self.build_set({'mode': 'independent', 'count': 21, 'width': 40, 'height': 1920,
                            'assets': [str(source)] * 21})


if __name__ == '__main__':
    unittest.main(verbosity=2)
