# Space Janitor

**We take out the space trash.** A swarm of small, cheap mirror satellites that focuses sunlight on
one piece of orbital debris until it vaporizes, slows down, and burns up in the atmosphere.

Built at **c0mpiled-18 · YC Startup School Hackathon, Taipei** (Nov 11, 2026) for the YC Request
for Startups topic **"Startups in a World of Abundant Space Access"**.

- **Orbit simulator + pricing calculator:** [`app/`](app/) (real debris orbits from CelesTrak TLEs; pick a target, clean it, see the price)
- **Film (90 s, all 3D):** [`video/space-janitor-90s.mp4`](video/space-janitor-90s.mp4)
- **Pitch script (90 s):** [`SCRIPT.md`](SCRIPT.md)

## Why now

Launch is about to get 100x cheaper. That helps Space Janitor twice:

1. **More demand.** More launches mean more dead satellites, spent stages and fragments. There are
   already about 130 million pieces of debris in orbit, and every collision makes more.
2. **Lower cost.** Our infrastructure is itself mass in orbit. One cheap launch carries hundreds of
   mirrors, and the energy source (the Sun) is free and never runs out.

Nobody wants to be the janitor, on Earth or in orbit. SpaceX and NASA would rather launch things.
We clean up after them.

## How it works

| | |
|---|---|
| **Mirrors, not lasers** | Each satellite is a flat mirror with a small bus. No fuel is spent on the target and there is no high-power laser to build, launch or license. |
| **Swarm focus** | 100 one-square-meter mirrors collect 136 kW (a hundred suns' worth) and put about 122 kW on a 1.9 m spot from 100 m away. That is near 930 K; about 400 mirrors reach 1,300 K. |
| **Ablation de-orbit** | The heated surface vaporizes and pushes the object like a tiny rocket. Aimed against the orbit, it lowers the perigee until drag takes over. |
| **Subscription** | Low Earth orbit has to be cleaned on a schedule. Mega-constellation operators (Starlink-scale), insurers and space agencies pay per shell kept clean. |

The film also shows the swarm almost cooking a brand-new rocket and "accidentally" removing a
competitor's satellite. Those parts are jokes.

## Try it

```bash
python3 -m http.server 8000   # from the repo root
# open http://localhost:8000/app/
```

- **Simulator:** 2,678 real debris objects from the 2009 Iridium 33 / Kosmos 2251 collision and the
  Fengyun-1C breakup, propagated with SGP4. Pick one, press "Clean it", and watch its perigee drop
  until it burns up.
- **Calculator:** mass, size and altitude in; mirrors, time and price per removal out. Every
  assumption is editable, and results that look bad for us are shown, not hidden. Details and a
  sanity table are in [`app/README.md`](app/README.md).

## How the film was made

Everything on screen is generated: there is no stock footage and no hand-modeled asset.

- [`blender/build_scene.py`](blender/build_scene.py) builds the whole film as one Blender 5.3 scene
  in Python: the Sun, the Earth (NASA Blue Marble and night-lights textures, procedural clouds and
  atmosphere), 19 janitor satellites with eyes, rockets, debris, beams, explosions, in-world labels,
  18 camera shots and every keyframe.
- [`blender/render.sh`](blender/render.sh) renders the 2,160 frames (1080p, 24 fps, EEVEE) with
  parallel Blender processes.
- [`video/captions.py`](video/captions.py) draws the captions and logo cards.
- [`video/soundtrack.py`](video/soundtrack.py) synthesizes the music and sound effects with numpy.
- [`video/assemble.sh`](video/assemble.sh) joins frames, captions and audio into the mp4.
- The five seconds of simulator footage (1:03 to 1:08) are a screen recording of `app/`, kept as
  frames in `assets/sim/` and swapped in for the same frame numbers before assembly.

```bash
BLENDER=/path/to/Blender ./blender/render.sh   # frames -> out/frames
python3 video/captions.py
python3 video/soundtrack.py
video/assemble.sh                              # -> video/space-janitor-90s.mp4
```

Earth textures are NASA Visible Earth images (public domain). `assemble.sh` expects an ffmpeg
binary at `video/bin/ffmpeg`.
