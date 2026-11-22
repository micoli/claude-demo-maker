# Docker

Run from the repository root. The repository is mounted at `/work`, so jobs still live under `.scratch/videos/`.

| Image | Contents | Used by |
| --- | --- | --- |
| `demo-maker-render` (`docker/render/Dockerfile`) | Node 22, Blender 5.2.2 (Eevee on Mesa), FFmpeg, Rhubarb 1.14, Pillow | `avatar-narrator` and `demo-maker/render.mjs` |
| `ghcr.io/remsky/kokoro-fastapi-cpu:v0.10.0` | Kokoro text-to-speech (upstream image) | speech synthesis |

Not dockerized: `demo-maker/capture.mjs` (Playwright Inspector needs a display) and `build_mpfb.py` (bank already versioned).

The render image is pinned to `linux/amd64` because Blender and Rhubarb only ship Linux x64 builds. It is emulated on Apple Silicon, so expect much slower renders than the native macOS Blender (about 15 s per avatar state versus a few seconds). For long dialogues, run `render.mjs` on the host and keep Docker for the other tools.

```bash
docker build -f docker/render/Dockerfile -t demo-maker-render .
docker network create demo-maker
docker run -d --name kokoro --network demo-maker ghcr.io/remsky/kokoro-fastapi-cpu:v0.10.0
```

```bash
docker run --rm -v "$PWD":/work --network demo-maker -e KOKORO_URL=http://kokoro:8880 \
  demo-maker-render node .claude/skills/demo-maker/scripts/render.mjs .scratch/videos/<slug>/dialogue.json
```
