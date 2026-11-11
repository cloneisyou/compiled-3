import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import * as PH from './physics.js';

const sat = window.satellite;
const $ = (id) => document.getElementById(id);
const RE = PH.RE_KM;
const KM = 1 / RE; // scene units per km (Earth radius = 1)

// ---------- formatting ----------
const num = (v, d = 0) => v.toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });
const sig = (v) => v.toLocaleString('en-US', { maximumFractionDigits: v >= 100 ? 0 : v >= 10 ? 1 : 2 });
function fmtPower(w) { return w >= 1e6 ? sig(w / 1e6) + ' MW' : w >= 1e3 ? sig(w / 1e3) + ' kW' : sig(w) + ' W'; }
function fmtForce(n) { return n >= 1 ? sig(n) + ' N' : n >= 1e-3 ? sig(n * 1e3) + ' mN' : sig(n * 1e6) + ' µN'; }
function fmtTime(s) {
  if (!isFinite(s)) return '—';
  if (s < 120) return sig(s) + ' s';
  if (s < 7200) return sig(s / 60) + ' min';
  if (s < 3 * 86400) return sig(s / 3600) + ' h';
  if (s < 90 * 86400) return sig(s / 86400) + ' days';
  if (s < 2 * 365.25 * 86400) return sig(s / (30.44 * 86400)) + ' months';
  return sig(s / (365.25 * 86400)) + ' years';
}
function fmtMoney(v) {
  if (!isFinite(v)) return '—';
  if (v >= 1e9) return '$' + sig(v / 1e9) + 'B';
  if (v >= 1e6) return '$' + sig(v / 1e6) + 'M';
  if (v >= 1e4) return '$' + num(v / 1e3, v >= 1e5 ? 0 : 1) + 'k';
  if (v >= 100) return '$' + num(v);
  return '$' + num(v, 2);
}
function fmtMass(kg) { return kg >= 1000 ? sig(kg / 1000) + ' t' : sig(kg) + ' kg'; }

// ---------- shared state ----------
let K = PH.defaults();
const swarm = () => ({ N: +$('i-n').value, area: Math.max(0.01, +$('i-area').value || 1) });
const totals = { count: 0, kg: 0, rev: 0 };

