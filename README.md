<img src=".github/fox.png" width="160" alt="">

# page-mascot for Codex

A Codex-native fork of [nilbuild/page-mascot](https://github.com/nilbuild/page-mascot): an interactive character that watches the cursor and reacts when clicked.

Custom art uses Codex’s built-in image generation. No API key, OpenAI SDK, model configuration, or automatic paid API fallback. Existing mascots need no generation or Python.

**[See the fifty-two &rarr;](https://koboyo.com/page-mascot)**

## Install

```bash
npm i page-mascot
```

## Use existing mascots

Pick a character on the [demo page](https://koboyo.com/page-mascot) and download its two
sheets into `public/mascots`, then point the component at them:

```tsx
import { Mascot } from 'page-mascot'

<Mascot
  directions="/mascots/fox-directions.webp"
  reactions="/mascots/fox-reactions.webp"
/>
```

The paths are whatever your app serves, so imported images work too.

Or let an agent do it, once the skill below is installed:

```
$page-mascot put the fox on my page
```

## Draw your own

Install the skill:

```bash
npx skills add nilbuild$page-mascot --skill page-mascot --global --yes
```

Then ask your agent:

```
$page-mascot a chibi otter with chocolate-brown fur
$page-mascot make one that looks like me        [attach a photo]
$page-mascot a chibi fox, in the riso style
```

It draws the nine directions and nine expressions, builds them into two aligned sheets,
checks the character does not jump between them, and puts the component on your page, with
the same two props as above.

Codex generates directions first, then matching reactions using the directions as a
reference. It copies both transparent PNGs into the project, builds and verifies atlases,
and integrates the bundled React component. Copying that component avoids a package
installation; `npm i page-mascot` above still installs the upstream React package.

## Local build (no image API)

For source sheets already in `characters/<name>/`, from the target project root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r <skill-dir>/scripts/requirements.txt
.venv/bin/python <skill-dir>/scripts/mascot.py fox
```

`<skill-dir>` is the absolute path to `skills/page-mascot` in your installed copy.
Reuse an existing Python environment when these dependencies are already installed.
Use `--dest static/mascots` for a different asset directory, or `--force` to bypass the
verified-build cache. `--skip-generate` is accepted for older callers but is no longer
needed. The API generator and its `--describe`, `--reference`, `--style`, `--only`,
`--key`, and `--retries` flags have been removed: give art instructions to Codex instead.

Speed improvements:

- Reuse existing art and the bundled React component before installing anything.
- Load the character catalog or art prompts only when that route needs them.
- Resize each alignment mask once per scale instead of once per offset (81× fewer resizes
  in that search; this is not an 81× whole-build claim).
- Skip screen/build/verify only when source, implementation, environment settings,
  dependencies and verified output hashes still match.
- Verify staged builds before replacing live atlases.

A single local macOS ARM64 benchmark on the shipped 1254×1254 fox sheets took
20.37s with upstream commit `76a44ed` and 12.07s with this fork; the unchanged cached
run took 0.064s. Both output WebPs were byte-for-byte identical to upstream. This
measures local processing, excludes image generation, and is not a latency guarantee.

The numerical gates remain 2px maximum shift at 140px display size, 22% minimum palette
match, and 12% maximum shoulder-width change. Visual inspection is still needed for
mirrored head turns and likeness. Source prompts and upstream design notes remain under
[skills/page-mascot/reference](skills/page-mascot/reference).

## Development checks

```bash
python3 -m unittest discover -s tests -v
npm ci
npm run check:skill
npm run typecheck
npm run lint
npm run build:site
```

Python tests use the local-build requirements above. They do not call an image API.

## Props

| prop | default | |
| --- | --- | --- |
| `directions` | none | path to the directions sheet |
| `reactions` | none | path to the reactions sheet |
| `size` | `140` | px, square |
| `label` | `'mascot'` | what a screen reader calls it |
| `className` | | |

Tracking switches off without a fine pointer, and the click squash honours
`prefers-reduced-motion`.

## How it works

Each character is two 3×3 sprite sheets: nine head directions, and nine expressions.

![the two sheets that make up one character](.github/sheets.png)

The pointer's angle picks a cell on the directions sheet, with a dead zone so the head
settles when the cursor is close. A click shows a cell from the reactions sheet for half a
second.

The same character can be drawn in six styles: colour, ink, sketch, riso, paper and pixel.
Only the rendering changes, so the alignment holds.

![the same fox drawn in six styles](.github/styles.png)

## License

MIT © [Kamran Ahmed](https://kamran.fyi)
