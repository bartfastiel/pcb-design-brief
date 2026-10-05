"""Exploded, realistic layer stack of a KiCad board (brief §12.4), rendered with Blender Cycles.

Input is a GLB from
  kicad-cli pcb export glb --include-tracks --include-pads --include-silkscreen --include-soldermask board.kicad_pcb
Run:
  blender -b --python layer_stack.py -- board.glb out.png [--gap 14] [--core-scale 1] [--light 0.05] [--background 0.94] [--size 1800x1500] [--samples 96]
Writes out.png (transparent background) and out.json: per layer its name, the screen point for a label leader (rightmost point of the layer)
and the screen bounding box, in pixels, so labels and PDF links can be added afterwards. Empty layers are left out."""
import json
import math
import os
import sys

import bpy
import bmesh
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ORDER = ["parts_top", "silk_top", "mask_top", "copper_top", "core", "copper_bottom", "mask_bottom", "silk_bottom",
         "parts_bottom"]


def args():
    argv = sys.argv[sys.argv.index("--") + 1:]
    opts = {"gap": 14.0, "core_scale": 1.0, "size": "1800x1500", "samples": 96, "elevation": 30.0, "azimuth": -22.0,
            "light": 0.05, "ambient": 0.25, "background": 0.94}
    pos = []
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i][2:].replace("-", "_")
            opts[key] = type(opts[key])(argv[i + 1]) if not isinstance(opts[key], str) else argv[i + 1]
            i += 2
        else:
            pos.append(argv[i])
            i += 1
    opts["glb"], opts["png"] = pos
    return opts


