"""Set the portrait lighting for both new and existing MPFB scenes."""

import bpy
from mathutils import Vector


def apply_portrait_lighting(scene, lighting='studio'):
    target = Vector((0, 0, scene.camera.location.z + .055))
    soft = lighting == 'soft'
    lamps = (
        ('Key', (-1.15, -1.85, 1.05), 110, 1.25, (1, .93, .86)),
        ('Fill', (1.55, -1.25, .38), 35 if soft else 29, 1.65, (.86, .94, 1)),
        ('Rim', (.65, 1.25, 1.40), 72 if soft else 105, 1.0, (1, .89, .80)),
    )
    for name, offset, energy, size, color in lamps:
        lamp = scene.objects.get(name)
        if lamp is None:
            data = bpy.data.lights.new(name, 'AREA')
            lamp = bpy.data.objects.new(name, data)
            scene.collection.objects.link(lamp)
        lamp.location = target + Vector(offset)
        lamp.rotation_euler = (target - lamp.location).to_track_quat('-Z', 'Y').to_euler()
        lamp.data.shape = 'DISK'
        lamp.data.energy = energy
        lamp.data.size = size
        lamp.data.color = color

    if scene.world is None:
        scene.world = bpy.data.worlds.new('Studio')
    scene.world.color = (.08, .08, .08)
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = 0
