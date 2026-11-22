// Voice track of a feature video, from <feature>/script.json:
//   { "voice": "af_heart", "speed": 1, "leadIn": 0.8, "pad": 0.4, "lines": [{ "id": "s1", "text": "Step inside." }] }
// Writes voice.wav (48 kHz mono, the lines separated by silence), timeline.json (start/end of each line and word),
// cues.json (Rhubarb mouth cues) and subs.srt.
//   node .claude/skills/avatar-narrator/scripts/tts.mjs <feature>
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { RHUBARB, ffprobeDuration, readJson, run, videoDir, writeJson } from './lib.mjs';

import { ensureKokoro, speakKokoro } from './kokoro.mjs';

const feature = process.argv[2];
if (!feature) throw new Error('usage: tts.mjs <feature>');
const dir = videoDir(feature);
const script = readJson(join(dir, 'script.json'));
const { voice = 'af_heart', speed = 1, leadIn = 0.8, pad = 0.4, lines } = script;

const isPunctuation = (token) => /^[^\p{L}\p{N}]+$/u.test(token);
const wrap = (text, width = 42) => {
  const rows = [];
  let row = '';
  for (const word of text.split(' ')) {
    if (row && `${row} ${word}`.length > width) {
      rows.push(row);
      row = word;
    } else row = row ? `${row} ${word}` : word;
  }
  if (row) rows.push(row);
  return rows.join('\n');
};
const srtTime = (seconds) => {
  const ms = Math.round(seconds * 1000);
  const part = (value, size) => String(value).padStart(size, '0');
  return `${part(Math.floor(ms / 3600000), 2)}:${part(Math.floor(ms / 60000) % 60, 2)}:${part(Math.floor(ms / 1000) % 60, 2)},${part(ms % 1000, 3)}`;
};

await ensureKokoro();
mkdirSync(join(dir, 'voice'), { recursive: true });

const timeline = [];
const concat = [];
let cursor = leadIn;
run('ffmpeg', ['-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono', '-t', String(leadIn), join(dir, 'voice/lead.wav')]);
run('ffmpeg', ['-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono', '-t', String(pad), join(dir, 'voice/pad.wav')]);
concat.push('lead.wav');

for (const line of lines) {
  const result = await speakKokoro(line.text, { voice, speed });
  const raw = join(dir, `voice/${line.id}.raw.wav`);
  const clean = join(dir, `voice/${line.id}.wav`);
  writeFileSync(raw, Buffer.from(result.audio, 'base64'));
  // Kokoro writes a streaming WAV header (unknown length) that Rhubarb reads as empty: re-encode.
  run('ffmpeg', ['-v', 'error', '-y', '-i', raw, '-ac', '1', '-ar', '48000', clean]);
  const duration = ffprobeDuration(clean);
  timeline.push({
    id: line.id,
    text: line.text,
    start: cursor,
    end: cursor + duration,
    words: result.timestamps.map((word) => ({ word: word.word, start: cursor + word.start_time, end: cursor + word.end_time })),
  });
  concat.push(`${line.id}.wav`, 'pad.wav');
  cursor += duration + pad;
}

writeFileSync(join(dir, 'voice/concat.txt'), concat.map((file) => `file '${file}'`).join('\n'));
run('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', join(dir, 'voice/concat.txt'), '-c', 'copy', join(dir, 'voice.wav')]);
writeJson(join(dir, 'timeline.json'), { voice, total: ffprobeDuration(join(dir, 'voice.wav')), lines: timeline });

run('ffmpeg', ['-v', 'error', '-y', '-i', join(dir, 'voice.wav'), '-ac', '1', '-ar', '22050', join(dir, 'voice/rhubarb.wav')]);
const language = new Intl.Locale(script.language ?? 'en-GB').language;
run(RHUBARB, ['-r',language === 'en' ? 'pocketSphinx' : 'phonetic','-f', 'json', '-q', join(dir, 'voice/rhubarb.wav'), '-o', join(dir, 'cues.json')]);

let index = 1;
let srt = '';
for (const line of timeline) {
  const tokens = line.words;
  let chunk = [];
  const flush = () => {
    if (chunk.length === 0) return;
    const text = chunk.reduce((acc, token) => (isPunctuation(token.word) ? `${acc}${token.word}` : `${acc} ${token.word}`), '').trim();
    srt += `${index}\n${srtTime(chunk[0].start)} --> ${srtTime(chunk[chunk.length - 1].end)}\n${wrap(text)}\n\n`;
    index += 1;
    chunk = [];
  };
  for (const token of tokens) {
    chunk.push(token);
    const length = chunk.map((item) => item.word).join(' ').length;
    if (length > 70 && !isPunctuation(token.word)) flush();
    else if (/[.!?]$/.test(token.word)) flush();
  }
  flush();
}
writeFileSync(join(dir, 'subs.srt'), srt);
console.log(`voice.wav ${ffprobeDuration(join(dir, 'voice.wav')).toFixed(1)} s, ${timeline.length} lines, ${index - 1} subtitles`);
