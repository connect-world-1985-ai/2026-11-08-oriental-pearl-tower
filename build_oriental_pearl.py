"""Procedural Oriental Pearl Tower. Offline only: no downloaded assets.

Run:
  blender.exe -b -P build_oriental_pearl.py -- [--stills-only | --anim-only | --build-only]
      [--frames 1,120,240] [--scale 100]
"""

import math
import os
import sys
import time
import traceback

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = r"E:\Work\2026-11-08-oriental-pearl-blender\2026-11-08-project"
BLEND_PATH = os.path.join(ROOT, "oriental_pearl.blend")
MP4_PATH = os.path.join(ROOT, "oriental_pearl.mp4")
LOG_PATH = os.path.join(ROOT, "render_log.txt")

# Column centerline distance from the tower axis, in meters.
RAD_KEYS = (
    (0.0, 52.0),
    (16.0, 44.0),
    (36.0, 30.0),
    (58.0, 22.0),
    (78.0, 18.0),
    (98.0, 16.5),
    (130.0, 16.0),
    (175.0, 15.5),
    (230.0, 15.0),
    (263.0, 14.5),
    (295.0, 12.0),
    (322.0, 8.0),
    (346.0, 3.2),
)
THICK_KEYS = (
    (0.0, 3.15),
    (40.0, 2.55),
    (110.0, 2.15),
    (250.0, 2.00),
    (310.0, 1.55),
    (346.0, 1.05),
)
ANGLES = (math.radians(0.0), math.radians(120.0), math.radians(240.0))

# Open sections only, so braces stay out of the glass spheres.
BRACE_BANDS = (
    (5.0, 30.0, 1.85),
    (26.0, 54.0, 1.55),
    (50.0, 70.0, 1.35),
    (130.0, 154.0, 1.25),
    (186.0, 228.0, 1.25),
    (292.0, 318.0, 1.15),
)


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    opts = {
        "mode": "all",
        "frames": [1, 120, 240],
        "scale": 100,
    }
    index = 0
    while index < len(raw):
        token = raw[index]
        if token == "--stills-only":
            opts["mode"] = "stills"
        elif token == "--anim-only":
            opts["mode"] = "anim"
        elif token == "--build-only":
            opts["mode"] = "build"
        elif token == "--frames":
            index += 1
            opts["frames"] = [int(part) for part in raw[index].split(",") if part]
        elif token == "--scale":
            index += 1
            opts["scale"] = int(raw[index])
        else:
            raise SystemExit(f"Unknown argument: {token}")
        index += 1
    return opts


def lerp_keys(keys, z_value):
    if z_value <= keys[0][0]:
        return keys[0][1]
    if z_value >= keys[-1][0]:
        return keys[-1][1]
    for (z0, value0), (z1, value1) in zip(keys, keys[1:]):
        if z0 <= z_value <= z1:
            blend = (z_value - z0) / (z1 - z0)
            return value0 + (value1 - value0) * blend
    return keys[-1][1]


def axis_radius(z_value):
    return lerp_keys(RAD_KEYS, z_value)


def column_radius(z_value):
    return lerp_keys(THICK_KEYS, z_value)


def column_point(angle, z_value):
    radius = axis_radius(z_value)
    return Vector((radius * math.cos(angle), radius * math.sin(angle), z_value))


def link_mesh(name, bm, material):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.shade_smooth()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.children["OrientalPearl"].objects.link(obj)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def basis_from_dir(direction):
    axis_z = direction.normalized()
    helper = Vector((0.0, 1.0, 0.0))
    if abs(axis_z.dot(helper)) > 0.85:
        helper = Vector((1.0, 0.0, 0.0))
    axis_x = axis_z.cross(helper)
    if axis_x.length < 1e-8:
        axis_x = axis_z.cross(Vector((1.0, 0.0, 0.0)))
    axis_x.normalize()
    axis_y = axis_z.cross(axis_x).normalized()
    basis = Matrix.Identity(3)
    basis.col[0] = axis_x
    basis.col[1] = axis_y
    basis.col[2] = axis_z
    return basis


