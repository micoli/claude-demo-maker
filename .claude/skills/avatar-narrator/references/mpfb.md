# MPFB migration

## Scope and current state

The user chose MakeHuman / MPFB after rejecting the initial procedural busts. Use MPFB anatomy and its own facial targets as the source. Do not substitute another model source without explaining the change and obtaining a decision.

At the start of the migration, MPFB was not installed and the twenty existing bank models were procedural prototypes. A downloaded archive is not an installed addon, and installed software is not a generated or visually approved avatar. Update the state below only from observed results.

## Explain the work

Before each action, say what will happen and why. In particular announce dependency detection, downloads, extraction, addon registration, model generation, source replacement, exports, renders and opening the viewer. Give progress during operations lasting more than 60 seconds. After any error, explain the error and next step before retrying. Never leave the user waiting without knowing what is running.

## Dependencies and provenance

- Project: https://github.com/makehumancommunity/mpfb2
- Official install guide: https://static.makehumancommunity.org/mpfb/docs/getting_started.html
- Release source identified on 2026-11-22: v2.0.18, https://github.com/makehumancommunity/mpfb2/archive/refs/tags/v2.0.18.zip
- Official asset packs: follow the asset-pack link from the install guide. Obtain system assets (eyes, teeth and skin), appropriate hair, visemes and face units. Inspect licenses for every pack; core bundled assets are CC0, addon code has its own GPL license. Never describe the addon code as CC0.
- Record the exact release, download URLs, checksums, asset author/license and original asset identifiers beside the generated bank. Keep license notices with distributed derived models.
- Prefer isolated project-local addon loading for headless generation. Explain any proposed persistent installation or Blender preference change first. Preserve the user's live scene.
- If shell networking fails, use an available browser download capability. Do not run download subprocesses through the live Blender connection to evade a denied network permission. If all authorized access fails, report the dependency blocker and preserve the migration work.

## First two pilots

1. Inspect actual MPFB source/API of the chosen installed version; use its sample scripts. Do not guess operator names or mesh vertex ranges.
2. Create one adult male and one adult female with natural face proportions and distinct appearances. Show only the head, neck and shoulders, with plain clothing and hair that leaves both eyes completely unobstructed. Reject bangs or strands in front of either eye. Keep the camera, head and gaze fixed.
3. Preserve the facial topology and the correspondence of eyes, teeth and lips. Crop or remove invisible lower-body geometry without losing shape-key vertex correspondence. Do not decimate a face before validating mouth closure, lip deformation and blinks.
4. Use simple materials, modest texture sizes and mesh hair suitable for low-poly rendering. Avoid strand simulation, subsurface-heavy shaders and unnecessary subdivision. Preserve silhouette and expression quality before minimizing triangles.
5. Load MPFB facial shapes and map them explicitly to `viseme_A..H/X`, blink and the expression states used by the cache. Retain original MPFB shapes in the editable source. Never reuse the old procedural lip geometry on a MPFB head.
6. Adapt `render_states.py` to these shapes. The legacy renderer manipulates objects named `lips`, `mouth`, `lid-*`, `brow-*`; this is not an MPFB facial rig. Do not declare MPFB lip sync functional until the adapter has rendered and inspected speech and blink states.
7. Save pilots under separate model keys such as `video/avatar-mpfb/pilot-man` and `video/avatar-mpfb/pilot-woman`, with matching `<id>.glb` filenames for the internal viewer. Preserve rejected originals until replacement is reviewable; never silently overwrite the existing twenty files.
8. Export a GLB with materials and facial morph targets, and render a front view plus a three-quarter view. Inspect mouth closed, mouth wide, blink and each expression. Check eyes are seated, teeth remain inside the mouth, hair does not intersect the face or obscure either eye in front and three-quarter views, and shoulders/clothing crop cleanly.
9. Open the pilot GLBs from the skill assets in Blender or a local GLB viewer. Show the result and collect visual feedback before producing the remaining eighteen.

## Complete the bank after visual approval

Build ten men and ten women with individually varied face shapes, ages, skin tones and hairstyles. Do not claim twenty characters represent all ethnicities. Keep voice selection independent of appearance. Save reproducible MPFB settings per character, source provenance, source `.blend`, GLB, preview and the facial-control mapping. Mark `generator: "mpfb"` and visual approval separately in the catalogue.

Reuse the existing cached-state approach. Include MPFB-generated source and the adapter in cache invalidation. Generate only required mouth/blink/expression images, not a Blender render per output frame. Measure a cold and warm run on the same short spoken clip, verifying zero missing states on the second run. Report the count of approved avatars separately from the target bank size.

## Reproducible pilot command

