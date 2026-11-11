"""Space Janitor: builds the whole 90-second 3D film as one Blender scene.

Usage:
  Blender -b -P blender/build_scene.py -- [--stills 1.5,5,10] [--half]
Writes blender/space_janitor.blend. Render the frames with render.sh.
"""
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix, Euler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, "assets", "tex")
FPS = 24
DUR = 90.0
random.seed(7)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
STILLS = []
if "--stills" in argv:
    STILLS = [float(x) for x in argv[argv.index("--stills") + 1].split(",")]
EARTH_LON = 121.0
if "--lon" in argv:
    EARTH_LON = float(argv[argv.index("--lon") + 1])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start = 1
scene.frame_end = int(DUR * FPS)
col = scene.collection
prefs = bpy.context.preferences.edit


def F(t):
    return int(round(t * FPS)) + 1


def _fcurves(idb):
    ad = idb.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    try:
        return act.layers[0].strips[0].channelbag(ad.action_slot).fcurves
    except Exception:
        return act.fcurves


def _set_interp(idb, frame, interp, path=None):
    for fc in _fcurves(idb):
        if path is not None and fc.data_path != path:
            continue
        for kp in fc.keyframe_points:
            if abs(kp.co.x - frame) < 0.5:
                kp.interpolation = interp


def key(o, path, t, value=None, interp="LINEAR"):
    if value is not None:
        setattr(o, path, value)
    o.keyframe_insert(path, frame=F(t))
    _set_interp(o, F(t), interp, path)


def keyin(sock, t, value, interp="LINEAR"):
    sock.default_value = value
    sock.keyframe_insert("default_value", frame=F(t))
    _set_interp(sock.id_data, F(t), interp)


def vis(o, ranges, s=1.0):
    """Show object only inside the given time ranges (by scale, constant keys)."""
    sv = (s, s, s) if not isinstance(s, tuple) else s
    key(o, "scale", 0, (0, 0, 0), "CONSTANT")
    for a, b in ranges:
        key(o, "scale", a, sv, "CONSTANT")
        key(o, "scale", b, (0, 0, 0), "CONSTANT")


