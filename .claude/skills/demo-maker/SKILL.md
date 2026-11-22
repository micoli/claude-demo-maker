---
name: demo-maker
description: Create a narrated web product demo. Use when the user wants to record a browser walkthrough with Playwright, write a dialogue for one to four presenters, and deliver an MP4 with speaking avatars over the capture.
---

# Demo maker

Work from the project root with the sibling [avatar-narrator skill](../avatar-narrator/SKILL.md) installed. Keep all job files in `.scratch/videos/<slug>/`. Install the avatar rendering dependencies before rendering. For browser capture, run `npm install --prefix .scratch/demo-playwright playwright@1.64.1` and `npm --prefix .scratch/demo-playwright exec -- playwright install chromium` from the project root if Playwright or Chromium is missing.

## Get the brief

Ask for the subject and language of the demo. Clarify the audience, the takeaway, the starting URL and state, the steps to show and the intended duration. Make a short brief with a clear end state. Ask only for details still missing. Distinguish the language of the spoken demo from that of the conversation.

## Record the walkthrough

Run the capture below as an ongoing process and tell the user when Chromium is ready. They control the browser. Ask them to click **Record** in Playwright Inspector, perform the walkthrough in the demo tab, stop recording actions, copy the generated JavaScript into an editor file under the job directory, then click **Resume** in Inspector to finish the video. Keep the main browser tab open until the capture has been saved.

```bash
node .claude/skills/demo-maker/scripts/capture.mjs .scratch/videos/<slug> "https://example.com"
```

Use the main tab for the walkthrough because Playwright saves one video per page. For an app that needs sign-in, accept a local Playwright storage state via `DEMO_STORAGE_STATE` so the sign-in stays outside the capture and replay. Keep that state and test data local. Use the authorized demo environment and avoid recording real credentials.

Preserve the original `capture.webm`. Adapt the recorded JavaScript actions into `replay.mjs` with `export default async function replay(page) { ... }`; the capture runner already opens the URL and manages Chromium. Review generated literals for sensitive data before reusing the file. Keep waits for visual states and add deliberate pauses if a replay should leave time for narration. To make a new take, run the same command in a new job directory with the replay file path as the third argument.

## Propose the dialogue

Review the recording, including its duration and screenshots at key beats. Propose one to four speakers based on the brief and honor any explicit count. Assign roles and avatar IDs from the catalog. Show a short table of approximate start time, visible action, speaker and line in the requested language. Let the user adjust it and wait for explicit approval of the dialogue before rendering. Keep enough time for each spoken line and for viewers to read the UI.

Save the approved dialogue as `dialogue.json` beside `capture.webm`. Use the avatar-narrator actor and voice schema. Follow its [Dialogue instructions](../avatar-narrator/SKILL.md#dialogue) for voice, blinking, expressions and head motion. Set `language` to a BCP 47 tag and set `start` on every line in seconds from the start of the capture. French and English have default voices. For other languages, check Kokoro support and set a compatible voice explicitly for every actor.

By default, give speakers and listeners a slight smile with the `warm` expression and a light side-to-side sway with `headMotion`. Alternate small positive and negative `tilt` values around visible actions and speaker changes, leaving pauses between gestures and staggering them across actors. Use small nods (`pitch`) for specific reactions and keep automatic blinks. Time expressions and gestures from the start of the capture. Use the Avatar Narrator dialogue guidance to keep the motion subtle.

```json
{
  "language": "fr-FR",
  "actors": {
    "host": {
      "avatar": "woman-03",
      "label": "Camille",
      "headMotion": [
        { "start": 1.4, "end": 2.3, "tilt": 2 },
        { "start": 3.1, "end": 4.1, "tilt": -1.5 }
      ],
      "expressions": [{ "start": 1.2, "end": 2.6, "value": "warm" }]
    }
  },
  "lines": [
    { "id": "intro", "speaker": "host", "start": 1.2, "text": "Voici comment créer votre premier projet." }
  ]
}
```

## Render and check

```bash
node .claude/skills/demo-maker/scripts/render.mjs .scratch/videos/<slug>/dialogue.json
```

The render uses the capture as its timeline, synthesizes speech, checks for overlaps and overruns, renders transparent talking avatars and overlays them at the lower right. If timings fail, shorten the dialogue or adjust starts against the capture. Return a substantial rewrite for approval. Use `--audio-only` on the same command to check timing without rendering the avatars.

Inspect the MP4 with sound, check the first and last beats and speaker switches, and confirm thumbnails do not cover the demonstrated controls. Report the final `demo.mp4`, the original capture, the replay script and the `dialogue.srt` sidecar. If any stage is incomplete, report what was produced and the specific blocker.
