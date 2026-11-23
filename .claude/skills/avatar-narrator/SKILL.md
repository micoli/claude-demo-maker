---
name: avatar-narrator
description: Make reusable Blender avatars read a text or voice recording, with lip sync, blinks and facial expressions. Use for talking heads, virtual presenters, narrated feature videos or a diverse bank of 10 male, 10 female and 10 neutral/androgynous low-poly shoulder-up avatars. Reuse cached mouth images to avoid rendering every video frame.
---

# Avatar narrator

Work from the demo-maker project root. This skill owns the avatar bank, Kokoro speech, Rhubarb lip sync and Blender render. Store generated jobs under `.scratch/videos/<slug>/`. Keep generated videos out of Git.

Run Blender with Eevee on the host. Use Node.js 22+, Python 3 and FFmpeg with libass and drawtext. Circular portraits additionally require Pillow. The bundled Rhubarb 1.14 binary is for macOS. On another platform, set `RHUBARB_BIN` to a compatible installation. Set `BLENDER_EXE` if Blender is not on PATH or installed at the standard macOS location. Set `AVATAR_FONT` to a local font file if the system cannot resolve Arial. For speech synthesis, Kokoro runs on the local Docker service at port 8880.

## Explain actions before executing them

- Before **every tool call or coherent group of calls**, send a concise user-facing message in the user's language stating the concrete action, its purpose, and the files or application affected. Announce first, execute second.
- For each background job, give its PID, requested output count, current phase and log path immediately after launch. Save this information in a process record, and explain how to follow the log (`tail -f <log>`). Report termination, success or failure explicitly; never equate launching a job with finishing it.
- Name downloads and their official sources before starting them. State size when verified; never invent an estimate. Explain whether an installation changes Blender preferences or only project-local dependencies.
- During long operations, report progress at least every 60 seconds. State what has finished, what is running, and what remains uncertain. Never silently wait through a long download or render.
- After a failure, explain the observed error and the next proposed action before retrying. Stop repeated attempts that provide no new evidence.
- Distinguish models generated, GLBs exported, renders inspected and speech actually tested. Never claim a pending action is completed.
- If the user interrupts, give the exact current state before resuming. Existing authorization remains valid; ask only for a missing decision or a genuinely blocked permission.

## Required model source: MakeHuman / MPFB

