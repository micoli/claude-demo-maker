import { execFileSync, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const SKILL_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const REPO = resolve(SKILL_DIR, '../../..');
export const KOKORO_IMAGE = 'ghcr.io/remsky/kokoro-fastapi-cpu:v0.10.0';
export const KOKORO_URL = process.env.KOKORO_URL ?? 'http://localhost:8880';
export const RHUBARB = process.env.RHUBARB_BIN ?? join(SKILL_DIR, 'vendor/rhubarb/rhubarb');

export const videoDir = (feature) => {
  const dir = join(REPO, '.scratch/videos', feature);
  mkdirSync(dir, { recursive: true });
  return dir;
};

export const readJson = (file) => JSON.parse(readFileSync(file, 'utf8'));
export const writeJson = (file, value) => writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`);

export const run = (cmd, args, options = {}) => {
  const result = spawnSync(cmd, args, { encoding: 'utf8', maxBuffer: 1 << 28, ...options });
  if (result.status !== 0) throw new Error(`${cmd} ${args.join(' ')} failed (${result.status})\n${result.stderr ?? ''}`);
  return result.stdout;
};

export const ffprobeDuration = (file) => Number(run('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file]).trim());

export const ensureDocker = () => {
  try {
    execFileSync('docker', ['info'], { stdio: 'ignore' });
  } catch {
    throw new Error('Docker is not running');
  }
};

