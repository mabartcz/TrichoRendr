# TrichoRendr -> Blender Cycles bridge.
# Run: blender -b --factory-startup --python cycles.py -- <job dir>
# Reads the job folder written by main.rb (see the layout comment there) and renders <job>/render.png.
import bpy, json, math, os, re, sys, time, unicodedata
import numpy as np
from mathutils import Matrix, Vector

job = os.path.abspath(sys.argv[sys.argv.index('--') + 1])  # Blender can't load textures from relative paths
with open(os.path.join(job, 'scene.json'), encoding='utf-8') as _f:
    S = json.load(_f)
INCH = 0.0254
SAMPLES = int(os.environ.get('TR_SAMPLES', S.get('samples', 128)))
# Material names decide the special shaders: parts of the name, ignoring case and accents (bazén = bazen).
# The window's Materials page edits the lists (config.rb WORDS, same defaults; these are for jobs without
# words, like the test fixture).
plain = lambda s: ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if not unicodedata.combining(c))
WORDS = {k: [w for w in map(plain, v) if w] for k, v in ({
    'water': ('water', 'voda', 'vodn', 'вода', 'pool', 'bazén', 'jezír', 'pond', 'lake', 'river', 'potok'),
    'glass': ('glass', 'glas', 'sklo', 'sklen', 'skleněný', 'okno', 'steklo', 'стекло', 'vidro'),  # also textured
    'glow': ('glow', 'emit', 'svit', 'lamp', 'lampa', 'osvětlení', 'oheň'),
} | S.get('words', {})).items()}
named = lambda kind, name: any(w in name for w in WORDS[kind])
# Look settings from the window (main.rb LOOK has the defaults and ranges; percentages are 100 = normal).
LOOK = S.get('look', {})
pct = lambda k, d=100: LOOK.get(k, d) / 100
EVENING_SKY = 50.0  # blue-hour sky strength relative to day
HAZE_START, HAZE_DEPTH, HAZE_MAX = 3.0, 120.0, 0.8  # meters; HAZE_MAX = haze over the sky at 100 %
# haze colors in scene light at Sky light 100 %: pale blue by day, warm at sunset, dusky blue in the evening
HAZE_DAY, HAZE_SUNSET, HAZE_EVENING = (0.54, 0.6, 0.72), (0.72, 0.57, 0.47), (0.1, 0.14, 0.26)

_last = 0.0


def report(text=None, pct=None, eta=None):
    """Progress for the TrichoRendr window. 'TR: <text>' = status line, 'TR_PROGRESS <pct> <eta s>'
    (-1 = unknown). Progress lines are throttled; a new status line always goes out with its progress."""
    global _last
    now = time.time()
    if text is None and now - _last < 0.5:
        return
    _last = now
    if text:
        print(f'TR: {text}', flush=True)
    print(f'TR_PROGRESS {-1 if pct is None else pct:.1f} {-1 if eta is None else eta:.0f}', flush=True)


report('Step 2/3 · Building scene in Blender', 0)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# --- geometry: flatten instances in numpy, camera-relative meters (eye at origin) ---
# ponytail: one flat mesh; Cycles instancing was tried and measured slower on a real garden (30k copies).
pos = np.fromfile(os.path.join(job, 'pos.bin'), '<f8').reshape(-1, 3, 3)
uv = np.fromfile(os.path.join(job, 'uv.bin'), '<f4').reshape(-1, 2, 3, 2)  # tri, side, vertex, uv
mat = np.fromfile(os.path.join(job, 'mat.bin'), '<i4').reshape(-1, 2)
inst = np.fromfile(os.path.join(job, 'inst.bin'),
                   np.dtype([('mesh', '<u4'), ('mat', '<i4'), ('fm', '<i4'), ('xf', '<f8', (16,))]))
eye = np.array(S['eye'])


def face_camera(f):
    """Face-me (2D tree) rotation about the component's blue axis turning its front (-Y) to the eye.
    Same math as face_camera in renderer/src/main.rs. f: 4x4, column vectors, inches."""
    z = f[:3, 2] / np.linalg.norm(f[:3, 2])
    o = f[:3, 3] / f[3, 3]
    flat = lambda v: v - z * v.dot(z)
    a, b = flat(-f[:3, 1]), flat(eye - o)
    if a.dot(a) < 1e-12 or b.dot(b) < 1e-12:
        return np.eye(4)
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    to, back = np.eye(4), np.eye(4)
    to[:3, 3], back[:3, 3] = o, -o
    return to @ np.array(Matrix.Rotation(math.atan2(np.cross(a, b).dot(z), a.dot(b)), 4, Vector(z))) @ back