# ---------------------------------------------------------------- meshes
def mesh_from_bm(name, bm, smooth=True, matrix=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if matrix is not None:
        me.transform(matrix)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return me


def m_sphere(name, r=1.0, u=32, v=16, matrix=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r, calc_uvs=True)
    return mesh_from_bm(name, bm, True, matrix)


def m_ico(name, r=1.0, sub=2, jitter=0.0, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    if jitter:
        for vtx in bm.verts:
            vtx.co *= 1 + random.uniform(-jitter, jitter)
    return mesh_from_bm(name, bm, smooth)


def _bevel(bm, w):
    if w:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=w, offset_type="OFFSET", segments=2,
                        profile=0.5, affect="EDGES")


def m_cone(name, r1, r2, depth, seg=24, matrix=None, smooth=True, caps=True, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=seg,
                          radius1=r1, radius2=r2, depth=depth)
    _bevel(bm, bevel)
    return mesh_from_bm(name, bm, smooth and not bevel, matrix)


def m_box(name, sx, sy, sz, matrix=None, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for vtx in bm.verts:
        vtx.co.x *= sx
        vtx.co.y *= sy
        vtx.co.z *= sz
    _bevel(bm, bevel)
    return mesh_from_bm(name, bm, False, matrix)


def obj(name, me, mat=None, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), shadow=True):
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    o.scale = scale if isinstance(scale, tuple) else (scale, scale, scale)
    if parent:
        o.parent = parent
    if mat and me is not None:
        if len(o.data.materials) == 0:
            o.data.materials.append(mat)
    if not shadow:
        o.visible_shadow = False
    return o


def empty(name, loc=(0, 0, 0), parent=None):
    return obj(name, None, None, parent, loc)


# ---------------------------------------------------------------- materials
def pbr(name, color, metallic=0.0, rough=0.5, emit=None, estr=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = estr
    m["bsdf"] = b.name
    return m


def bsdf(m):
    return m.node_tree.nodes["Principled BSDF"]


def glow(name, color, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], out.inputs[0])
    return m


def ghost(name, color, strength, fac):
    """Additive-looking transparent emission. Returns (material, mix node)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = fac
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(e.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    m.surface_render_method = "BLENDED"
    return m, mix


# ---------------------------------------------------------------- world
R = 25.0
S = Vector((0.75, -0.3, 0.6)).normalized()      # direction to the Sun
C = Vector((0, 0, R + 2.2))                     # the stage, low orbit

world = bpy.data.worlds.new("Space")
scene.world = world
world.use_nodes = True
wn = world.node_tree
wn.nodes.clear()
tc = wn.nodes.new("ShaderNodeTexCoord")
# what the camera sees: stars
vor = wn.nodes.new("ShaderNodeTexVoronoi")
vor.inputs["Scale"].default_value = 260
ramp = wn.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.0
ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
ramp.color_ramp.elements[1].position = 0.045
ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
noi = wn.nodes.new("ShaderNodeTexNoise")
noi.inputs["Scale"].default_value = 40
mul = wn.nodes.new("ShaderNodeMixRGB")
mul.blend_type = "MULTIPLY"
mul.inputs[0].default_value = 1
bg = wn.nodes.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 2.2
wn.links.new(tc.outputs["Generated"], vor.inputs["Vector"])
wn.links.new(tc.outputs["Generated"], noi.inputs["Vector"])
wn.links.new(vor.outputs["Distance"], ramp.inputs[0])
wn.links.new(ramp.outputs[0], mul.inputs[1])
wn.links.new(noi.outputs[0], mul.inputs[2])
wn.links.new(mul.outputs[0], bg.inputs["Color"])
# what shiny surfaces reflect: a cloudy blue Earth below, black sky above
sep = wn.nodes.new("ShaderNodeSeparateXYZ")
emask = wn.nodes.new("ShaderNodeMapRange")
emask.inputs[1].default_value = 0.08
emask.inputs[2].default_value = -0.22
cn = wn.nodes.new("ShaderNodeTexNoise")
cn.inputs["Scale"].default_value = 5.0
cn.inputs["Detail"].default_value = 8
cn.inputs["Distortion"].default_value = 1.2
cramp = wn.nodes.new("ShaderNodeValToRGB")
cramp.color_ramp.elements[0].position = 0.45
cramp.color_ramp.elements[0].color = (0.05, 0.18, 0.55, 1)
cramp.color_ramp.elements[1].position = 0.68
cramp.color_ramp.elements[1].color = (0.9, 0.95, 1.0, 1)
emul = wn.nodes.new("ShaderNodeMixRGB")
emul.blend_type = "MULTIPLY"
emul.inputs[0].default_value = 1
ebg = wn.nodes.new("ShaderNodeBackground")
ebg.inputs["Strength"].default_value = 1.5
lp = wn.nodes.new("ShaderNodeLightPath")
wmix = wn.nodes.new("ShaderNodeMixShader")
wo = wn.nodes.new("ShaderNodeOutputWorld")
wn.links.new(tc.outputs["Generated"], sep.inputs[0])
wn.links.new(sep.outputs["Z"], emask.inputs[0])
wn.links.new(tc.outputs["Generated"], cn.inputs["Vector"])
wn.links.new(cn.outputs[0], cramp.inputs[0])
wn.links.new(cramp.outputs[0], emul.inputs[1])
wn.links.new(emask.outputs[0], emul.inputs[2])
warm = wn.nodes.new("ShaderNodeMixRGB")
warm.blend_type = "MIX"
warm.inputs[1].default_value = (0.16, 0.11, 0.05, 1)
wn.links.new(emask.outputs[0], warm.inputs[0])
wn.links.new(cramp.outputs[0], warm.inputs[2])
sdot = wn.nodes.new("ShaderNodeVectorMath")
sdot.operation = "DOT_PRODUCT"
sdot.inputs[1].default_value = S
smr = wn.nodes.new("ShaderNodeMapRange")
smr.inputs[1].default_value = 0.992
smr.inputs[2].default_value = 1.0
smr.inputs[4].default_value = 9.0
spw = wn.nodes.new("ShaderNodeMath")
spw.operation = "POWER"
spw.inputs[1].default_value = 3.0
sadd = wn.nodes.new("ShaderNodeMixRGB")
sadd.blend_type = "ADD"
sadd.inputs[0].default_value = 1
wn.links.new(tc.outputs["Generated"], sdot.inputs[0])
wn.links.new(sdot.outputs["Value"], smr.inputs[0])
wn.links.new(smr.outputs[0], spw.inputs[0])
wn.links.new(warm.outputs[0], sadd.inputs[1])
wn.links.new(spw.outputs[0], sadd.inputs[2])
wn.links.new(sadd.outputs[0], ebg.inputs["Color"])
wn.links.new(lp.outputs["Is Camera Ray"], wmix.inputs[0])
wn.links.new(ebg.outputs[0], wmix.inputs[1])
wn.links.new(bg.outputs[0], wmix.inputs[2])
wn.links.new(wmix.outputs[0], wo.inputs[0])

sl = bpy.data.lights.new("SunLamp", "SUN")
sl.energy = 5.0
sl.angle = math.radians(1.5)
slo = obj("SunLamp", sl)
slo.rotation_euler = (-S).to_track_quat("-Z", "Y").to_euler()

# ---------------------------------------------------------------- Earth
def sundot(nt, lo, hi):
    """Map the surface normal's dot with the Sun direction from [lo, hi] to [0, 1]."""
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = S
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs[1].default_value = lo
    mr.inputs[2].default_value = hi
    nt.links.new(geo.outputs["Normal"], dot.inputs[0])
    nt.links.new(dot.outputs["Value"], mr.inputs[0])
    return mr.outputs[0]


def mulc(nt, a, b):
    n = nt.nodes.new("ShaderNodeMixRGB")
    n.blend_type = "MULTIPLY"
    n.inputs[0].default_value = 1
    nt.links.new(a, n.inputs[1])
    nt.links.new(b, n.inputs[2])
    return n.outputs[0]


earth_tilt = empty("EarthTilt")
lat = math.radians(24)
theta = math.radians(EARTH_LON)
earth_tilt.rotation_euler = (Matrix.Rotation(-(math.pi / 2 - lat), 3, "Y") @ Matrix.Rotation(-theta, 3, "Z")).to_euler()

# The Earth is lit in its own shader (emission only) so the fake reflection
# environment above never tints it.
em = bpy.data.materials.new("Earth")
em.use_nodes = True
nt = em.node_tree
nt.nodes.clear()
day = nt.nodes.new("ShaderNodeTexImage")
day.image = bpy.data.images.load(os.path.join(TEX, "earth_day.jpg"))
night = nt.nodes.new("ShaderNodeTexImage")
night.image = bpy.data.images.load(os.path.join(TEX, "earth_night.jpg"))
hsv = nt.nodes.new("ShaderNodeHueSaturation")
hsv.inputs["Saturation"].default_value = 1.3
hsv.inputs["Value"].default_value = 1.9
nt.links.new(day.outputs[0], hsv.inputs["Color"])
lit = mulc(nt, hsv.outputs[0], sundot(nt, -0.05, 0.7))
dark = mulc(nt, night.outputs[0], sundot(nt, 0.12, -0.2))
add = nt.nodes.new("ShaderNodeMixRGB")
add.blend_type = "ADD"
add.inputs[0].default_value = 1
nt.links.new(lit, add.inputs[1])
nt.links.new(dark, add.inputs[2])
ee = nt.nodes.new("ShaderNodeEmission")
ee.inputs["Strength"].default_value = 1.0
eo = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(add.outputs[0], ee.inputs["Color"])
nt.links.new(ee.outputs[0], eo.inputs[0])
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=R)
earth = bpy.context.active_object
earth.name = "Earth"
for p_ in earth.data.polygons:
    p_.use_smooth = True
earth.data.materials.append(em)
earth.parent = earth_tilt
earth.visible_shadow = False

cm, cmix = ghost("Clouds", (1, 1, 1), 1.0, 0.0)
nt = cm.node_tree
tcn = nt.nodes.new("ShaderNodeTexCoord")
n1 = nt.nodes.new("ShaderNodeTexNoise")
n1.inputs["Scale"].default_value = 0.22
n1.inputs["Detail"].default_value = 14
n1.inputs["Roughness"].default_value = 0.62
n1.inputs["Distortion"].default_value = 1.6
cr = nt.nodes.new("ShaderNodeValToRGB")
cr.color_ramp.elements[0].position = 0.5
cr.color_ramp.elements[1].position = 0.74
cr.color_ramp.elements[1].color = (0.92, 0.92, 0.92, 1)
nt.links.new(tcn.outputs["Object"], n1.inputs["Vector"])
nt.links.new(n1.outputs[0], cr.inputs[0])
nt.links.new(cr.outputs[0], cmix.inputs[0])
cem = [n for n in nt.nodes if n.type == "EMISSION"][0]
clit = nt.nodes.new("ShaderNodeMath")
clit.operation = "MULTIPLY"
clit.inputs[1].default_value = 1.7
nt.links.new(sundot(nt, -0.1, 0.7), clit.inputs[0])
nt.links.new(clit.outputs[0], cem.inputs["Strength"])
clouds = obj("Clouds", m_sphere("Clouds", R * 1.006, 128, 64), cm, earth_tilt, shadow=False)
key(clouds, "rotation_euler", 0, (0, 0, 0))
key(clouds, "rotation_euler", DUR, (0, 0.02, 0.10))