// ---------- scene ----------
const canvas = $('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 200);
camera.position.set(2.6, 1.5, 2.6);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.enablePan = false;
controls.minDistance = 1.3; controls.maxDistance = 9; controls.rotateSpeed = 0.5;

scene.add(new THREE.AmbientLight(0xffffff, 0.55));
const sun = new THREE.DirectionalLight(0xffffff, 2.4);
sun.position.set(5, 2, 3); scene.add(sun);

const earthTex = new THREE.TextureLoader().load('tex/earth_day.jpg');
earthTex.colorSpace = THREE.SRGBColorSpace; earthTex.anisotropy = 8;
const earth = new THREE.Mesh(new THREE.SphereGeometry(1, 96, 64),
  new THREE.MeshStandardMaterial({ map: earthTex, roughness: 0.9, metalness: 0 }));
scene.add(earth);
scene.add(new THREE.Mesh(new THREE.SphereGeometry(1.025, 64, 48),
  new THREE.MeshBasicMaterial({ color: 0x4d8dff, transparent: true, opacity: 0.1, side: THREE.BackSide, depthWrite: false })));

{ // stars
  const p = new Float32Array(1800 * 3);
  for (let i = 0; i < 1800; i++) {
    const v = new THREE.Vector3().randomDirection().multiplyScalar(90);
    p.set([v.x, v.y, v.z], i * 3);
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  scene.add(new THREE.Points(g, new THREE.PointsMaterial({ color: 0x8a94a8, size: 1.2, sizeAttenuation: false })));
}

function discTexture(ring) {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const x = c.getContext('2d');
  if (ring) { x.strokeStyle = '#fff'; x.lineWidth = 4; x.beginPath(); x.arc(32, 32, 26, 0, 7); x.stroke(); }
  else { const g = x.createRadialGradient(32, 32, 0, 32, 32, 32); g.addColorStop(0, '#fff'); g.addColorStop(0.5, '#fff'); g.addColorStop(1, 'rgba(255,255,255,0)'); x.fillStyle = g; x.fillRect(0, 0, 64, 64); }
  return new THREE.CanvasTexture(c);
}
const dotTex = discTexture(false);

// TEME (km) -> scene (y up)
const toScene = (p, out) => out.set(p.x * KM, p.z * KM, -p.y * KM);

// ---------- data ----------
const GROUPS = [
  { file: 'data/cosmos-2251-debris.tle', color: 0xff9d4d, css: '#ff9d4d', parent: 'COSMOS 2251', parentMass: 900, parentSize: 2.0 },
  { file: 'data/iridium-33-debris.tle', color: 0x4dd8ff, css: '#4dd8ff', parent: 'IRIDIUM 33', parentMass: 560, parentSize: 1.8 },
  { file: 'data/fengyun-1c-debris.tle', color: 0xb9a6ff, css: '#b9a6ff', parent: 'FENGYUN 1C', parentMass: 880, parentSize: 1.8 },
];
const objects = [];
let latestEpochJd = 0;

function hash01(n) { let x = Math.imul(n ^ 0x9e3779b9, 0x85ebca6b); x ^= x >>> 13; x = Math.imul(x, 0xc2b2ae35); x ^= x >>> 16; return (x >>> 0) / 4294967296; }

async function loadGroup(g) {
  const res = await fetch(g.file);
  if (!res.ok) return;
  const lines = (await res.text()).split(/\r?\n/).map((l) => l.trimEnd()).filter(Boolean);
  for (let i = 0; i + 2 < lines.length + 1; i += 3) {
    const name = lines[i].trim(), l1 = lines[i + 1], l2 = lines[i + 2];
    if (!l1 || !l2 || l1[0] !== '1' || l2[0] !== '2') continue;
    const rec = sat.twoline2satrec(l1, l2);
    if (rec.error) continue;
    const n = rec.no / 60; // rad/s
    const a = Math.cbrt(PH.MU / (n * n)) / 1e3; // km
    const apo = a * (1 + rec.ecco) - RE, peri = a * (1 - rec.ecco) - RE;
    if (peri < 160) continue; // already decaying
    const id = +rec.satnum;
    const isParent = name === g.parent;
    // TLEs carry no mass or size: fragments get a deterministic log-uniform 0.1–20 kg estimate.
    const mass = isParent ? g.parentMass : +(0.1 * Math.pow(200, hash01(id))).toPrecision(2);
    const size = isParent ? g.parentSize : +(0.15 * Math.cbrt(mass)).toFixed(2);
    latestEpochJd = Math.max(latestEpochJd, rec.jdsatepoch);
    objects.push({ name, id, rec, group: g, apo, peri, periodMin: 2 * Math.PI / rec.no, inc: rec.inclo * 180 / Math.PI,
      mass, size, isParent, alive: true, pos: new THREE.Vector3(), ok: false });
  }
}

// ---------- points ----------
let points, posAttr, colAttr;
function buildPoints() {
  const n = objects.length;
  const g = new THREE.BufferGeometry();
  posAttr = new THREE.BufferAttribute(new Float32Array(n * 3), 3); posAttr.setUsage(THREE.DynamicDrawUsage);
  colAttr = new THREE.BufferAttribute(new Float32Array(n * 3), 3);
  const c = new THREE.Color();
  objects.forEach((o, i) => { c.set(o.group.color); colAttr.setXYZ(i, c.r, c.g, c.b); o.index = i; });
  g.setAttribute('position', posAttr); g.setAttribute('color', colAttr);
  g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 20);
  points = new THREE.Points(g, new THREE.PointsMaterial({ size: 4.5, sizeAttenuation: false, vertexColors: true,
    map: dotTex, transparent: true, alphaTest: 0.2, depthWrite: false }));
  scene.add(points);
}

// ---------- time ----------
let simMs = Date.now();
let warp = 60;
const jdOf = (ms) => ms / 86400000 + 2440587.5;

function propagateAll() {
  const jd = jdOf(simMs);
  for (const o of objects) {
    if (!o.alive) continue;
    if (o === mission?.obj) continue; // driven by the de-orbit model
    const pv = sat.sgp4(o.rec, (jd - o.rec.jdsatepoch) * 1440);
    const p = pv && pv.position;
    if (!p || !isFinite(p.x)) { o.ok = false; posAttr.setXYZ(o.index, 0, 0, 0); continue; }
    o.ok = true; o.vel = pv.velocity; o.eci = p;
    toScene(p, o.pos);
    posAttr.setXYZ(o.index, o.pos.x, o.pos.y, o.pos.z);
  }
  posAttr.needsUpdate = true;
}

// ---------- selection ----------
let selected = null;
const ring = new THREE.Sprite(new THREE.SpriteMaterial({ map: discTexture(true), color: 0xffffff, sizeAttenuation: false, depthTest: false, transparent: true }));
ring.scale.setScalar(0.035); ring.visible = false; ring.renderOrder = 5; scene.add(ring);

const ORBIT_N = 256;
const orbitLine = new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array((ORBIT_N + 1) * 3), 3)),
  new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.85 }));
