#!/usr/bin/env bash
# Generates tests/fixtures/sample_10s.mp4 — a 10s video with 3 hard scene cuts
# at t=3s (red→white) and t=6s (white→blue).
#
# Why these specific colors: ffmpeg's scene filter compares luma histograms.
# Red and green both have YUV luma Y≈81, so a red→green transition shows
# zero scene change to the filter at threshold 0.30. Red, white, and blue
# have luma Y≈81/235/41 — gaps of ~154 and ~194 — both producing a scene
# score of 1.0 at the boundary. Verified with:
#     ffmpeg -i sample_10s.mp4 -vf "select='gt(scene,0.30)',showinfo" -f null -
#
# `-threads 1` makes the libx264 encode bit-exact across machines so the
# LFS pointer (sha256 OID) doesn't drift when contributors regenerate
# the fixture on different CPUs.
#
# `-g 24` forces a keyframe every second at 24 fps, guaranteeing keyframes
# at t=3 and t=6 so the scene filter's frame-comparison is well-aligned.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

ffmpeg -y -loglevel error \
  -f lavfi -i "color=red:size=320x240:duration=3:rate=24" \
  -f lavfi -i "color=white:size=320x240:duration=3:rate=24" \
  -f lavfi -i "color=blue:size=320x240:duration=4:rate=24" \
  -filter_complex "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]" \
  -map "[v]" -c:v libx264 -pix_fmt yuv420p -g 24 -threads 1 \
  sample_10s.mp4

echo "Built: $DIR/sample_10s.mp4"
