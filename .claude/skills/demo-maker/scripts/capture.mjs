import { existsSync, mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = fileURLToPath(new URL('../../../../', import.meta.url));
const [jobDir, address, replayFile] = process.argv.slice(2);
if (!jobDir || !address) throw Error('Usage: capture.mjs job-directory url [replay.mjs]');
const dir = resolve(jobDir);
if (!dir.startsWith(join(root, '.scratch/videos') + sep)) {
  throw Error('Place captures below .scratch/videos');
}
const url = new URL(address);
if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) {
  throw Error('Use an HTTP(S) URL without embedded credentials');
}
const output = join(dir, 'capture.webm');
if (existsSync(output)) throw Error('Capture already exists. Use a new job directory.');

const require = createRequire(join(root, '.scratch/demo-playwright/package.json'));
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (error) {
  if (error.code !== 'MODULE_NOT_FOUND') throw error;
  throw Error('Install Playwright as documented in README.md', { cause: error });
}
const replay = replayFile ? (await import(pathToFileURL(resolve(replayFile)))).default : null;
if (replayFile && typeof replay !== 'function') throw Error('Replay module must export a default function');

mkdirSync(dir, { recursive: true });
const recording = mkdtempSync(join(dir, '.recording-'));
const viewport = { width: 1600, height: 900 };
try {
  const browser = await chromium.launch({ headless: Boolean(replay) });
  try {
    const context = await browser.newContext({
      viewport,
      recordVideo: { dir: recording, size: viewport },
      storageState: process.env.DEMO_STORAGE_STATE,
    });
    const page = await context.newPage();
    const video = page.video();
    try {
      await page.goto(url.href, { waitUntil: 'domcontentloaded' });
      if (replay) {
        await replay(page);
      } else {
        console.log('Chromium is ready. Record your actions in Inspector, copy the script, then click Resume.');
        await page.pause();
      }
    } finally {
      await context.close();
    }
    await video.saveAs(output);
    console.log(output);
  } finally {
    await browser.close();
  }
} finally {
  rmSync(recording, { recursive: true, force: true });
}