am, amix = ghost("Atmo", (0.25, 0.55, 1.0), 2.2, 0.0)
nt = am.node_tree
lw = nt.nodes.new("ShaderNodeLayerWeight")
lw.inputs["Blend"].default_value = 0.22
pw = nt.nodes.new("ShaderNodeMath")
pw.operation = "POWER"
pw.inputs[1].default_value = 2.2
mm = nt.nodes.new("ShaderNodeMath")
mm.operation = "MULTIPLY"
nt.links.new(lw.outputs["Facing"], pw.inputs[0])
nt.links.new(pw.outputs[0], mm.inputs[0])
nt.links.new(sundot(nt, -0.25, 0.35), mm.inputs[1])
nt.links.new(mm.outputs[0], amix.inputs[0])
am.use_backface_culling = True
atmo = obj("Atmo", m_sphere("Atmo", R * 1.03, 96, 48), am, shadow=False)

# ---------------------------------------------------------------- Sun
SUNP = S * 900
sm = bpy.data.materials.new("SunSurf")
sm.use_nodes = True
nt = sm.node_tree
nt.nodes.clear()
tcn = nt.nodes.new("ShaderNodeTexCoord")
sn = nt.nodes.new("ShaderNodeTexNoise")
sn.noise_dimensions = "4D"
sn.inputs["Scale"].default_value = 0.11
sn.inputs["Detail"].default_value = 10
sn.inputs["Roughness"].default_value = 0.7
sn.inputs["Distortion"].default_value = 1.2
keyin(sn.inputs["W"], 0, 0.0)
keyin(sn.inputs["W"], DUR, 6.0)
sr = nt.nodes.new("ShaderNodeValToRGB")
sr.color_ramp.elements[0].position = 0.42
sr.color_ramp.elements[0].color = (0.9, 0.08, 0.0, 1)
sr.color_ramp.elements[1].position = 0.62
sr.color_ramp.elements[1].color = (1.0, 0.7, 0.12, 1)
se = nt.nodes.new("ShaderNodeEmission")
se.inputs["Strength"].default_value = 2.6
so = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(tcn.outputs["Object"], sn.inputs["Vector"])
nt.links.new(sn.outputs[0], sr.inputs[0])
nt.links.new(sr.outputs[0], se.inputs["Color"])
nt.links.new(se.outputs[0], so.inputs[0])
sun = obj("Sun", m_sphere("Sun", 60, 96, 48), sm, loc=SUNP, shadow=False)
key(sun, "rotation_euler", 0, (0, 0, 0))
key(sun, "rotation_euler", DUR, (0, 0, 0.5))
com, comix = ghost("Corona", (1.0, 0.4, 0.05), 3, 0.0)
nt = com.node_tree
lw = nt.nodes.new("ShaderNodeLayerWeight")
lw.inputs["Blend"].default_value = 0.5
inv = nt.nodes.new("ShaderNodeMath")
inv.operation = "SUBTRACT"
inv.inputs[0].default_value = 1.0
pw = nt.nodes.new("ShaderNodeMath")
pw.operation = "POWER"
pw.inputs[1].default_value = 3.0
nt.links.new(lw.outputs["Facing"], inv.inputs[1])
nt.links.new(inv.outputs[0], pw.inputs[0])
nt.links.new(pw.outputs[0], comix.inputs[0])
obj("Corona", m_sphere("Corona", 84, 64, 32), com, loc=SUNP, shadow=False)

# ---------------------------------------------------------------- shared materials
HOT = (1.0, 0.25, 0.02)


def foil(name, color=(1.0, 0.62, 0.18), rough=0.28):
    """Crinkled multi-layer insulation."""
    m = pbr(name, color, 1.0, rough, HOT, 0.0)
    nt_ = m.node_tree
    t = nt_.nodes.new("ShaderNodeTexCoord")
    n = nt_.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 7
    n.inputs["Detail"].default_value = 3
    n.inputs["Roughness"].default_value = 0.7
    bp = nt_.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.4
    bp.inputs["Distance"].default_value = 0.03
    nt_.links.new(t.outputs["Object"], n.inputs["Vector"])
    nt_.links.new(n.outputs[0], bp.inputs["Height"])
    nt_.links.new(bp.outputs[0], bsdf(m).inputs["Normal"])
    return m


def cells(name, c1=(0.004, 0.012, 0.09), c2=(0.008, 0.025, 0.16), scale=9.0):
    """Solar cells: a dark glassy grid with silver bus lines."""
    m = pbr(name, c1, 0.5, 0.12, HOT, 0.0)
    nt_ = m.node_tree
    t = nt_.nodes.new("ShaderNodeTexCoord")
    br = nt_.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.inputs["Color1"].default_value = (*c1, 1)
    br.inputs["Color2"].default_value = (*c2, 1)
    br.inputs["Mortar"].default_value = (0.55, 0.57, 0.62, 1)
    br.inputs["Scale"].default_value = scale
    br.inputs["Mortar Size"].default_value = 0.035
    br.inputs["Brick Width"].default_value = 1.0
    br.inputs["Row Height"].default_value = 0.5
    nt_.links.new(t.outputs["Object"], br.inputs["Vector"])
    nt_.links.new(br.outputs["Color"], bsdf(m).inputs["Base Color"])
    return m


