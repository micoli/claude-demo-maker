"""Validate native MPFB sources/GLBs and render only missing/stale review views. Run headlessly."""
import argparse
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
BANK=ROOT/'assets/avatar-mpfb'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--group',choices=['man','woman','neutral'])
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if not bpy.app.background:
        raise RuntimeError('Run in a separate headless Blender process')
    spec=importlib.util.spec_from_file_location('builder',Path(__file__).with_name('build_mpfb.py'))
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    catalogue=json.loads((BANK/'catalog.json').read_text())['avatars']
    expected=json.loads((Path(__file__).resolve().parents[1]/'assets/profiles.json').read_text())['avatars']
    assert {e['id'] for e in catalogue}=={p['id'] for p in expected}, 'Catalogue differs from configured profiles'
    assert all(sum(e['gender']==group for e in catalogue)==10 for group in ('man','woman','neutral'))
    selected=[e for e in catalogue if not args.group or e['gender']==args.group]
    report_path=BANK/'bank-validation.json'
    old=json.loads(report_path.read_text()).get('avatars',[]) if report_path.exists() else []
    selected_ids={e['id'] for e in selected}
    checks=[e for e in old if e['id'] not in selected_ids]
    for entry in selected:
        folder=BANK/entry['id'];source=folder/'avatar.blend'
        raw=(BANK/entry['glb']).read_bytes();assert raw[:4]==b'glTF'
        n=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+n])
        assert all('uri' not in b for b in doc['buffers'])
        assert all('bufferView' in image for image in doc.get('images',[]))
        bpy.ops.wm.open_mainfile(filepath=str(source))
        scene=bpy.context.scene;face=bpy.data.objects['mpfb-face']
        keys=set(face.data.shape_keys.key_blocks.keys())
        assert set(builder.VISEMES.values())|{'eyeBlinkLeft','eyeBlinkRight'} <= keys
        meshes=[o for o in scene.objects if o.type=='MESH']
        eye=next(o for o in meshes if o.name.endswith('.low-poly'))
        hairs=[o for o in meshes if o.get('avatar_hair') or any(o.name.endswith('.'+h) for h in ('short01','short02','afro01','ponytail01'))]
        assert all(not builder.eye_clearance_faces(h,eye) for h in hairs),entry['id']+' hair overlaps eyes'
        assert not any(o.animation_data for o in meshes),'Unexpected body/head animation'
        for preview in ('preview.png','three-quarter.png'):
            path=folder/preview
            if path.exists() and path.stat().st_mtime>=source.stat().st_mtime:
                continue
            if preview=='three-quarter.png':
                camera=scene.camera;target=Vector((0,0,camera.location.z))
                camera.location=target+Vector((1.5,-2.598,0))
                camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
            scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
        info=json.loads((folder/'provenance.json').read_text())
        info['hair_eye_clearance'].update(passed=True,checked_angles_degrees=[-30,0,30])
        (folder/'provenance.json').write_text(json.dumps(info,indent=2)+'\n')
        checks.append({'id':entry['id'],'facial_morphs':len(keys)-1,'hair_clearance':True,'triangles':info['triangles'],'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
        print('CHECKED '+entry['id'],flush=True)
    report_path.write_text(json.dumps({'avatars':sorted(checks,key=lambda e:e['id']),'count':len(checks),'checks':'Native facial keys, embedded GLB textures, eye clearance at -30/0/30 degrees, fixed heads, front/three-quarter views','speech_audio_tested':False},indent=2)+'\n')
    print('BANK_VALIDATED '+str(len(checks)),flush=True)


if __name__=='__main__':
    main()