orbitLine.frustumCulled = false; orbitLine.visible = false; scene.add(orbitLine);

function drawSgp4Orbit(o) {
  const a = orbitLine.geometry.attributes.position, v = new THREE.Vector3();
  const t0 = (jdOf(simMs) - o.rec.jdsatepoch) * 1440;
  for (let i = 0; i <= ORBIT_N; i++) {
    const pv = sat.sgp4(o.rec, t0 + (i / ORBIT_N) * o.periodMin);
    if (pv && pv.position) toScene(pv.position, v);
    a.setXYZ(i, v.x, v.y, v.z);
  }
  a.needsUpdate = true; orbitLine.visible = true;
}

function planFor(o) {
  return PH.removal({ mass: o.mass, size: o.size, raKm: RE + o.apo, rpKm: RE + o.peri, ...swarm() }, K);
}

function select(o, fromList) {
  if (mission && !mission.done) return;
  if (mission) endMission();
  selected = o;
  $('target-empty').hidden = !!o; $('target-body').hidden = !o;
  ring.visible = !!o; orbitLine.visible = false;
  document.querySelectorAll('#list li.sel').forEach((li) => li.classList.remove('sel'));
  if (!o) return;
  const li = document.querySelector(`#list li[data-id="${o.id}"]`);
  if (li) { li.classList.add('sel'); if (!fromList) li.scrollIntoView({ block: 'nearest' }); }
  $('t-name').textContent = o.name; $('t-id').textContent = 'NORAD ' + o.id;
  $('t-apo').textContent = num(o.apo) + ' km'; $('t-peri').textContent = num(o.peri) + ' km';
  $('t-period').textContent = num(o.periodMin, 1) + ' min'; $('t-inc').textContent = num(o.inc, 1) + '°';
  $('t-mass').textContent = fmtMass(o.mass); $('t-size').textContent = o.size + ' m';
  $('mission').hidden = true; $('btn-clean').hidden = false; $('btn-clean').disabled = false;
  // mirror the target into the calculator
  $('i-mass').value = o.mass; $('i-size').value = o.size; $('i-alt').value = Math.round((o.apo + o.peri) / 2);
  drawSgp4Orbit(o); lastOrbitDraw = performance.now();
  refreshAll();
}
let lastOrbitDraw = 0;

function refreshTargetPlan() {
  if (!selected || mission) return;
  const p = planFor(selected);
  $('t-thrust').textContent = fmtForce(p.thrust); $('t-dv').textContent = num(p.dv, 1) + ' m/s';
  $('t-time').textContent = fmtTime(p.time); $('t-price').textContent = fmtMoney(p.price);
}

// ---------- list ----------
let listed = [];
function renderList() {
  const q = $('search').value.trim().toUpperCase();
  listed = objects.filter((o) => o.alive && (!q || o.name.includes(q) || String(o.id).includes(q)));
  listed.sort((a, b) => (b.isParent - a.isParent) || (b.mass - a.mass));
  $('obj-count').textContent = num(listed.length) + ' objects';
  $('list').innerHTML = listed.slice(0, 200).map((o) =>
    `<li data-id="${o.id}"${o === selected ? ' class="sel"' : ''}><span><i style="background:${o.group.css}"></i>${o.name}</span><span>${fmtMass(o.mass)} · ${num((o.apo + o.peri) / 2)} km</span></li>`).join('');
}
$('search').addEventListener('input', renderList);
$('list').addEventListener('click', (e) => {
  const li = e.target.closest('li'); if (!li) return;
  const o = objects.find((x) => x.id === +li.dataset.id); if (o) select(o, true);
});