M_MIRROR = pbr("Mirror", (1.0, 0.74, 0.3), 1.0, 0.05, (1.0, 0.6, 0.18), 0.18)
M_FRAME = pbr("Frame", (0.025, 0.025, 0.03), 0.3, 0.45)
M_PANEL = cells("Panel")
M_STEEL = pbr("Steel", (0.75, 0.77, 0.8), 1.0, 0.25)
M_GREY = pbr("Grey", (0.3, 0.3, 0.32), 0.9, 0.45)
M_NOZZLE = pbr("Nozzle", (0.08, 0.07, 0.07), 1.0, 0.35)
M_FOIL = foil("Foil")
M_SILVER = foil("SilverFoil", (0.8, 0.82, 0.86), 0.22)
M_WHITE = pbr("White", (0.88, 0.88, 0.9), 0.0, 0.45)
M_SPARK = glow("Spark", (1.0, 0.55, 0.15), 14)
M_FLASH = glow("Flash", (1.0, 0.9, 0.7), 40)
M_TAG = glow("Tag", (0.4, 1.0, 0.6), 3.0)
M_TAGR = glow("TagRed", (1.0, 0.25, 0.2), 4.0)
M_TAGW = glow("TagWhite", (1.0, 1.0, 1.0), 3.0)

RX = Matrix.Rotation(-math.pi / 2, 4, "X")       # +Z -> +Y
ME_STRUT = m_cone("Strut", 1.0, 1.0, 1.0, 10)


def strut(parent, p0, p1, r, mat):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    o = obj("strut", ME_STRUT, mat, parent, loc=(p0 + p1) / 2, scale=(r, r, d.length))
    o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return o


# ---------------------------------------------------------------- camera
camd = bpy.data.cameras.new("Cam")
camd.clip_start = 0.05
camd.clip_end = 5000
cam = obj("Cam", camd)
scene.camera = cam
look = empty("Look")
tt = cam.constraints.new("TRACK_TO")
tt.target = look
tt.track_axis = "TRACK_NEGATIVE_Z"
tt.up_axis = "UP_Y"


def shot(t0, t1, p0, p1, l0, l1, lens=35):
    e = t1 - 1.0 / FPS
    key(cam, "location", t0, Vector(p0))
    key(cam, "location", e, Vector(p1))
    key(look, "location", t0, Vector(l0))
    key(look, "location", e, Vector(l1))
    key(camd, "lens", t0, lens, "CONSTANT")


def tag(text, loc, ranges, mat=M_TAG, size=0.34):
    cu = bpy.data.curves.new("T_" + text[:12], "FONT")
    cu.body = text
    cu.align_x = "CENTER"
    cu.size = size
    o = obj("Tag_" + text[:12], cu, loc=loc, shadow=False)
    o.data.materials.append(mat)
    cr_ = o.constraints.new("COPY_ROTATION")
    cr_.target = cam
    vis(o, ranges)
    return o


# ---------------------------------------------------------------- junk pieces + burst helper
def _m_shard(name):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 2.0 * random.uniform(0.6, 1.0)
        v.co.y *= 1.4 * random.uniform(0.5, 1.0)
        v.co.z *= 0.05
    return mesh_from_bm(name, bm, False)


def _m_scrap(name):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=7, y_segments=7, size=0.9)
    for v in bm.verts:
        v.co.z = 0.28 * math.sin(v.co.x * 5 + random.uniform(-1, 1)) * math.cos(v.co.y * 4) + random.uniform(-0.08, 0.08)
    return mesh_from_bm(name, bm, True)


def _m_bolt(name):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.7, radius2=0.7, depth=0.4)
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.32, radius2=0.32, depth=1.5,
                          matrix=Matrix.Translation((0, 0, -0.9)))
    return mesh_from_bm(name, bm, False)


CHUNKS = [m_ico("Chunk%d" % i, 1.0, 2, 0.32, smooth=True) for i in range(3)]
JUNK = [
    (_m_shard("ShardA"), M_PANEL), (_m_shard("ShardB"), M_PANEL), (_m_shard("ShardC"), M_STEEL),
    (_m_scrap("ScrapA"), M_FOIL), (_m_scrap("ScrapB"), M_FOIL), (_m_scrap("ScrapC"), M_SILVER),
    (_m_bolt("Bolt"), M_STEEL),
    (m_cone("Rod", 0.07, 0.07, 2.4, 10), M_GREY),
    (m_sphere("Tank", 0.75, 24, 12), M_WHITE),
    (CHUNKS[0], M_GREY), (CHUNKS[1], M_NOZZLE),
]


def burst(center, t, n, sparks, dmin, dmax, life, smin=0.04, smax=0.16, end=None):
    """n pieces fly out from center at time t. `sparks` is the share that glows."""
    center = Vector(center)
    for i in range(n):
        d = Vector((random.gauss(0, 1), random.gauss(0, 1), random.gauss(0, 1))).normalized()
        dist = random.uniform(dmin, dmax)
        s = random.uniform(smin, smax)
        if random.random() < sparks:
            me, mat = random.choice(CHUNKS), random.choice((M_SPARK, M_SPARK, M_FLASH))
            s *= 0.16
        else:
            me, mat = random.choice(JUNK)
        o = obj("B", me, mat, shadow=False)
        key(o, "scale", 0, (0, 0, 0), "CONSTANT")
        key(o, "scale", t, (s, s, s), "LINEAR")
        key(o, "location", t, center)
        key(o, "location", t + life, center + d * dist)
        if end is None:
            key(o, "scale", t + life, (0, 0, 0), "LINEAR")
        else:
            key(o, "scale", t + life, (s, s, s), "CONSTANT")
            key(o, "scale", end, (0, 0, 0), "CONSTANT")
        key(o, "rotation_euler", t, (0, 0, 0))
        key(o, "rotation_euler", t + life, tuple(random.uniform(-9, 9) for _ in range(3)))


def flash(center, t, size):
    o = obj("Flash", m_ico("FlashM", 1.0, 3), M_FLASH, loc=center, shadow=False)
    key(o, "scale", 0, (0, 0, 0), "CONSTANT")
    key(o, "scale", t - 0.04, (0.01,) * 3, "LINEAR")
    key(o, "scale", t + 0.08, (size,) * 3, "LINEAR")
    key(o, "scale", t + 0.45, (0, 0, 0), "LINEAR")
    ld = bpy.data.lights.new("FlashL", "POINT")
    ld.color = (1.0, 0.8, 0.5)
    obj("FlashL", ld, loc=center)
    key(ld, "energy", 0, 0.0, "CONSTANT")
    key(ld, "energy", t - 0.04, 0.0)
    key(ld, "energy", t + 0.08, 9000.0)
    key(ld, "energy", t + 0.6, 0.0)


# ---------------------------------------------------------------- big assets
ME_BUS = m_box("Bus", 0.8, 0.8, 1.1, bevel=0.035)
ME_SPAN = m_box("SolarPanel", 0.56, 0.5, 0.02, bevel=0.006)
ME_DISH = m_cone("Dish", 0.05, 0.52, 0.2, 40)
ME_FEED = m_cone("Feed", 0.05, 0.035, 0.1, 16)
ME_INSTR = m_cone("Instr", 0.13, 0.13, 0.36, 24, bevel=0.012)
ME_BELL = m_cone("Bell", 0.07, 0.17, 0.2, 28)
PX = (math.pi / 2, 0, 0)


