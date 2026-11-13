#!/usr/bin/env python3
"""Export ordered X image sets; generate art separately with an image tool."""
import argparse
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

MAX_IMAGES = 20
MAX_TOTAL_PIXELS = 80_000_000
SOURCE_XATTRS = ('com.apple.metadata:kMDItemWhereFroms', 'com.apple.quarantine')
MAGICK = os.environ.get('MAGICK_BIN') or shutil.which('magick')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def magick(*arguments):
    require(MAGICK, 'ImageMagick 7 is required: add magick to PATH or set MAGICK_BIN.')
    completed = subprocess.run([MAGICK, *map(str, arguments)], capture_output=True)
    require(completed.returncode == 0, completed.stderr.decode(errors='replace').strip())
    return completed.stdout


def dimensions(path):
    measured = magick('identify', '-format', '%w %h\n', path).decode().splitlines()
    require(len(measured) == 1, f'Expected one static image: {path}')
    return tuple(map(int, measured[0].split()))


def digest_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def pixel_digest(path):
    return digest_bytes(magick(path, '-alpha', 'on', '-depth', '8', 'rgba:-'))


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def validate_shape(plan):
    for key in ('count', 'width', 'height'):
        require(type(plan.get(key)) is int and plan[key] > 0, f'{key} must be a positive integer.')
    require(2 <= plan['count'] <= MAX_IMAGES, 'This exporter supports 2–20 independent images.')
    require(plan['count'] * plan['width'] * plan['height'] <= MAX_TOTAL_PIXELS,
            'Requested set exceeds the 80 million pixel local processing budget.')
    require(plan.get('mode') in ('independent', 'panorama', 'reveal'), 'Unknown mode.')
    require(plan.get('fit', 'exact') in ('exact', 'contain', 'cover'), 'Unknown fit policy.')


def resolve_source(source, plan_directory):
    require(isinstance(source, str) and '://' not in source, 'source must be a local file path.')
    path = (plan_directory / source).resolve()
    require(path.is_file(), f'Missing source image: {path}')
    return path


def prepare_frame(asset, destination, plan, plan_directory, temporary_directory):
    if isinstance(asset, str):
        asset = {'source': asset}
    require(isinstance(asset, dict), 'Each asset must be a path or object.')
    source = resolve_source(asset.get('source'), plan_directory)
    source_width, source_height = dimensions(source)
    cropped = temporary_directory / ('crop-' + destination.name)
    if 'crop' in asset:
        rectangle = asset['crop']
        require(isinstance(rectangle, list) and len(rectangle) == 4 and
                all(type(n) is int for n in rectangle), 'crop must be [left, top, width, height].')
        left, top, crop_width, crop_height = rectangle
        require(left >= 0 and top >= 0 and crop_width > 0 and crop_height > 0 and
                left + crop_width <= source_width and top + crop_height <= source_height,
                f'Crop extends outside {source.name}.')
        magick(source, '-crop', f'{crop_width}x{crop_height}+{left}+{top}', '+repage', '-strip', cropped)
        source = cropped
        source_width, source_height = crop_width, crop_height
    target_width, target_height = plan['width'], plan['height']
    if 'stretch_band' in asset:
        require(plan['mode'] == 'independent', 'stretch_band is only for independent objects.')
        band = asset['stretch_band']
        require(isinstance(band, list) and len(band) == 2 and all(type(n) is int for n in band),
                'stretch_band must be [start_y, end_y].')
        start_y, end_y = band
        require(0 < start_y < end_y < source_height, 'stretch_band must leave both endpoints intact.')
        top_output_height = max(1, round(start_y * target_width / source_width))
        bottom_output_height = max(1, round((source_height - end_y) * target_width / source_width))
        middle_output_height = target_height - top_output_height - bottom_output_height
        require(middle_output_height > 0, 'Endpoints cannot fit at the requested width and height.')
        regions = ((0, start_y, top_output_height),
                   (start_y, end_y - start_y, middle_output_height),
                   (end_y, source_height - end_y, bottom_output_height))
        pieces = []
        for index, (region_y, region_height, output_height) in enumerate(regions):
            piece = temporary_directory / f'{destination.stem}-part-{index}.png'
            magick(source, '-crop', f'{source_width}x{region_height}+0+{region_y}', '+repage',
                   '-resize', f'{target_width}x{output_height}!', '-strip', piece)
            pieces.append(piece)
        magick(*pieces, '-append', '-strip', destination)
    else:
        fit = asset.get('fit', plan.get('fit', 'exact'))
        require(fit in ('exact', 'contain', 'cover'), 'Unknown asset fit policy.')
        if fit == 'exact':
            require((source_width, source_height) == (target_width, target_height),
                    f'{source.name} is {source_width}x{source_height}; expected '
                    f'{target_width}x{target_height}. Choose contain/cover explicitly or prepare the source.')
            magick(source, '-strip', destination)
        else:
            geometry = f'{target_width}x{target_height}' + ('^' if fit == 'cover' else '')
            magick(source, '-resize', geometry, '-background', plan.get('background', 'white'),
                   '-gravity', 'center', '-extent', f'{target_width}x{target_height}', '-strip', destination)
    require(dimensions(destination) == (target_width, target_height), 'Exporter produced incorrect dimensions.')