// ---------- picking ----------
let downAt = null;
canvas.addEventListener('pointerdown', (e) => { downAt = [e.clientX, e.clientY]; });
canvas.addEventListener('pointerup', (e) => {
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 4) return;
  const r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  const v = new THREE.Vector3(), d = new THREE.Vector3(); let best = null, bestD = 14;
  for (const o of objects) {
    if (!o.alive || !o.ok) continue;
    v.copy(o.pos).project(camera);
    if (v.z > 1) continue;
    const dist = Math.hypot((v.x * 0.5 + 0.5) * r.width - mx, (-v.y * 0.5 + 0.5) * r.height - my);
    if (dist >= bestD) continue;
    d.copy(o.pos).sub(camera.position); // occlusion by Earth
    const t = -camera.position.dot(d) / d.lengthSq();
    if (t > 0 && t < 1 && d.clone().multiplyScalar(t).add(camera.position).length() < 1) continue;
    best = o; bestD = dist;
  }
  if (best) select(best);
});

// ---------- de-orbit mission ----------
let mission = null;
const MISSION_WALL_S = 12; // wall-clock seconds a de-orbit takes on screen
const beam = new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3)),
  new THREE.LineBasicMaterial({ color: 0xffd98a, transparent: true, opacity: 0.9 }));
beam.frustumCulled = false; beam.visible = false; scene.add(beam);
const SW = 40;
const swarmPts = new THREE.Points(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(SW * 3), 3)),
  new THREE.PointsMaterial({ color: 0xffe9b8, size: 3, sizeAttenuation: false, map: dotTex, transparent: true, depthWrite: false }));
swarmPts.frustumCulled = false; swarmPts.visible = false; scene.add(swarmPts);
const swarmOffsets = Array.from({ length: SW }, () => new THREE.Vector3().randomDirection().multiplyScalar(0.012 * Math.cbrt(Math.random())));
const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: dotTex, color: 0xffb547, sizeAttenuation: false, depthTest: false, transparent: true, blending: THREE.AdditiveBlending }));
glow.visible = false; glow.renderOrder = 6; scene.add(glow);

const V = (o) => new THREE.Vector3(o.x, o.y, o.z);

function startMission() {
  const o = selected; if (!o || !o.ok || mission) return;
  // osculating two-body elements from the current SGP4 state (km, km/s)
  const r = V(o.eci), v = V(o.vel), mu = PH.MU / 1e9;
  const h = r.clone().cross(v);
  const ev = v.clone().cross(h).divideScalar(mu).sub(r.clone().normalize());
  const e = ev.length(), a = 1 / (2 / r.length() - v.lengthSq() / mu);
  const pHat = e > 1e-6 ? ev.clone().normalize() : r.clone().normalize();
  const qHat = h.clone().normalize().cross(pHat);
  const ra = a * (1 + e), rp = a * (1 - e);
  const nu = Math.atan2(r.dot(qHat), r.dot(pHat));
  const E = 2 * Math.atan2(Math.sqrt(1 - e) * Math.sin(nu / 2), Math.sqrt(1 + e) * Math.cos(nu / 2));
  const plan = PH.removal({ mass: o.mass, size: o.size, raKm: ra, rpKm: rp, ...swarm() }, K);
  mission = { obj: o, plan, pHat, qHat, ra, rp0: rp, rp, M: E - e * Math.sin(E), t: 0, done: false, flash: 0,
    rate: Math.max(plan.time / MISSION_WALL_S, 1) };
  $('btn-clean').hidden = true; $('mission').hidden = false;
  $('m-status').textContent = 'Engaging'; $('m-status').classList.remove('done');
  $('m-rate').textContent = 'mission clock ×' + num(mission.rate);
  beam.visible = swarmPts.visible = glow.visible = true;
  orbitLine.material.color.set(0xffb547);
}