def junk_sat(name, mat_body=M_FOIL, mat_panel=M_PANEL, broken=True, parent=None):
    """A communications satellite: foil bus, two three-panel wings, dish, booms."""
    root = empty(name, parent=parent)
    obj(name + "_bus", ME_BUS, mat_body, root)
    obj(name + "_deck", m_box("Deck", 0.84, 0.84, 0.04, bevel=0.01), M_FRAME, root, loc=(0, 0, 0.56))
    obj(name + "_dish", ME_DISH, M_WHITE, root, loc=(0, 0, 0.72))
    obj(name + "_feed", ME_FEED, M_STEEL, root, loc=(0, 0, 1.08))
    for k in range(3):
        a = k * 2.094
        strut(root, (0.45 * math.cos(a), 0.45 * math.sin(a), 0.8), (0, 0, 1.06), 0.008, M_STEEL)
    obj(name + "_instr", ME_INSTR, M_SILVER, root, loc=(0.18, 0.5, 0.1), rot=PX)
    obj(name + "_bell", ME_BELL, M_NOZZLE, root, loc=(0, 0, -0.64))
    strut(root, (-0.3, -0.3, -0.55), (-0.55, -0.6, -1.35), 0.012, M_GREY)
    strut(root, (0.3, -0.35, 0.5), (0.5, -1.2, 0.75), 0.01, M_GREY)
    for sx in (-1, 1):
        strut(root, (sx * 0.4, 0, 0), (sx * 0.62, 0, 0), 0.02, M_STEEL)
        for k in range(3):
            x = sx * (0.92 + k * 0.6)
            if broken and sx < 0:
                if k == 2:
                    continue
                if k == 1:
                    obj(name + "_pb", ME_SPAN, mat_panel, root, loc=(x + 0.1, 0.22, 0.12), rot=(1.2, 0.5, 0.7))
                    continue
            rot = PX if not (broken and sx > 0 and k == 2) else (1.95, 0.25, 0.0)
            obj(name + "_p", ME_SPAN, mat_panel, root, loc=(x, 0, 0 if rot == PX else 0.1), rot=rot)
            strut(root, (x - 0.28, 0.012, 0.27), (x + 0.28, 0.012, 0.27), 0.006, M_STEEL)
            strut(root, (x - 0.28, 0.012, -0.27), (x + 0.28, 0.012, -0.27), 0.006, M_STEEL)
    return root


def rocket(name, mat):
    """A spent upper stage."""
    root = empty(name)
    obj(name + "_tank", m_cone("StageTank", 0.36, 0.36, 2.2, 40), mat, root)
    obj(name + "_dome", m_sphere("StageDome", 0.36, 32, 16), mat, root, loc=(0, 0, 1.1), scale=(1, 1, 0.45))
    for z in (-0.9, -0.2, 0.5, 1.0):
        obj(name + "_ring", m_cone("StageRing", 0.372, 0.372, 0.05, 40), M_STEEL, root, loc=(0, 0, z))
    obj(name + "_skirt", m_cone("StageSkirt", 0.3, 0.365, 0.25, 40), M_FRAME, root, loc=(0, 0, -1.22))
    obj(name + "_bell", m_cone("StageBell", 0.3, 0.1, 0.55, 40), M_NOZZLE, root, loc=(0, 0, -1.6))
    for k in range(4):
        a = k * math.pi / 2 + 0.6
        obj(name + "_btl", m_sphere("Bottle", 0.09, 16, 10), M_SILVER, root,
            loc=(0.24 * math.cos(a), 0.24 * math.sin(a), -1.28))
    return root


# debris field (shots B, C)
field = empty("Field", loc=C)
vis(field, [(8, 24)])
for i in range(170):
    p = Vector((random.uniform(-11, 16), random.uniform(-6, 7), random.uniform(-1.4, 3.2)))
    s = random.uniform(0.04, 0.2) * (2.0 if random.random() < 0.06 else 1)
    me, mat = random.choice(JUNK)
    o = obj("F", me, mat, field, loc=p, scale=s)
    v = Vector((random.uniform(-0.25, 0.1), random.uniform(-0.05, 0.05), random.uniform(-0.03, 0.03)))
    key(o, "location", 8, p)
    key(o, "location", 24, p + v * 16)
    key(o, "rotation_euler", 8, tuple(random.uniform(-3, 3) for _ in range(3)))
    key(o, "rotation_euler", 24, tuple(random.uniform(-10, 10) for _ in range(3)))
dead0 = junk_sat("DeadB", parent=field)
key(dead0, "location", 8, Vector((-2.5, 1.2, 0.9)))
key(dead0, "location", 17, Vector((-6.2, -0.3, 1.25)))
key(dead0, "rotation_euler", 8, (0.3, 0.2, 0))
key(dead0, "rotation_euler", 17, (2.4, 1.4, 1.1))
key(dead0, "scale", 17, (0, 0, 0), "CONSTANT")
stage_j = rocket("OldStage", M_WHITE)
stage_j.parent = field
key(stage_j, "location", 8, Vector((7, 3.5, 1.6)))
key(stage_j, "location", 17, Vector((5.2, 3.2, 1.5)))
key(stage_j, "rotation_euler", 8, (1.2, 0.3, 0))
key(stage_j, "rotation_euler", 17, (2.6, 1.0, 0.8))
key(stage_j, "scale", 17, (0, 0, 0), "CONSTANT")

# collision (shot C)
HC = C + Vector((4, 0, 1))
TC_ = 19.6
x1 = rocket("X1", M_WHITE)
vis(x1, [(17, TC_)])
key(x1, "location", 17, HC + Vector((-7.5, -1.6, 0.5)))
key(x1, "location", TC_, HC + Vector((-0.3, 0, 0)))
key(x1, "rotation_euler", 17, (0.2, 1.3, 0))
key(x1, "rotation_euler", TC_, (1.5, 2.2, 0.6))
x2 = junk_sat("X2")
vis(x2, [(17, TC_)])
key(x2, "location", 17, HC + Vector((7.5, 1.8, -0.4)))
key(x2, "location", TC_, HC + Vector((0.3, 0, 0)))
key(x2, "rotation_euler", 17, (0, 0, 0))
key(x2, "rotation_euler", TC_, (1.0, 0.5, 2.0))
flash(HC, TC_, 2.6)
burst(HC, TC_, 170, 0.25, 2.5, 14, 4.4, 0.03, 0.2, end=24)

