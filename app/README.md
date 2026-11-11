# Space Janitor — orbit simulator + pricing calculator

Static page, no build step, works offline (three.js r160 and satellite.js 5.0.0 are vendored in `vendor/`).

## Run

```
cd <repo root>
python3 -m http.server 8000
# open http://localhost:8000/app/
```

Sanity table: `node app/sanity.mjs`.

## What it does

- **Simulator.** Real TLEs propagated with SGP4 (satellite.js), drawn in the inertial frame around a rotating Earth.
  Click a point or pick from the list to see apogee, perigee, period and the removal plan. "Clean it" runs the de-orbit;
  when perigee reaches the burn-up altitude the object flashes, disappears, and the header counters increase.
- **Calculator.** Same physics module (`physics.js`). Every constant is editable in the Assumptions drawer and
  changes both the calculator and the simulator. Selecting a target copies its mass, size and mean altitude into the calculator;
  the simulator uses the calculator's mirror count and mirror area.

## Data

`data/*.tle` is a CelesTrak snapshot downloaded 2026-11-11 (latest element epoch 2026-11-10/11):
`cosmos-2251-debris`, `iridium-33-debris`, `fengyun-1c-debris`. 2,678 objects load (those with perigee under 160 km are skipped).
The simulation clock starts at the browser's current time, so accuracy degrades as the snapshot ages.

## Model and assumptions

| Quantity | Formula | Default |
|---|---|---|
| Power | P = N·A·S·ρ | S = 1361 W/m², ρ = 0.9 |
| Spot diameter | standoff × 0.00925 + √A | standoff 100 m → 1.92 m for a 1 m² mirror |
| Intercepted power | P × min(1, target area / spot area), target area = π·size²/4 | |
| Equilibrium temperature | T = (α·flux / (ε·σ))^¼, flux = P / spot area | α = ε = 0.9 |
| Thrust | F = Cm · P_absorbed | **Cm = 10 µN/W — the key uncertain assumption** |
| Δv | burn at apogee that lowers perigee to 120 km; for a circular orbit v_c·(1 − √(2·r_p/(r_a+r_p))) | 120 km |
| Time | m·Δv / (F·duty) | duty 0.25 |
| Price | (unit cost × N + launch $/kg × N × 15 kg) ÷ (lifetime ÷ time per object) × (1 + margin) | $50k, $100/kg (today $2,500/kg), 5 yr, 60% |

Other assumptions:

- **De-orbit phase in the simulator is analytic, not numerically integrated.** At "Clean it" the osculating two-body orbit is taken
  from the SGP4 state. Apogee stays fixed; perigee follows `perigeeAfter(Δv applied)` with Δv applied growing linearly over the
  calculator's de-orbit time. The object then moves on that shrinking Kepler ellipse. No drag, no J2 in this phase.
- The mission clock is accelerated so every de-orbit takes about 12 s on screen (the factor is shown); the orbit display keeps the selected time warp.
- TLEs carry no mass or size. Fragments get a deterministic log-uniform 0.1–20 kg estimate from the NORAD ID and size = 0.15·m^⅓ m.
  Parent bodies: Cosmos 2251 900 kg / 2.0 m, Iridium 33 560 kg / 1.8 m, Fengyun-1C 880 kg / 1.8 m. Labeled "est." in the UI.
- All mirrors overlap in one spot, each mirror is flat, pointing is perfect.
- "Margin 60%" is a markup on cost (price = cost × 1.6).
- Added constant: "Retarget time per object" (default 0 days, so travel between targets is free). Raising it changes small-fragment prices a lot.
- The swarm marker in the 3D view is drawn about 640 km ahead of the target so it is visible; the model uses the 100 m standoff.
- Earth radius 6378.137 km for altitudes.

## Sanity check (`node app/sanity.mjs`, N = 100, A = 1 m², defaults)

N = 100, A = 1 m²: 136.1 kW collected, 122.5 kW delivered, spot 1.925 m, flux 42.1 kW/m², **T = 928 K**.
(At 136 kW/m² the same formula gives 1,245 K.)

| Case | Intercepted | Thrust | Δv | Time | Mirrors for 30 d | Price @ $100/kg | Price @ $2,500/kg |
|---|---|---|---|---|---|---|---|
| 1 kg fragment, 0.15 m, 800 km | 0.74 kW | 6.7 mN | 187.6 m/s | 1.30 d | 5 | $5,855 | $9,948 |
| 100 kg, 1 m, 780 km | 33.06 kW | 297.5 mN | 182.6 m/s | 2.84 d | 10 | $12,818 | $21,779 |
| 1,400 kg dead satellite, 3 m, 800 km | 122.49 kW | 1102.4 mN | 187.6 m/s | 11.03 d | 37 | $49,771 | $84,562 |

## Results that look bad (shown, not hidden)

- **The default swarm does not reach vaporization temperature.** 100 one-square-metre flat mirrors at 100 m give 42 kW/m² and 928 K,
  below aluminium's melting point (933 K) and far below its boiling point. The calculator flags this in red. The thrust formula
  does not depend on temperature, so thrust, time and price are still computed. About 400 mirrors give 1,313 K; reaching real
  ablation needs a smaller spot (shorter standoff or focusing mirrors) or many more mirrors.
- A small fragment catches under 1% of the spot, so most of the power misses it.
- Price per removal does not depend on N in this model: cost grows with N and time shrinks with N.
- With Cm = 10 µN/W the 1.4 t satellite takes 11 days, not months. At Cm = 1 µN/W it takes 110 days and costs 10× more.

## Files

`index.html`, `style.css`, `main.js` (simulator + UI), `physics.js` (shared model), `sanity.mjs`, `data/`, `tex/earth_day.jpg` (2048 px copy), `vendor/`, `screenshots/`.
