"""Build deterministic, reusable shoulder-up Blender presenters. Run headlessly."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / 'assets/avatar-bank'
# Design references, not a claim to represent every ethnicity or infer real identities.
PROFILES = [
    ('west-african', '#754a36', '#161313'),
    ('east-african', '#925e42', '#211816'),
    ('north-african', '#bc8863', '#28201b'),
    ('west-asian', '#c99a78', '#35251d'),
    ('south-asian', '#9f6c48', '#1f1918'),
    ('east-asian', '#dfb18c', '#17191e'),
    ('southeast-asian', '#bd8a60', '#2b201c'),
    ('european', '#ebc4a9', '#775241'),
    ('latin-american-mixed', '#bd8969', '#453127'),
    ('pacific-islander', '#a77852', '#29201c'),
]


def mat(name, color):
    value = tuple(int(color[i:i+2], 16) / 255 for i in (1, 3, 5))
    # sRGB hex -> linear material.
    value = tuple(c / 12.92 if c < .04045 else ((c + .055) / 1.055) ** 2.4 for c in value)
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*value, 1)
    m.use_nodes = True
    shader = m.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*value, 1)
    shader.inputs['Roughness'].default_value = .72
    return m


def mesh(name, vertices, faces, material):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    ob = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(material)
    return ob


def ellipsoid(name, center, scale, material, segments=20, rings=12, smooth=False):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(material)
    for p in ob.data.polygons:
        p.use_smooth = smooth
    return ob


def head(skin, width, jaw):
    # Horizontal anatomical contours: chin, jaw, cheeks, temples, cranium.
    rows = [(1.18, .058, .064), (1.23, .093*jaw, .080), (1.31, .124*jaw, .097),
            (1.40, .143, .111), (1.49, .147, .116), (1.59, .144, .115),
            (1.69, .137, .111), (1.77, .108, .091), (1.81, .045, .043)]
    vertices, faces, n = [], [], 24
    for z, rx, ry in rows:
        for i in range(n):
            a = i * 2 * math.pi / n
            # Front is -Y; flatten facial plane, preserve rounded skull.
            x = math.sin(a) * rx * width
            y = -math.cos(a) * ry
            if y < 0:
                y = -ry * (1 - .16 * (abs(math.sin(a)) ** 2))
            vertices.append((x, y, z))
    for r in range(len(rows)-1):
        for i in range(n):
            a, b = r*n+i, r*n+(i+1)%n
            faces.append((a, b, b+n, a+n))
    faces.extend([tuple(reversed(range(n))), tuple((len(rows)-1)*n+i for i in range(n))])
    return mesh('face', vertices, faces, skin)


def mouth(lip, dark, teeth):
    # Cavity + continuous lip rim. Same topology in every talking state.
    n, z, y = 24, 1.317, -.103
    states = {'X': (.043, .003), 'A': (.043, .002), 'B': (.047, .008),
              'C': (.048, .019), 'D': (.048, .035), 'E': (.031, .025),
              'F': (.020, .019), 'G': (.043, .007), 'H': (.044, .017)}
    def coords(w, h):
        return [(math.cos(i*2*math.pi/n)*w*scale, y-offset,
                 z+math.sin(i*2*math.pi/n)*(h+extra))
                for scale, extra, offset in ((1.13, .006, .003), (1, 0, .005)) for i in range(n)]
    w, h = states['X']
    ob = mesh('lips', coords(w, h), [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)], lip)
    ob.shape_key_add(name='Basis')
    for state, (w, h) in states.items():
        key = ob.shape_key_add(name='viseme_'+state)
        key.value = 0
        for p, co in zip(key.data, coords(w, h)):
            p.co = co
    # Cavity follows lip aperture; front surface sits just behind the rim.
    cavity = mesh('mouth', [(0, y-.0035, z)]+[(x, yy+.001, zz) for x, yy, zz in coords(*states['X'])[n:]],
                  [(0, i+1, (i+1)%n+1) for i in range(n)], dark)
    cavity.shape_key_add(name='Basis')
    for state, dims in states.items():
        key = cavity.shape_key_add(name='viseme_'+state)
        key.value = 0
        for p, co in zip(list(key.data)[1:], coords(*dims)[n:]):
            p.co = (co[0], co[1]+.001, co[2])
    tooth = ellipsoid('teeth', (0, y-.004, z+.009), (.036, .001, .006), teeth, 16, 6)
    tooth.hide_render = True


def hair_cap(material, style, width):
    n, vertices, faces = 24, [], []
    for r in range(7):
        t = .03 + r/6*1.44
        for i in range(n):
            a = i*2*math.pi/n
            front = max(0, math.cos(a))
            # High hairline at front; cover the back down toward the neck.
            end = 1.45 - .24*front if style != 'crop' else 1.31
            theta = t/1.47*end
            vertices.append((.17*width*math.sin(theta)*math.sin(a),
                             -.142*math.sin(theta)*math.cos(a), 1.58+.25*math.cos(theta)))
    for r in range(6):
        for i in range(n):
            a, b = r*n+i, r*n+(i+1)%n
            faces.append((a, b, b+n, a+n))
    mesh('hair-cap', vertices, faces, material)
    if style == 'bob':
        for side in (-1, 1):
            ellipsoid('hair-side', (side*.139*width, .027, 1.48), (.038, .094, .23), material, 16, 10)
    elif style == 'bun':
        ellipsoid('hair-bun', (0, .124, 1.74), (.09, .09, .09), material, 16, 10)
    elif style == 'curls':
        for i in range(14):
            a = i*2*math.pi/14
            ellipsoid('curl', (.127*width*math.sin(a), -.102*math.cos(a), 1.75+.013*(i%3)),
                      (.049, .048, .053), material, 10, 6)


def scene():
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 32
    sc.render.resolution_x = sc.render.resolution_y = 540
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'Standard'
    sc.world = bpy.data.worlds.new('Studio')
    sc.world.color = (.22, .22, .22)
    bpy.ops.object.camera_add(location=(0, -4, 1.35))
    camera = bpy.context.object
    camera.name = 'Camera'
    camera.rotation_euler = (Vector((0, 0, 1.35))-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = .74
    sc.camera = camera
    for name, loc, power, size in [('Key', (-2, -3, 4), 320, 4), ('Fill', (2, -2, 2), 150, 3), ('Rim', (1, 2, 3), 240, 2)]:
        bpy.ops.object.light_add(type='AREA', location=loc)
        lamp = bpy.context.object
        lamp.name, lamp.data.energy, lamp.data.shape, lamp.data.size = name, power, 'DISK', size
        lamp.rotation_euler = (Vector((0, 0, 1.5))-lamp.location).to_track_quat('-Z', 'Y').to_euler()


def build(index, gender):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference, skin_hex, hair_hex = PROFILES[index]
    ident = f'{gender}-{index+1:02}'
    skin = mat('skin', skin_hex)
    hair = mat('hair', '#aaa29b' if index == 7 and gender == 'man' else hair_hex)
    white, iris, dark = mat('sclera', '#dfd9cd'), mat('iris', '#4e483a'), mat('dark', '#271c1a')
    lip = mat('lip', '#' + ''.join(f'{max(0, int(skin_hex[i:i+2],16)-v):02x}' for i,v in ((1,22),(3,32),(5,18))))
    shirt = mat('shirt', ['#435e71', '#55736b', '#88685b', '#595774', '#657184'][index%5])
    width = [.98, .93, 1.03, .96, 1.0, 1.04, .95, .98, 1.02, 1.05][index]
    jaw = 1.02 if gender == 'man' else .90
    # Bust ends below the clavicles; no arms, hands or lower body.
    ellipsoid('shoulders', (0, .035, 1.04), (.31 if gender=='man' else .28, .135, .16), shirt, 24, 10)
    ellipsoid('neck', (0, .015, 1.20), (.064 if gender=='man' else .055, .065, .15), skin, 20, 10)
    head(skin, width, jaw)
    for side in (-1, 1):
        ellipsoid('ear', (side*.147*width, .005, 1.475), (.025, .030, .056), skin, 12, 8)
        x = side*.061*width
        eye = ellipsoid(f'eye-{side}', (x, -.108, 1.503), (.032, .014, .014), white, 16, 8, True)
        pupil = ellipsoid(f'iris-{side}', (x, -.122, 1.503), (.011, .003, .011), iris, 16, 8, True)
        ellipsoid(f'pupil-{side}', (x, -.125, 1.503), (.005, .002, .006), dark, 12, 6, True)
        brow = ellipsoid(f'brow-{side}', (x, -.115, 1.546), (.035, .007, .006), hair, 12, 6)
        brow['side'] = side
        lid = ellipsoid(f'lid-{side}', (x, -.127, 1.503), (.034, .004, .016), skin, 16, 8)
        lid.hide_render = True
    # Bridge and alar wings distinguish a face from a flat cartoon mask.
    ellipsoid('nose-bridge', (0, -.115, 1.46), (.020+(index%3)*.002, .025, .055), skin, 12, 8)
    ellipsoid('nose-tip', (0, -.140, 1.417), (.025+(index%3)*.003, .023, .018), skin, 12, 8)
    for side in (-1, 1):
        ellipsoid('nose-wing', (side*.022, -.128, 1.409), (.014, .014, .012), skin, 12, 6)
    mouth(lip, dark, white)
    style = (['crop', 'curls', 'crop', 'bun', 'crop', 'crop', 'curls', 'crop', 'crop', 'curls'] if gender=='man'
             else ['curls', 'bun', 'bob', 'bob', 'bun', 'bob', 'crop', 'bun', 'curls', 'bob'])[index]
    hair_cap(hair, style, width)
    for ob in bpy.context.scene.objects:
        if ob.type == 'MESH':
            ob.location.z = 1.18 + (ob.location.z - 1.18)*.78
            ob.scale.z *= .78
    scene()
    bpy.context.scene['avatar_id'] = ident
    bpy.context.scene['style_version'] = 1
    path = BANK / ident
    path.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path / 'avatar.blend'))
    bpy.ops.object.select_all(action='DESELECT')
    for ob in bpy.context.scene.objects:
        if ob.type == 'MESH' and not ob.hide_render:
            ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path / (ident+'.glb')), use_selection=True,
                              export_format='GLB', export_animations=False, export_morph=True)
    return {'id': ident, 'gender': gender, 'design_reference': reference, 'skin': skin_hex,
            'hair': style, 'glb': f'{ident}/{ident}.glb', 'blend': f'{ident}/avatar.blend', 'status': 'built'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only')
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    BANK.mkdir(parents=True, exist_ok=True)
    catalog = []
    for gender in ('man', 'woman'):
        for index in range(10):
            ident = f'{gender}-{index+1:02}'
            if args.only and args.only != ident:
                continue
            catalog.append(build(index, gender))
            if args.preview:
                bpy.context.scene.render.filepath = str(BANK / ident / 'preview.png')
                bpy.ops.render.render(write_still=True)
    if not catalog:
        raise ValueError('Unknown avatar ID')
    manifest = BANK / 'catalog.json'
    if args.only and manifest.exists():
        old = json.loads(manifest.read_text())
        catalog = [entry for entry in old['avatars'] if entry['id'] != args.only]+catalog
    manifest.write_text(json.dumps({'version': 1, 'avatars': catalog}, indent=2)+'\n')
    print(f'##JSON##{json.dumps({"built": len(catalog), "catalog": str(manifest)})}')


if __name__ == '__main__':
    main()
