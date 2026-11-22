import { execFileSync } from 'node:child_process';
import { randomInt } from 'node:crypto';
import { existsSync, mkdtempSync, readdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const portraitSize = 156;
const borderWidth = 4;
const idleBorder = [99, 116, 135];
const speakingBorder = [33, 206, 154];

const backgroundDir = fileURLToPath(new URL('../../avatar-narrator/assets/background/', import.meta.url));
const imageExtensions = new Set(['.jpg', '.jpeg', '.png', '.webp']);

function selectBackgrounds(actors, settings, dir) {
  const images = readdirSync(backgroundDir, { withFileTypes: true })
    .filter(entry => entry.isFile() && imageExtensions.has(extname(entry.name).toLowerCase()))
    .map(entry => entry.name)
    .sort();
  if (!images.length) throw Error(`No portrait backgrounds in ${backgroundDir}`);

  const path = join(dir, 'background-selection.json');
  const previous = existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : {};
  const selected = new Map();
  const used = new Set();
  for (const actor of actors) {
    const explicit = settings[actor].background;
    if (explicit == null) continue;
    if (!images.includes(explicit)) throw Error(`Unknown portrait background: ${explicit}`);
    selected.set(actor, explicit);
    used.add(explicit);
  }
  for (const actor of actors) {
    if (selected.has(actor)) continue;
    const image = previous[actor];
    if (!images.includes(image) || used.has(image)) continue;
    selected.set(actor, image);
    used.add(image);
  }
  for (const actor of actors) {
    if (selected.has(actor)) continue;
    const available = images.filter(image => !used.has(image));
    const choices = available.length ? available : images;
    const image = choices[randomInt(choices.length)];
    selected.set(actor, image);
    used.add(image);
  }
  return selected;
}

function circularPortrait(lines) {
  const active = lines.map(({ start, end }) => `gte(T,${start})*lt(T,${end})`).join('+') || '0';
  const radius = portraitSize / 2;
  const distance = 'hypot(X-(W-1)/2,Y-(H-1)/2)';
  const rgb = [...'rgb'].map((channel, index) => {
    const fill = `${channel}(X,Y)`;
    const border = `if(${active},${speakingBorder[index]},${idleBorder[index]})`;
    return `${channel}='if(gte(${distance},${radius - borderWidth}),${border},${fill})'`;
  });
  const alpha = `a='255*clip(${radius}-${distance},0,1)'`;
  return [
    'format=gbrap',
    `geq=${[...rgb, alpha].join(':')}`,
    'format=rgba',
  ].join(',');
}

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
  const { lines } = JSON.parse(readFileSync(join(dir, 'timeline.json'), 'utf8'));
  const inputs = ['-i', capture];
  for (const id of actors) {
    inputs.push('-framerate', String(fps), '-start_number', '1', '-i', join('actors', id, 'f_%04d.png'));
  }
  const audioInput = actors.length + 1;
  inputs.push('-i', 'voice.wav');
  const selectionPath = join(dir, 'background-selection.json');
  const backgrounds = selectBackgrounds(actors, job.actors, dir);
  for (const actor of actors) {
    inputs.push('-i', join(backgroundDir, backgrounds.get(actor)));
  }
  const filters = [
    '[0:v]scale=1600:900:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1600:900:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25,tpad=stop_mode=clone:stop_duration=0.08[base]',
  ];
  let base = 'base';
  for (const [index, actor] of actors.entries()) {
    const next = `v${index}`;
    const portrait = circularPortrait(lines.filter(line => line.speaker === actor));
    filters.push(
      `[${index + 1}:v]crop=ih*0.54:ih*0.54:(iw-ow)/2:ih*0.17,scale=${portraitSize}:${portraitSize}:flags=lanczos,setsar=1[avatar${index}]`,
      `[${audioInput + index + 1}:v]scale=${portraitSize}:${portraitSize}:force_original_aspect_ratio=increase:flags=lanczos,crop=${portraitSize}:${portraitSize},setsar=1,loop=loop=-1:size=1:start=0,setpts=N/(${fps}*TB)[background${index}]`,
      `[background${index}][avatar${index}]overlay=shortest=1:format=rgb,${portrait}[a${index}]`,
    );
    filters.push(`[${base}][a${index}]overlay=W-w-20-${index}*(w+12):H-h-20[${next}]`);
    base = next;
  }
  const staging = mkdtempSync(join(dir, '.demo-render-'));
  const temporary = join(staging, 'demo.mp4');
  try {
    run('ffmpeg', [
      '-v', 'error', ...inputs, '-filter_complex_threads', '1', '-filter_complex', filters.join(';'),
      '-map', `[${base}]`, '-map', `${audioInput}:a`, '-t', String(duration),
      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', temporary,
    ]);
    const result = probe(temporary);
    const video = result.streams.find(stream => stream.codec_type === 'video');
    if (video?.width !== 1600 || video?.height !== 900 || video.r_frame_rate !== '25/1' ||
        !result.streams.some(stream => stream.codec_type === 'audio') ||
        Math.abs(Number(result.format.duration) - duration) > 0.1) {
      throw Error('Rendered MP4 failed media checks');
    }
    const savedBackgrounds = join(staging, 'background-selection.json');
    writeFileSync(savedBackgrounds, JSON.stringify(Object.fromEntries(backgrounds), null, 2) + '\n');
    renameSync(savedBackgrounds, selectionPath);
    const output = join(dir, 'demo.mp4');
    renameSync(temporary, output);
    console.log(output);
  } finally {
    rmSync(staging, { recursive: true, force: true });
  }
}
