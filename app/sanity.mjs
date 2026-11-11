// node app/sanity.mjs — prints the sanity table used in app/README.md
import * as PH from './physics.js';
const k = PH.defaults();
const cases = [
  ['1 kg fragment, 0.15 m, 800 km', { mass: 1, size: 0.15, altKm: 800 }],
  ['100 kg, 1 m, 780 km', { mass: 100, size: 1, altKm: 780 }],
  ['1,400 kg dead satellite, 3 m, 800 km', { mass: 1400, size: 3, altKm: 800 }],
];
const e0 = PH.engagement({ N: 100, area: 1, size: 3 }, k);
console.log(`N=100, A=1 m²: incident ${(e0.pIncident / 1e3).toFixed(1)} kW, delivered ${(e0.pDelivered / 1e3).toFixed(1)} kW, spot ${e0.spotD.toFixed(3)} m, flux ${(e0.flux / 1e3).toFixed(1)} kW/m², T ${e0.tempK.toFixed(0)} K`);
console.log(`T at 136 kW/m² flux: ${Math.pow(0.9 * 136100 / (0.9 * PH.SIGMA), 0.25).toFixed(0)} K`);
console.log('| Case | Intercepted | Thrust | Δv | Time | Mirrors for 30 d | Price @ $100/kg | Price @ $2,500/kg |');
console.log('|---|---|---|---|---|---|---|---|');
for (const [name, c] of cases) {
  const r = PH.removal({ ...c, N: 100, area: 1, deadlineDays: 30 }, k);
  console.log(`| ${name} | ${(r.pIntercepted / 1e3).toFixed(2)} kW | ${(r.thrust * 1e3).toFixed(1)} mN | ${r.dv.toFixed(1)} m/s | ${(r.time / 86400).toFixed(2)} d | ${r.mirrorsForDeadline} | $${Math.round(r.price).toLocaleString()} | $${Math.round(r.priceToday).toLocaleString()} |`);
}
