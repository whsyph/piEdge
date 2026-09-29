#!/usr/bin/env bash
set -Eeuo pipefail

# Validate files before copying them to a Pi 5 signage playlist.
# Usage: ./validate_media.sh path/to/video.mp4 [more files...]

if [[ "$#" -eq 0 ]]; then
  echo "Usage: $0 VIDEO [VIDEO ...]" >&2
  exit 2
fi

command -v ffprobe >/dev/null || { echo "ffprobe tidak ditemukan" >&2; exit 1; }
failed=0
for file in "$@"; do
  if [[ ! -f "$file" ]]; then
    echo "MISSING  $file"
    failed=1
    continue
  fi
  result="$(ffprobe -v error -select_streams v:0 \
    -show_entries stream=codec_name,width,height,avg_frame_rate,pix_fmt \
    -of default=noprint_wrappers=1:nokey=0 "$file" 2>&1)" || {
      echo "INVALID  $file"
      echo "$result"
      failed=1
      continue
    }
  echo "OK      $file"
  echo "$result" | sed 's/^/        /'
done
exit "$failed"
