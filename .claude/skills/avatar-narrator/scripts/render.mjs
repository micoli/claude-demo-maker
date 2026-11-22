// Usage: node .../render.mjs job.json [--plan]
// All paths in job.json are relative to that file, never the current directory.
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { copyFileSync, existsSync, linkSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '../../../..');
const BANK = resolve(HERE, '../assets/avatar-mpfb');
export const EXPRESSIONS = ['neutral', 'warm', 'concerned', 'surprised'];
const read = file => JSON.parse(readFileSync(file, 'utf8'));
const run = (command, args) => execFileSync(command, args, { encoding: 'utf8', maxBuffer: 32*1024*1024 });
const hash = bytes => createHash('sha256').update(bytes).digest('hex');

export function plan(job, cues) {
  const fps = job.fps ?? 25;
  const size = job.size ?? 540;
  const samples = job.samples ?? 32;
  const blinkStart = job.blinkStart ?? 1.8;
  if (!Number.isFinite(blinkStart) || blinkStart < 0) throw Error('blinkStart must be nonnegative');
  if (!Number.isInteger(fps) || fps < 1 || fps > 60) throw Error('fps must be 1..60');
  if (!Number.isInteger(size) || size < 64 || size > 2160) throw Error('size must be 64..2160');
  if (!Number.isInteger(samples) || samples < 1 || samples > 256) throw Error('samples must be 1..256');
  if (!Number.isFinite(job.duration) || job.duration <= 0) throw Error('duration must be positive');
  if (!Array.isArray(cues.mouthCues)) throw Error('mouthCues array required');
  let previous = 0;
  for (const cue of cues.mouthCues) {
    if (!Number.isFinite(cue.start) || !Number.isFinite(cue.end) || cue.start < previous || cue.end <= cue.start || !/^[A-HX]$/.test(cue.value)) throw Error('Invalid or overlapping mouth cues');
    previous = cue.end;
  }
  const expressions = [...(job.expressions ?? [])].sort((a,b)=>a.start-b.start);
  previous = 0;
  for (const item of expressions) {
    if (!EXPRESSIONS.includes(item.value) || !Number.isFinite(item.start) || !Number.isFinite(item.end) || item.start < previous || item.end <= item.start || item.end > job.duration) throw Error('Invalid or overlapping expressions');
    previous = item.end;
  }
  if (job.blink !== undefined && typeof job.blink !== 'boolean') throw Error('blink must be boolean');
  const motions = [...(job.headMotion ?? [])].sort((a,b)=>a.start-b.start);
  previous = 0;
  for (const {start,end,pitch=0,tilt=0,turn=0} of motions) {
    if (!Number.isFinite(start) || !Number.isFinite(end) || start < previous || end <= start || end > job.duration) {
      throw Error('Head motions must be non-overlapping intervals within the video');
    }
    if ([pitch,tilt,turn].some(angle=>!Number.isFinite(angle) || Math.abs(angle)>6)) {
      throw Error('Head motion angles must be between -6 and 6 degrees');
    }
    previous = end;
  }
  const frames = [];
  let cueIndex = 0, exprIndex = 0, motionIndex = 0;
  for (let frame=0; frame<Math.ceil(job.duration*fps); frame++) {
    const t=frame/fps;
    while (cueIndex<cues.mouthCues.length && cues.mouthCues[cueIndex].end<=t) cueIndex++;
    while (exprIndex<expressions.length && expressions[exprIndex].end<=t) exprIndex++;
    const cue = cues.mouthCues[cueIndex];
    const expr = expressions[exprIndex];
    const mouth = cue && cue.start<=t && t<cue.end ? cue.value : 'X';
    const expression = expr && expr.start<=t && t<expr.end ? expr.value : 'neutral';
    const blink = job.blink !== false && t>=blinkStart && (t-blinkStart)%3.7<.12 ? 1:0;
    while (motionIndex<motions.length && motions[motionIndex].end<=t) motionIndex++;
    const motion = motions[motionIndex];
    let state = `${expression}_${mouth}_${blink}`;
    if (motion && t>motion.start) {
      const phase = (t-motion.start)/(motion.end-motion.start);
      // Half-degree increments allow nearby frames to reuse the same Blender render.
      const ease = Math.sin(Math.PI*phase)**2;
      const angles = [motion.pitch,motion.tilt,motion.turn].map(angle=>Math.round(2*(angle??0)*ease));
      if (angles.some(Boolean)) state += '_'+angles.join('_');
    }
    frames.push(state);
  }
  return { fps, size, samples, frames, states: [...new Set(frames)] };
}