def edge_error(left_path, right_path, height):
    left_width = dimensions(left_path)[0]
    left = magick(left_path, '-crop', f'1x{height}+{left_width - 1}+0', '+repage',
                  '-alpha', 'on', '-depth', '8', 'rgba:-')
    right = magick(right_path, '-crop', f'1x{height}+0+0', '+repage',
                   '-alpha', 'on', '-depth', '8', 'rgba:-')
    return round(sum(abs(a-b) for a, b in zip(left, right)) / (len(left) * 255), 6)


def build(plan_path, destination):
    plan_path, destination = Path(plan_path).resolve(), Path(destination).resolve()
    plan = load_json(plan_path)
    validate_shape(plan)
    require(not destination.exists(), f'Output already exists; use a new version: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.x-image-build-', dir=destination.parent) as scratch:
        scratch = Path(scratch)
        staged = scratch / 'set'
        image_directory = staged / 'images'
        image_directory.mkdir(parents=True)
        image_paths = [image_directory / f'{index:02}.png' for index in range(1, plan['count']+1)]
        reconstruction_matches = None
        if plan['mode'] == 'panorama':
            master_plan = dict(plan, width=plan['width'] * plan['count'])
            master = scratch / 'master.png'
            prepare_frame(plan.get('source'), master, master_plan, plan_path.parent, scratch)
            for index, path in enumerate(image_paths):
                magick(master, '-crop', f"{plan['width']}x{plan['height']}+{index * plan['width']}+0",
                       '+repage', '-strip', path)
            reconstructed = scratch / 'reconstructed.png'
            magick(*image_paths, '+append', '-strip', reconstructed)
            reconstruction_matches = pixel_digest(master) == pixel_digest(reconstructed)
            require(reconstruction_matches, 'Slice reconstruction differs from the prepared master.')
        else:
            assets = plan.get('assets')
            if plan['mode'] == 'reveal' and assets is None:
                assets = [plan.get('head')] + [plan.get('bridge')] * (plan['count']-2) + [plan.get('tail')]
            require(isinstance(assets, list) and len(assets) == plan['count'],
                    'Asset list length must equal count.')
            for asset, path in zip(assets, image_paths):
                prepare_frame(asset, path, plan, plan_path.parent, scratch)
        frames = []
        for index, path in enumerate(image_paths, 1):
            frames.append({'index': index, 'file': f'images/{path.name}',
                           'width': plan['width'], 'height': plan['height'],
                           'pixels_sha256': pixel_digest(path)})
        manifest = {'schema_version': 1, 'mode': plan['mode'], 'count': plan['count'],
                    'width': plan['width'], 'height': plan['height'], 'frames': frames,
                    'panorama_reconstruction_matches': reconstruction_matches,
                    'edge_mae': [edge_error(a, b, plan['height']) for a, b in zip(image_paths, image_paths[1:])],
                    'privacy_skill': 'pending', 'x_client_verified': False,
                    'notes': ['Edge errors are diagnostic only; inspect thin connecting lines visually.',
                              'Preview is a local simulation, not an X client verification.']}
        write_json(staged / 'manifest.json', manifest)
        finalize(staged, initial=True)
        staged.rename(destination)
    return audit(destination)