def add_tube(name, points, radius_at, sides, material):
    bm = bmesh.new()
    rings = []
    count = len(points)
    for index, point in enumerate(points):
        if index < count - 1:
            direction = points[index + 1] - point
        else:
            direction = point - points[index - 1]
        if direction.length < 1e-8:
            direction = Vector((0.0, 0.0, 1.0))
        basis = basis_from_dir(direction)
        radius = radius_at(point.z) if callable(radius_at) else float(radius_at)
        ring = []
        for side in range(sides):
            theta = 2.0 * math.pi * side / sides
            local = Vector((math.cos(theta) * radius, math.sin(theta) * radius, 0.0))
            ring.append(bm.verts.new(point + basis @ local))
        rings.append(ring)
    for index in range(count - 1):
        lower, upper = rings[index], rings[index + 1]
        for side in range(sides):
            nxt = (side + 1) % sides
            bm.faces.new((lower[side], lower[nxt], upper[nxt], upper[side]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return link_mesh(name, bm, material)


def add_sphere(name, location, radius, segments, rings, material):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(
        bm,
        u_segments=segments,
        v_segments=rings,
        radius=radius,
        matrix=Matrix.Translation(Vector(location)),
    )
    return link_mesh(name, bm, material)


def add_cylinder(name, location, radius, depth, segments, material):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segments,
        radius1=radius,
        radius2=radius,
        depth=depth,
        matrix=Matrix.Translation(Vector(location)),
    )
    return link_mesh(name, bm, material)


def add_cone(name, location, radius_bottom, radius_top, depth, segments, material):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segments,
        radius1=radius_bottom,
        radius2=radius_top,
        depth=depth,
        matrix=Matrix.Translation(Vector(location)),
    )
    return link_mesh(name, bm, material)


def add_torus(name, location, major, minor, major_segments, material):
    minor_segments = 8
    origin = Vector(location)
    bm = bmesh.new()
    rings = []
    for major_index in range(major_segments):
        theta = 2.0 * math.pi * major_index / major_segments
        radial = Vector((math.cos(theta), math.sin(theta), 0.0))
        center = origin + radial * major
        ring = []
        for minor_index in range(minor_segments):
            phi = 2.0 * math.pi * minor_index / minor_segments
            point = center + radial * (math.cos(phi) * minor) + Vector((0.0, 0.0, math.sin(phi) * minor))
            ring.append(bm.verts.new(point))
        rings.append(ring)
    for major_index in range(major_segments):
        major_next = (major_index + 1) % major_segments
        for minor_index in range(minor_segments):
            minor_next = (minor_index + 1) % minor_segments
            bm.faces.new(
                (
                    rings[major_index][minor_index],
                    rings[major_next][minor_index],
                    rings[major_next][minor_next],
                    rings[major_index][minor_next],
                )
            )
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return link_mesh(name, bm, material)


def add_plane(name, size, z_value, material):
    half = size * 0.5
    bm = bmesh.new()
    v1 = bm.verts.new((-half, -half, z_value))
    v2 = bm.verts.new((half, -half, z_value))
    v3 = bm.verts.new((half, half, z_value))
    v4 = bm.verts.new((-half, half, z_value))
    bm.faces.new((v1, v2, v3, v4))
    return link_mesh(name, bm, material)


def set_socket(bsdf, socket_name, value):
    socket = bsdf.inputs.get(socket_name)
    if socket is not None:
        socket.default_value = value


def new_material(name):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    return material, bsdf


def finish_glass(material):
    material.use_raytrace_refraction = True
    material.thickness_mode = "SPHERE"
    material.surface_render_method = "DITHERED"
    material.use_transparent_shadow = True


