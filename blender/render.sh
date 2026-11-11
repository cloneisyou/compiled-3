#!/bin/zsh
# Build the scene, then render all 2160 frames with N parallel Blender processes.
cd "$(dirname "$0")/.."
BL=${BLENDER:-$HOME/Desktop/dev/tools/Blender.app/Contents/MacOS/Blender}
N=${N:-4}; TOTAL=2160
"$BL" -b -P blender/build_scene.py > out/build.log 2>&1 || exit 1
mkdir -p out/frames
for i in $(seq 0 $((N-1))); do
  s=$((i*TOTAL/N+1)); e=$(((i+1)*TOTAL/N))
  "$BL" -b blender/space_janitor.blend -o "$PWD/out/frames/f_####" -s $s -e $e -a > out/render_$i.log 2>&1 &
done
wait
ls out/frames | wc -l