# ---------------------------------------------------------------- the janitors
FC = C + Vector((-5, 0, 0.6))
aim = empty("Aim")
SEG_R = 0.2
ME_SEG = m_cone("MirrorSeg", SEG_R, SEG_R, 0.022, 6, RX, smooth=False, bevel=0.004)
ME_BACK = m_cone("Backplane", 0.57, 0.57, 0.02, 48, RX, smooth=False)
ME_HUB = m_cone("Hub", 0.09, 0.06, 0.1, 24, RX)
ME_SBUS = m_box("SatBus", 0.26, 0.24, 0.26, bevel=0.012)
ME_WING = m_box("SatWing", 0.62, 0.3, 0.012, bevel=0.004)
ME_THR = m_cone("Thruster", 0.03, 0.012, 0.05, 16, RX)
ME_ANT = m_cone("Antenna", 0.1, 0.015, 0.05, 24, RX)
ME_TRK = m_cone("Tracker", 0.03, 0.03, 0.09, 16, bevel=0.004)
ME_BEAM = m_cone("BeamM", 0.13, 0.015, 1.0, 20, RX @ Matrix.Translation((0, 0, 0.5)), caps=False)
M_BEAM, beam_mix = ghost("Beam", (1.0, 0.82, 0.45), 9, 0.0)
SEG_D = SEG_R * math.sqrt(3) + 0.014
SEGS = [(0.0, 0.0)] + [(SEG_D * math.cos(math.radians(60 * k)), SEG_D * math.sin(math.radians(60 * k)))
                       for k in range(6)]


def janitor(name, loc):
    """One mirror satellite: 7 gold mirror segments, truss, foil bus, two solar wings.
    The mirror faces local +Y."""
    root = empty(name, loc=loc)
    for x, z in SEGS:
        obj("seg", ME_SEG, M_MIRROR, root, loc=(x, 0, z))
    obj("back", ME_BACK, M_FRAME, root, loc=(0, -0.03, 0))
    obj("hub", ME_HUB, M_FRAME, root, loc=(0, -0.09, 0))
    by = -0.5
    for k in range(3):
        a = math.radians(90 + 120 * k)
        strut(root, (0.42 * math.cos(a), -0.04, 0.42 * math.sin(a)), (0.1 * math.cos(a), by + 0.1, 0.1 * math.sin(a)), 0.011, M_FRAME)
    obj("bus", ME_SBUS, M_FOIL, root, loc=(0, by, 0))
    for sx in (-1, 1):
        strut(root, (sx * 0.13, by, 0), (sx * 0.27, by, 0), 0.012, M_STEEL)
        obj("wing", ME_WING, M_PANEL, root, loc=(sx * 0.58, by, 0), rot=PX)
        for sz in (-1, 1):
            obj("thr", ME_THR, M_NOZZLE, root, loc=(sx * 0.1, by - 0.14, sz * 0.1))
    obj("ant", ME_ANT, M_WHITE, root, loc=(0, by - 0.15, 0))
    obj("trk", ME_TRK, M_FRAME, root, loc=(0.06, by, 0.17))
    strut(root, (-0.08, by, 0.13), (-0.14, by - 0.05, 0.42), 0.005, M_STEEL)
    c = root.constraints.new("TRACK_TO")
    c.target = aim
    c.track_axis = "TRACK_Y"
    c.up_axis = "UP_Z"
    return root


sats = []
pos = [(0, 0)]
for ring, n in ((1, 6), (2, 12)):
    for k in range(n):
        a = 2 * math.pi * k / n + (0.26 if ring == 2 else 0)
        pos.append((ring * 1.42 * math.cos(a), ring * 1.42 * math.sin(a) * 0.92))
for i, (py, pz) in enumerate(pos):
    r2 = py * py + pz * pz
    home = FC + Vector((0.06 * r2, py, pz))
    root = janitor("Sat%d" % i, home)
    root["home"] = home
    if i == 0:
        vis(root, [(24, DUR + 1)])
    else:
        t0 = 30.3 + 0.11 * i
        key(root, "scale", 0, (0, 0, 0), "CONSTANT")
        key(root, "scale", t0, (0.15,) * 3, "BEZIER")
        key(root, "scale", t0 + 1.7, (1,) * 3, "BEZIER")
        key(root, "location", t0, FC + Vector((-4.5, 0, -0.3)), "BEZIER")
        key(root, "location", t0 + 1.7, home, "BEZIER")
    bm_ = obj("beam", ME_BEAM, M_BEAM, shadow=False)
    cl = bm_.constraints.new("COPY_LOCATION")
    cl.target = root
    st = bm_.constraints.new("STRETCH_TO")
    st.target = aim
    st.rest_length = 1.0
    st.volume = "NO_VOLUME"
    sats.append(root)

# ---------------------------------------------------------------- targets
DP = C + Vector((6.2, -0.2, -0.2))
M_HOT = foil("HotFoil")
M_HOTP = cells("HotPanel")
dead = junk_sat("Dead", M_HOT, M_HOTP)
dead.location = DP
TV = 54.5
vis(dead, [(30, TV + 0.3)])
key(dead, "scale", TV, (1, 1, 1), "LINEAR")
key(dead, "rotation_euler", 30, (0.4, 0.2, 0))
key(dead, "rotation_euler", 60, (1.6, 2.4, 1.2))

RP = C + Vector((6.2, 0, 0.5))
M_RIV = pbr("RivalSkin", (0.9, 0.9, 0.93), 0.2, 0.3, HOT, 0.0)
M_RIVP = cells("RivalPanel", (0.09, 0.004, 0.07), (0.16, 0.008, 0.12))
rival = junk_sat("Rival", M_RIV, M_RIVP, broken=False)
rival.location = RP
TR = 81.4
vis(rival, [(72, TR + 0.25)])
key(rival, "scale", TR, (1, 1, 1), "LINEAR")
key(rival, "rotation_euler", 72, (0.15, 0, 0.3))
key(rival, "rotation_euler", 84, (0.15, 0, 1.0))

