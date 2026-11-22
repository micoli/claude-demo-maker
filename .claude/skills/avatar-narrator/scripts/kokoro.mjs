import { spawnSync } from 'node:child_process';
import { KOKORO_IMAGE, KOKORO_URL, ensureDocker, run } from './lib.mjs';

const healthy = async () => {
  try {
    return (await fetch(`${KOKORO_URL}/health`)).ok;
  } catch {
    return false;
  }
};

export const ensureKokoro = async () => {
  if (await healthy()) return;
  ensureDocker();
  const name = 'kokoro-demo-maker';
  const state = spawnSync('docker', ['inspect', '--format', '{{.State.Running}}', name], { encoding: 'utf8' });
  if (state.status !== 0) {
    run('docker', ['run', '-d', '--name', name, '-p', '127.0.0.1:8880:8880', KOKORO_IMAGE]);
  } else if (state.stdout.trim() === 'false') {
    run('docker', ['start', name]);
  }
  for (let attempt = 0; attempt < 90; attempt += 1) {
    if (await healthy()) return;
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error('Kokoro did not become healthy in 3 minutes');
};

export const speakKokoro = async (text, { voice, speed }) => {
  const response = await fetch(`${KOKORO_URL}/dev/captioned_speech`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: 'kokoro', input: text, voice, speed, response_format: 'wav', stream: false }),
  });
  if (!response.ok) throw new Error(`Kokoro ${response.status}: ${await response.text()}`);
  return response.json();
};
