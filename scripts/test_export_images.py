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

    def breakout_plan(self, left=30, right=69, count=5):
        source = self.root / 'scene.png'
        mask = self.root / 'mask.png'
        exporter.magick('-size', '120x80', 'gradient:#f08424-#234f92', '-strip', source)
        exporter.magick('-size', '120x80', 'xc:black', '-fill', 'white',
                       '-draw', f'rectangle {left},20 {right},59', '-strip', mask)
        return {'mode': 'breakout', 'layout': 'adaptive', 'source': str(source), 'foreground_mask': str(mask),
                'count': count, 'bar_width': 12, 'gap_width': 3, 'corner_radius': 2}

    def test_breakout_preserves_foreground_and_transparency_through_finalize(self):
        plan = self.breakout_plan()
        source_digest = exporter.pixel_digest(plan['source'])
        destination = self.build_set(plan)
        manifest = exporter.load_json(destination / 'manifest.json')
        self.assertEqual(sum(manifest['widths']), 120)
        self.assertTrue(manifest['panorama_reconstruction_matches'])
        self.assertTrue(manifest['breakout']['foreground_pixels_preserved'])
        joined = self.root / 'joined.png'
        exporter.magick(*sorted((destination / 'images').glob('*.png')), '+append', joined)
        original = exporter.magick(plan['source'], '-depth', '8', 'rgba:-')
        actual = exporter.magick(joined, '-depth', '8', 'rgba:-')
        for y in range(20, 60):
            for x in range(30, 70):
                offset = 4 * (120 * y + x)
                self.assertEqual(actual[offset:offset+4], original[offset:offset+4])
        self.assertEqual(actual[4 * (10 * 120 + 13) + 3], 0)
        self.assertEqual(actual[4 * (10 * 120 + 6) + 3], 255)
        before = [frame['pixels_sha256'] for frame in manifest['frames']]
        exporter.finalize(destination, privacy_unavailable=True)
        after = exporter.load_json(destination / 'manifest.json')
        self.assertEqual(before, [frame['pixels_sha256'] for frame in after['frames']])
        self.assertEqual(exporter.pixel_digest(plan['source']), source_digest)

    def test_breakout_layout_follows_left_and_right_subject(self):
        left = self.build_set(self.breakout_plan(5, 34), 'left')
        right = self.build_set(self.breakout_plan(85, 114), 'right')
        left_widths = exporter.audit(left)['widths']
        right_widths = exporter.audit(right)['widths']
        self.assertEqual(left_widths[0], right_widths[-1])
        self.assertEqual(sorted(left_widths[1:]), sorted(right_widths[:-1]))
        self.assertGreater(left_widths[0], max(left_widths[1:]))
        self.assertGreater(right_widths[-1], max(right_widths[:-1]))

    def test_breakout_wide_foreground_changes_layout_and_honors_count(self):
        destination = self.build_set(self.breakout_plan(15, 104, count=3))
        widths = exporter.audit(destination)['widths']
        self.assertEqual(len(widths), 3)
        self.assertGreaterEqual(widths[1], 90)
        self.assertEqual(sum(widths), 120)

    def test_breakout_rejects_cuts_through_foreground_and_invalid_widths(self):
        for widths in ([20, 20, 20, 20, 40], [5, 5, 5, 5, 5]):
            plan = self.breakout_plan()
            plan['widths'] = widths
            with self.assertRaises(ValueError):
                self.build_set(plan)
            self.assertFalse((self.root / 'output').exists())

    def test_breakout_rejects_empty_or_misaligned_mask(self):
        plan = self.breakout_plan()
        for size in ('120x80', '119x80'):
            exporter.magick('-size', size, 'xc:black', plan['foreground_mask'])
            with self.assertRaises(ValueError):
                self.build_set(plan)

    def test_breakout_does_not_force_twenty_panels_or_cut_full_width_subject(self):
        plan = self.breakout_plan(0, 119)
        with self.assertRaisesRegex(ValueError, 'Not enough background'):
            self.build_set(plan)
        plan = self.breakout_plan(15, 104, count=20)
        plan['min_panel_width'] = 10
        with self.assertRaisesRegex(ValueError, 'Not enough background'):
            self.build_set(plan)

    def test_breakout_honors_explicit_unequal_widths(self):
        plan = self.breakout_plan()
        plan['widths'] = [10, 15, 50, 20, 25]
        destination = self.build_set(plan)
        self.assertEqual(exporter.audit(destination)['widths'], plan['widths'])

    def test_breakout_preserves_existing_source_alpha(self):
        plan = self.breakout_plan()
        exporter.magick('-size', '120x80', 'xc:rgba(180,120,60,0.5)', plan['source'])
        destination = self.build_set(plan)
        report = exporter.load_json(destination / 'manifest.json')['breakout']
        self.assertTrue(report['foreground_pixels_preserved'])

    def test_breakout_explicit_uniform_has_twenty_equal_eighty_pixel_panels(self):
        plan = self.breakout_plan()
        for key in ('count', 'bar_width', 'gap_width'):
            del plan[key]
        exporter.magick('-size', '1600x80', 'gradient:red-blue', plan['source'])
        exporter.magick('-size', '1600x80', 'xc:black', '-fill', 'white',
                       '-draw', 'rectangle 510,20 1000,59', plan['foreground_mask'])
        plan['layout'] = 'uniform'
        destination = self.build_set(plan)
        report = exporter.audit(destination)
        self.assertEqual(report['widths'], [80] * 20)
        manifest = exporter.load_json(destination / 'manifest.json')
        self.assertEqual(manifest['breakout']['layout'], 'uniform')
        self.assertEqual(manifest['breakout']['bar_width'], 72)
        self.assertEqual(manifest['breakout']['gap_width'], 8)
        self.assertTrue(manifest['breakout']['subject_cut_positions'])
        self.assertTrue(manifest['breakout']['foreground_pixels_preserved'])
        self.assertTrue(manifest['panorama_reconstruction_matches'])

    def test_breakout_uniform_rejects_wrong_canvas_and_unequal_widths(self):
        plan = self.breakout_plan()
        plan['layout'] = 'uniform'
        with self.assertRaisesRegex(ValueError, 'Prepare both at the same scale'):
            self.build_set(plan)
        plan['width'] = 24
        plan['widths'] = [20, 20, 20, 20, 40]
        with self.assertRaisesRegex(ValueError, 'rejects unequal widths'):
            self.build_set(plan)

    def test_breakout_uniform_respects_explicit_no_subject_cuts(self):
        plan = self.breakout_plan()
        plan.update(layout='uniform', width=24, allow_subject_cuts=False)
        with self.assertRaisesRegex(ValueError, 'cut crosses'):
            self.build_set(plan)

    def test_hybrid_preserves_subject_in_one_attachment_and_matches_column_grid(self):
        source = self.make_image('grid-source.png', '1752x80')
        mask = self.make_image('grid-mask.png', '1752x80', 'black')
        exporter.magick(mask, '-fill', 'white', '-draw', 'rectangle 520,20 1030,59', mask)
        destination = self.build_set({'mode': 'breakout', 'source': str(source), 'foreground_mask': str(mask)})
        manifest = exporter.load_json(destination / 'manifest.json')
        report = manifest['breakout']
        self.assertEqual(report['layout'], 'hybrid')
        self.assertEqual(report['column_count'], 20)
        self.assertEqual(report['main_columns'], [5, 11])
        self.assertEqual(manifest['widths'], [80] * 5 + [608] + [80] * 8)
        self.assertEqual(manifest['count'], 14)
        self.assertEqual(report['subject_cut_positions'], [])
        self.assertTrue(manifest['panorama_reconstruction_matches'])
        self.assertTrue(report['foreground_pixels_preserved'])
        # A real narrow attachment has no baked-in full-height side gap.
        alpha = exporter.magick(destination / 'images/01.png', '-alpha', 'extract', '-depth', '8', 'gray:-')
        self.assertEqual(alpha[40 * 80:41 * 80], bytes([255]) * 80)
        # The same grid gap exists above the subject but is occluded within it.
        main = exporter.magick(destination / 'images/06.png', '-depth', '8', 'rgba:-')
        self.assertEqual(main[4 * (10 * 608 + 84) + 3], 0)
        self.assertEqual(main[4 * (40 * 608 + 84) + 3], 255)

    def test_hybrid_rejects_attachment_count_confused_with_columns(self):
        source = self.make_image('scene.png', '1752x80')
        mask = self.make_image('mask.png', '1752x80', 'black')
        exporter.magick(mask, '-fill', 'white', '-draw', 'rectangle 520,20 1030,59', mask)
        plan = {'mode': 'breakout', 'source': str(source), 'foreground_mask': str(mask), 'count': 20}
        with self.assertRaisesRegex(ValueError, 'actual attachments'):
            self.build_set(plan)

    def test_hybrid_refuses_full_width_subject_instead_of_cutting_it(self):
        source = self.make_image('scene.png', '1752x80')
        mask = self.make_image('mask.png', '1752x80', 'white')
        with self.assertRaisesRegex(ValueError, 'never cut the subject'):
            self.build_set({'mode': 'breakout', 'source': str(source), 'foreground_mask': str(mask)})


if __name__ == '__main__':
    unittest.main(verbosity=2)