def checked_files(folder, manifest):
    validate_shape(manifest)
    expected = [f'images/{index:02}.png' for index in range(1, manifest['count']+1)]
    require([frame['file'] for frame in manifest['frames']] == expected, 'Manifest image order is invalid.')
    require([frame['index'] for frame in manifest['frames']] == list(range(1, manifest['count']+1)),
            'Manifest indices are invalid.')
    observed = sorted(path.relative_to(folder).as_posix() for path in (folder / 'images').iterdir())
    require(observed == expected, 'Image folder contains missing or extra files.')
    paths = [folder / name for name in expected]
    for path, frame in zip(paths, manifest['frames']):
        require(path.is_file() and not path.is_symlink(), 'Exported images must be ordinary files.')
        require(dimensions(path) == (manifest['width'], manifest['height']), f'Wrong dimensions: {path.name}')
        require((frame['width'], frame['height']) == (manifest['width'], manifest['height']),
                'Frame dimensions do not match the set specification.')
        require(pixel_digest(path) == frame['pixels_sha256'], f'Image pixels changed: {path.name}; rebuild.')
    return paths


def clear_source_xattrs(path):
    if not hasattr(os, 'listxattr'):
        return {'supported': False, 'remaining': []}
    try:
        for attribute in (*SOURCE_XATTRS, 'com.apple.provenance'):
            if attribute in os.listxattr(path):
                try:
                    os.removexattr(path, attribute)
                except OSError:
                    pass
        remaining = [attribute for attribute in (*SOURCE_XATTRS, 'com.apple.provenance')
                     if attribute in os.listxattr(path)]
    except OSError as error:
        raise ValueError(f'Cannot audit source attributes on {path.name}: {error}') from error
    require(not any(attribute in remaining for attribute in SOURCE_XATTRS),
            f'Source download metadata remains: {path.name}')
    return {'supported': True, 'remaining': remaining}


def png_metadata_chunks(payload):
    require(payload.startswith(b'\x89PNG\r\n\x1a\n'), 'Expected PNG bytes.')
    offset, metadata = 8, []
    while offset < len(payload):
        require(offset + 12 <= len(payload), 'Truncated PNG chunk.')
        length = struct.unpack('>I', payload[offset:offset+4])[0]
        chunk = payload[offset+4:offset+8]
        require(offset + 12 + length <= len(payload), 'Truncated PNG payload.')
        if chunk in (b'eXIf', b'tEXt', b'zTXt', b'iTXt'):
            metadata.append(chunk.decode())
        offset += length + 12
    return metadata


def validate_privacy_report(report_path, paths):
    report = load_json(report_path)
    require(isinstance(report, list), 'Privacy report must be the skill JSON array.')
    require(len(report) == len(paths), 'Privacy report image count does not match this set.')
    covered = {Path(entry['output']).resolve() for entry in report}
    require(covered == {path.resolve() for path in paths}, 'Privacy report does not cover this exact image set.')
    for entry in report:
        privacy = entry['privacy']
        require(privacy.get('gpsPresent') is False and privacy.get('sourceExifPresent') is False and
                privacy.get('requiredMacSourceXattrsPresent') == [], 'Privacy skill reported remaining source data.')


