"""Realistic product render from a JSON scene description (brief §12.1 and §12.3), Blender Cycles.

  blender -b --python exploded_scene.py -- scene.json out.png

scene.json (lengths in mm):
  {"size": "2400x1500", "samples": 128, "camera": {"elevation": 28, "azimuth": -35, "lens": 60, "margin": 1.06},
   "light": 0.6, "ambient": 0.25, "background": 0.94,
   "parts": [
     {"name": "base", "file": "base.stl", "offset": [0, 0, 0], "material": {"color": [0.03, 0.03, 0.03], "roughness": 0.4}},
     {"name": "board", "file": "board.glb", "offset": [27, 25.1, 37], "uniform_finish": true},  # GLB keeps its materials
     {"name": "psu", "box": [[-80, -10, 20], [-35, 38, 60]], "bevel": 4, "material": {...}},
     {"name": "cable", "curve": [[160, 14, 42], [200, 14, 42], [230, 30, 10]], "radius": 2, "material": {...}}]}
camera "ortho": [x, y, width] renders a parallel view of that width centred on (x, y), e.g. elevation 90 for a plan; "roll" turns the image about the view axis in degrees.
Material keys: color (linear RGB), metallic, roughness, alpha, transmission. Parts with the same name form one group.
Writes out.png and out.json with the screen bounding box of every group in pixels (for PDF links and callouts)."""
import json
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

MM = 0.001


def make_material(name, spec):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*spec.get("color", [0.8, 0.8, 0.8]), 1)
    bsdf.inputs["Metallic"].default_value = spec.get("metallic", 0.0)
    bsdf.inputs["Roughness"].default_value = spec.get("roughness", 0.5)
    bsdf.inputs["Alpha"].default_value = spec.get("alpha", 1.0)
    bsdf.inputs["Transmission Weight"].default_value = spec.get("transmission", 0.0)
    return mat


def unify_board_finish(objs):
    """KiCad colours pads under solder paste grey; on a finished board every exposed pad has the same finish."""
    finishes = []
    for obj in objs:
        for mat in obj.data.materials:
            bsdf = mat and mat.node_tree and mat.node_tree.nodes.get("Principled BSDF")
            if bsdf and bsdf.inputs["Metallic"].default_value > 0.99 and bsdf.inputs["Roughness"].default_value < 0.45:
                finishes.append(bsdf)
    if not finishes:
        return
    def saturation(bsdf):
        r, g, b, _ = bsdf.inputs["Base Color"].default_value
        return max(r, g, b) - min(r, g, b)
    colour = tuple(max(finishes, key=saturation).inputs["Base Color"].default_value)
    for bsdf in finishes:
        bsdf.inputs["Base Color"].default_value = colour


def new_objects(action):
    before = set(bpy.context.scene.objects)
    action()
    return [o for o in bpy.context.scene.objects if o not in before]


def load_part(part, base_dir):
    if "file" in part:
        path = os.path.join(base_dir, part["file"])
        if path.lower().endswith(".glb") or path.lower().endswith(".gltf"):
            objs = new_objects(lambda: bpy.ops.import_scene.gltf(filepath=path))
        else:
            objs = new_objects(lambda: bpy.ops.wm.stl_import(filepath=path, global_scale=MM))
    elif "box" in part:
        (x0, y0, z0), (x1, y1, z1) = part["box"]
        objs = new_objects(lambda: bpy.ops.mesh.primitive_cube_add(size=1))
        obj = objs[0]
        obj.scale = ((x1 - x0) * MM, (y1 - y0) * MM, (z1 - z0) * MM)
        obj.location = ((x0 + x1) / 2 * MM, (y0 + y1) / 2 * MM, (z0 + z1) / 2 * MM)
        bpy.context.view_layer.update()
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        if part.get("bevel"):
            mod = obj.modifiers.new("bevel", "BEVEL")
            mod.width = part["bevel"] * MM
            mod.segments = 6
    elif "cylinder" in part:
        (x, y, z), radius, depth, axis = part["cylinder"]
        rot = {"x": (0, math.pi / 2, 0), "y": (math.pi / 2, 0, 0), "z": (0, 0, 0)}[axis]
        objs = new_objects(lambda: bpy.ops.mesh.primitive_cylinder_add(
            radius=radius * MM, depth=depth * MM, location=(x * MM, y * MM, z * MM), rotation=rot, vertices=48))
    elif "curve" in part:
        data = bpy.data.curves.new(part["name"], "CURVE")
        data.dimensions = "3D"
        data.bevel_depth = part.get("radius", 2) * MM
        data.bevel_resolution = 6
        spline = data.splines.new("NURBS")
        spline.points.add(len(part["curve"]) - 1)
        for point, (x, y, z) in zip(spline.points, part["curve"]):
            point.co = (x * MM, y * MM, z * MM, 1)
        spline.use_endpoint_u = True
        spline.order_u = min(4, len(part["curve"]))
        obj = bpy.data.objects.new(part["name"], data)
        bpy.context.collection.objects.link(obj)
        objs = [obj]
    else:
        raise SystemExit(f"part {part['name']}: needs file, box, cylinder or curve")
    meshes = [o for o in objs if o.type in ("MESH", "CURVE")]
    roots = [o for o in objs if o.parent is None]
    dx, dy, dz = (v * MM for v in part.get("offset", [0, 0, 0]))
    for obj in roots:
        obj.location = (obj.location.x + dx, obj.location.y + dy, obj.location.z + dz)
    if "material" in part:
        mat = make_material(part["name"], part["material"])
        for obj in meshes:
            obj.data.materials.clear()
            obj.data.materials.append(mat)
    if part.get("uniform_finish"):
        unify_board_finish(meshes)
    if part.get("smooth"):
        for obj in meshes:
            if obj.type == "MESH":
                obj.data.polygons.foreach_set("use_smooth", [True] * len(obj.data.polygons))
                obj.data.set_sharp_from_angle(angle=math.radians(30))
    return meshes