`scripts/build_mpfb.py` is the MPFB pilot generator. It requires an actual MPFB source checkout, a system-asset folder and the official `extra-targets` checkout. It refuses to run in a live Blender scene. The startup environment must isolate Blender user resources as shown below; the script registers MPFB only in that process and does not save preferences.

```bash
BLENDER_USER_RESOURCES="$PWD/.scratch/videos/mpfb-source/blender-user" \
python3 .claude/skills/avatar-narrator/scripts/bl.py --script .claude/skills/avatar-narrator/scripts/build_mpfb.py -- \
  --mpfb-root "$PWD/.claude/skills/avatar-narrator/vendor/mpfb/mpfb2-2.0.18" \
  --assets "$PWD/.claude/skills/avatar-narrator/vendor/mpfb/system-assets" \
  --targets "$PWD/.claude/skills/avatar-narrator/vendor/mpfb/extra-targets-main"
```

Use `--only pilot-man` or `--only pilot-woman` for a correction. Sources and exports are written under `assets/avatar-mpfb/<pilot-id>/`. The outputs include `avatar.blend`, matching `<pilot-id>.glb`, `preview.png` and `provenance.json`. They remain pending visual approval.

The reference Rhubarb mapping is A→PP, B→SS, C→E, D→aa, E→O, F→U, G→FF, H→nn, X→sil. These are approximate categories; inspect real spoken clips and adjust when needed. Blender scene property `avatar_controls` carries the mapping and expression weights. `render_states.py` uses that property for MPFB sources instead of the old object-name conventions.

Run `render.mjs` with `avatar: "pilot-man"` or `"pilot-woman"` to exercise the cached PNG pipeline. Do not label untested pilot speech production-ready.

The system pack mirror can be slow. It supports HTTP byte ranges: a targeted extraction may use the ZIP central directory to fetch required records, but must verify each decompressed entry's CRC and size, reject unsafe paths, and record the original official archive URL. Only mark the selected subset installed after integrity checks pass; do not claim the full system pack was installed.

## Migration checkpoint (2026-11-22)

- MPFB 2.0.18 successfully loaded and created human geometry in isolated headless Blender 5.2.2. The live scene and installed addon preferences were not modified.
- The official system ZIP was accessed by ranges; selected eyes, brows, lashes, teeth, tongue, short hair and ponytail files passed size and CRC checks. `assets/avatar-mpfb/system-assets.json` records file hashes. `dependencies.json` records source archive hashes; `licenses/` retains asset license texts.
- The two pilot GLBs and Blender sources were generated. Original procedural models remain in `avatar-bank/`; MPFB review pilots are in `avatar-mpfb/`. Visual approval is pending.
- A 2.4-second synthetic-cue test produced 60 frames from 7 unique mouth/blink/expression states. Mouth opening and eye closure were visually inspected. This was not a TTS or audio synchronisation test.
- The user subsequently authorized proceeding to the complete bank. Preserve the required clear-eye constraint and record any requested style corrections in the profiles/generator.

Measured cache check on the 2.4-second synthetic-cue pilot: 60 frames, 7 unique states; first run 4.32 seconds and warm run 0.28 seconds with zero missing states. These timings include startup/file work for this short test; do not extrapolate them into a guaranteed full-video speedup. The final artistic corrections keep the head-and-shoulders crop and replace the eye-obscuring bob with the official ponytail asset.

Final-source rerun: 7.08 seconds cold and 0.59 seconds warm, again 60 frames, 7 rendered states followed by 0. The bank-level `validation.json` stores the final check; timings vary between runs. Both GLBs loaded in the internal viewer and contain 67 facial morph channels. Two pilots are reviewable; the remaining eighteen and a complete spoken-audio test are still pending.

## Mandatory hair constraint

The user requires no hair in front of the eyes for any avatar. Both eyes must remain fully visible in the review views and expression tests. Short hair, swept-back hair and tied-back styles are suitable starting points, but check the actual fit on each face. Replace, refit or trim any offending fringe or strand before presenting the model. The current pilot choices are `short01` (male) and `ponytail01` (female); do not reintroduce the rejected eye-obscuring `bob01`.

## Full twenty-avatar bank

The user authorized this stage with “passe a la suite”. Do not stop to request the same expansion approval again. `assets/profiles.json` holds ten male and ten female adult profiles. Shapes vary through MPFB macro controls and modest nose/head targets, with independent skin, clothing and hair colors. These artistic parameters do not assert real people's ethnic identities.

Add `--bank` to the pilot command above. Outputs use `man-01..10` and `woman-01..10`, under `assets/avatar-mpfb/`. `--bank --only woman-03` rebuilds one profile. The catalogue is checkpointed after each completed avatar. The renderer uses the MPFB bank for standard IDs; rejected procedural prototypes are not a fallback.

