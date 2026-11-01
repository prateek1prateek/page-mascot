"""Build and verify Codex-generated sheets locally; never calls an image API.

    python mascot.py fox
    python mascot.py fox --dest static/mascots --force

Run from the target project, or set MASCOT_ROOT. Source PNGs live in
characters/<name>/ (MASCOT_SRC overrides characters/). Unchanged verified outputs
are reused; --force runs the complete pipeline again.
"""
import argparse
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
BOOP_LIMIT = 2.0
PALETTE_LIMIT = 0.22
WIDTH_LIMIT = 0.12


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(sources):
    """Invalidate on source, implementation, dependency, or build-setting changes."""
    return {
        'sources': {str(p): digest(p) for p in sources},
        'pipeline': {p.name: digest(p) for p in sorted(HERE.glob('*.py'))},
        'requirements': digest(HERE / 'requirements.txt'),
        'python': sys.version,
        'packages': {name: version(name) for name in ('pillow', 'numpy', 'scipy')},
        'settings': {key: os.environ.get(key) for key in ('MATCH_CLAMP', 'FADE_DEPTH')},
    }


def cache_matches(path, inputs, outputs):
    try:
        cached = json.loads(path.read_text())
        return (cached['inputs'] == inputs and
                cached['outputs'] == {str(p): digest(p) for p in outputs})
    except (OSError, ValueError, KeyError, TypeError):
        return False


def save_cache(path, inputs, outputs):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {'inputs': inputs, 'outputs': {str(p): digest(p) for p in outputs}}
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as file:
        tmp = Path(file.name)
        json.dump(data, file, sort_keys=True)
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def run(script, *args, env):
    result = subprocess.run([sys.executable, str(HERE / script), *map(str, args)],
                            capture_output=True, text=True, env=env)
    if result.returncode:
        raise ValueError(f'{script} failed:\n{result.stdout}{result.stderr}')
    print(result.stdout.rstrip())
    return result.stdout


def validate_sources(sources):
    # Reject malformed grids before the numerical pipeline can divide by zero or
    # silently crop a rectangular/empty sheet. 1024px need not divide evenly by 3.
    from PIL import Image
    sizes = []
    for path in sources:
        with Image.open(path) as im:
            if im.format != 'PNG' or im.width != im.height or im.width < 9:
                raise ValueError(f'{path}: expected a square PNG containing a 3x3 grid.')
            sizes.append(im.size)
            alpha = im.convert('RGBA').getchannel('A')
            tile = im.width // 3
            for row in range(3):
                for col in range(3):
                    cell = alpha.crop((col*tile, row*tile, (col+1)*tile, (row+1)*tile))
                    if cell.getextrema()[1] <= 128:
                        raise ValueError(f'{path}: empty cell at row {row+1}, column {col+1}; redraw this sheet.')
    if sizes[0] != sizes[1]:
        raise ValueError('Directions and reactions must have the same pixel dimensions. Regenerate the mismatched sheet at the matching size.')


def screen(path, env):
    out = run('screen.py', path, env=env)
    if 'alpha: MISSING' in out:
        raise ValueError(f'{path}: redraw this sheet with the native image tool and transparent_background=true.')
    spread = re.search(r'shoulder spread ([\d.]+)%', out)
    if path.stem == 'directions' and (not spread or float(spread.group(1)) >= 8):
        raise ValueError('Directions have inconsistent shoulders. Redraw directions with one fixed body, then match reactions to it.')


def measure(name, env):
    out = run('verify.py', name, env=env)
    moved = re.search(r'moves ([\d.]+) rendered px', out)
    match = re.search(r'weakest palette match: \S+ at ([\d.]+)%', out)
    width = re.search(r'worst width change: \S+ at ([\d.]+)%', out)
    if not all((moved, match, width)):
        raise ValueError('Verification did not return all three metrics; no atlases were installed.')
    return float(moved[1]), float(match[1])/100, float(width[1])/100


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name', help='character slug (letters, numbers, hyphens, underscores)')
    root = Path(os.environ.get('MASCOT_ROOT', Path.cwd())).resolve()
    parser.add_argument('--dest', default=os.environ.get('MASCOT_DEST', str(root/'public'/'mascots')))
    parser.add_argument('--force', action='store_true', help='ignore cache and rerun all checks')
    parser.add_argument('--skip-generate', action='store_true', help=argparse.SUPPRESS)  # old callers
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', args.name):
        parser.error('name must be a slug, not a filesystem path')
    src = Path(os.environ.get('MASCOT_SRC', str(root/'characters'))).resolve()
    dest = Path(args.dest).resolve()
    sources = [src/args.name/f'{kind}.png' for kind in ('directions', 'reactions')]
    outputs = [dest/f'{args.name}-{kind}.webp' for kind in ('directions', 'reactions')]
    cache = root/'.cache'/'page-mascot'/f'{args.name}.json'
    missing = [str(p) for p in sources if not p.is_file()]
    if missing:
        parser.error('Missing source sheets: ' + ', '.join(missing) +
                     '. Generate them with Codex native image generation first (see SKILL.md). No API key is needed.')
    env = {**os.environ, 'MASCOT_ROOT': str(root), 'MASCOT_SRC': str(src)}
    try:
        inputs = fingerprint(sources)
        if not args.force and cache_matches(cache, inputs, outputs):
            print(f'{args.name}: unchanged verified atlases reused (cache hit).')
        else:
            validate_sources(sources)
            for path in sources:
                screen(path, env)
            dest.mkdir(parents=True, exist_ok=True)
            # Build and verify in isolation. A rejected build leaves live assets intact.
            with tempfile.TemporaryDirectory(prefix=f'.{args.name}-', dir=dest) as staging:
                build_env = {**env, 'MASCOT_DEST': staging}
                run('build.py', args.name, '--anchor', 'shoulders', env=build_env)
                moved, match, width = measure(args.name, build_env)
                if moved > BOOP_LIMIT or match < PALETTE_LIMIT or width > WIDTH_LIMIT:
                    raise ValueError(f'{args.name}: verification failed (shift {moved:.2f}px; palette {match:.0%}; width change {width:.0%}). '
                                     'Inspect/redraw the reactions sheet using directions as reference, then rerun. Existing atlases are unchanged.')
                for output in outputs:
                    (Path(staging)/output.name).replace(output)
            save_cache(cache, inputs, outputs)
        print(f'{args.name} is ready:\n' + '\n'.join(f'  {p}' for p in outputs))
        print('Integrate <Mascot /> into the requested page and check pointer tracking and click reactions.')
    except (PackageNotFoundError, ModuleNotFoundError) as exc:
        parser.exit(1, f'Missing local build dependency: {exc}. Install {HERE / "requirements.txt"} in this Python environment.\n')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