Use **MPFB** (https://github.com/makehumancommunity/mpfb2) for the replacement avatars. The user rejected the original procedural busts. Do not regenerate them, reuse their primitive faces, or present them as MPFB output.

Read [references/mpfb.md](references/mpfb.md) for the migration and validation procedure. For a new visual style, first make one male and one female MPFB pilot and show both in Blender or a local GLB viewer. The user has now authorized expanding the existing MPFB pilots into the full thirty-avatar bank; continue without asking for this decision again. Preserve the existing image-state cache strategy, adapting its facial controls to the MPFB shapes.

## Visual contract

- Maintain 30 reusable fictional adult presenters: `man-01..10`, `woman-01..10` and `neutral-01..10`. The neutral group uses a deliberately balanced/androgynous visual appearance with varied adult ages, facial shapes, skin tones and hairstyles.
- Dress each MPFB avatar in a fitted shirt, polo, blouse or T-shirt from the bundled wardrobe. Inspect the neckline and shoulders for skin clipping in front and three-quarter views. Keep the garment still during head motion.
- Show only head, neck and shoulders. Keep the camera, lighting and torso fixed. Keep the head fixed by default for standalone narration. For dialogue, use the subtle, explicitly timed gestures described below.
- For this bank, give the female characters a visibly feminine art direction: tapered jaw and chin, softer cheek contours, a more slender neck, subtly shaped brows, and varied hairstyles with the face unobstructed. Preserve distinct adult ages, facial identities and skin tones. Apply the reproducible face targets in `assets/profiles.json`; do not rely on changing hair or colors alone. The user found the first female pass too androgynous.
- Render a neutral, open-eyed frame at full size to verify that the eyes and eyebrows have their intended colors. Pack every used image texture in new Blender sources. When an existing source refers to missing images, the renderer restores them from its matching GLB and stops if an image cannot be recovered.
- Choose classic professional hairstyles in natural colors and understated clothing without visible logos. Compare frontal renders at the final portrait size. Give speakers distinct hair silhouettes that are visible from the front.
- Keep **both eyes completely unobstructed by hair** for every avatar. No fringe, bangs or strands in front of either eye. Prefer short, swept-back, tied-back or otherwise clear-face hairstyles. Reject or adjust any hairstyle that overlaps an eye in the front or three-quarter review views; check again after fitting it to a different face and when testing expressions.
- Use low-poly anatomical proportions with a shaped jaw, nose, lips, ears, eyelids and simple hair geometry. No photoreal textures or expensive hair simulation.
- Use `neutral`, `warm`, `concerned`, `surprised` expressions through MPFB facial shape keys, plus blinks and Rhubarb mouth shapes A–H/X. The facial cache uses discrete states. Head gestures add a pose to a facial state only when enabled.
- Treat the old procedural bank as rejected; new MPFB pilots require visual approval. Show GLBs before declaring the visual style approved. Do not claim that thirty people represent every ethnicity; use the broad design references in `catalog.json` to diversify appearances. Choose voice and language independently of appearance.

## Inspect or rebuild the bank

The canonical MPFB bank is `assets/avatar-mpfb/catalog.json`, with IDs `man-01..10`, `woman-01..10` and `neutral-01..10`. Each entry points to a `.blend`, a GLB, a neutral preview, and per-avatar provenance. Read `assets/profiles.json` for the thirty reproducible adult appearance profiles and their outfits. The bundled hairstyles and their sources are listed in `assets/hairstyles/catalog.json`. To override one build, pass `--outfit shirt|polo|blouse|t-shirt` with `--only <avatar-id>`. Vary macro proportions, age, face-detail targets, skin, shirt and hair colors; hair choice must preserve eye clearance.

Use `scripts/build_mpfb.py --bank` to build the full bank, add `--group neutral` to build only the neutral group, or add `--only neutral-03` to correct one member. Without `--bank`, it builds review pilots. Dependency paths and the complete command are in `references/mpfb.md`. The old `scripts/build_bank.py` and `assets/avatar-bank/` contain rejected procedural prototypes; never regenerate or select them for new narrations. The renderer resolves standard IDs to the MPFB bank.

Use a separate headless Blender process with isolated user resources. Never reset or overwrite the user's live scene. If headless startup fails, preserve files and report the error.

Open the GLBs under `assets/avatar-mpfb/<id>/` in Blender or a local GLB viewer. The adjacent previews show front and three-quarter views.

## Turn text into narration

For text input, use the bundled `scripts/tts.mjs`.

1. Write `.scratch/videos/<slug>/script.json`:
   ```json
   {"voice":"af_heart","speed":1,"leadIn":0.8,"pad":0.4,"lines":[{"id":"s1","text":"Welcome to Urbtopia."}]}
   ```
2. Run `node .claude/skills/avatar-narrator/scripts/tts.mjs <slug>` to produce `voice.wav`, `timeline.json`, `cues.json`, and subtitles. Set `language` and a compatible `voice` in `script.json`. The command selects PocketSphinx for English and the phonetic recognizer for other languages. Review non-English lip sync manually.
3. For an existing recording, convert it to mono PCM WAV with FFmpeg and generate Rhubarb JSON directly. Keep an audible recording: a text alone is not a source of accurate mouth timings.

Do not regenerate speech when only the chosen avatar or expression schedule changes.

## Dialogue

Use `scripts/dialogue.mjs <dialogue.json>` with the bundled Docker-hosted Kokoro integration. Set `language` to a tag such as `fr-FR` or `en-GB`. Each actor supplies an `avatar` ID and a `label`, and each line supplies `id`, `speaker` and `text`. Optional `spokenText` controls pronunciation while preserving the original subtitle.

- French defaults to `ff_siwis` for both actors. Use speed 0.94 and pitch 0.87 for `man-*`, and speed 1.01 and pitch 1 for the other profiles. These are the approved manager and Camille settings. Actors may explicitly set `voice`, `speed` and `pitch`.
- English uses the British Kokoro voices. For `woman-*` choose from `bf_alice`, `bf_emma`, `bf_isabella`, `bf_lily`. For `man-*` choose from `bm_daniel`, `bm_george`, `bm_fable`, `bm_lewis`. For `neutral-*` choose at random from all eight. Draw once per actor and keep the selection in `voice-selection.json` across reruns. An explicit English `voice` must belong to the actor's pool. Speed and pitch default to 1.

`--audio-only` prepares the voice track and subtitles. The full command uses the bundled macOS Rhubarb by default. Override it with `RHUBARB_BIN` or the job's `rhubarbBin`. Align the final audio after any voice adjustments, using PocketSphinx for English and the phonetic recognizer for French.

Run from the project root:

```bash
node .claude/skills/avatar-narrator/scripts/dialogue.mjs .scratch/videos/<slug>/dialogue.json
```

Set `"layout":"circles"` for 2–4 portraits with a tight crop showing the whole head and just the top of the shoulders. Use a muted outline in silence and a contrasting outline only for the active speaker. Use a stable random background per actor from `assets/background/`. Specify an actor's `background` filename for a fixed choice. The default `panels` layout accepts two people. Circular portraits default to `"lighting":"soft"` for reduced highlights. Use `"lighting":"studio"` on a job or actor to select the original light. The rendered-state cache distinguishes both options.

For dialogue, give speakers and listeners occasional small head gestures with `headMotion`. Use an array of intervals in absolute dialogue seconds. For example, `[{ "start": 12.76, "end": 13.56, "pitch": 3.5 }]` creates one nod. `pitch` nods, `tilt` inclines sideways and `turn` turns left or right. Angles are in degrees and at most 6 in either direction. Intervals for one actor cannot overlap. The motion returns to rest at each interval boundary and uses half-degree poses on the MPFB neck. Preview the actual result with its voice track before adopting a motion style. Set the actor's `expressions` to intervals with `start`, `end` and `value` (`neutral`, `warm`, `concerned` or `surprised`). For blinking, the actor can override `blinkStart` in seconds or set `blink: false`.

Use `warm` for a slight smile at greetings, positive explanations and listening reactions. Alternate small left and right `tilt` gestures of roughly 1–2.5° over about a second, with quiet gaps and staggered timings between actors. Add a small nod when it serves the exchange. Keep blinks enabled and inspect close-ups for natural mouth movement.

## Render a narration

Write `avatar.json` next to the cues. Resolve all paths relative to this JSON file. Use the measured `timeline.json.total` as `duration`, plus any desired silent tail:

```json
{
  "avatar":"woman-03",
  "cues":"cues.json",
  "output":"hero",
  "duration":12.4,
  "fps":25,
  "size":540,
  "samples":32,
  "blink":true,
  "expressions":[{"start":0,"end":2,"value":"warm"}]
}
```

```bash
node .claude/skills/avatar-narrator/scripts/render.mjs .scratch/videos/<slug>/avatar.json --plan
node .claude/skills/avatar-narrator/scripts/render.mjs .scratch/videos/<slug>/avatar.json
```

The plan lists frames, unique states and missing cached images without rendering. Output is `hero/f_0001.png` onward, transparent RGBA, plus `hero/avatar-render.json`. Use a dedicated output directory; the renderer refuses to overwrite directories it does not own.

For a standalone preview, assemble the PNG sequence and audio with FFmpeg (MP4 has an opaque background; retain PNGs for transparent compositing):

```bash
ffmpeg -y -framerate 25 -i .scratch/videos/<slug>/hero/f_%04d.png -i .scratch/videos/<slug>/voice.wav -vf 'format=yuv420p' -af apad -shortest -c:v libx264 -c:a aac .scratch/videos/<slug>/avatar.mp4
```

## Keep rendering fast

Read [references/cache.md](references/cache.md) before changing the renderer or estimating costs. Never rerender the entire timeline in Blender. The bank is persistent; the rendered-state cache lives under `.scratch/videos/avatar-cache/`. Render only states the narration actually uses, in a single Blender process. Reuse the same cached pixels across texts, languages, frame rates and durations when the avatar and render settings match.

Default to 540 px and 32 Eevee samples. Test changes on a short line before rendering a full narration. Never promise a speedup in seconds until measured on this machine.

## Check and report

- Verify 10 male, 10 female and 10 neutral bank entries and existing source/GLB files.
- Inspect front and three-quarter GLB views, mouth closed/open, blink and each used expression. Require both eyes to remain fully visible with no hair in front of them. Flag clipping or visual defects; do not declare art quality approved automatically.
- Verify transparent PNG dimensions, frame count `ceil(duration*fps)` and agreement with audio. Check pauses use mouth X and the head stays still.
- Rerun the same job: `missingStates` must become zero, with no Blender render launched.
- Report avatar IDs, output paths, actual rendered-state counts and anything unverified. Do not describe structural validation as an end-to-end speech test.