def finalize(folder, privacy_report=None, privacy_unavailable=False, initial=False):
    folder = Path(folder).resolve()
    manifest = load_json(folder / 'manifest.json')
    paths = checked_files(folder, manifest)
    if privacy_report:
        validate_privacy_report(privacy_report, paths)
        manifest['privacy_skill'] = 'completed'
    elif privacy_unavailable:
        manifest['privacy_skill'] = 'unavailable'
    elif not initial:
        require(manifest.get('privacy_skill') == 'completed',
                'Provide --privacy-report, or explicitly report --privacy-unavailable.')
    for path, frame in zip(paths, manifest['frames']):
        temporary = path.with_name(path.stem + '.clean.png')
        try:
            magick(path, '-strip', temporary)
            require(pixel_digest(temporary) == frame['pixels_sha256'], 'Metadata stripping changed image pixels.')
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        frame['mac_source_attributes'] = clear_source_xattrs(path)
        frame['sha256'] = digest_bytes(path.read_bytes())
        frame['bytes'] = path.stat().st_size
        require(not png_metadata_chunks(path.read_bytes()), f'Embedded metadata remains: {path.name}')
    write_json(folder / 'manifest.json', manifest)
    with zipfile.ZipFile(folder / 'images.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.name)
    write_preview(folder, manifest)
    return audit(folder)


def audit(folder):
    folder = Path(folder).resolve()
    manifest = load_json(folder / 'manifest.json')
    paths = checked_files(folder, manifest)
    with zipfile.ZipFile(folder / 'images.zip') as archive:
        require(archive.namelist() == [path.name for path in paths], 'ZIP order or image count does not match.')
        require(archive.testzip() is None, 'ZIP failed its integrity check.')
        for path, frame in zip(paths, manifest['frames']):
            payload = path.read_bytes()
            require(digest_bytes(payload) == frame['sha256'] and len(payload) == frame['bytes'],
                    f'Image file changed after finalization: {path.name}')
            require(not png_metadata_chunks(payload), f'Embedded EXIF/text metadata in {path.name}')
            require(archive.read(path.name) == payload, f'ZIP contains a different image: {path.name}')
    return {'file_checks_passed': True, 'count': manifest['count'],
            'width': manifest['width'], 'height': manifest['height'],
            'privacy_workflow_complete': manifest.get('privacy_skill') == 'completed',
            'privacy_skill': manifest.get('privacy_skill'), 'x_client_verified': False,
            'output': str(folder)}


def write_preview(folder, manifest):
    tiles, links = [], []
    for frame in manifest['frames']:
        payload = base64.b64encode((folder / frame['file']).read_bytes()).decode()
        tiles.append(f'<img src="data:image/png;base64,{payload}" width="{frame["width"]}" '
                     f'height="{frame["height"]}" alt="第 {frame["index"]} 张" title="{frame["file"]}">')
        links.append(f'<a download href="{html.escape(frame["file"])}">{frame["index"]:02} · '
                     f'{frame["width"]}×{frame["height"]}</a>')
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>X 多图模拟预览</title>
<style>body{font:16px system-ui;margin:24px;background:#f6f6f6;color:#222}h1{font-size:24px}
.viewport{max-width:650px;overflow-x:auto;background:white;padding:12px;border:1px solid #ddd}
.strip{display:flex;gap:6px;width:max-content;align-items:stretch}.strip img{height:560px;width:auto;display:block;border-radius:6px;flex:none}
label,button{margin-right:16px}nav{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px}a{color:#135dc0}p{line-height:1.6}</style>
<h1>X 多图模拟预览</h1><p>本地模拟，不代表 X 客户端已验证。图片保持独立；横向滑动查看终点。</p>
<p>MODE · COUNT 张 · 每张 WIDTH×HEIGHT 像素</p>
<p><label>显示高度 <input id="height" type="range" min="240" max="900" value="560"></label>
<label>间距 <input id="gap" type="range" min="0" max="16" value="6"></label>
<button id="end">滑到末尾</button><button id="start">回到开头</button></p>
<div class="viewport"><div class="strip">TILES</div></div><nav>LINKS</nav>
<p><a href="images.zip" download>下载全部独立图片</a> · <a href="manifest.json">查看实际文件清单</a></p>
<script>const viewport=document.querySelector('.viewport'),strip=document.querySelector('.strip');
document.querySelector('#height').oninput=e=>strip.querySelectorAll('img').forEach(i=>i.style.height=e.target.value+'px');
document.querySelector('#gap').oninput=e=>strip.style.gap=e.target.value+'px';
document.querySelector('#end').onclick=()=>viewport.scrollTo({left:viewport.scrollWidth,behavior:'smooth'});
document.querySelector('#start').onclick=()=>viewport.scrollTo({left:0,behavior:'smooth'});</script></html>'''
    for placeholder, value in [('MODE', manifest['mode']), ('COUNT', str(manifest['count'])),
                               ('WIDTH', str(manifest['width'])), ('HEIGHT', str(manifest['height'])),
                               ('TILES', ''.join(tiles)), ('LINKS', ''.join(links))]:
        document = document.replace(placeholder, value)
    (folder / 'preview.html').write_text(document, encoding='utf8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    builder = commands.add_parser('build')
    builder.add_argument('plan')
    builder.add_argument('--out', required=True)
    finalizer = commands.add_parser('finalize')
    finalizer.add_argument('folder')
    privacy = finalizer.add_mutually_exclusive_group()
    privacy.add_argument('--privacy-report')
    privacy.add_argument('--privacy-unavailable', action='store_true')
    auditor = commands.add_parser('audit')
    auditor.add_argument('folder')
    arguments = parser.parse_args()
    try:
        if arguments.command == 'build':
            report = build(arguments.plan, arguments.out)
        elif arguments.command == 'finalize':
            report = finalize(arguments.folder, arguments.privacy_report, arguments.privacy_unavailable)
        else:
            report = audit(arguments.folder)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