def build_materials():
    glass, bsdf = new_material("MagentaGlass")
    set_socket(bsdf, "Base Color", (0.78, 0.025, 0.22, 1.0))
    set_socket(bsdf, "Metallic", 0.0)
    set_socket(bsdf, "Roughness", 0.045)
    set_socket(bsdf, "IOR", 1.48)
    set_socket(bsdf, "Specular IOR Level", 0.55)
    set_socket(bsdf, "Transmission Weight", 0.88)
    set_socket(bsdf, "Coat Weight", 1.0)
    set_socket(bsdf, "Coat Roughness", 0.02)
    set_socket(bsdf, "Coat Tint", (1.0, 0.82, 0.90, 1.0))
    set_socket(bsdf, "Emission Color", (1.0, 0.12, 0.40, 1.0))
    set_socket(bsdf, "Emission Strength", 0.35)
    finish_glass(glass)
    glass.refraction_depth = 48.0

    core, bsdf = new_material("MagentaCore")
    set_socket(bsdf, "Base Color", (1.0, 0.12, 0.38, 1.0))
    set_socket(bsdf, "Roughness", 0.25)
    set_socket(bsdf, "Emission Color", (1.0, 0.14, 0.45, 1.0))
    set_socket(bsdf, "Emission Strength", 4.5)

    metal, bsdf = new_material("RoseMetal")
    set_socket(bsdf, "Base Color", (0.92, 0.72, 0.76, 1.0))
    set_socket(bsdf, "Metallic", 0.95)
    set_socket(bsdf, "Roughness", 0.22)
    set_socket(bsdf, "Coat Weight", 0.2)
    set_socket(bsdf, "Emission Color", (1.0, 0.45, 0.58, 1.0))
    set_socket(bsdf, "Emission Strength", 0.25)

    concrete, bsdf = new_material("Concrete")
    set_socket(bsdf, "Base Color", (0.74, 0.72, 0.69, 1.0))
    set_socket(bsdf, "Roughness", 0.62)
    set_socket(bsdf, "Specular IOR Level", 0.28)

    steel, bsdf = new_material("Steel")
    set_socket(bsdf, "Base Color", (0.32, 0.35, 0.40, 1.0))
    set_socket(bsdf, "Metallic", 0.88)
    set_socket(bsdf, "Roughness", 0.34)

    deck, bsdf = new_material("DeckMetal")
    set_socket(bsdf, "Base Color", (0.78, 0.80, 0.83, 1.0))
    set_socket(bsdf, "Metallic", 0.72)
    set_socket(bsdf, "Roughness", 0.28)

    capsule, bsdf = new_material("CapsuleMetal")
    set_socket(bsdf, "Base Color", (0.82, 0.84, 0.88, 1.0))
    set_socket(bsdf, "Metallic", 0.9)
    set_socket(bsdf, "Roughness", 0.18)
    set_socket(bsdf, "Coat Weight", 0.35)

    windows, bsdf = new_material("WindowLights")
    set_socket(bsdf, "Base Color", (0.85, 0.95, 1.0, 1.0))
    set_socket(bsdf, "Emission Color", (0.75, 0.92, 1.0, 1.0))
    set_socket(bsdf, "Emission Strength", 6.0)
    set_socket(bsdf, "Roughness", 0.2)

    antenna, bsdf = new_material("Antenna")
    set_socket(bsdf, "Base Color", (0.90, 0.91, 0.93, 1.0))
    set_socket(bsdf, "Metallic", 0.65)
    set_socket(bsdf, "Roughness", 0.25)
    set_socket(bsdf, "Emission Color", (0.85, 0.88, 0.95, 1.0))
    set_socket(bsdf, "Emission Strength", 0.35)

    beacon, bsdf = new_material("Beacon")
    set_socket(bsdf, "Base Color", (1.0, 0.02, 0.02, 1.0))
    set_socket(bsdf, "Emission Color", (1.0, 0.03, 0.02, 1.0))
    set_socket(bsdf, "Emission Strength", 25.0)

    plaza, bsdf = new_material("Plaza")
    set_socket(bsdf, "Base Color", (0.38, 0.37, 0.35, 1.0))
    set_socket(bsdf, "Roughness", 0.82)
    set_socket(bsdf, "Specular IOR Level", 0.2)

    water = make_water_material()
    return {
        "glass": glass,
        "core": core,
        "metal": metal,
        "concrete": concrete,
        "steel": steel,
        "deck": deck,
        "capsule": capsule,
        "windows": windows,
        "antenna": antenna,
        "beacon": beacon,
        "plaza": plaza,
        "water": water,
    }


def make_water_material():
    material, bsdf = new_material("River")
    set_socket(bsdf, "Base Color", (0.012, 0.028, 0.034, 1.0))
    set_socket(bsdf, "Metallic", 0.0)
    set_socket(bsdf, "Roughness", 0.045)
    set_socket(bsdf, "Specular IOR Level", 1.0)
    set_socket(bsdf, "IOR", 1.333)
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (0.006, 0.006, 0.006)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0
    noise.inputs["Detail"].default_value = 4.0
    noise.inputs["Roughness"].default_value = 0.5
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.045
    bump.inputs["Distance"].default_value = 0.6
    span = nodes.new("ShaderNodeMapRange")
    span.inputs["From Min"].default_value = 0.35
    span.inputs["From Max"].default_value = 0.75
    span.inputs["To Min"].default_value = 0.02
    span.inputs["To Max"].default_value = 0.12
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(noise.outputs["Fac"], span.inputs["Value"])
    links.new(span.outputs["Result"], bsdf.inputs["Roughness"])
    return material