# where the swarm points
AIM_D = FC + Vector((4.0, 1.9, 2.3))
key(aim, "location", 0, AIM_D)
key(aim, "location", 41.6, AIM_D)
key(aim, "location", 44.2, DP, "BEZIER")
key(aim, "location", 71.9, DP)
key(aim, "location", 72.0, AIM_D, "CONSTANT")
key(aim, "location", 72.6, AIM_D)
key(aim, "location", 74.0, RP)
key(aim, "location", 82.2, RP)
key(aim, "location", 83.1, FC + Vector((3, -2, 14)))
key(aim, "location", 84.0, FC + Vector((12.5, 4.3, 3.4)), "CONSTANT")

# beams + hot spot
BEAMS = [(47.4, TV + 0.25), (79.4, TR + 0.2)]
hot = obj("Hot", m_ico("HotM", 1.0, 3), glow("HotMat", (1.0, 0.85, 0.5), 30), shadow=False)
hc = hot.constraints.new("COPY_LOCATION")
hc.target = aim
hl = bpy.data.lights.new("HotL", "POINT")
hl.color = (1.0, 0.7, 0.35)
hlo = obj("HotL", hl)
hc2 = hlo.constraints.new("COPY_LOCATION")
hc2.target = aim
keyin(beam_mix.inputs[0], 0, 0.0)
key(hot, "scale", 0, (0, 0, 0))
key(hl, "energy", 0, 0.0)
for a, b_ in BEAMS:
    keyin(beam_mix.inputs[0], a, 0.0)
    keyin(beam_mix.inputs[0], a + 0.35, 0.16)
    keyin(beam_mix.inputs[0], b_ - 0.15, 0.3)
    keyin(beam_mix.inputs[0], b_, 0.0)
    key(hot, "scale", a, (0, 0, 0))
    key(hot, "scale", a + 0.35, (0.1,) * 3)
    key(hot, "scale", b_ - 0.15, (0.3,) * 3)
    key(hot, "scale", b_, (0, 0, 0))
    key(hl, "energy", a, 0.0)
    key(hl, "energy", a + 0.35, 1500.0)
    key(hl, "energy", b_ - 0.15, 9000.0)
    key(hl, "energy", b_, 0.0)


def heat(mats, a, b_, peak):
    for m in mats:
        s = bsdf(m).inputs["Emission Strength"]
        c_ = bsdf(m).inputs["Emission Color"]
        keyin(s, a, 0.0)
        keyin(s, (a + b_) / 2, peak * 0.12)
        keyin(s, b_, peak)
        keyin(c_, a, (1.0, 0.12, 0.01, 1))
        keyin(c_, (a + b_) / 2, (1.0, 0.3, 0.04, 1))
        keyin(c_, b_, (1.0, 0.75, 0.45, 1))


heat([M_HOT, M_HOTP], 47.6, TV, 30)
heat([M_RIV, M_RIVP], 79.6, TR, 30)

# vaporize + fireball
flash(DP, TV, 1.1)
burst(DP, TV, 120, 0.8, 1.0, 5.0, 1.5, 0.03, 0.12)
FB0, FB1 = DP, C + Vector((15.5, 1.5, -2.05))
fb = empty("Fireball")
obj("fbh", m_ico("FBH", 0.22, 3), M_FLASH, fb, shadow=False)
trm, _ = ghost("Trail", (1.0, 0.5, 0.12), 12, 0.55)
d = (FB1 - FB0).normalized()
obj("fbt", m_cone("FBT", 0.01, 0.2, 2.6, 16, Matrix.Translation((0, 0, -1.3))), trm, fb, shadow=False)
fb.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
vis(fb, [(TV + 0.5, 59.6)])
key(fb, "location", TV + 0.5, FB0)
key(fb, "location", 59.6, FB1)
key(fb, "scale", TV + 0.5, (0.4,) * 3, "LINEAR")
key(fb, "scale", 57.0, (1.3,) * 3, "LINEAR")
key(fb, "scale", 59.5, (0.1,) * 3, "LINEAR")


def fbpos(t):
    return FB0.lerp(FB1, (t - TV - 0.5) / (59.6 - TV - 0.5))


flash(RP, TR, 1.2)
burst(RP, TR, 130, 0.7, 1.0, 6.0, 1.8, 0.03, 0.13)

# ---------------------------------------------------------------- constellation
shell = empty("Shell")
vis(shell, [(3.5, 8), (60, 72)])
bm = bmesh.new()
for i in range(520):
    d = Vector((random.gauss(0, 1), random.gauss(0, 1), random.gauss(0, 1))).normalized()
    rr = R + random.choice((2.4, 3.2, 4.2))
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.11, matrix=Matrix.Translation(d * rr))
dots = obj("Dots", mesh_from_bm("DotsM", bm), glow("Dot", (0.6, 0.85, 1.0), 6), shell, shadow=False)
key(dots, "rotation_euler", 0, (0, 0, 0))
key(dots, "rotation_euler", DUR, (0.5, 0.9, 1.6))
M_RED = glow("RedDot", (1.0, 0.12, 0.05), 12)
ME_DOT = m_ico("RD", 0.2, 1)
camdir_h = Vector((0.05, -0.9, 0.42)).normalized()
reds = []
while len(reds) < 46:
    d = Vector((random.gauss(0, 1), random.gauss(0, 1), random.gauss(0, 1))).normalized()
    if d.dot(camdir_h) < 0.25:
        continue
    reds.append(d)
for i, d in enumerate(reds):
    o = obj("Red", ME_DOT, M_RED, shell, loc=d * (R + random.uniform(2.2, 4.4)), shadow=False)
    tk = 61.5 + 9.3 * i / len(reds)
    key(o, "scale", 60, (1, 1, 1))
    key(o, "scale", tk, (1, 1, 1))
    key(o, "scale", tk + 0.12, (2.6,) * 3)
    key(o, "scale", tk + 0.3, (0, 0, 0))

# rockets leaving Earth (shot A2)
camdir_a = Vector((0.66, -0.45, 0.45)).normalized()
ME_RKT = m_cone("Streak", 0.02, 0.2, 3.2, 12, Matrix.Translation((0, 0, -1.6)))
M_STREAK = glow("Streak", (1.0, 0.8, 0.5), 10)
n = 0
while n < 16:
    d = Vector((random.gauss(0, 1), random.gauss(0, 1), random.gauss(0, 1))).normalized()
    if d.dot(camdir_a) < 0.2 or d.dot(S) < 0.1:
        continue
    o = obj("Streak", ME_RKT, M_STREAK, shadow=False)
    o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    t0 = 3.3 + n * 0.22
    key(o, "scale", 0, (0, 0, 0), "CONSTANT")
    key(o, "scale", t0, (1, 1, 0.2), "LINEAR")
    key(o, "scale", t0 + 0.8, (1, 1, 1), "LINEAR")
    key(o, "scale", 8.0, (0, 0, 0), "CONSTANT")
    key(o, "location", t0, d * (R + 0.1))
    key(o, "location", t0 + 4.5, d * (R + 13))
    n += 1

