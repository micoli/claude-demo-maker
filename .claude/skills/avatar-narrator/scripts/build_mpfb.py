"""Build MPFB shoulder-up presenters in a fresh, isolated headless Blender process.

Run with --mpfb-root <mpfb source checkout> --assets <system pack> --targets <extra-targets checkout>.
No reset of the user's live scene; require background mode. Source geometry and facial shapes are CC0.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/avatar-mpfb'
VISEMES = {'A': 'viseme_PP', 'B': 'viseme_SS', 'C': 'viseme_E', 'D': 'viseme_aa',
           'E': 'viseme_O', 'F': 'viseme_U', 'G': 'viseme_FF', 'H': 'viseme_nn', 'X': 'viseme_sil'}
EXPRESSIONS = {'neutral': {}, 'warm': {'mouthSmileLeft': .3, 'mouthSmileRight': .3, 'cheekSquintLeft': .15, 'cheekSquintRight': .15},
               'concerned': {'browInnerUp': .35, 'browDownLeft': .2, 'browDownRight': .2},
               'surprised': {'browInnerUp': .45, 'browOuterUpLeft': .4, 'browOuterUpRight': .4, 'eyeWideLeft': .3, 'eyeWideRight': .3}}


def material(name, color):
    rgb = [int(color[i:i+2], 16)/255 for i in (1,3,5)]
    rgb = [c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in rgb]
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1)
    mat.use_nodes = True
    shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value = (*rgb, 1)
    shader.inputs['Roughness'].default_value = .72
    return mat


def fit_surface_clearance(human, garment, body, bottom):
    world = human.matrix_world
    surface = BVHTree.FromPolygons(
        [world @ vertex.co for vertex in human.data.vertices],
        [tuple(face.vertices) for face in human.data.polygons if all(i in body for i in face.vertices)],
    )
    garment_world = garment.matrix_world
    inverse = garment_world.inverted()
    for vertex in garment.data.vertices:
        point = garment_world @ vertex.co
        if point.z < bottom - .04:
            continue
        nearest, normal, _, _ = surface.find_nearest(point, .03)
        if nearest is not None and (point - nearest).dot(normal) < .003:
            vertex.co = inverse @ (nearest + normal * .003)


def covered_torso_vertices(human, garment, body, bottom):
    garment_world = garment.matrix_world
    cloth = BVHTree.FromPolygons(
        [garment_world @ vertex.co for vertex in garment.data.vertices],
        [tuple(face.vertices) for face in garment.data.polygons],
    )
    covered = set()
    world = human.matrix_world
    normal_transform = world.to_3x3().inverted().transposed()
    for index in body:
        vertex = human.data.vertices[index]
        point = world @ vertex.co
        if not bottom <= point.z <= bottom + .085:
            continue
        normal = (normal_transform @ vertex.normal).normalized()
        if any(cloth.ray_cast(point, direction, .05)[0] is not None for direction in (normal, -normal)):
            covered.add(index)
    return covered


def crop_mesh(ob, allowed, min_z, max_x, blocked=None):
    """Copy a vertex subset and every corresponding morph/UV; preserve morph deltas exactly."""
    source = ob.data
    keep = {v.index for v in source.vertices if v.index in allowed and (ob.matrix_world @ v.co).z >= min_z and abs((ob.matrix_world @ v.co).x) <= max_x}
    faces = [p for p in source.polygons if p.index not in (blocked or set()) and all(i in keep for i in p.vertices)]
    used = sorted({i for p in faces for i in p.vertices})
    remap = {old: new for new, old in enumerate(used)}
    data = bpy.data.meshes.new(ob.name+'-bust')
    data.from_pydata([source.vertices[i].co for i in used], [], [[remap[i] for i in p.vertices] for p in faces])
    for mat in source.materials:
        data.materials.append(mat)
    for new, old in zip(data.polygons, faces):
        new.material_index = old.material_index
        new.use_smooth = True
    for layer in source.uv_layers:
        uv = data.uv_layers.new(name=layer.name)
        for new, old in zip(data.polygons, faces):
            for li, old_li in zip(new.loop_indices, old.loop_indices):
                uv.data[li].uv = layer.data[old_li].uv
    shapes = source.shape_keys
    ob.data = data
    for mod in list(ob.modifiers):
        ob.modifiers.remove(mod)
    if shapes:
        for original in shapes.key_blocks:
            shape = ob.shape_key_add(name=original.name, from_mix=False)
            shape.value = 0
            for point, old in zip(shape.data, used):
                point.co = original.data[old].co
    # Straighten only the lower cut boundary; keep all face and neck morph deltas intact.
    edge_counts = {}
    for polygon in data.polygons:
        ids = list(polygon.vertices)
        for a, b in zip(ids, ids[1:]+ids[:1]):
            pair = tuple(sorted((a, b)))
            edge_counts[pair] = edge_counts.get(pair, 0)+1
    boundary = {i for edge, count in edge_counts.items() if count == 1 for i in edge}
    inverse = ob.matrix_world.to_3x3().inverted()
    for i in boundary:
        world = ob.matrix_world @ data.vertices[i].co
        if world.z < min_z+.075:
            offset = inverse @ Vector((0,0,min_z-world.z))
            data.vertices[i].co += offset
            if data.shape_keys:
                for key in data.shape_keys.key_blocks:
                    key.data[i].co += offset
    return len(data.polygons)


def studio(top, bottom):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 32
    scene.render.resolution_x = scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'AgX'
    scene.world = bpy.data.worlds.new('Studio')
    scene.world.color = (.15,.15,.15)
    target = Vector((0,0,(top+bottom)/2))
    bpy.ops.object.camera_add(location=(0,-3,target.z))
    camera=bpy.context.object
    camera.name='Camera'
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO'
    camera.data.ortho_scale=max(.56, (top-bottom)*1.13)
    scene.camera=camera
    for name, offset, energy, size in [('Key',(-1.5,-2,2),180,2.5),('Fill',(1.5,-1,1),100,2),('Rim',(1,1,1.5),220,1.5)]:
        bpy.ops.object.light_add(type='AREA',location=target+Vector(offset))
        lamp=bpy.context.object
        lamp.name=name
        lamp.data.energy=energy
        lamp.data.size=size
        lamp.rotation_euler=(target-lamp.location).to_track_quat('-Z','Y').to_euler()



def tint_hair(hair, hex_color):
    # Bake tint into a small RGBA texture: preserve alpha and direct GLB texture links.
    import numpy as np
    color=np.array([int(hex_color[i:i+2],16)/255 for i in (1,3,5)],dtype=np.float32)
    for mat in hair.data.materials:
        if not mat.use_nodes:
            continue
        shader=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
        if shader is None:
            continue
        sources={node.image for node in mat.node_tree.nodes if node.type=='TEX_IMAGE' and node.image}
        for source in sources:
            if max(source.size)>1024:
                factor=1024/max(source.size)
                source.scale(max(1,round(source.size[0]*factor)),max(1,round(source.size[1]*factor)))
            pixels=np.empty(len(source.pixels),dtype=np.float32)
            source.pixels.foreach_get(pixels)
            rgba=pixels.reshape(-1,4)
            brightness=np.clip(rgba[:,:3].mean(axis=1)*1.5,0,1)
            rgba[:,:3]=np.clip(color[None,:]*(.35+brightness[:,None]*.85),0,1)
            tinted=bpy.data.images.new(source.name+'-tinted',width=source.size[0],height=source.size[1],alpha=True)
            tinted.pixels.foreach_set(pixels)
            tinted.update()
            tinted.pack()
            for node in mat.node_tree.nodes:
                if node.type=='TEX_IMAGE' and node.image==source:
                    node.image=tinted


def eye_clearance_faces(hair, eyes):
    # Conservative front and +/-30-degree protection of the complete eyeball band.
    # Operate after MPFB shape transfer so original vertex indices remain valid.
    blocked=set()
    for angle in (0, -math.pi/6, math.pi/6):
        def project(point):
            return (point.x*math.cos(angle)+point.y*math.sin(angle),
                    -point.x*math.sin(angle)+point.y*math.cos(angle),point.z)
        eye_points=[project(eyes.matrix_world@v.co) for v in eyes.data.vertices]
        x0=min(p[0] for p in eye_points)-.008; x1=max(p[0] for p in eye_points)+.008
        z0=min(p[2] for p in eye_points)-.004; z1=max(p[2] for p in eye_points)+.008
        front=max(p[1] for p in eye_points)
        for polygon in hair.data.polygons:
            points=[project(hair.matrix_world@hair.data.vertices[i].co) for i in polygon.vertices]
            if min(p[1] for p in points)<front and max(p[0] for p in points)>=x0 and min(p[0] for p in points)<=x1 and max(p[2] for p in points)>=z0 and min(p[2] for p in points)<=z1:
                blocked.add(polygon.index)
    return blocked


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mpfb-root',required=True,type=Path)
    parser.add_argument('--assets',required=True,type=Path)
    parser.add_argument('--targets',required=True,type=Path)
    parser.add_argument('--only')
    parser.add_argument('--outfit', help='Override the outfit when building one avatar')
    parser.add_argument('--group',choices=['man','woman','neutral'],help='Rebuild only one group in --bank mode')
    parser.add_argument('--bank',action='store_true',help='Build ten men, ten women and ten neutral presenters from profiles.json')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.outfit and not args.only:
        parser.error('--outfit requires --only')
    wardrobe = ROOT / 'assets/wardrobe'
    outfits = json.loads((wardrobe / 'catalog.json').read_text())
    hairstyle_root = ROOT / 'assets/hairstyles'
    hairstyle_catalog = hairstyle_root / 'catalog.json'
    hairstyles = json.loads(hairstyle_catalog.read_text()) if hairstyle_catalog.is_file() else {}
    if args.outfit and args.outfit not in outfits:
        parser.error(f'Unknown outfit. Choose from {", ".join(outfits)}')
    if not bpy.app.background:
        raise RuntimeError('Use a separate headless Blender process; do not run in a live scene')
    for path in (args.mpfb_root/'src/mpfb/blender_manifest.toml', args.assets, args.targets/'assets/visemes02'):
        if not path.exists():
            raise FileNotFoundError(path)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.context.preferences.extensions.repos.new(name='MPFB job',module='mpfb_job',custom_directory=str(args.mpfb_root.resolve()/'src'),source='USER')
    import addon_utils
    addon_utils.enable('bl_ext.mpfb_job.mpfb',default_set=True,persistent=False)
    from bl_ext.mpfb_job.mpfb.services.humanservice import HumanService
    from bl_ext.mpfb_job.mpfb.services.targetservice import TargetService
    from bl_ext.mpfb_job.mpfb.services.faceservice import FaceService
    from bl_ext.mpfb_job.mpfb.services.locationservice import LocationService
    import shutil
    data=Path(LocationService.get_user_data())
    shutil.copytree(args.assets, data, dirs_exist_ok=True)
    for name in ('visemes02','faceunits01'):
        shutil.copytree(args.targets/'assets'/name, data, dirs_exist_ok=True)
    profiles=json.loads((Path(__file__).resolve().parents[1]/'assets/profiles.json').read_text())['avatars'] if args.bank else [
        {'id':'pilot-man','gender':1,'skin':'#b27e5b','hair':'short01','hair_color':'#28221d','age':.43,'race':{'african':.55,'asian':.15,'caucasian':.3}},
        {'id':'pilot-woman','gender':0,'skin':'#ca9d7e','hair':'ponytail01','hair_color':'#59402e','age':.43,'race':{'african':.15,'asian':.55,'caucasian':.3}}]
    if args.group:
        if not args.bank:
            raise ValueError('--group requires --bank')
        profiles=[p for p in profiles if p['id'].startswith(args.group+'-')]
    if args.only and args.only not in {p['id'] for p in profiles}:
        raise ValueError('Unknown avatar ID for the selected pilot/bank mode')
    catalog=[]
    for profile in profiles:
        ident,gender,skin_hex,hairname=[profile[k] for k in ['id','gender','skin','hair']]
        if args.only and args.only != ident:
            continue
        for ob in list(bpy.context.scene.objects):
            bpy.data.objects.remove(ob,do_unlink=True)
        bpy.data.orphans_purge(do_recursive=True)
        print('BUILDING '+ident,flush=True)
        macro=TargetService.get_default_macro_info_dict()
        macro.update({key:profile.get(key,default) for key,default in [('gender',gender),('age',.43),('muscle',.45),('weight',.43),('proportions',.5)]})
        macro['race']=profile['race']
        human=HumanService.create_human(macro_detail_dict=macro)
        human.name='mpfb-face'
        for target, weight in profile.get('details',{}).items():
            path=args.mpfb_root/'src/mpfb/data/targets'/(target+'.target.gz')
            if not path.is_file():
                raise FileNotFoundError(path)
            TargetService.load_target(human,str(path),weight=weight)
        # Bake macro shape into Basis while retaining the full original vertex numbering for target loading.
        baked=human.shape_key_add(name='Baked',from_mix=True)
        coords=[p.co.copy() for p in baked.data]
        human.shape_key_clear()
        for v, co in zip(human.data.vertices,coords):
            v.co=co
        human.data.materials.clear()
        skin=material('Skin',skin_hex)
        human.data.materials.append(skin)
        human.data.materials.append(material('Lips','#'+''.join(f'{max(0,int(skin_hex[i:i+2],16)-d):02x}' for i,d in [(1,10),(3,20),(5,12)])))
        def group_members(name):
            idx=human.vertex_groups[name].index
            return {v.index for v in human.data.vertices if any(g.group==idx and g.weight>.5 for g in v.groups)}
        body=group_members('body')
        lips=group_members('lips')
        top=max((human.matrix_world @ human.data.vertices[i].co).z for i in body)
        bottom=top-.33
        for face in human.data.polygons:
            face.material_index = int(len(set(face.vertices) & lips) >= len(face.vertices) * .75)
        outfit_id = args.outfit or profile.get('outfit') or ('shirt' if gender >= .5 else 'blouse')
        outfit = outfits[outfit_id]
        garment_file = wardrobe / outfit['file']
        garment = HumanService.add_mhclo_asset(str(garment_file), human, subdiv_levels=0, set_up_rigging=False)
        garment['avatar_garment'] = outfit_id
        bpy.context.view_layer.update()
        delete_group = 'Delete.' + garment_file.stem.replace(' ', '_')
        covered = group_members(delete_group) if delete_group in human.vertex_groups else set()
        fit_surface_clearance(human, garment, body, bottom)
        if not covered:
            covered = covered_torso_vertices(human, garment, body, bottom)
        assets_used=[]
        def asset(subdir, filename, kind, required=True):
            matches=list(args.assets.rglob(filename))
            if not matches:
                if required:
                    raise FileNotFoundError(f'{subdir}/{filename} in {args.assets}')
                return None
            path=matches[0]
            ob=HumanService.add_mhclo_asset(str(path),human,asset_type=kind,subdiv_levels=0,set_up_rigging=False)
            assets_used.append({'file':str(path.relative_to(args.assets)),'type':kind,'license':'CC0'})
            return ob
        eye=asset('eyes','low-poly.mhclo','Eyes')
        asset('eyebrows','eyebrow001.mhclo','Eyebrows')
        asset('eyelashes','eyelashes01.mhclo','Eyelashes')
        asset('teeth','teeth_base.mhclo','Teeth')
        asset('tongue','tongue01.mhclo','Tongue')
        hair=None
        if hairname != 'bald':
            if hairname in hairstyles:
                hairstyle = hairstyles[hairname]
                hair = HumanService.add_mhclo_asset(str(hairstyle_root / hairstyle['file']), human,
                                                    asset_type='Hair', subdiv_levels=0, set_up_rigging=False)
                bpy.context.view_layer.update()
                fit_surface_clearance(human, hair, body, bottom)
                assets_used.append({'type': 'Hair', **hairstyle})
            else:
                hair = asset('hair', hairname+'.mhclo', 'Hair')
            hair['avatar_hair'] = hairname
            tint_hair(hair,profile['hair_color'])
        FaceService.load_targets(human,load_microsoft_visemes=False,load_meta_visemes=True,load_arkit_faceunits=True)
        FaceService.interpolate_targets(human)
        # Crop only after all official targets were loaded/transferred against original topology.
        blocked=eye_clearance_faces(hair,eye) if hair else set()
        meshes=[ob for ob in bpy.context.scene.objects if ob.type=='MESH']
        for ob in meshes:
            allowed=body - covered if ob==human else set(range(len(ob.data.vertices)))
            crop_mesh(ob,allowed,bottom,.29,blocked if ob==hair else set())
        studio(top+.025,bottom)
        scene=bpy.context.scene
        scene['avatar_generator']='mpfb'
        scene['avatar_id']=ident
        scene['avatar_controls']=json.dumps({'visemes':VISEMES,'blink':{'eyeBlinkLeft':1,'eyeBlinkRight':1},'expressions':EXPRESSIONS})
        # Simple materials are GLB-compatible; keep textures in the editable source and pack them.
        for image in bpy.data.images:
            if image.source != 'FILE' or image.packed_file or not image.users:
                continue
            width, height = image.size
            if not width or not height:
                raise ValueError(f'Cannot load avatar texture {image.filepath}')
            if max(width, height) > 1024:
                factor = 1024 / max(width, height)
                image.scale(max(1, round(width * factor)), max(1, round(height * factor)))
            image.pack()
        folder=OUT/ident
        folder.mkdir(parents=True,exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(folder/'avatar.blend'))
        bpy.ops.object.select_all(action='DESELECT')
        for ob in meshes:
            ob.select_set(True)
        bpy.ops.export_scene.gltf(filepath=str(folder/(ident+'.glb')),use_selection=True,export_format='GLB',export_animations=False,export_morph=True,export_apply=False)
        scene.render.filepath=str(folder/'preview.png')
        bpy.ops.render.render(write_still=True)
        info={'profile':profile,'outfit':{'id':outfit_id,**outfit},'hair_eye_clearance':{'protected':True,'trimmed_faces':len(blocked)},'generator':'mpfb','version':'2.0.18','id':ident,'visual_approval':'pending','macro':macro,'assets':assets_used,'controls':json.loads(scene['avatar_controls']),'source':'https://github.com/makehumancommunity/mpfb2/tree/v2.0.18','geometry_license':'CC0-1.0','triangles':sum(sum(len(p.vertices)-2 for p in ob.data.polygons) for ob in meshes)}
        (folder/'provenance.json').write_text(json.dumps(info,indent=2)+'\n')
        catalog.append({'id':ident,'generator':'mpfb','blend':ident+'/avatar.blend','glb':ident+'/'+ident+'.glb','preview':ident+'/preview.png','gender':profile.get('group','man' if gender >= .75 else 'woman' if gender <= .25 else 'neutral'),'hair':hairname,'visual_approval':'pending','triangles':info['triangles']})
        if args.bank:
            manifest=OUT/'catalog.json'
            previous=json.loads(manifest.read_text())['avatars'] if manifest.exists() else []
            previous=[entry for entry in previous if entry['id'] != ident]+[catalog[-1]]
            manifest.write_text(json.dumps({'version':1,'generator':'mpfb','avatars':sorted(previous,key=lambda p:p['id'])},indent=2)+'\n')
        print('##JSON##'+json.dumps({'id':ident,'status':'exported','triangles':info['triangles'],'progress':len(catalog),'requested':1 if args.only else len(profiles)}),flush=True)

    if args.bank:
        path=OUT/'catalog.json'
        if (args.only or args.group) and path.exists():
            old=json.loads(path.read_text())['avatars']
            rebuilt={p['id'] for p in catalog}
            catalog=[p for p in old if p['id'] not in rebuilt]+catalog
        path.write_text(json.dumps({'version':1,'generator':'mpfb','avatars':sorted(catalog,key=lambda p:p['id'])},indent=2)+'\n')


if __name__=='__main__':
    main()