turn = np.array([face_camera(np.array(f).reshape(4, 4).T) for f in S.get('faceme', [])]).reshape(-1, 4, 4)

P, UV, M = [], [], []
for mi, md in enumerate(S['meshes']):
    report(pct=40 * mi / len(S['meshes']))
    sel = inst[inst['mesh'] == mi]
    if not len(sel):
        continue
    a, n = md['first'], md['count']
    xf = sel['xf'].reshape(-1, 4, 4).transpose(0, 2, 1)  # SketchUp to_a is column-major
    fm = sel['fm'] >= 0
    xf[fm] = turn[sel['fm'][fm]] @ xf[fm]
    h = np.concatenate([pos[a:a + n].reshape(-1, 3), np.ones((n * 3, 1))], 1)
    w = np.einsum('kij,vj->kvi', xf, h)
    P.append(((w[..., :3] / w[..., 3:] - eye) * INCH).reshape(-1, 3).astype(np.float32))
    mirrored = np.linalg.det(xf[:, :3, :3]) < 0  # flips winding, so front/back swap
    m = np.where(mat[None, a:a + n] < 0, sel['mat'][:, None, None], mat[None, a:a + n])
    u = np.broadcast_to(uv[None, a:a + n], (len(sel), n, 2, 3, 2)).copy()
    m[mirrored] = m[mirrored][..., ::-1]
    u[mirrored] = u[mirrored][:, :, ::-1]
    M.append(m.reshape(-1, 2))
    UV.append(u.reshape(-1, 2, 3, 2))
if not M:  # nothing visible: render the empty sky instead of failing
    P, UV, M = [np.zeros((0, 3), np.float32)], [np.zeros((0, 2, 3, 2), np.float32)], [np.zeros((0, 2), np.int32)]