The generator protects both eye bands from the front and +/-30 degree views by removing overlapping hair faces after transferring MPFB shape keys. This conservative geometry check supplements visual inspection; it does not replace inspecting the actual exported head, hair silhouette and alpha materials. Recheck all neutral front previews, representative three-quarter views and expression/blink states before marking checks complete. Avoid fringe-heavy hairstyles; `bob01` is rejected. Hair tint is baked into a small RGBA texture so the same colors and alpha export into GLB.

Give each long job a PID and a log immediately after launch. The current batch uses `.scratch/videos/mpfb-source/bank.log` and records its launch in `bank-process.json`. Users can run `tail -f .scratch/videos/mpfb-source/bank.log` from the project directory. Keep reporting progress at least once per minute. A recorded PID is not proof the process is still running; check output progress and completion markers.

After generation, verify the catalogue has exactly ten men and ten women, every source and GLB exists, facial morph targets are present, textures are embedded, both eyes remain unobstructed, and a second cached render produces zero missing states. Distinguish synthetic-cue animation tests from spoken-audio synchronization tests; unavailable TTS/Rhubarb dependencies must not be reported as tested.

## Female art-direction revision

The user found the first complete female group too androgynous and requested a more feminine appearance. The revised female recipes use narrower/less prominent jaw and chin targets, softer bilateral cheek volume, a slimmer neck, gently shaped eyebrows, and lower muscle macro values. Most hairstyles are tied back; retain the afro styles and one short style for variety. Both eyes must stay free of hair.

Keep these changes in `assets/profiles.json`; face morphology is the main change, rather than hair or makeup alone. Use `--bank --group woman` to rebuild all ten women, or `--bank --only woman-03` to change one. Group rebuilds merge into the twenty-entry catalogue and preserve the other group. MPFB's endpoint interpolation was checked: its configured range is -0.01..1.01, so 0 and 1 already work; do not introduce an unnecessary endpoint workaround.

Validate regenerated sources with:

```bash
python3 .claude/skills/avatar-narrator/scripts/bl.py --script .claude/skills/avatar-narrator/scripts/validate_bank.py -- --group woman
```

The validator checks native face controls, embedded GLB textures, fixed heads and geometric eye clearance in front and +/-30-degree views. It renders only missing or stale review images and merges the group results into the existing bank report. Reinspect the updated female front/three-quarter contact sheets and recheck facial animation after changing facial morphology. Leave spoken-audio validation explicitly pending until an actual voice track is tested.

Completed female revision: all ten updated profiles generated and verified with the twenty-entry catalogue preserved. Front and three-quarter review sheets were refreshed. Eye clearance passed for all ten revised sources. The updated `woman-10` cache check produced 60 frames from 8 cold state renders and 0 warm state renders. Contact sheets and a two-profile before/after comparison are in the bank’s `review/` folder; subjective art approval remains with the user.

## Neutral group extension

The user requested ten additional neutral/androgynous presenters, for a total of thirty: ten men, ten women and ten neutral appearances. These use IDs `neutral-01..10`. Their MPFB anatomy macro `gender` is 0.5; their catalogue group is explicitly `neutral`, rather than treating any nonzero numeric macro as male. Skin tones, continuous phenotype mixtures, adult ages, head/nose/chin details, hair styles and colors vary independently across the ten profiles.

Use `--bank --group neutral` to generate only this group, or `--bank --only neutral-03` to regenerate one. `validate_bank.py --group neutral` checks it and merges results with existing male/female checks. The validator derives the required catalogue IDs from `assets/profiles.json` and requires ten entries per group. The image renderer and dialogue accept all three ID ranges.

Keep the strict eye-clearance constraint. Prefer the existing short, afro, tied-back and shaved choices; do not use the rejected eye-obscuring bob. Inspect front and three-quarter review sheets and run a cold/warm synthetic facial animation test on representative new profiles. Reuse approved existing groups rather than rebuilding them for this extension. Record progress in `.scratch/videos/mpfb-bank-review/neutral.log` and its adjacent process record.

Neutral extension completed: all ten `neutral-*` sources, GLBs and front/three-quarter previews are generated, with thirty catalogue entries and geometric validation records. Visual contact sheets are `review/neutral-sheet.png` and `review/neutral-three-quarter-sheet.png`. Synthetic facial checks for `neutral-01` and `neutral-10` each produced 60 frames from 8 cold-state renders and 0 warm-state renders; a spoken voice track was not part of these checks. Neutral appearance IDs are distinct from the `neutral` resting expression, which every avatar supports.