def sphere_bands(location, radius, offsets, tube, material, name):
    center = Vector(location)
    for index, offset in enumerate(offsets):
        if abs(offset) >= radius * 0.96:
            continue
        major = math.sqrt(max(radius * radius - offset * offset, 0.25))
        add_torus(
            f"{name}_{index}",
            center + Vector((0.0, 0.0, offset)),
            major,
            tube,
            64,
            material,
        )


def build_tower(materials):
    for index, angle in enumerate(ANGLES):
        points = []
        z_value = 0.0
        while z_value < 346.0 - 1e-6:
            points.append(column_point(angle, z_value))
            z_value += 4.0
        points.append(column_point(angle, 346.0))
        add_tube(f"Column_{index}", points, column_radius, 14, materials["concrete"])
        foot = column_point(angle, 0.0)
        add_cylinder(
            f"Footing_{index}",
            (foot.x, foot.y, -1.1),
            8.0,
            2.4,
            20,
            materials["plaza"],
        )

    for band_index, (z0, z1, radius) in enumerate(BRACE_BANDS):
        for index, angle in enumerate(ANGLES):
            other = ANGLES[(index + 1) % 3]
            add_tube(
                f"BraceA_{band_index}_{index}",
                [column_point(angle, z0), column_point(other, z1)],
                radius,
                8,
                materials["steel"],
            )
            add_tube(
                f"BraceB_{band_index}_{index}",
                [column_point(other, z0), column_point(angle, z1)],
                radius,
                8,
                materials["steel"],
            )

    for z_value, tube in ((8.0, 1.5), (338.0, 0.7)):
        points = [column_point(angle, z_value) for angle in ANGLES]
        for index in range(3):
            add_tube(
                f"RingStrut_{int(z_value)}_{index}",
                [points[index], points[(index + 1) % 3]],
                tube,
                8,
                materials["steel"],
            )

    for z_value, tube in ((66.0, 1.55), (132.0, 1.25), (236.0, 1.15), (294.0, 1.05)):
        add_torus(
            f"Deck_{int(z_value)}",
            (0.0, 0.0, z_value),
            axis_radius(z_value),
            tube,
            48,
            materials["deck"],
        )

    lower = (0.0, 0.0, 98.0)
    upper = (0.0, 0.0, 263.0)
    add_sphere("LowerSphere", lower, 27.0, 64, 40, materials["glass"])
    add_sphere("LowerCore", lower, 14.0, 32, 20, materials["core"])
    sphere_bands(lower, 27.0, (-13.5, -1.5, 11.5), 0.42, materials["deck"], "LowerBand")

    add_sphere("UpperSphere", upper, 22.0, 64, 36, materials["glass"])
    add_sphere("UpperCore", upper, 11.2, 32, 18, materials["core"])
    sphere_bands(upper, 22.0, (-10.5, 0.5, 10.0), 0.38, materials["deck"], "UpperBand")

    for index, angle in enumerate(ANGLES):
        add_sphere(
            f"MidSphere_{index}",
            column_point(angle, 172.0),
            8.6,
            32,
            20,
            materials["metal"],
        )
        add_sphere(
            f"HighSphere_{index}",
            column_point(angle, 308.0),
            4.8,
            24,
            16,
            materials["metal"],
        )

    add_sphere("Capsule", (0.0, 0.0, 350.0), 11.0, 48, 28, materials["capsule"])
    add_torus("CapsuleWindows", (0.0, 0.0, 350.0), 11.15, 1.15, 48, materials["windows"])
    add_torus("CapsuleRim", (0.0, 0.0, 350.0), 8.2, 0.45, 32, materials["deck"])
    add_cylinder("Neck", (0.0, 0.0, 366.0), 1.7, 22.0, 12, materials["antenna"])
    add_sphere("TopPearl", (0.0, 0.0, 376.5), 4.6, 32, 20, materials["glass"])
    add_sphere("TopPearlCore", (0.0, 0.0, 376.5), 2.6, 16, 12, materials["core"])

    antenna_height = 86.0
    antenna_base = 382.0
    add_cone(
        "Antenna",
        (0.0, 0.0, antenna_base + antenna_height * 0.5),
        1.15,
        0.22,
        antenna_height,
        12,
        materials["antenna"],
    )
    add_sphere("MastBeadLow", (0.0, 0.0, 404.0), 2.7, 20, 14, materials["capsule"])
    add_sphere("MastBeadHigh", (0.0, 0.0, 436.0), 1.9, 16, 12, materials["capsule"])
    add_sphere("Beacon", (0.0, 0.0, 470.2), 2.15, 16, 12, materials["beacon"])


