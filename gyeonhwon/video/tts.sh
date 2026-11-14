#!/bin/bash
# script.md → audio/sN.m4a 가이드 TTS 생성 (맥 내장 say, 음성 Yuna)
# 사용: ./tts.sh [속도(분당 단어, 기본 190)]
cd "$(dirname "$0")"; RATE=${1:-190}; mkdir -p audio
awk '/^## s[0-9]+/{f="audio/"$2".txt"; printf "" > f; next} /^## /{f=""} f && NF{print $0 " [[slnc 350]]" >> f}' script.md
for t in audio/s*.txt; do
  n=$(basename "$t" .txt)
  say -v Yuna -r "$RATE" -f "$t" -o "audio/$n.aiff"
  ffmpeg -v error -y -i "audio/$n.aiff" -c:a aac -b:a 128k "audio/$n.m4a" && rm "audio/$n.aiff"
done
total=0
for f in audio/s*.m4a; do
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
  printf "%s  %5.1f초\n" "$(basename "$f" .m4a)" "$d"; total=$(echo "$total+$d" | bc)
done
printf "합계  %5.1f초\n" "$total"