export function renderAvatar(job, base, { planOnly=false }={}) {
  if (!/^(?:(man|woman|neutral)-(0[1-9]|10)|pilot-(man|woman))$/.test(job.avatar)) throw Error('Use man-01..10, woman-01..10, neutral-01..10, pilot-man or pilot-woman');
  if (typeof job.cues !== 'string' || typeof job.output !== 'string') throw Error('cues and output paths required');
  const cueFile=resolve(base, job.cues), out=resolve(base, job.output);
  const spec=plan(job, read(cueFile));
  const lighting=job.lighting??'studio';
  if (!['studio','soft'].includes(lighting)) throw Error('lighting must be studio or soft');
  const blend=join(BANK, job.avatar, 'avatar.blend');
  if (!existsSync(blend)) throw Error('MPFB avatar missing: run build_mpfb.py --bank first (or omit --bank for pilots)');
  // Blend, companion textures and renderer contents determine the cache key.
  // Include Blender version for different installations / upgrades.
  const macBlender='/Applications/Blender.app/Contents/MacOS/Blender';
  const blender=process.env.BLENDER_EXE??(existsSync(macBlender)?macBlender:'blender');
  const version=run(blender, ['--version']);
  const glb=join(BANK, job.avatar, job.avatar+'.glb');
  const textureSource=existsSync(glb) ? readFileSync(glb) : Buffer.alloc(0);
  const digest=hash(Buffer.concat([readFileSync(blend), textureSource, readFileSync(join(HERE,'render_states.py')),
    Buffer.from(JSON.stringify([spec.size,spec.samples,lighting,version]))]));
  const cache=join(ROOT,'.scratch/videos/avatar-cache',job.avatar,digest);
  const missing=spec.states.filter(state=>!existsSync(join(cache,state+'.png')));
  const report={avatar:job.avatar,frames:spec.frames.length,uniqueStates:spec.states.length,
    missingStates:missing.length,cachedStates:spec.states.length-missing.length,cache,fps:spec.fps};
  if (planOnly) return report;
  // Require a dedicated output directory. Reject any path outside generated video work.
  const videoRoot=join(ROOT,'.scratch/videos')+'/';
  if (!out.startsWith(videoRoot) || out.startsWith(join(ROOT,'.scratch/videos/avatar-cache')+'/') || out===join(ROOT,'.scratch/videos/avatar-cache')) throw Error('output must be a dedicated folder below .scratch/videos, outside avatar-cache');
  mkdirSync(cache,{recursive:true});
  const temp=mkdtempSync(join(tmpdir(),'avatar-render-'));
  try {
    if (missing.length) {
      const request=join(temp,'states.json');
      writeFileSync(request,JSON.stringify({...spec,frames:undefined,states:missing,cache,lighting,glb}));
      run('python3',[join(HERE,'bl.py'),'--blend',blend,'--script',join(HERE,'render_states.py'),'--',request]);
    }
    // Build a fresh sequence then atomically replace only a renderer-owned directory.
    const marker=join(out,'avatar-render.json');
    if (existsSync(out) && !existsSync(marker)) throw Error(`Refusing to replace unowned output directory: ${out}`);
    mkdirSync(dirname(out),{recursive:true});
    const staging=mkdtempSync(out+'.staging-');
    try {
      spec.frames.forEach((state,index)=>{
        const source=join(cache,state+'.png'), target=join(staging,`f_${String(index+1).padStart(4,'0')}.png`);
        try {linkSync(source,target);} catch(error) {
          if (!['EXDEV','EPERM','ENOTSUP','EACCES'].includes(error.code)) throw error;
          copyFileSync(source,target);
        }
      });
      writeFileSync(join(staging,'avatar-render.json'),JSON.stringify(report,null,2)+'\n');
      if (existsSync(out)) rmSync(out,{recursive:true});
      renameSync(staging,out);
    } finally {if(existsSync(staging))rmSync(staging,{recursive:true});}
  } finally {rmSync(temp,{recursive:true});}
  return report;
}

if(process.argv[1] && resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  if(!process.argv[2]) throw Error('Usage: render.mjs job.json [--plan]');
  const file=resolve(process.argv[2]);
  console.log(JSON.stringify(renderAvatar(read(file),dirname(file),{planOnly:process.argv.includes('--plan')}),null,2));
}