def build_site(materials):
    add_cylinder("Island", (0.0, 0.0, -3.0), 108.0, 6.0, 64, materials["plaza"])
    add_cylinder("Podium", (0.0, 0.0, -0.35), 36.0, 0.7, 32, materials["concrete"])
    add_plane("River", 8000.0, -3.15, materials["water"])


def build_world():
    world = bpy.data.worlds.new("PearlSky")
    bpy.context.scene.world = world
    if world.node_tree is None:
        world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputWorld")
    background = nodes.new("ShaderNodeBackground")
    sky = nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_disc = True
    sky.sun_size = math.radians(1.6)
    sky.sun_intensity = 0.22
    sky.sun_elevation = math.radians(16.0)
    sky.sun_rotation = math.radians(40.0)
    sky.altitude = 80.0
    sky.air_density = 1.2
    sky.aerosol_density = 2.2
    sky.ozone_density = 1.6
    background.inputs["Strength"].default_value = 0.08
    links.new(sky.outputs["Color"], background.inputs["Color"])
    links.new(background.outputs["Background"], output.inputs["Surface"])
    output.location = (400, 0)
    background.location = (160, 0)
    sky.location = (-120, 0)


def add_sun(name, energy, color, rotation):
    light = bpy.data.lights.new(name, "SUN")
    light.energy = energy
    light.color = color
    light.angle = math.radians(0.7)
    light.use_shadow = True
    obj = bpy.data.objects.new(name, light)
    obj.rotation_euler = rotation
    bpy.context.scene.collection.children["OrientalPearl"].objects.link(obj)
    return obj


def build_lights():
    add_sun(
        "KeySun",
        4.5,
        (1.0, 0.90, 0.78),
        (math.radians(74.0), 0.0, math.radians(40.0)),
    )
    add_sun(
        "FillSun",
        1.15,
        (0.62, 0.74, 1.0),
        (math.radians(78.0), 0.0, math.radians(215.0)),
    )
    add_sun(
        "RimSun",
        1.6,
        (1.0, 0.72, 0.78),
        (math.radians(82.0), 0.0, math.radians(150.0)),
    )


def set_linear_interpolation(action):
    curves = []
    if hasattr(action, "fcurves"):
        curves.extend(action.fcurves)
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                bags = list(strip.channelbags) if hasattr(strip, "channelbags") else []
                for bag in bags:
                    curves.extend(bag.fcurves)
    if not curves:
        raise RuntimeError("Orbit action has no fcurves")
    for curve in curves:
        for key in curve.keyframe_points:
            key.interpolation = "LINEAR"
            key.handle_left_type = "VECTOR"
            key.handle_right_type = "VECTOR"
    return len(curves)


def build_camera():
    scene = bpy.context.scene
    orbit = bpy.data.objects.new("Orbit", None)
    orbit.location = (0.0, 0.0, 230.0)
    target = bpy.data.objects.new("LookTarget", None)
    target.location = (0.0, 0.0, 230.0)
    collection = scene.collection.children["OrientalPearl"]
    collection.objects.link(orbit)
    collection.objects.link(target)

    camera_data = bpy.data.cameras.new("HeroCam")
    camera_data.lens = 28.0
    camera_data.sensor_fit = "HORIZONTAL"
    camera_data.sensor_width = 36.0
    camera_data.clip_start = 0.5
    camera_data.clip_end = 20000.0
    camera = bpy.data.objects.new("HeroCam", camera_data)
    camera.location = (0.0, -780.0, 0.0)
    collection.objects.link(camera)
    camera.parent = orbit
    constraint = camera.constraints.new("TRACK_TO")
    constraint.target = target
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"
    scene.camera = camera

    orbit.rotation_euler = (0.0, 0.0, 0.0)
    orbit.keyframe_insert(data_path="rotation_euler", frame=1)
    orbit.rotation_euler = (0.0, 0.0, math.tau)
    orbit.keyframe_insert(data_path="rotation_euler", frame=240)
    curve_count = set_linear_interpolation(orbit.animation_data.action)
    log(f"orbit fcurves set to LINEAR: {curve_count}")


