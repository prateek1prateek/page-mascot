---
name: page-mascot
description: Add a cursor-tracking chibi mascot to a React page. Reuse a ready-made character or create matching sprite sheets with Codex native image generation, build aligned atlases, and integrate the component. Use for website mascots or a personal photo-based avatar, not ChatGPT Work pets.
---

# Page Mascot for Codex

Finish with a working mascot on the requested page, not just images or a snippet.
A character needs two square 3×3 sheets: head directions and click reactions.

## Choose the shortest route

- **Existing character:** read [reference/characters.md](reference/characters.md), choose
  the requested character (or a fitting one), and reuse its two WebP atlases. Skip Python
  and image generation entirely. Reuse project-local files before downloading both missing
  sheets concurrently from the URLs in that reference.
- **New character or likeness:** use Codex's native image generation as below. First check
  for usable source sheets in `characters/<name>/`; resume instead of regenerating them.
- **Layout/code changes only:** keep the current art and edit the page directly.

## Generate new art with Codex

Use the session's built-in `image_gen` capability. Follow the installed `imagegen` skill
when available and the tool's current schema. Do not call an Images/Responses API, look
for API credentials, install the OpenAI SDK, or choose a model for the user. The build
scripts are local image processing only. If the native tool is unavailable, explain that
custom generation is unavailable in this session and offer an existing character or
user-provided sheets; do not silently change providers or switch to a paid API.

1. Describe the character in one sentence: colours plus two or three identifying features.
   Keep shoulders visible; tie long hair back. Avoid held props and features wider than the
   head. Use the user's requested style; otherwise use `colour`.
2. Read the DIRECTIONS (or photo REFERENCE) and EXPRESSIONS prompts in
   [reference/prompts.md](reference/prompts.md). Keep the 3×3 cell order, fixed body, matching
   scale, and empty margins. Request square PNGs, normally around 1024px; larger sheets add
   generation and build work. Set **`transparent_background: true`** on the native call.
3. Generate directions first. If using a local reference photo, inspect it with `view_image`
   before generation and include it using the reference mechanism the tool exposes. For a
   new character without a reference, omit reference arguments.
4. Inspect the directions result, then generate reactions using it as the visual reference.
   These calls are dependent: do not run them in parallel. Use local reference paths when
   supported; otherwise include the smallest recent-image count that contains the target.
   Never supply both reference mechanisms. Preserve the character, shoulders and cell size.
5. Copy the returned images into the project as `characters/<name>/directions.png` and
   `reactions.png`. Use the actual paths returned by the tool, not guessed output paths;
   never leave project assets only in Codex's generation directory. Both sheets must have
   the same dimensions. Inspect alpha and art before building; a painted checkerboard is
   not transparency. Correct it with the native image tool, preserving the character.

Use one directions call and one dependent reactions call for the initial pair. Inspect and
repair only the failed sheet when possible; a redesigned directions sheet may also need
new matching reactions. After two unsuccessful repair rounds, report the remaining issue
and offer a simpler description or existing character instead of retrying indefinitely.

## Build and verify locally

`<skill-dir>` is the absolute directory containing this file. Run commands from the target
project root. Reuse its Python environment if Pillow, NumPy and SciPy are installed;
otherwise create a project-local virtual environment and install
`<skill-dir>/scripts/requirements.txt` once. No Python dependencies are needed for existing
WebP characters.

```bash
python3 <skill-dir>/scripts/mascot.py <name>
# If static assets live elsewhere:
python3 <skill-dir>/scripts/mascot.py <name> --dest static/mascots
```

The command screens both sources, aligns them, verifies shift/palette/width, then installs
verified WebPs. Rejected builds leave existing atlases intact. A content-based cache reuses
unchanged verified outputs; changed sources, scripts, settings, dependencies or output bytes
invalidate it. `--force` reruns checks. The old `--skip-generate` flag remains a no-op alias.
`MASCOT_ROOT`, `MASCOT_SRC`, and `MASCOT_DEST` can override the project/source/output paths.

A successful metric check does not prove head-turn direction or visual identity. Inspect
left and right cells (middle row, first/third columns): they must face the viewer's left
and right. Compare the centre direction and a reaction for identity, scale and clipping.
Read [reference/design-rules.md](reference/design-rules.md) only for diagnosed art/alignment
problems. Preserve sources so later code edits or rebuilds need no new generation.

## Put it on the page

Inspect the target framework and requested placement. For React, **copy the bundled
`mascot.tsx` into the project's component directory**; it depends only on React and adds no
package install. Reuse an already installed `page-mascot` package if appropriate. In a
React Server Components project, place `'use client'` at the top of the copied component.
Do not install React into an unrelated framework without first resolving the integration.

```tsx
import { Mascot } from './components/mascot'

<Mascot
  directions="/mascots/fox-directions.webp"
  reactions="/mascots/fox-reactions.webp"
  label="fox"
/>
```

Use the project's real import and asset paths, including its deployment base path. Place
it where requested; otherwise use the header or hero. Optional props are `size` (140),
`label`, and `className`. Keep the button's accessible label and reduced-motion behavior.

Run the relevant project checks. If browser tooling is available, verify assets load,
head turns track the pointer, clicks react without a jump, and the narrow layout fits.
Report what changed and where, which art was reused/generated, and any untested behavior.
