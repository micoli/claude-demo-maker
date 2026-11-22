"""Render only missing mouth/blink/expression states in one Blender process."""
import json
import math
import struct
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy
from mathutils import Euler, Matrix, Vector

job = json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())


def restore_missing_textures(glb):
    missing = [image for image in bpy.data.images
               if image.source == 'FILE' and image.users and not image.has_data and not image.size[0]]
    if not missing:
        return
    if not glb.is_file():
        raise FileNotFoundError(f'Missing texture sources and companion GLB: {glb}')

    with glb.open('rb') as stream:
        if stream.read(8) != b'glTF\x02\x00\x00\x00':
            raise ValueError(f'Expected glTF 2.0 binary: {glb}')
        stream.read(4)
        size, kind = struct.unpack('<I4s', stream.read(8))
        if kind != b'JSON':
            raise ValueError(f'Missing GLB JSON chunk: {glb}')
        manifest = json.loads(stream.read(size))
        _, kind = struct.unpack('<I4s', stream.read(8))
        if kind != b'BIN\x00':
            raise ValueError(f'Missing GLB binary chunk: {glb}')
        offset = stream.tell()
        embedded = {item['name']: item['bufferView'] for item in manifest.get('images', [])
                    if 'name' in item and 'bufferView' in item}

        with TemporaryDirectory() as staging:
            for index, image in enumerate(missing):
                name = Path(image.filepath).stem
                if name not in embedded:
                    raise ValueError(f'Missing texture {image.name} in {glb}')
                view = manifest['bufferViews'][embedded[name]]
                stream.seek(offset + view.get('byteOffset', 0))
                source = Path(staging) / f'{index}{Path(image.filepath).suffix}'
                source.write_bytes(stream.read(view['byteLength']))
                image.filepath = str(source)
                image.reload()
                if not image.size[0]:
                    raise ValueError(f'Cannot load texture {image.name} from {glb}')
                image.pack()


scene = bpy.context.scene
if scene.get('avatar_generator') == 'mpfb':
    restore_missing_textures(Path(job['glb']))

scene.render.resolution_x = scene.render.resolution_y = job['size']
scene.eevee.taa_render_samples = job['samples']
if job.get('lighting') == 'soft':
    for name, factor in {'Key': .82, 'Fill': .50, 'Rim': .30}.items():
        lamp = scene.objects.get(name)
        if lamp and lamp.type == 'LIGHT':
            lamp.data.energy *= factor
    if scene.world:
        scene.world.color = tuple(channel * .68 for channel in scene.world.color)
    scene.view_settings.exposure -= .24

base = {ob.name: ob.location.copy() for ob in bpy.data.objects}
controls = json.loads(scene['avatar_controls']) if scene.get('avatar_generator') == 'mpfb' else None
def prepare_head_rig():
    meshes = [ob for ob in scene.objects if ob.type == 'MESH']
    face = bpy.data.objects['mpfb-face']
    bounds = [face.matrix_world @ Vector(corner) for corner in face.bound_box]
    bottom = min(point.z for point in bounds)
    height = max(point.z for point in bounds) - bottom
    neck = Vector((0, (min(point.y for point in bounds) + max(point.y for point in bounds)) / 2,
                   bottom + height * .29))

    armature = bpy.data.armatures.new('Dialogue head')
    rig = bpy.data.objects.new('Dialogue head', armature)
    scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bone = armature.edit_bones.new('DialogueHead')
    bone.head = neck
    bone.tail = neck + Vector((0, 0, height * .3))
    fixed = armature.edit_bones.new('DialogueFixed')
    fixed.head = neck
    fixed.tail = neck + Vector((0, 0, height * .2))
    bpy.ops.object.mode_set(mode='OBJECT')

    for ob in meshes:
        group = ob.vertex_groups.new(name='DialogueHead')
        if ob == face:
            fixed_group = ob.vertex_groups.new(name='DialogueFixed')
            for vertex in ob.data.vertices:
                z = (ob.matrix_world @ vertex.co).z
                weight = max(0, min(1, ((z-bottom)/height-.07)/.29))
                weight = weight * weight * (3-2*weight)
                if weight:
                    group.add([vertex.index], weight, 'REPLACE')
                if weight < 1:
                    fixed_group.add([vertex.index], 1-weight, 'REPLACE')
        elif ob.data.vertices:
            group.add(range(len(ob.data.vertices)), 1, 'REPLACE')
        modifier = ob.modifiers.new('Dialogue head motion', 'ARMATURE')
        modifier.object = rig
    return rig.pose.bones['DialogueHead'], neck


has_motion = any(len(state.split('_')) > 3 for state in job['states'])
if has_motion and not controls:
    raise ValueError('Head motion requires an MPFB avatar')
head_rig = prepare_head_rig() if has_motion else None
for state in job['states']:
    expression, shape, blink, *angles = state.split('_')
    if head_rig:
        bone, neck = head_rig
        if angles:
            rotation = Euler(tuple(math.radians(int(angle)/2) for angle in angles)).to_matrix().to_4x4()
            bone.matrix = Matrix.Translation(neck) @ rotation @ Matrix.Translation(-neck) @ bone.bone.matrix_local
        else:
            bone.matrix_basis.identity()
    if controls:
        weights = {controls['visemes'][shape]: 1.0}
        if blink == '1':
            weights.update(controls['blink'])
        for key, value in controls['expressions'][expression].items():
            weights[key] = max(weights.get(key, 0), value)
        for ob in bpy.context.scene.objects:
            if ob.type == 'MESH' and ob.data.shape_keys:
                for key in ob.data.shape_keys.key_blocks:
                    if key.name != 'Basis':
                        key.value = weights.get(key.name, 0.0)
    else:
        for ob in bpy.data.objects:
            ob.location = base[ob.name]
            if ob.type == 'MESH' and ob.data.shape_keys:
                for key in ob.data.shape_keys.key_blocks:
                    if key.name.startswith('viseme_'):
                        key.value = float(key.name == 'viseme_'+shape)
            if ob.name.startswith('lid-'):
                ob.hide_render = blink != '1'
            if ob.name.startswith(('eye-', 'iris-', 'pupil-')):
                ob.hide_render = blink == '1'
            if ob.name == 'teeth':
                ob.hide_render = shape not in ('B', 'C', 'D', 'G', 'H')
            if ob.name.startswith('brow-'):
                ob.rotation_euler.y = 0
                if expression == 'warm':
                    ob.location.z += .007
                elif expression == 'concerned':
                    ob.rotation_euler.y = int(ob['side'])*.18
                elif expression == 'surprised':
                    ob.location.z += .018
    bpy.context.view_layer.update()
    target = Path(job['cache']) / (state+'.png')
    scene.render.filepath = str(target.with_suffix('.part.png'))
    bpy.ops.render.render(write_still=True)
    Path(scene.render.filepath).replace(target)
print('##JSON##'+json.dumps({'rendered': len(job['states'])}))
