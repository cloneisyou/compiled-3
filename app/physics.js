// Space Janitor — shared physics for the simulator and the pricing calculator.
// Units: SI unless the name says otherwise (Km, Days).
export const MU = 3.986004418e14;      // m^3/s^2
export const RE_KM = 6378.137;         // km (equatorial, same as SGP4/WGS-84)
export const SIGMA = 5.670374e-8;      // W/m^2/K^4
export const DAY = 86400;

export const ASSUMPTIONS = [
  { key: 'solar',        label: 'Solar constant',              unit: 'W/m²',  value: 1361 },
  { key: 'reflect',      label: 'Mirror reflectivity',         unit: '',      value: 0.9 },
  { key: 'sunAngle',     label: 'Sun angular diameter',        unit: 'rad',   value: 0.00925 },
  { key: 'standoff',     label: 'Standoff distance',           unit: 'm',     value: 100 },
  { key: 'absorb',       label: 'Target absorptivity',         unit: '',      value: 0.9 },
  { key: 'emiss',        label: 'Target emissivity',           unit: '',      value: 0.9 },
  { key: 'cm',           label: 'Momentum coupling Cm',        unit: 'µN/W',  value: 10, uncertain: true },
  { key: 'duty',         label: 'Duty cycle',                  unit: '',      value: 0.25 },
  { key: 'perigeeKm',    label: 'Burn-up perigee',             unit: 'km',    value: 120 },
  { key: 'unitCost',     label: 'Mirror satellite unit cost',  unit: '$',     value: 50000 },
  { key: 'mirrorMass',   label: 'Mirror satellite mass',       unit: 'kg',    value: 15 },
  { key: 'launch',       label: 'Launch cost (cheap launch)',  unit: '$/kg',  value: 100 },
  { key: 'launchToday',  label: 'Launch cost (today)',         unit: '$/kg',  value: 2500 },
  { key: 'lifeYears',    label: 'Swarm lifetime',              unit: 'yr',    value: 5 },
  { key: 'retargetDays', label: 'Retarget time per object',    unit: 'days',  value: 0 },
  { key: 'margin',       label: 'Margin',                      unit: '',      value: 0.6 },
];

export function defaults() {
  const k = {};
  for (const a of ASSUMPTIONS) k[a.key] = a.value;
  return k;
}

/** Beam on target: power, spot, temperature, thrust. size = target width/diameter (m). */
export function engagement({ N, area, size }, k) {
  const pIncident = N * area * k.solar;                // sunlight collected by the swarm
  const pDelivered = pIncident * k.reflect;            // leaves the mirrors toward the target
  const mirrorWidth = Math.sqrt(area);
  const spotD = k.standoff * k.sunAngle + mirrorWidth; // flat mirror: sun-disc divergence + aperture
  const spotArea = Math.PI * spotD * spotD / 4;
  const objArea = Math.PI * size * size / 4;           // target cross-section (disc)
  const frac = Math.min(1, objArea / spotArea);        // share of the spot the target intercepts
  const pIntercepted = pDelivered * frac;
  const pAbsorbed = pIntercepted * k.absorb;
  const flux = pDelivered / spotArea;                  // W/m² in the spot (all mirrors overlapped)
  const tempK = Math.pow(k.absorb * flux / (k.emiss * SIGMA), 0.25);
  const thrust = k.cm * 1e-6 * pAbsorbed;              // N
  return { pIncident, pDelivered, spotD, spotArea, objArea, frac, pIntercepted, pAbsorbed, flux, tempK, thrust };
}

/** Δv (m/s) of one retrograde burn at apogee that lowers perigee to the burn-up altitude.
 *  For a circular orbit this is v_c·(1 − sqrt(2·r_p/(r_a+r_p))). Radii in km. */
export function deltaV(raKm, rpKm, k) {
  const ra = raKm * 1e3, rp = rpKm * 1e3, rt = (RE_KM + k.perigeeKm) * 1e3;
  if (rp <= rt) return 0;
  const vNow = Math.sqrt(MU * 2 * rp / (ra * (ra + rp)));
  const vTarget = Math.sqrt(MU * 2 * rt / (ra * (ra + rt)));
  return vNow - vTarget;
}

/** Perigee radius (km) after dv (m/s) of retrograde thrust has been applied at apogee. */
export function perigeeAfter(raKm, rpKm, dv) {
  const ra = raKm * 1e3, rp = rpKm * 1e3;
  const v = Math.sqrt(MU * 2 * rp / (ra * (ra + rp))) - dv;
  const a = 1 / (2 / ra - v * v / MU);
  return (2 * a - ra) / 1e3;
}

export function capex(N, launchPerKg, k) {
  return N * k.unitCost + launchPerKg * N * k.mirrorMass;
}

/** Full removal case. Give altKm (circular) or raKm/rpKm (radii from Earth's centre). */
export function removal(input, k) {
  const { mass, size, N, area } = input;
  const raKm = input.raKm ?? RE_KM + input.altKm;
  const rpKm = input.rpKm ?? RE_KM + input.altKm;
  const e = engagement({ N, area, size }, k);
  const dv = deltaV(raKm, rpKm, k);
  const time = mass * dv / (e.thrust * k.duty);         // s
  const cycle = time + k.retargetDays * DAY;
  const removals = k.lifeYears * 365.25 * DAY / cycle;  // per swarm lifetime
  const price = (launchPerKg) => capex(N, launchPerKg, k) / removals * (1 + k.margin);
  let mirrorsForDeadline = null;
  if (input.deadlineDays > 0) {
    const fReq = mass * dv / (k.duty * input.deadlineDays * DAY);
    const perMirror = k.cm * 1e-6 * k.absorb * k.reflect * k.solar * area * e.frac;
    mirrorsForDeadline = Math.max(1, Math.ceil(fReq / perMirror));
  }
  return { ...e, raKm, rpKm, dv, time, removals, mirrorsForDeadline,
    capex: capex(N, k.launch, k), capexToday: capex(N, k.launchToday, k),
    price: price(k.launch), priceToday: price(k.launchToday) };
}
