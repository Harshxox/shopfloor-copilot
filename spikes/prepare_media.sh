#!/usr/bin/env bash
# Converts any phone recording into what the APIs accept.
#   video -> H.264 MP4, 720p, 15 fps, small file (for Spark + SAM as base64)
#   audio -> WAV mono 16-bit PCM 16 kHz (for Muse Voice Transcribe)
# Usage: bash spikes/prepare_media.sh <input_video> <name>
#   e.g. bash spikes/prepare_media.sh ~/Downloads/VID_2026.mp4 expert
set -euo pipefail
IN="$1"; NAME="${2:-expert}"
OUT_DIR="$(dirname "$0")/media"; mkdir -p "$OUT_DIR"

ffmpeg -y -i "$IN" -vf "scale=-2:720,fps=15" -c:v libx264 -preset veryfast -crf 28 \
  -c:a aac -b:a 64k -movflags +faststart "$OUT_DIR/$NAME.mp4"

ffmpeg -y -i "$IN" -vn -ac 1 -ar 16000 -sample_fmt s16 "$OUT_DIR/$NAME.wav"

ls -lh "$OUT_DIR/$NAME.mp4" "$OUT_DIR/$NAME.wav"