# ---------------------------------------------------------------- tags
tag("TARGET LOCKED", DP + Vector((0, 0, 1.95)), [(44.4, 47.2)], M_TAG, 0.2)
tag("DEAD SINCE 2009", DP + Vector((0, 0, 1.55)), [(44.4, 54.3)], M_TAG, 0.26)
tag("CLEANED.", DP + Vector((0, 0, 0.6)), [(55.6, 58.0)], M_TAG, 0.3)
tag("RIVAL CORP", RP + Vector((0, 0, 1.7)), [(72, 81.3)], M_TAGW, 0.42)
tag("oops.", RP + Vector((0, 0, 0.2)), [(82.0, 84.0)], M_TAGR, 0.5)

# ---------------------------------------------------------------- shots
V = Vector
H3 = Vector(sats[3]["home"])
# A1 the Sun
shot(0, 3.5, SUNP - S * 330 + V((40, 60, 10)), SUNP - S * 270 + V((20, 40, 5)), SUNP + V((0, 30, 0)), SUNP, 35)
# A2 Earth, rockets leaving
shot(3.5, 8, camdir_a * 92, camdir_a * 80 + V((0, 6, 0)), V((0, 0, 3)), V((0, 0, 3)), 38)
# B debris field
shot(8, 17, C + V((-13, -3, 1.3)), C + V((-6, -1.6, 1.0)), C + V((8, 1, -0.6)), C + V((8, 1.5, -0.4)), 26)
# C collision
shot(17, 24, HC + V((-1, -10, 1.6)), HC + V((0.5, -7.5, 1.2)), HC + V((0, 0, -0.5)), HC + V((0, 0, -0.3)), 30)
# D the first janitor, alone
shot(24, 30, FC + V((3.0, 2.3, 1.9)), FC + V((2.2, 1.2, 1.5)), FC + V((0, 0, -0.25)), FC + V((0, 0, -0.2)), 40)
# E the swarm deploys
shot(30, 37, FC + V((5.5, -6.5, 3.2)), FC + V((6.5, -5.0, 2.6)), FC + V((-0.5, 0, 0)), FC + V((0, 0, 0)), 30)
# F1 close on one mirror satellite
shot(37, 41.2, H3 + V((1.7, -1.5, 0.75)), H3 + V((1.5, 0.9, 0.5)), H3 + V((0, 0, -0.1)), H3 + V((0, 0, -0.05)), 45)
# F2 wide: the swarm turns to the dead satellite
shot(41.2, 47, C + V((0.5, -13.4, 2.5)), C + V((0.5, -12.6, 2.3)), C + V((0.6, 0, 0.2)), C + V((0.6, 0, 0.2)), 30)
# G1 wide: beams on
shot(47, 51, C + V((0.5, -12.6, 2.3)), C + V((1.5, -10.5, 1.9)), C + V((0.6, 0, 0.2)), C + V((1.2, 0, 0.1)), 30)
# G2 close on the dead satellite
shot(51, 55.5, DP + V((3.9, -5.6, 1.3)), DP + V((3.2, -4.5, 1.0)), DP + V((0, 0, 0.3)), DP + V((0, 0, 0.3)), 35)
# G3 burn-up
shot(55.5, 60, C + V((5, -10, 1.6)), C + V((8, -9, 1.2)), fbpos(55.5), fbpos(59.6), 32)
# H the market
shot(60, 72, camdir_h * 98, camdir_h * 86 + V((8, 0, 0)), V((0, 0, 2)), V((0, 0, 2)), 38)
# I1 the rival, swarm behind it
shot(72, 76, RP + V((4.6, -3.6, 1.7)), RP + V((4.0, -3.1, 1.5)), C + V((1.5, 0, 0.6)), C + V((1.5, 0, 0.6)), 28)
# I2 low angle on the mirrors
shot(76, 79, FC + V((3.4, -3.0, -0.9)), FC + V((3.0, -2.2, -0.7)), FC + V((0, 0, 0.5)), FC + V((0, 0, 0.5)), 32)
# I3 wide
shot(79, 84, C + V((0.6, -12.5, 2.2)), C + V((0.6, -11.5, 2.0)), C + V((0.6, 0, 0.3)), C + V((0.2, 0, 0.5)), 30)
# J end card
shot(84, 90.1, FC + V((13.5, 4.6, 3.6)), FC + V((12.0, 4.1, 3.2)), FC + V((0, 0, 1.5)), FC + V((0, 0, 1.5)), 32)

# ---------------------------------------------------------------- render setup
r = scene.render
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        r.engine = eng
        break
    except Exception:
        pass
r.resolution_x, r.resolution_y = 1920, 1080
r.resolution_percentage = 50 if "--half" in argv else 100
r.film_transparent = False
try:
    scene.eevee.taa_render_samples = 32
except Exception as ex:
    print("samples", ex)
r.image_settings.file_format = "JPEG"
r.image_settings.quality = 95
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
except Exception as ex:
    print("look", ex)

try:
    tree = bpy.data.node_groups.new("Comp", "CompositorNodeTree")
    scene.compositing_node_group = tree
    rl = tree.nodes.new("CompositorNodeRLayers")
    gl = tree.nodes.new("CompositorNodeGlare")
    go = tree.nodes.new("NodeGroupOutput")
    tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    print("GLARE INPUTS", [(i.name, i.type) for i in gl.inputs])
    try:
        gl.inputs["Type"].default_value = "Bloom"
    except Exception as ex:
        print("glare type", ex)
        gl.glare_type = "BLOOM"
    for k, v in (("Threshold", 1.2), ("Strength", 0.55), ("Size", 0.55), ("Saturation", 1.0)):
        if k in gl.inputs:
            gl.inputs[k].default_value = v
    tree.links.new(rl.outputs["Image"], gl.inputs["Image"])
    tree.links.new(gl.outputs["Image"], go.inputs[0])
except Exception as ex:
    print("COMPOSITOR FAILED", ex)

blend = os.path.join(ROOT, "blender", "space_janitor.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend)
print("saved", blend)

for t in STILLS:
    scene.frame_set(F(t))
    r.filepath = os.path.join(ROOT, "out", "stills3", "t%05.1f.jpg" % t)
    bpy.ops.render.render(write_still=True)
    print("still", t)