def studio(ambient, background):
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
    env.inputs["Strength"].default_value = ambient
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (background, background, background, 1)
    nt.links.new(path.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(env.outputs[0], mix.inputs[1])
    nt.links.new(bg.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])


def add_light(name, location, energy, size, target):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()


def world_points(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    pts = [obj.matrix_world @ v.co for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return pts


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    scene_path, png = argv[0], os.path.abspath(argv[1])
    spec = json.load(open(scene_path, encoding="utf-8"))
    base_dir = os.path.dirname(os.path.abspath(scene_path))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    groups = {}
    for part in spec["parts"]:
        groups.setdefault(part["name"], []).extend(load_part(part, base_dir))
    bpy.context.view_layer.update()

    scene = bpy.context.scene
    w, h = (int(v) for v in spec.get("size", "2400x1500").split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    studio(spec.get("ambient", 0.25), spec.get("background", 0.94))
    points = {name: [p for o in objs for p in world_points(o)] for name, objs in groups.items()}
    every = [p for pts in points.values() for p in pts]
    centre = sum(every, Vector()) / len(every)
    lo = Vector([min(p[i] for p in every) for i in range(3)])
    hi = Vector([max(p[i] for p in every) for i in range(3)])
    centre = (lo + hi) / 2
    span = max(hi - lo)

    cam_spec = spec.get("camera", {})
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = cam_spec.get("lens", 60)
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    el, az = math.radians(cam_spec.get("elevation", 28)), math.radians(cam_spec.get("azimuth", -35))
    direction = Vector((math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)))
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    if cam_spec.get("roll"):
        cam.rotation_euler.rotate_axis("Z", math.radians(cam_spec["roll"]))
    if "ortho" in cam_spec:
        cx, cy, width = cam_spec["ortho"]
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = width * MM
        cam.location = Vector((cx * MM, cy * MM, 0)) + direction * span * 4
        cam_data.clip_end = span * 10
    else:
        margin = cam_spec.get("margin", 1.06)
        flat = [c for p in every[::max(1, len(every) // 20000)] for c in ((p - centre) * margin + centre)]
        cam.location, _ = cam.camera_fit_coords(bpy.context.evaluated_depsgraph_get(), flat)
    bpy.context.view_layer.update()

    light = spec.get("light", 0.6)
    add_light("key", centre + Vector((-0.5, -0.8, 1.2)) * span, light, span * 0.7, centre)
    add_light("fill", centre + Vector((1.0, -0.7, 0.5)) * span, light * 0.35, span, centre)
    add_light("rim", centre + Vector((0.2, 1.1, 0.8)) * span, light * 0.5, span * 0.6, centre)
    scene.render.engine = "CYCLES"
    scene.cycles.samples = spec.get("samples", 128)
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "Standard"
    scene.render.film_transparent = spec.get("transparent", False)
    scene.render.filepath = png
    bpy.ops.render.render(write_still=True)

    boxes = {}
    for name, pts in points.items():
        screen = [world_to_camera_view(scene, cam, p) for p in pts[::max(1, len(pts) // 5000)]]
        xs, ys = [s.x * w for s in screen], [(1 - s.y) * h for s in screen]
        boxes[name] = [round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)]
    with open(os.path.splitext(png)[0] + ".json", "w", encoding="utf-8") as handle:
        json.dump({"size": [w, h], "boxes": boxes}, handle, indent=1)
    print("GROUPS", " ".join(boxes))


main()