P, UV, M = np.concatenate(P), np.concatenate(UV), np.concatenate(M)
T = len(M)
# One int per (front, back) pair: a 1-D unique is ~10x faster than unique(axis=0) (3 s on 3M triangles).
n_mat = len(S['materials']) + 1
keys, mat_index = np.unique((M[:, 0].astype(np.int64) + 1) * n_mat + M[:, 1] + 1, return_inverse=True)
pairs = np.stack([keys // n_mat - 1, keys % n_mat - 1], 1)
report(f'Step 2/3 · Building scene in Blender ({T:,} triangles)', 40)

me = bpy.data.meshes.new('scene')
me.vertices.add(T * 3)
me.vertices.foreach_set('co', P.ravel())
me.loops.add(T * 3)
me.loops.foreach_set('vertex_index', np.arange(T * 3, dtype=np.int32))
me.polygons.add(T)
me.polygons.foreach_set('loop_start', np.arange(0, T * 3, 3, dtype=np.int32))
me.polygons.foreach_set('material_index', mat_index.astype(np.int32).ravel())
for side, name in enumerate(('front', 'back')):
    me.uv_layers.new(name=name).uv.foreach_set('vector', UV[:, side].ravel())
me.update()
obj = bpy.data.objects.new('scene', me)
sc.collection.objects.link(obj)

# --- materials: one Blender material per (front, back) pair, switched by Backfacing ---
images = {}
srgb_to_lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def shader(nt, mid, uvmap):
    N, L = nt.nodes, nt.links
    m = S['materials'][mid]
    name = plain(m.get('name') or '')
    col = [srgb_to_lin(c) for c in m['color']] + [1.0]
    b = N.new('ShaderNodeBsdfPrincipled')
    b.inputs['Roughness'].default_value = 0.7

    if named('water', name):
        t = pct('water_tint', 50)  # 0 = clear, 1 = the SketchUp color
        b.inputs['Base Color'].default_value = [1 - t + t * c for c in col[:3]] + [1]
        b.inputs['Transmission Weight'].default_value = 1.0
        b.inputs['IOR'].default_value = 1.333
        b.inputs['Roughness'].default_value = 0.02
        geo, noise, bump = N.new('ShaderNodeNewGeometry'), N.new('ShaderNodeTexNoise'), N.new('ShaderNodeBump')
        noise.inputs['Scale'].default_value = 3.0
        bump.inputs['Strength'].default_value = 0.16 * pct('waves', 50)
        L.new(geo.outputs['Position'], noise.inputs['Vector'])
        L.new(noise.outputs['Fac'], bump.inputs['Height'])
        L.new(bump.outputs['Normal'], b.inputs['Normal'])
        return through_for_shadows(nt, b.outputs[0], b.inputs['Base Color'].default_value)

    if m['alpha'] < 1 and (not m['texture'] or named('glass', name)):  # thin architectural glass
        tint = [1 - m['alpha'] * (1 - c) for c in col[:3]] + [1]
        tr, add = N.new('ShaderNodeBsdfTransparent'), N.new('ShaderNodeAddShader')
        tr.inputs['Color'].default_value = tint
        b.inputs['Base Color'].default_value = (0, 0, 0, 1)
        b.inputs['Roughness'].default_value = 0.0
        b.inputs['IOR'].default_value = 1.5
        b.inputs['Specular IOR Level'].default_value = min(1.0, 0.5 * pct('glass'))  # reflection strength
        L.new(tr.outputs[0], add.inputs[0])
        L.new(b.outputs[0], add.inputs[1])
        return add.outputs[0]

    b.inputs['Base Color'].default_value = col
    if m['texture']:
        path = os.path.join(job, m['texture'])
        if path not in images:
            images[path] = bpy.data.images.load(path)
        tex, uvn = N.new('ShaderNodeTexImage'), N.new('ShaderNodeUVMap')
        tex.image, uvn.uv_map = images[path], uvmap
        L.new(uvn.outputs['UV'], tex.inputs['Vector'])
        L.new(tex.outputs['Color'], b.inputs['Base Color'])
        mul = N.new('ShaderNodeMath')
        mul.operation, mul.inputs[1].default_value = 'MULTIPLY', m['alpha']
        L.new(tex.outputs['Alpha'], mul.inputs[0])
        L.new(mul.outputs[0], b.inputs['Alpha'])
    else:
        b.inputs['Alpha'].default_value = m['alpha']
    if named('glow', name):
        if m['texture']:
            L.new(b.inputs['Base Color'].links[0].from_socket, b.inputs['Emission Color'])
        else:
            b.inputs['Emission Color'].default_value = col
        b.inputs['Emission Strength'].default_value = 10.0 * pct('lamps')
    leaves = pct('leaves', 0)
    if leaves and m['texture'] and images[path].channels == 4:  # cut-out PNG: plants, trees
        # Sun shining through leaves: part diffuse, part translucent. The cut-out moves from the
        # Principled alpha to a Transparent mix, so the translucent part keeps the leaf shape.
        tl, mx, cut, tr = (N.new(t) for t in ('ShaderNodeBsdfTranslucent', 'ShaderNodeMixShader',
                                               'ShaderNodeMixShader', 'ShaderNodeBsdfTransparent'))
        L.new(tex.outputs['Color'], tl.inputs['Color'])
        L.new(mul.outputs[0], cut.inputs['Fac'])
        L.remove(b.inputs['Alpha'].links[0])
        mx.inputs['Fac'].default_value = 0.6 * leaves
        L.new(b.outputs[0], mx.inputs[1])
        L.new(tl.outputs[0], mx.inputs[2])
        L.new(tr.outputs[0], cut.inputs[1])
        L.new(mx.outputs[0], cut.inputs[2])
        return cut.outputs[0]
    return b.outputs[0]


def through_for_shadows(nt, surface, tint):
    """Let sunlight through (no caustics in a path tracer), so pool bottoms aren't black."""
    N, L = nt.nodes, nt.links
    lp, tr, mix = N.new('ShaderNodeLightPath'), N.new('ShaderNodeBsdfTransparent'), N.new('ShaderNodeMixShader')
    tr.inputs['Color'].default_value = tint
    L.new(lp.outputs['Is Shadow Ray'], mix.inputs[0])
    L.new(surface, mix.inputs[1])
    L.new(tr.outputs[0], mix.inputs[2])
    return mix.outputs[0]


report(pct=60)
for i, (f, bk) in enumerate(pairs):
    report(pct=60 + 40 * i / len(pairs))
    bm = bpy.data.materials.new(f'm{f}_{bk}')
    bm.use_nodes = True
    nt = bm.node_tree
    nt.nodes.clear()
    out, geo, mix = nt.nodes.new('ShaderNodeOutputMaterial'), nt.nodes.new('ShaderNodeNewGeometry'), nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(geo.outputs['Backfacing'], mix.inputs[0])
    nt.links.new(shader(nt, f, 'front'), mix.inputs[1])
    nt.links.new(shader(nt, bk, 'back'), mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    me.materials.append(bm)

# --- camera ---
fwd = Vector(np.array(S['target']) - eye).normalized()
right = fwd.cross(Vector(S['up'])).normalized()
up = right.cross(fwd)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
cam.matrix_world = Matrix((right, up, -fwd)).transposed().to_4x4()  # columns: x=right, y=up, z=-forward
cam.data.sensor_fit = 'VERTICAL'
cam.data.clip_start = 0.01
cam.data.clip_end = 10000
if S.get('ortho'):  # parallel projection (plans, elevations): view height in meters
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = S['ortho']  # VERTICAL sensor fit: the scale is the view height
    cam.location = -1000 * fwd  # step back 1 km so nothing behind SketchUp's eye gets clipped
    cam.data.clip_end = 20000
else:
    cam.data.angle = math.radians(S['vfov'])
sc.collection.objects.link(cam)
sc.camera = cam

# --- sun + sky ---
world = bpy.data.worlds.new('world')
world.use_nodes = True
sc.world = world
wn = world.node_tree
sky, bg = wn.nodes.new('ShaderNodeTexSky'), wn.nodes['Background']
sky.sky_type = 'MULTIPLE_SCATTERING'
sky.sun_disc = False
sun_dir = Vector(S['sun']).normalized() if S.get('sun') else Vector((0.3, -0.5, 0.8)).normalized()
sunset, evening = LOOK.get('time') == 'sunset', LOOK.get('time') == 'evening'
if sunset or evening:  # SketchUp's sun direction, moved to 4 degrees above the horizon (orange sky, long shadows)
    # or 6 below it (blue hour: no sun, deep blue sky, the lamps carry the picture)
    flat = Vector((sun_dir.x, sun_dir.y, 0)).normalized() if sun_dir.xy.length > 1e-6 else Vector((0, -1, 0))
    sun_dir = (flat + Vector((0, 0, math.tan(math.radians(4 if sunset else -6))))).normalized()
sky.sun_elevation = math.asin(sun_dir.z)
sky.sun_rotation = math.atan2(sun_dir.x, sun_dir.y)
wn.links.new(sky.outputs['Color'], bg.inputs['Color'])
sunlit = (S.get('sun') or sunset) and LOOK.get('shadows', True) and not evening
# no sun: brighter overcast sky; sunset: the low-sun sky is darker, lift it; evening: twilight is far darker
bg.inputs['Strength'].default_value = (0.06 * pct('sky') * (1 if sunlit else 4) * (3 if sunset else 1)
                                       * (EVENING_SKY if evening else 1))
background = LOOK.get('background', 'sky')
paper = None  # the white background's light value, when there is one
if background == 'transparent':  # PNG with alpha: sky added later in Photoshop; the sky still lights
    sc.render.film_transparent = True
elif background == 'white' or S.get('ortho'):  # plans look down past the horizon at a black ground
    white, mix, lp = (wn.nodes.new(t) for t in ('ShaderNodeBackground', 'ShaderNodeMixShader', 'ShaderNodeLightPath'))
    white.inputs['Strength'].default_value = 10.0  # AgX needs ~10 for paper white
    paper = [c * 10.0 for c in white.inputs['Color'].default_value[:3]]
    wn.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    wn.links.new(bg.outputs[0], mix.inputs[1])
    wn.links.new(white.outputs[0], mix.inputs[2])
    wn.links.new(mix.outputs[0], wn.nodes['World Output'].inputs['Surface'])
if sunlit:
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 5.0 * pct('sun')
    if sunset:
        sun.data.color = (1.0, 0.55, 0.3)  # low sun light is orange (the sky texture doesn't tint the lamp)
        sun.data.energy *= 0.8
    sun.data.angle = math.radians(0.5 + 0.2 * LOOK.get('softness', 0))  # wider sun = softer shadow edges
    sun.rotation_euler = sun_dir.to_track_quat('Z', 'Y').to_euler()  # light travels along -Z
    sc.collection.objects.link(sun)

# Lens flare, only when the sun is in the picture over the sky. The camera sees a sky with the sun disc
# (lighting keeps the disc-less sky: the lamp already is the sun); the compositor turns that bright spot
# into a halo, ghosts and beams. sun_xy: the sun's position in the frame, 0..1 from the bottom left.
sun_xy = None
if pct('flare', 0) and background == 'sky' and not S.get('ortho') and sunlit and sun_dir.dot(fwd) > 0:
    t = math.tan(math.radians(S['vfov']) / 2)
    z = sun_dir.dot(fwd)
    x = 0.5 + sun_dir.dot(right) / z / t / (S['width'] / S['height']) / 2
    y = 0.5 + sun_dir.dot(up) / z / t / 2
    if -0.02 < x < 1.02 and -0.02 < y < 1.02:
        sun_xy = (x, y)
if sun_xy:
    disc, disc_bg, lp, mix = (wn.nodes.new(t) for t in ('ShaderNodeTexSky', 'ShaderNodeBackground',
                                                        'ShaderNodeLightPath', 'ShaderNodeMixShader'))
    disc.sky_type, disc.sun_disc = sky.sky_type, True
    disc.sun_elevation, disc.sun_rotation = sky.sun_elevation, sky.sun_rotation
    disc_bg.inputs['Strength'].default_value = bg.inputs['Strength'].default_value
    wn.links.new(disc.outputs['Color'], disc_bg.inputs['Color'])
    wn.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    wn.links.new(bg.outputs[0], mix.inputs[1])
    wn.links.new(disc_bg.outputs[0], mix.inputs[2])
    wn.links.new(mix.outputs[0], wn.nodes['World Output'].inputs['Surface'])

# --- render settings ---
prefs = bpy.context.preferences.addons['cycles'].preferences
sc.render.engine = 'CYCLES'
c = sc.cycles
gpu_found = False
env_dev = os.environ.get('TR_DEVICE')
for dev_type in ([env_dev] if env_dev else ['OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL']):
    try:
        prefs.compute_device_type = dev_type
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == dev_type]  # devices lists every backend's devices
        if gpus:
            for d in prefs.devices:
                d.use = d.type == dev_type
            gpu_found = True
            break
    except Exception:
        continue
c.device = 'GPU' if gpu_found else 'CPU'
c.samples = SAMPLES
c.use_denoising = True
c.denoiser = 'OPENIMAGEDENOISE'
c.max_bounces = 8
c.transparent_max_bounces = 64  # stacked plant cards
c.caustics_reflective = c.caustics_refractive = False
sc.render.resolution_x, sc.render.resolution_y = S['width'], S['height']
sc.render.resolution_percentage = 100
# --- image look: tone mapping style, exposure, white balance; saturation and glow in the compositor ---
vs = sc.view_settings
vs.view_transform, vs.look = {'natural': ('AgX', 'None'), 'punchy': ('AgX', 'AgX - Punchy'),
                              'soft': ('AgX', 'AgX - Low Contrast'), 'contrast': ('AgX', 'AgX - High Contrast'),
                              'vivid': ('Standard', 'Medium High Contrast')}[LOOK.get('style', 'natural')]
vs.exposure = LOOK.get('exposure', 0)
if LOOK.get('warmth', 0):
    vs.use_white_balance = True
    vs.white_balance_temperature = 6500 + 25 * LOOK['warmth']  # bluer assumed white point = warmer picture
# Haze: distant things fade into the air (aerial perspective), from the mist pass (0 near, 1 far and sky).
haze = 0 if S.get('ortho') else pct('haze', 0)
if haze:
    sc.view_layers[0].use_pass_mist = True
    ms = world.mist_settings
    ms.start, ms.depth, ms.falloff = HAZE_START, HAZE_DEPTH, 'LINEAR'
if pct('saturation') != 1 or LOOK.get('glow', 0) or sun_xy or haze:
    g = bpy.data.node_groups.new('look', 'CompositorNodeTree')
    g.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = g.nodes.new('CompositorNodeRLayers')
    img = rl.outputs['Image']
    if haze:
        amount, mix = g.nodes.new('ShaderNodeMath'), g.nodes.new('ShaderNodeMix')
        amount.operation, amount.inputs[1].default_value = 'MULTIPLY', HAZE_MAX * haze
        mix.data_type = 'RGBA'
        sock = lambda n, ident: next(x for x in n.inputs if x.identifier == ident)
        dn = g.nodes.new('CompositorNodeDenoise')  # the mist pass is noisy behind cut-out leaves
        g.links.new(rl.outputs['Mist'], dn.inputs['Image'])
        g.links.new(dn.outputs['Image'], amount.inputs[0])
        fac = amount.outputs[0]
        if sc.render.film_transparent:  # mist is 1 on the empty background too: keep it empty (alpha 0)
            keep = g.nodes.new('ShaderNodeMath')
            keep.operation = 'MULTIPLY'
            g.links.new(fac, keep.inputs[0])
            g.links.new(rl.outputs['Alpha'], keep.inputs[1])
            fac = keep.outputs[0]
        g.links.new(fac, sock(mix, 'Factor_Float'))
        g.links.new(img, sock(mix, 'A_Color'))
        # White background: distant things fade to the same paper white, so the background stays white
        sock(mix, 'B_Color').default_value = (paper or [c * pct('sky') for c in (
            HAZE_SUNSET if sunset else HAZE_EVENING if evening else HAZE_DAY)]) + [1]
        img = next(o for o in mix.outputs if o.identifier == 'Result_Color')
    if LOOK.get('glow', 0):
        gl = g.nodes.new('CompositorNodeGlare')
        gl.inputs['Type'].default_value = 'Bloom'
        gl.inputs['Strength'].default_value = pct('glow', 0)
        g.links.new(img, gl.inputs['Image'])
        img = gl.outputs['Image']
    if sun_xy:
        f = pct('flare', 0)
        for kind, strength in (('Fog Glow', 0.15), ('Ghosts', 0.8), ('Sun Beams', 0.2)):
            gl = g.nodes.new('CompositorNodeGlare')
            gl.inputs['Type'].default_value = kind
            gl.inputs['Threshold'].default_value = 4.0  # only the sun disc, not white walls
            gl.inputs['Strength'].default_value = strength * f
            if kind == 'Sun Beams':
                gl.inputs['Sun Position'].default_value[0], gl.inputs['Sun Position'].default_value[1] = sun_xy
            g.links.new(img, gl.inputs['Image'])
            img = gl.outputs['Image']
    if pct('saturation') != 1:
        hs = g.nodes.new('CompositorNodeHueSat')
        hs.inputs['Saturation'].default_value = pct('saturation')
        g.links.new(img, hs.inputs['Image'])
        img = hs.outputs['Image']
    g.links.new(img, g.nodes.new('NodeGroupOutput').inputs[0])
    sc.compositing_node_group = g
sc.render.image_settings.file_format = 'PNG'

# Progressive passes for the live preview: in batch mode render straight to SAMPLES (saves ~30% time);
# in single-view mode render a fast 4-sample preview pass (plus 32 if SAMPLES > 64) before the final pass.
sc.render.use_persistent_data = True
steps = () if S.get('batch') else ((4, 32) if SAMPLES > 64 else (4,))
passes = [n for n in steps if n < SAMPLES] + [SAMPLES]
total, done, t_first = sum(passes), 0, None


def progress(stats, *_):
    """render_stats fires live: 'Updating Geometry BVH ...' while preparing, '... | Sample 12/32' while
    rendering. Turned into one overall % and time left for all passes."""
    global t_first
    m = re.search(r'Sample (\d+)/\d+', stats)
    if not m:  # still preparing (first pass syncs the whole scene and builds the BVH)
        report(pct=None)
        return
    now = time.time()
    k = done + int(m.group(1))
    t_first = t_first or now
    eta = (now - t_first) / k * (total - k) if k and now - t_first > 2 else None
    report(pct=100 * k / total, eta=eta)


bpy.app.handlers.render_stats.append(progress)
for i, n in enumerate(passes, 1):
    c.samples = n
    final = i == len(passes)
    report(f'Step 3/3 · Rendering pass {i}/{len(passes)} ({n} samples)' + (' · preparing scene' if i == 1 else ''),
           100 * done / total)
    sc.render.filepath = os.path.join(job, 'render.png' if final else f'pass_{i}.png')
    try:
        bpy.ops.render.render(write_still=True)
    except RuntimeError:
        if c.device != 'GPU':
            raise
        # e.g. a graphics driver too old for this Blender's GPU kernels ("Invalid kernel image"): slower, but renders
        c.device = 'CPU'
        report('Graphics card failed (update its driver) · rendering on the processor, slower')
        bpy.ops.render.render(write_still=True)
    done += n
