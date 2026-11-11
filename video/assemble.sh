#!/bin/bash
# Assemble the final film: frames + caption overlays + soundtrack -> MP4.
#
#   video/assemble.sh                              # out/frames, 2160 frames -> video/space-janitor-90s.mp4
#   video/assemble.sh FRAMES_DIR FRAME_COUNT OUT   # overrides (for testing / partial renders)
#
# Env: FPS (24), CRF (17), PRESET (slow), AUDIO (out/audio/soundtrack.wav), CAPTIONS (out/captions)
# Captions that start after the end of a shortened film are skipped.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FFMPEG="$ROOT/video/bin/ffmpeg"
FRAMES="${1:-$ROOT/out/frames}"
COUNT="${2:-2160}"
OUT="${3:-$ROOT/video/space-janitor-90s.mp4}"
FPS="${FPS:-24}"
CRF="${CRF:-17}"
PRESET="${PRESET:-slow}"
AUDIO="${AUDIO:-$ROOT/out/audio/soundtrack.wav}"
CAPS="${CAPTIONS:-$ROOT/out/captions}"
FADE=0.25

[ -x "$FFMPEG" ] || { echo "missing $FFMPEG (copy ffmpeg-static binary there)"; exit 1; }
[ -f "$CAPS/captions.json" ] || /usr/bin/python3 "$ROOT/video/captions.py"
have=$(ls "$FRAMES" | grep -c '^f_[0-9]\{4\}\.jpg$' || true)
[ "$have" -ge "$COUNT" ] || { echo "only $have frames in $FRAMES, need $COUNT"; exit 1; }

DUR=$(/usr/bin/python3 -c "print(f'{$COUNT/$FPS:.6f}')")
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

# Build ffmpeg input args (one per line) and the filter graph from captions.json
/usr/bin/python3 - "$CAPS" "$DUR" "$FADE" "$FPS" "$WORK" <<'PY'
import json, sys, os
caps_dir, dur, fade, fps, work = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5]
caps = [c for c in json.load(open(os.path.join(caps_dir, "captions.json"))) if c["start"] < dur - 0.05]
args, fg = [], []
# JPEG frames are full-range BT.601 -> convert to limited-range BT.709
fg.append("[0:v]scale=in_range=full:in_color_matrix=bt601:out_range=tv:out_color_matrix=bt709,"
          "format=yuv420p,setsar=1[v0]")
for i, c in enumerate(caps, 1):
    s, e = c["start"], min(c["end"], dur)
    d = e - s
    f = min(fade, d / 2)
    args += ["-loop", "1", "-framerate", fps, "-t", f"{d:.4f}", "-i", os.path.join(caps_dir, c["file"])]
    fg.append(f"[{i}:v]format=rgba,fade=t=in:st=0:d={f}:alpha=1,fade=t=out:st={d - f:.4f}:d={f}:alpha=1,"
              f"scale=out_color_matrix=bt709:out_range=tv,format=yuva420p,setpts=PTS+{s}/TB[c{i}]")
    fg.append(f"[v{i-1}][c{i}]overlay=0:0:format=yuv420:eof_action=pass:"
              f"enable='between(t,{s},{e})'[v{i}]")
fg.append(f"[v{len(caps)}]format=yuv420p[vout]")
open(os.path.join(work, "inputs.txt"), "w").write("\n".join(args) + "\n")
open(os.path.join(work, "filter.txt"), "w").write(";\n".join(fg) + "\n")
open(os.path.join(work, "n.txt"), "w").write(str(len(caps) + 1))
PY

CAP_ARGS=()
while IFS= read -r line; do [ -n "$line" ] && CAP_ARGS+=("$line"); done < "$WORK/inputs.txt"
AIDX=$(cat "$WORK/n.txt")

if [ -f "$AUDIO" ]; then
  echo "audio: $AUDIO"
  AUDIO_ARGS=(-i "$AUDIO")
  AFILTER="[$AIDX:a]aresample=48000,apad,atrim=0:$DUR,asetpts=PTS-STARTPTS[aout]"
else
  echo "audio: none found at $AUDIO -> silent track"
  AUDIO_ARGS=(-f lavfi -t "$DUR" -i "anullsrc=channel_layout=stereo:sample_rate=48000")
  AFILTER="[$AIDX:a]atrim=0:$DUR[aout]"
fi
printf ';\n%s\n' "$AFILTER" >> "$WORK/filter.txt"

mkdir -p "$(dirname "$OUT")"
"$FFMPEG" -hide_banner -loglevel warning -stats -y \
  -framerate "$FPS" -start_number 1 -i "$FRAMES/f_%04d.jpg" \
  ${CAP_ARGS[@]+"${CAP_ARGS[@]}"} "${AUDIO_ARGS[@]}" \
  -filter_complex_script "$WORK/filter.txt" \
  -map "[vout]" -map "[aout]" \
  -frames:v "$COUNT" -t "$DUR" -r "$FPS" \
  -c:v libx264 -profile:v high -preset "$PRESET" -crf "$CRF" -pix_fmt yuv420p \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv \
  -c:a aac -b:a 256k -ar 48000 -ac 2 \
  -movflags +faststart "$OUT"

echo "wrote $OUT"
"$FFMPEG" -hide_banner -i "$OUT" 2>&1 | grep -E "Duration|Stream" || true