def configure_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.render.fps_base = 1.0
    scene.frame_start = 1
    scene.frame_end = 240
    scene.render.film_transparent = False
    scene.render.use_overwrite = True
    scene.render.use_file_extension = False
    scene.render.use_persistent_data = True
    scene.eevee.taa_render_samples = 16
    scene.eevee.use_raytracing = True
    scene.eevee.use_shadows = True
    scene.eevee.use_fast_gi = False
    scene.eevee.use_taa_reprojection = False
    scene.eevee.shadow_ray_count = 1
    options = scene.eevee.ray_tracing_options
    options.resolution_scale = "4"
    options.use_denoise = True
    options.trace_max_roughness = 0.5
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception as exc:
        log(f"look unchanged: {exc}")
    log(
        "render "
        f"engine={scene.render.engine} samples={scene.eevee.taa_render_samples} "
        f"raytracing={scene.eevee.use_raytracing} scale={options.resolution_scale}"
    )


def render_stills(frames, scale):
    scene = bpy.context.scene
    scene.render.resolution_percentage = scale
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    started = time.perf_counter()
    for frame in frames:
        scene.frame_set(frame)
        if scale == 100:
            filename = f"frame_{frame:04d}.png"
        else:
            filename = f"preview_frame_{frame:04d}.png"
        path = os.path.join(ROOT, filename)
        scene.render.filepath = path
        log(f"still frame {frame} -> {path}")
        bpy.ops.render.render(write_still=True)
        log(f"still frame {frame} done, bytes={os.path.getsize(path)}")
    elapsed = time.perf_counter() - started
    log(f"stills elapsed {elapsed:.2f}s for {len(frames)} frame(s) at scale {scale}")
    return elapsed


def render_animation():
    scene = bpy.context.scene
    scene.render.resolution_percentage = 100
    scene.frame_start = 1
    scene.frame_end = 240
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.ffmpeg.gopsize = 12
    scene.render.filepath = MP4_PATH
    scene.render.use_file_extension = False
    if not scene.render.is_movie_format:
        raise RuntimeError("FFmpeg output was not accepted as a movie format")
    log(f"animation -> {MP4_PATH}")
    started = time.perf_counter()
    bpy.ops.render.render(animation=True)
    elapsed = time.perf_counter() - started
    size = os.path.getsize(MP4_PATH) if os.path.exists(MP4_PATH) else -1
    log(f"animation elapsed {elapsed:.2f}s bytes={size}")
    return elapsed


def build_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    collection = bpy.data.collections.new("OrientalPearl")
    scene.collection.children.link(collection)
    scene.unit_settings.system = "METRIC"
    materials = build_materials()
    build_site(materials)
    build_tower(materials)
    build_world()
    build_lights()
    build_camera()
    configure_render()
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    log(f"saved {BLEND_PATH} bytes={os.path.getsize(BLEND_PATH)}")


def main():
    opts = parse_args()
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(f"\n==== run mode={opts['mode']} {time.strftime('%Y-%m-%d %H:%M:%S')} ====\n")
    log(f"Blender {bpy.app.version_string} mode={opts['mode']} frames={opts['frames']} scale={opts['scale']}")
    started = time.perf_counter()
    build_scene()
    log(f"build elapsed {time.perf_counter() - started:.2f}s")
    if opts["mode"] in {"all", "stills"}:
        render_stills(opts["frames"], opts["scale"])
    if opts["mode"] in {"all", "anim"}:
        render_animation()
    log("finished")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        text = traceback.format_exc()
        print(text, flush=True)
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as handle:
                handle.write(text + "\n")
        except Exception:
            pass
        raise