def bounds(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def split_by_face_height(obj, low, high):
    """Separates faces whose centre lies between low and high (via barrels) into a new object."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    mesh = bmesh.from_edit_mesh(obj.data)
    picked = 0
    for face in mesh.faces:
        z = (obj.matrix_world @ face.calc_center_median()).z
        face.select = low < z < high
        picked += face.select
    bmesh.update_edit_mesh(obj.data)
    if picked in (0, len(mesh.faces)):
        bpy.ops.object.mode_set(mode="OBJECT")
        return obj if picked else None
    bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    parts = [o for o in bpy.context.selected_objects if o is not obj]
    return parts[0] if parts else None


def classify(objects, thickness):
    groups = {name: [] for name in ORDER}
    flat, copper = [], []
    body = None
    for obj in objects:
        lo, hi = bounds(obj)
        extent = hi[2] - lo[2]
        if extent < 0.02 * thickness:
            flat.append(obj)
        elif lo[2] > -0.01 * thickness and hi[2] < thickness * 1.01 and extent > 0.5 * thickness and body is None:
            body = obj
        elif lo[2] < 0.01 * thickness and hi[2] > 0.99 * thickness and hi[2] < thickness * 1.2 and lo[2] > -0.2 * thickness:
            copper.append(obj)
        else:
            groups["parts_top" if (lo[2] + hi[2]) / 2 > thickness / 2 else "parts_bottom"].append(obj)
    groups["core"].append(body)
    flat.sort(key=lambda o: bounds(o)[0][2])
    top = [o for o in flat if bounds(o)[0][2] > thickness / 2]
    bottom = [o for o in flat if bounds(o)[0][2] <= thickness / 2]
    if top:
        groups["silk_top"].append(top[-1])
        groups["mask_top"] += top[:-1]
    if bottom:
        groups["silk_bottom"].append(bottom[0])
        groups["mask_bottom"] += bottom[1:]
    for obj in copper:
        barrels = split_by_face_height(obj, 0.08 * thickness, 0.92 * thickness)
        if barrels:
            groups["core"].append(barrels)
        bottom_part = split_by_face_height(obj, -thickness, thickness / 2)
        if bottom_part is not obj:
            groups["copper_top"].append(obj)
        if bottom_part:
            groups["copper_bottom"].append(bottom_part)
    return {k: [o for o in v if o is not None] for k, v in groups.items() if any(o is not None for o in v)}


def material(name, colour, metallic=0.0, roughness=0.5, alpha=1.0, transmission=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*colour, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Alpha"].default_value = alpha
    bsdf.inputs["Transmission Weight"].default_value = transmission
    return mat


def restyle(groups):
    mats = {
        "silk": material("silk", (0.92, 0.92, 0.9), roughness=0.7),
        "mask": material("mask", (0.02, 0.28, 0.1), roughness=0.22, alpha=0.92),
        "copper": material("copper", (0.95, 0.55, 0.36), metallic=1.0, roughness=0.28),
        "core": material("fr4", (0.86, 0.72, 0.38), roughness=0.55, transmission=0.15),
    }
    for name, objs in groups.items():
        kind = name.split("_")[0]
        for obj in objs:
            if kind in mats:
                obj.data.materials.clear()
                obj.data.materials.append(mats[kind])
            if kind in ("silk", "mask"):
                mod = obj.modifiers.new("thickness", "SOLIDIFY")
                mod.thickness = 0.00004


def explode(groups, gap, core_scale, thickness):
    names = [n for n in ORDER if n in groups]
    core_i = names.index("core")
    offsets = {}
    for i, name in enumerate(names):
        offsets[name] = (core_i - i) * gap
    for name, objs in groups.items():
        for obj in objs:
            if name == "core":
                obj.scale.z *= core_scale
                obj.location.z = obj.location.z * core_scale - thickness * (core_scale - 1) / 2
            extra = (core_scale - 1) * thickness / 2
            shift = offsets[name] + (extra if offsets[name] > 0 else -extra if offsets[name] < 0 else 0)
            obj.location.z += shift
    bpy.context.view_layer.update()
    return names


def studio(world_strength, background):
    world = bpy.data.worlds.new("studio")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    mix = nt.nodes.new("ShaderNodeMixShader")
    path = nt.nodes.new("ShaderNodeLightPath")
    env = nt.nodes.new("ShaderNodeBackground")
    env.inputs["Color"].default_value = (0.8, 0.82, 0.85, 1)
    env.inputs["Strength"].default_value = world_strength
    white = nt.nodes.new("ShaderNodeBackground")
    white.inputs["Color"].default_value = (background, background, background, 1)
    white.inputs["Strength"].default_value = 1.0
    nt.links.new(path.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(env.outputs[0], mix.inputs[1])
    nt.links.new(white.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])


def add_light(name, location, energy, size, target):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    direction = Vector(target) - Vector(location)
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return obj


def frame_camera(objects, elevation, azimuth, size, margin=1.08):
    scene = bpy.context.scene
    w, h = (int(v) for v in size.split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 70
    cam_data.clip_start = 1e-4
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    coords = []
    for obj in objects:
        coords += [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    centre = sum(coords, Vector()) / len(coords)
    el, az = math.radians(elevation), math.radians(azimuth)
    direction = Vector((math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)))
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    cam.location = centre + direction
    bpy.context.view_layer.update()
    flat = [c for v in coords for c in ((v - centre) * margin + centre)]
    location, _ = cam.camera_fit_coords(bpy.context.evaluated_depsgraph_get(), flat)
    cam.location = location
    bpy.context.view_layer.update()
    return cam, centre


def screen_info(cam, objs):
    scene = bpy.context.scene
    w, h = scene.render.resolution_x, scene.render.resolution_y
    pts = []
    for obj in objs:
        mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        for v in mesh.vertices:
            p = world_to_camera_view(scene, cam, obj.matrix_world @ v.co)
            pts.append((p.x * w, (1 - p.y) * h))
    right = max(pts, key=lambda p: p[0])
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return {"anchor": [round(right[0], 1), round(right[1], 1)],
            "bbox": [round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)]}


def main():
    opts = args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=opts["glb"])
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for obj in meshes:
        obj.matrix_world = obj.matrix_world.copy()
    def footprint_area(obj):
        lo, hi = bounds(obj)
        return (hi[0] - lo[0]) * (hi[1] - lo[1]) if lo[2] > -1e-5 and hi[2] - lo[2] > 1e-4 else 0
    body = max(meshes, key=footprint_area)
    thickness = bounds(body)[1][2] - bounds(body)[0][2]
    groups = classify(meshes, thickness)
    restyle(groups)
    gap = opts["gap"] / 1000
    names = explode(groups, gap, opts["core_scale"], thickness)
    studio(opts["ambient"], opts["background"])
    every = [o for objs in groups.values() for o in objs]
    cam, centre = frame_camera(every, opts["elevation"], opts["azimuth"], opts["size"])
    span = max(max(bounds(o)[1][i] for o in every) - min(bounds(o)[0][i] for o in every) for i in range(3))
    add_light("key", centre + Vector((-0.6, -0.9, 1.4)) * span, opts["light"] * 1.0, span * 0.8, centre)
    add_light("fill", centre + Vector((1.2, -0.6, 0.6)) * span, opts["light"] * 0.35, span, centre)
    add_light("rim", centre + Vector((0.3, 1.2, 0.9)) * span, opts["light"] * 0.5, span * 0.6, centre)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = opts["samples"]
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "Standard"
    scene.render.film_transparent = True
    scene.render.filepath = os.path.abspath(opts["png"])
    bpy.ops.render.render(write_still=True)
    info = {"order": names, "layers": {name: screen_info(cam, groups[name]) for name in names},
            "size": [scene.render.resolution_x, scene.render.resolution_y],
            "board_thickness_mm": round(thickness * 1000, 3), "gap_mm": opts["gap"], "core_scale": opts["core_scale"]}
    with open(os.path.splitext(scene.render.filepath)[0] + ".json", "w", encoding="utf-8") as handle:
        json.dump(info, handle, indent=1)
    print("LAYERS", " ".join(names))


main()