function stepMission(dtWall, dtSim) {
  const m = mission; if (!m) return;
  const o = m.obj;
  if (m.done) { // burn-up flash
    m.flash += dtWall;
    const f = m.flash / 0.9;
    glow.scale.setScalar(0.03 + 0.22 * f); glow.material.opacity = Math.max(0, 1 - f); glow.material.color.set(0xffffff);
    if (f >= 1) glow.visible = false;
    return;
  }
  m.t = Math.min(m.t + dtWall * m.rate, m.plan.time);
  const f = m.plan.time > 0 ? m.t / m.plan.time : 1;
  m.rp = PH.perigeeAfter(m.ra, m.rp0, f * m.plan.dv);
  const a = (m.ra + m.rp) / 2, e = (m.ra - m.rp) / (m.ra + m.rp), mu = PH.MU / 1e9;
  m.M += Math.sqrt(mu / (a * a * a)) * dtSim;
  let E = m.M; for (let i = 0; i < 6; i++) E -= (E - e * Math.sin(E) - m.M) / (1 - e * Math.cos(E));
  const at = (Ea, out) => { // perifocal -> TEME -> scene
    const x = a * (Math.cos(Ea) - e), y = a * Math.sqrt(1 - e * e) * Math.sin(Ea);
    return toScene({ x: m.pHat.x * x + m.qHat.x * y, y: m.pHat.y * x + m.qHat.y * y, z: m.pHat.z * x + m.qHat.z * y }, out);
  };
  at(E, o.pos);
  posAttr.setXYZ(o.index, o.pos.x, o.pos.y, o.pos.z); posAttr.needsUpdate = true;
  const la = orbitLine.geometry.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i <= ORBIT_N; i++) { at((i / ORBIT_N) * 2 * Math.PI, v); la.setXYZ(i, v.x, v.y, v.z); }
  la.needsUpdate = true; orbitLine.visible = true;
  // swarm flies just ahead of the target (offset exaggerated for visibility) and lights its leading face
  const ahead = at(E + 0.05, new THREE.Vector3()).sub(o.pos).normalize().multiplyScalar(0.1).add(o.pos);
  const sp = swarmPts.geometry.attributes.position;
  swarmOffsets.forEach((off, i) => sp.setXYZ(i, ahead.x + off.x, ahead.y + off.y, ahead.z + off.z)); sp.needsUpdate = true;
  const bp = beam.geometry.attributes.position; bp.setXYZ(0, ahead.x, ahead.y, ahead.z); bp.setXYZ(1, o.pos.x, o.pos.y, o.pos.z); bp.needsUpdate = true;
  glow.position.copy(o.pos); glow.scale.setScalar(0.022 + 0.006 * Math.sin(performance.now() / 90)); glow.material.opacity = 0.9; glow.material.color.set(0xffb547);

  $('m-peri').textContent = num(m.rp - RE);
  $('m-bar').style.width = (f * 100).toFixed(1) + '%';
  $('m-day').textContent = fmtTime(m.t) + ' / ' + fmtTime(m.plan.time);
  $('m-dv').textContent = 'Δv ' + num(f * m.plan.dv, 1) + ' / ' + num(m.plan.dv, 1) + ' m/s';
  if (f >= 1) burnUp();
}

function burnUp() {
  const m = mission, o = m.obj;
  m.done = true; o.alive = false;
  posAttr.setXYZ(o.index, 0, 0, 0); posAttr.needsUpdate = true;
  beam.visible = swarmPts.visible = orbitLine.visible = ring.visible = false;
  $('m-status').textContent = 'Burned up · ' + fmtMoney(m.plan.price); $('m-status').classList.add('done');
  totals.count++; totals.kg += o.mass; totals.rev += m.plan.price;
  for (const [id, txt] of [['c-count', num(totals.count)], ['c-kg', fmtMass(totals.kg)], ['c-rev', fmtMoney(totals.rev)]]) {
    const el = $(id); el.textContent = txt; el.classList.remove('bump'); void el.offsetWidth; el.classList.add('bump');
  }
  renderList();
}

function endMission() {
  mission = null; selected = null;
  glow.visible = beam.visible = swarmPts.visible = false;
  orbitLine.material.color.set(0xffffff);
}
$('btn-clean').addEventListener('click', startMission);

// ---------- time controls ----------
document.querySelectorAll('.warp button').forEach((b) => b.addEventListener('click', () => {
  warp = +b.dataset.warp;
  document.querySelectorAll('.warp button').forEach((x) => x.classList.toggle('on', x === b));
}));

