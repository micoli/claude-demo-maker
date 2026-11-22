import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, renameSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const [jobFile, mode] = process.argv.slice(2);
if (!jobFile || (mode && mode !== '--audio-only')) {
  throw Error('Usage: render.mjs dialogue.json [--audio-only]');
}
const input = resolve(jobFile);
const dir = dirname(input);
const job = JSON.parse(readFileSync(input, 'utf8'));
const actors = Object.keys(job.actors ?? {});
if (actors.length < 1 || actors.length > 4) throw Error('Use 1 to 4 presenters');
if (!Array.isArray(job.lines) || job.lines.some(line => !Number.isFinite(line.start) || line.start < 0)) {
  throw Error('Set each line start to a nonnegative timestamp in seconds');
}

const run = (cmd, args, stdio = 'pipe') => execFileSync(cmd, args, { cwd: dir, encoding: 'utf8', stdio });
const probe = file => JSON.parse(run('ffprobe', ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', file]));
const capture = 'capture.webm';
const source = probe(capture);
const duration = Number(source.format.duration);
if (!source.streams.some(stream => stream.codec_type === 'video') || !(duration > 0 && Number.isFinite(duration))) {
  throw Error('Capture must contain a video stream with a measurable duration');
}
const dialogue = fileURLToPath(new URL('../../avatar-narrator/scripts/dialogue.mjs', import.meta.url));
run(process.execPath, [dialogue, input, '--overlay', String(duration), ...(mode ? [mode] : [])], 'inherit');

if (!mode) {
  const fps = 25;
  const inputs = ['-i', capture];
  for (const id of actors) {
    inputs.push('-framerate', String(fps), '-start_number', '1', '-i', join('actors', id, 'f_%04d.png'));
  }
  inputs.push('-i', 'voice.wav');
  const filters = [
    '[0:v]scale=1600:900:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1600:900:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25,tpad=stop_mode=clone:stop_duration=0.08[base]',
  ];
  let base = 'base';
  for (const [index] of actors.entries()) {
    const next = `v${index}`;
    filters.push(`[${index + 1}:v]format=rgba,scale=220:220[a${index}]`);
    filters.push(`[${base}][a${index}]overlay=W-w-20-${index}*(w+16):H-h-20[${next}]`);
    base = next;
  }
  const staging = mkdtempSync(join(dir, '.demo-render-'));
  const temporary = join(staging, 'demo.mp4');
  try {
    run('ffmpeg', [
      '-v', 'error', ...inputs, '-filter_complex_threads', '1', '-filter_complex', filters.join(';'),
      '-map', `[${base}]`, '-map', `${actors.length + 1}:a`, '-t', String(duration),
      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', temporary,
    ]);
    const result = probe(temporary);
    const video = result.streams.find(stream => stream.codec_type === 'video');
    if (video?.width !== 1600 || video?.height !== 900 || video.r_frame_rate !== '25/1' ||
        !result.streams.some(stream => stream.codec_type === 'audio') ||
        Math.abs(Number(result.format.duration) - duration) > 0.1) {
      throw Error('Rendered MP4 failed media checks');
    }
    const output = join(dir, 'demo.mp4');
    renameSync(temporary, output);
    console.log(output);
  } finally {
    rmSync(staging, { recursive: true, force: true });
  }
}
