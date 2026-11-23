// Avatar dialogue: Docker-hosted Kokoro voices -> Rhubarb -> cached avatars -> FFmpeg.
// node dialogue.mjs <dialogue.json> [--audio-only] [--overlay <duration>]
import {execFileSync,spawnSync} from 'node:child_process';
import {createHash,randomInt} from 'node:crypto';
import {existsSync,mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {dirname,join,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {renderAvatar,resolveAvatar} from './render.mjs';
import {ensureKokoro,speakKokoro} from './kokoro.mjs';
import {KOKORO_IMAGE,RHUBARB} from './lib.mjs';

const HERE=dirname(fileURLToPath(import.meta.url));
const ROOT=resolve(HERE,'../../../..');
const input=resolve(process.argv[2]??'');
if(!process.argv[2])throw Error('Usage: dialogue.mjs dialogue.json [--audio-only] [--overlay <duration>]');
const dir=dirname(input),job=JSON.parse(readFileSync(input,'utf8'));
if(!dir.startsWith(join(ROOT,'.scratch/videos')+'/'))throw Error('Place dialogue jobs below .scratch/videos');
const actors=Object.entries(job.actors??{});
const overlayIndex=process.argv.indexOf('--overlay',3);
const overlay=overlayIndex!==-1;
const targetDuration=overlay ? Number(process.argv[overlayIndex+1]) : null;
if(overlay&&!(targetDuration>0&&Number.isFinite(targetDuration)))throw Error('Overlay needs a positive duration in seconds');
const layout=job.layout??'panels';
if(!['panels','circles'].includes(layout))throw Error('layout must be panels or circles');
if(overlay){
 if(actors.length<1||actors.length>4)throw Error('Use 1 to 4 actors for an overlay');
}else if(!(layout==='circles'?[2,3,4]:[2]).includes(actors.length)){
 throw Error('Use 2 actors for panels or 2 to 4 for circles');
}
const identifier=/^[a-zA-Z][a-zA-Z0-9_-]*$/;
for(const [id,actor] of actors)if(!identifier.test(id)||!actor.avatar||!actor.label)throw Error('Actor id/avatar/label required');
if(!Array.isArray(job.lines)||!job.lines.length)throw Error('Dialogue lines required');
const ids=new Set();
for(const line of job.lines){if(!identifier.test(line.id)||ids.has(line.id)||!job.actors[line.speaker]||typeof line.text!=='string'||!line.text.trim())throw Error('Invalid/duplicate line or speaker');ids.add(line.id);}
const engine=job.engine??'kokoro';
if(engine!=='kokoro')throw Error('Use engine: kokoro');
const language=new Intl.Locale(job.language??'fr-FR').language;
const femaleVoices=['bf_alice','bf_emma','bf_isabella','bf_lily'];
const maleVoices=['bm_daniel','bm_george','bm_fable','bm_lewis'];
const englishVoices={woman:femaleVoices,man:maleVoices,neutral:[...femaleVoices,...maleVoices]};
if(overlay&&job.lines.some(line=>!Number.isFinite(line.start)||line.start<0||line.start>=targetDuration)){
 throw Error('Each overlay line needs a start within the capture');
}
const fps=25,lead=overlay ? 0 : job.leadIn??.8,gap=overlay ? 0 : job.gap??.6,tail=overlay ? 0 : job.tail??1.2;
for(const n of [lead,gap,tail])if(!Number.isFinite(n)||n<0)throw Error('Invalid silence duration');
const run=(cmd,args)=>execFileSync(cmd,args,{cwd:dir,encoding:'utf8',maxBuffer:64*1024*1024});
const write=(name,data)=>writeFileSync(join(dir,name),JSON.stringify(data,null,2)+'\n');
const read=name=>JSON.parse(readFileSync(join(dir,name),'utf8'));
const hash=data=>createHash('sha256').update(data).digest('hex');
const duration=file=>Number(run('ffprobe',['-v','error','-show_entries','format=duration','-of','csv=p=0',file]).trim());
const stage=(name,data={})=>{console.log(JSON.stringify({stage:name,...data}));write('status.json',{stage:name,...data,updatedAt:new Date().toISOString()});};
const ff=(args)=>run('ffmpeg',['-v','error','-y',...args]);
const number=n=>n.toFixed(6);
const assTime=t=>{const n=Math.round(t*100),pad=(v,w=2)=>String(v).padStart(w,'0');return `${Math.floor(n/360000)}:${pad(Math.floor(n/6000)%60)}:${pad(Math.floor(n/100)%60)}.${pad(n%100)}`;};
const srtTime=t=>{const n=Math.round(t*1000),pad=(v,w=2)=>String(v).padStart(w,'0');return `${pad(Math.floor(n/3600000))}:${pad(Math.floor(n/60000)%60)}:${pad(Math.floor(n/1000)%60)},${pad(n%1000,3)}`;};
const wrap=(text,width=68)=>{const lines=[];let row='';for(const word of text.split(/\s+/)){if(row&&`${row} ${word}`.length>width){lines.push(row);row=word;}else row=row?`${row} ${word}`:word;}if(row)lines.push(row);return lines;};
const assEscape=s=>s.replaceAll('\\','\\\\').replaceAll('{','\\{').replaceAll('}','\\}');

// Keep the random choice per actor across reruns so their voice and audio cache stay stable.
const previous=existsSync(join(dir,'voice-selection.json')) ? read('voice-selection.json') : {};
const voiceSelection=Object.fromEntries(actors.map(([id,actor])=>{
 const {gender:group}=resolveAvatar(actor.avatar);
 let voice=actor.voice;
 if(language==='en'){
  const pool=Object.hasOwn(englishVoices,group) ? englishVoices[group] : null;
  if(!pool)throw Error('Unknown avatar group for English voice selection: '+actor.avatar);
  if(voice!=null&&!pool.includes(voice))throw Error('Voice is outside the English pool for '+actor.avatar);
  const prior=Object.hasOwn(previous,id) ? previous[id] : null;
  const reusable=prior?.language===language&&prior.avatar===actor.avatar&&pool.includes(prior.voice);
  voice??=reusable ? prior.voice : pool[randomInt(pool.length)];
 }else if(language==='fr'){
  voice??='ff_siwis';
 }
 if(typeof voice!=='string'||!voice.trim())throw Error('Kokoro voice required for '+id);
 const frenchManager=language==='fr'&&group==='man';
 const speed=actor.speed??job.speed??(language==='fr' ? (frenchManager ? .94 : 1.01) : 1);
 const pitch=actor.pitch??(frenchManager ? .87 : 1);
 if(!Number.isFinite(speed)||speed<.5||speed>2)throw Error('Kokoro speed must be .5..2');
 if(!Number.isFinite(pitch)||pitch<.75||pitch>1.25)throw Error('Pitch ratio must be .75..1.25');
 return [id,{language,avatar:actor.avatar,voice,speed,pitch}];
}));
write('voice-selection.json',voiceSelection);

mkdirSync(join(dir,'voice'),{recursive:true});
stage('synthesizing',{lines:job.lines.length});
const timeline=[],concat=[];
const silence=(name,seconds)=>{if(seconds<=0)return;ff(['-f','lavfi','-i','anullsrc=r=48000:cl=mono','-t',String(seconds),'-c:a','pcm_s16le',join(dir,'voice',name)]);};
silence('lead.wav',lead);silence('gap.wav',gap);silence('tail.wav',tail);
if(lead>0)concat.push('lead.wav');
let cursor=lead;
let kokoroReady;
for(const [index,line] of job.lines.entries()){
 if(overlay&&line.start<cursor-.0001)throw Error('Speech overlaps the previous line: '+line.id);
 if(overlay&&line.start>cursor){
  const padding=`.overlay-before-${index}.wav`;
  silence(padding,line.start-cursor);
  concat.push(padding);
  cursor=line.start;
 }
 const {voice,speed,pitch}=voiceSelection[line.speaker];
 const spokenText=line.spokenText??line.text;
 const settings={engine,image:KOKORO_IMAGE,voice,speed,pitch,text:spokenText};
 const key=hash(JSON.stringify(settings));
 const stamp=join(dir,'voice',`${line.id}.json`);
 const wav=join(dir,'voice',`${line.id}.wav`);
 const cached=existsSync(wav)&&existsSync(stamp)&&JSON.parse(readFileSync(stamp,'utf8')).key===key;
 if(!cached){
  kokoroReady??=ensureKokoro();
  await kokoroReady;
  const result=await speakKokoro(spokenText,{voice,speed});
  if(typeof result.audio!=='string'||!result.audio.length)throw Error('Kokoro returned empty audio: '+line.id);
  const raw=join(dir,'voice',`${line.id}.raw.wav`);
  writeFileSync(raw,Buffer.from(result.audio,'base64'));
  const filters=['aresample=48000'];
  if(pitch!==1)filters.push(`asetrate=${Math.round(48000*pitch)}`,`atempo=${1/pitch}`);
  filters.push('loudnorm=I=-18:TP=-2:LRA=7');
  ff(['-i',raw,'-ac','1','-ar','48000','-af',filters.join(','),'-c:a','pcm_s16le',wav]);
  writeFileSync(stamp,JSON.stringify({key,...settings},null,2)+'\n');
 }
 const seconds=duration(wav);
 if(!(seconds>.1))throw Error('Empty speech: '+line.id);
 if(overlay&&cursor+seconds>targetDuration+.0001)throw Error('Speech exceeds the capture duration: '+line.id);
 timeline.push({...line,spokenText,voice,start:cursor,end:cursor+seconds,duration:seconds});
 concat.push(`${line.id}.wav`);cursor+=seconds;
 if(index<job.lines.length-1&&gap>0){concat.push('gap.wav');cursor+=gap;}
 stage('speech-line-ready',{line:line.id,completed:index+1,total:job.lines.length,duration:seconds,cached});
}
if(overlay&&targetDuration>cursor){
 silence('.overlay-tail.wav',targetDuration-cursor);
 concat.push('.overlay-tail.wav');
}else if(tail>0){
 concat.push('tail.wav');
}
writeFileSync(join(dir,'voice/concat.txt'),concat.map(name=>`file '${name}'`).join('\n')+'\n');
ff(['-f','concat','-safe','0','-i',join(dir,'voice/concat.txt'),'-c','copy',join(dir,'voice.wav')]);
const total=duration(join(dir,'voice.wav'));
write('timeline.json',{language:job.language??language,engine,total,lines:timeline});
let srt='',ass=`[Script Info]\nScriptType: v4.00+\nPlayResX: 1600\nPlayResY: 900\nWrapStyle: 2\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Dialogue,Arial,32,&H00FFFFFF,&H00FFFFFF,&H00131C2B,&HA0131C2B,0,0,0,0,100,100,0,0,1,2,0,2,60,60,28,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n`;
for(const [i,line] of timeline.entries()){
 const actor=job.actors[line.speaker],caption=`${actor.subtitleLabel??actor.label} : ${line.text}`;
 const rows=wrap(caption);
 srt+=`${i+1}\n${srtTime(line.start)} --> ${srtTime(line.end)}\n${rows.join('\n')}\n\n`;
 ass+=`Dialogue: 0,${assTime(line.start)},${assTime(line.end)},Dialogue,,0,0,0,,${rows.map(assEscape).join('\\N')}\n`;
}
writeFileSync(join(dir,'dialogue.srt'),srt);writeFileSync(join(dir,'dialogue.ass'),ass);
stage('audio-ready',{duration:total,lines:timeline.length,voices:actors.map(([id])=>({speaker:id,voice:voiceSelection[id].voice}))});
if(process.argv.includes('--audio-only'))process.exit(0);

const rhubarb=job.rhubarbBin??RHUBARB;
if(!rhubarb||!existsSync(rhubarb))throw Error('Rhubarb missing: set RHUBARB_BIN to the approved extracted binary');
const recognizer=language==='en' ? 'pocketSphinx' : 'phonetic';
const rhubarbVersion=run(rhubarb,['--version']).trim();
const cuesByActor=Object.fromEntries(actors.map(([id])=>[id,[]]));
for(const [index,line] of timeline.entries()){
 const wav=join(dir,'voice',`${line.id}.wav`),cueFile=join(dir,'voice',`${line.id}.cues.json`),stamp=join(dir,'voice',`${line.id}.cues-key`);
 const key=hash(Buffer.concat([readFileSync(wav),Buffer.from(rhubarbVersion+recognizer)]));
 if(!existsSync(cueFile)||!existsSync(stamp)||readFileSync(stamp,'utf8')!==key){
  run(rhubarb,['-r',recognizer,'-f','json','-q',wav,'-o',cueFile]);writeFileSync(stamp,key);
 }
 const cues=JSON.parse(readFileSync(cueFile,'utf8')).mouthCues;
 for(const cue of cues){
  const start=line.start+Math.max(0,cue.start),end=line.start+Math.min(line.duration,cue.end);
  if(end>start)cuesByActor[line.speaker].push({start,end,value:cue.value});
 }
 stage('lip-sync-line-ready',{line:line.id,completed:index+1,total:timeline.length,recognizer});
}
const avatarReports=[];
for(const [index,[id,actor]] of actors.entries()){
 write(`${id}-cues.json`,{mouthCues:cuesByActor[id]});
 const avatarJob={
  avatar:actor.avatar,
  cues:`${id}-cues.json`,
  output:`actors/${id}`,
  duration:total,
  fps,
  size:540,
  samples:32,
  blink:actor.blink,
  blinkStart:actor.blinkStart??(1.8+index*1.3),
  expressions:actor.expressions??[],
  headMotion:actor.headMotion??[],
  lighting:actor.lighting??job.lighting??(overlay||layout==='circles'?'soft':'studio')
 };
 write(`${id}-avatar.json`,avatarJob);
 stage('rendering-avatar',{speaker:id,avatar:actor.avatar});
 const report=renderAvatar(avatarJob,dir);avatarReports.push({speaker:id,...report});
}
write('avatar-reports.json',avatarReports);
if(overlay){
 stage('overlay-assets-ready',{duration:total,actors:actors.length});
 process.exit(0);
}
stage('composing',{duration:total});
if(layout==='circles'){
 run('python3',[join(HERE,'compose_circles.py'),dir,input]);
}else{
const font=process.env.AVATAR_FONT;
const fontFilter=font ? `fontfile='${font}'` : 'font=Arial';
const inputs=['-f','lavfi','-i',`color=c=0x111B2B:s=1600x900:r=${fps}:d=${number(total)}`];
for(const [id] of actors)inputs.push('-framerate',String(fps),'-i',join(dir,`actors/${id}/f_%04d.png`));
inputs.push('-i',join(dir,'voice.wav'));
const filters=[`[0:v]drawbox=x=30:y=70:w=720:h=650:color=0xE5EAF0:t=fill,drawbox=x=850:y=70:w=720:h=650:color=0xE5EAF0:t=fill[bg]`,`[1:v]format=rgba,scale=640:640[a0]`,`[2:v]format=rgba,scale=640:640[a1]`,`[bg][a0]overlay=70:80:shortest=1[v0]`,`[v0][a1]overlay=890:80:shortest=1[v1]`];
let chain='[v1]';
for(const [index,[id,actor]] of actors.entries()){
 const labelFile=join(dir,`${id}-label.txt`);writeFileSync(labelFile,actor.label);
 const on=timeline.filter(line=>line.speaker===id).map(line=>`between(t,${number(line.start)},${number(line.end)})`).join('+');
 const out=`[label${index}]`,center=index===0?390:1210,x=index===0?30:850;
 filters.push(`${chain}drawbox=x=${x}:y=70:w=720:h=650:color=${index===0?'0x67B7FF':'0x72D1AF'}:t=5:enable='${on}',drawtext=${fontFilter}:textfile='${labelFile}':fontsize=32:fontcolor=white:x=${center}-text_w/2:y=726${out}`);chain=out;
}
const defaultTitle=language==='fr' ? 'Dialogue en français' : language==='en' ? 'Dialogue in English' : 'Dialogue';
writeFileSync(join(dir,'title.txt'),job.title??defaultTitle);
filters.push(`${chain}drawtext=${fontFilter}:textfile='${join(dir,'title.txt')}':fontsize=28:fontcolor=0xDAE7F5:x=44:y=22,drawbox=x=30:y=774:w=1540:h=116:color=0x0B1423:t=fill,ass='${join(dir,'dialogue.ass')}',format=yuv420p[out]`);
writeFileSync(join(dir,'compose-filter.txt'),filters.join(';'));
ff([...inputs,'-filter_complex_script',join(dir,'compose-filter.txt'),'-map','[out]','-map','3:a','-t',number(total),'-r',String(fps),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-af','loudnorm=I=-16:TP=-1.5:LRA=7','-ar','48000','-movflags','+faststart',join(dir,'dialogue.mp4')]);
}
const probe=JSON.parse(run('ffprobe',['-v','error','-show_streams','-show_format','-of','json',join(dir,'dialogue.mp4')]));
const video=probe.streams.find(s=>s.codec_type==='video'),audio=probe.streams.find(s=>s.codec_type==='audio');
if(!audio||video?.width!==1600||video?.height!==900||video?.r_frame_rate!=='25/1'||Math.abs(Number(probe.format.duration)-total)>.15)throw Error('Output media checks failed');
mkdirSync(join(dir,'qa'),{recursive:true});
for(const index of [0,1,4].filter(i=>i<timeline.length)){const line=timeline[index];ff(['-ss',number((line.start+line.end)/2),'-i',join(dir,'dialogue.mp4'),'-frames:v','1',join(dir,`qa/line-${index+1}.png`)]);}
const measure=spawnSync('ffmpeg',['-hide_banner','-i',join(dir,'dialogue.mp4'),'-af','loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json','-f','null','-'],{encoding:'utf8',maxBuffer:16*1024*1024});
const match=measure.stderr?.match(/\{\s*"input_i"[\s\S]*?\}/);const loudness=match?JSON.parse(match[0]):null;
write('checks.json',{duration:total,videoDuration:Number(probe.format.duration),size:[video.width,video.height],fps:25,audioCodec:audio.codec_name,language:job.language??language,ttsEngine:engine,ttsImage:KOKORO_IMAGE,rhubarbRecognizer:recognizer,voices:actors.map(([id])=>({speaker:id,...voiceSelection[id]})),lines:timeline.length,avatarReports,loudness,subtitles:'original user text; phrase-level timings from measured utterances'});
stage('complete',{file:'dialogue.mp4',duration:total,lines:timeline.length,renderedStates:avatarReports.reduce((sum,r)=>sum+r.missingStates,0)});