// ---------- calculator ----------
function calcInput() {
  return { mass: Math.max(1e-3, +$('i-mass').value || 0), size: Math.max(0.01, +$('i-size').value || 0),
    altKm: Math.max(K.perigeeKm, +$('i-alt').value || 0), deadlineDays: +$('i-deadline').value || 0, ...swarm() };
}
function refreshCalc() {
  const inp = calcInput(), r = PH.removal(inp, K);
  $('o-n').textContent = num(inp.N);
  $('r-price').textContent = fmtMoney(r.price);
  $('r-price-sub').textContent = `${num(r.removals, r.removals < 10 ? 1 : 0)} removals over a ${K.lifeYears}-year swarm · ${fmtMoney(r.capex)} swarm cost`;
  $('r-l1').textContent = '$' + num(K.launch); $('r-l2').textContent = '$' + num(K.launchToday);
  $('r-price1').textContent = fmtMoney(r.price); $('r-price2').textContent = fmtMoney(r.priceToday);
  const mx = Math.max(r.price, r.priceToday) || 1;
  $('r-bar1').style.width = (100 * r.price / mx) + '%'; $('r-bar2').style.width = (100 * r.priceToday / mx) + '%';
  $('r-power').textContent = fmtPower(r.pIntercepted);
  $('r-power-sub').textContent = `${fmtPower(r.pDelivered)} delivered · ${fmtPower(r.pIncident)} collected`;
  $('r-spot').textContent = num(r.spotD, 2) + ' m';
  $('r-spot-sub').textContent = `target catches ${num(r.frac * 100, r.frac < 0.1 ? 1 : 0)}% of the spot`;
  $('r-temp').textContent = num(r.tempK) + ' K';
  const ts = $('r-temp-sub'); const cold = r.tempK < 933;
  ts.textContent = cold ? `${fmtPower(r.flux)}/m² · below aluminium melting (933 K)` : `${fmtPower(r.flux)}/m² in the spot`;
  ts.classList.toggle('flag', cold);
  $('r-thrust').textContent = fmtForce(r.thrust);
  $('r-thrust-sub').textContent = `Cm ${K.cm} µN/W · key uncertainty`;
  $('r-dv').textContent = num(r.dv, 1) + ' m/s';
  $('r-dv-sub').textContent = `perigee to ${K.perigeeKm} km`;
  $('r-time').textContent = fmtTime(r.time);
  $('r-time-sub').textContent = `${num(K.duty * 100)}% duty cycle`;
  $('r-need').textContent = r.mirrorsForDeadline ? num(r.mirrorsForDeadline) : '—';
  $('r-capex').textContent = fmtMoney(r.capex);
  $('r-capex-sub').textContent = `${fmtMoney(r.capexToday)} at today's launch cost`;
  $('r-need-sub').textContent = `to finish in ${inp.deadlineDays} days`;
}
function refreshAll() { refreshCalc(); refreshTargetPlan(); }
$('inputs').addEventListener('input', refreshAll);
document.querySelectorAll('.presets button').forEach((b) => b.addEventListener('click', () => {
  const [m, s, h] = b.dataset.preset.split(',');
  $('i-mass').value = m; $('i-size').value = s; $('i-alt').value = h; refreshAll();
}));

// ---------- assumptions drawer ----------
function buildDrawer() {
  $('assume-list').innerHTML = PH.ASSUMPTIONS.map((a) =>
    `<label${a.uncertain ? ' class="key"' : ''}>${a.label}<input type="number" step="any" data-key="${a.key}" value="${K[a.key]}"><span class="unit">${a.unit}</span></label>`).join('');
}
$('assume-list').addEventListener('input', (e) => {
  const k = e.target.dataset.key, v = parseFloat(e.target.value);
  if (k && isFinite(v)) { K[k] = v; refreshAll(); }
});
$('btn-assume').addEventListener('click', () => $('drawer').classList.toggle('open'));
$('btn-close').addEventListener('click', () => $('drawer').classList.remove('open'));
$('btn-reset').addEventListener('click', () => { K = PH.defaults(); buildDrawer(); refreshAll(); });

// ---------- loop ----------
function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== Math.floor(w * renderer.getPixelRatio()) || canvas.height !== Math.floor(h * renderer.getPixelRatio())) {
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
  }
}
let last = performance.now();
function frame(now) {
  const raw = (now - last) / 1000, dt = Math.min(raw, 0.1); last = now;
  resize();
  simMs += dt * warp * 1000;
  earth.rotation.y = sat.gstime(new Date(simMs));
  propagateAll();
  stepMission(Math.min(raw, 0.5), dt * warp);
  if (selected && selected.alive) {
    ring.position.copy(selected.pos);
    if (!mission && now - lastOrbitDraw > 1500) { drawSgp4Orbit(selected); lastOrbitDraw = now; }
  }
  $('clock').textContent = new Date(simMs).toISOString().slice(0, 19).replace('T', ' ') + ' UTC';
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

async function init() {
  buildDrawer(); refreshCalc();
  await Promise.all(GROUPS.map(loadGroup));
  buildPoints(); renderList();
  const d = new Date((latestEpochJd - 2440587.5) * 86400000);
  $('snapshot').textContent = 'CelesTrak TLE snapshot · ' + d.toISOString().slice(0, 10);
  window.__app = { objects, camera, canvas, select, startMission, totals, get mission() { return mission; }, get selected() { return selected; } };
  requestAnimationFrame(frame);
}
init();
