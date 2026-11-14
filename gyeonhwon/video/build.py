#!/usr/bin/env python3
"""견훤 덱 → 내레이션·자막 영상 합성.

입력: ../index.html(슬라이드), script.md(대본·자막), audio/sN.m4a(슬라이드별 음성)
출력: build/gyeonhwon.mp4, build/gyeonhwon.srt (+ 지정 시 복사본)

사용: python3 build.py [복사할_경로.mp4]
음성을 직접 녹음한 파일로 바꾸려면 audio/sN.m4a 를 덮어쓰고 다시 실행하면 된다.
"""
import re, shutil, subprocess, sys, urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
DECK = HERE.parent
BUILD = HERE / "build"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H, FPS = 1920, 1080, 30
S = W / 1600  # 덱 스테이지(1600x900) → 1080p 배율
LEAD, TAIL = 0.6, 1.0  # 슬라이드 시작 후 말 시작까지, 말 끝난 후 다음 장까지(초)

# 슬라이드 안 영상 위치(덱 좌표 left, top, width, height). speed: 재생 배속
# s5 플레이 영상은 74초 전체를 슬라이드 길이(min_dur)에 맞춰 빠르게 보여 준다.
SLIDE_VIDEOS = {
    4: [("assets/kintex-loop.mp4", 1178, 225, 342, 280, None)],
    5: [("assets/gameplay.mp4", 160, 108, 1280, 720, "fit")],
    6: [("assets/gameplay-fishing.mp4", 80, 230, 830, 467, None),
        ("assets/kintex-loop.mp4", 960, 230, 560, 467, None)],
}
MIN_DUR = {5: 46.0}

HIDE_UI = ("<style>#controls,#help,#notesPanel{display:none!important}"
           "video{visibility:hidden!important}</style>")

SUB_HTML = """<!doctype html><meta charset="utf-8"><style>
html,body{margin:0;width:1920px;height:1080px;background:transparent;overflow:hidden}
div{position:absolute;left:50%;bottom:44px;transform:translateX(-50%);max-width:1600px;
padding:12px 30px;border-radius:10px;background:rgba(0,0,0,.72);color:#fff;
font:600 42px/1.35 'Apple SD Gothic Neo',sans-serif;text-align:center;word-break:keep-all}
</style><div id=t></div><script>
document.getElementById('t').textContent=decodeURIComponent(location.hash.slice(1));
</script>"""


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout)


def shot(url, out, transparent=False):
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           f"--window-size={W},{H}", "--virtual-time-budget=2500", f"--screenshot={out}", url]
    if transparent:
        cmd.insert(3, "--default-background-color=00000000")
    run(cmd)


def parse_script():
    slides, cur = {}, None
    for line in (HERE / "script.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## s(\d+)", line)
        if m:
            cur = int(m.group(1)); slides[cur] = []
        elif line.startswith("#"):
            cur = None
        elif cur and line.strip():
            slides[cur].append(line.strip())
    return slides


def cue_times(lines, start, total):
    """문장 길이(글자 수) 비율로 음성 구간을 나눠 자막 시간 계산."""
    weights = [len(l.replace(" ", "")) + 3 for l in lines]
    t, cues = start, []
    for l, w in zip(lines, weights):
        d = total * w / sum(weights)
        cues.append((l, t, t + d)); t += d
    return cues


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def main():
    BUILD.mkdir(exist_ok=True)
    slides = parse_script()

    # 1) 슬라이드 배경 캡처 (UI·영상 숨긴 임시 사본 사용)
    rec = DECK / ".record.html"
    rec.write_text((DECK / "index.html").read_text(encoding="utf-8")
                   .replace("</head>", HIDE_UI + "</head>", 1), encoding="utf-8")
    sub_page = BUILD / "sub.html"
    sub_page.write_text(SUB_HTML, encoding="utf-8")
    try:
        for n in slides:
            shot(f"file://{rec}#{n}", BUILD / f"slide{n}.png")
    finally:
        rec.unlink()

    # 2) 슬라이드별 구간 영상
    srt, offset, segs = [], 0.0, []
    for n, lines in slides.items():
        audio = HERE / "audio" / f"s{n}.m4a"
        adur = duration(audio)
        dur = max(LEAD + adur + TAIL, MIN_DUR.get(n, 0))
        cues = cue_times(lines, LEAD, adur)

        inputs = ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur}", "-i", str(BUILD / f"slide{n}.png")]
        filters, last, idx = [], "0:v", 1
        for src, x, y, w, h, speed in SLIDE_VIDEOS.get(n, []):
            src = DECK / src
            sw, sh = round(w * S) // 2 * 2, round(h * S) // 2 * 2
            if speed == "fit":
                pts = f"setpts=PTS*{dur / duration(src):.4f},"
                inputs += ["-i", str(src)]
            else:
                pts = ""
                inputs += ["-stream_loop", "-1", "-i", str(src)]
            filters.append(f"[{idx}:v]{pts}fps={FPS},scale={sw}:{sh},setsar=1[v{idx}]")
            filters.append(f"[{last}][v{idx}]overlay={round(x * S)}:{round(y * S)}:shortest=0:eof_action=repeat[o{idx}]")
            last, idx = f"o{idx}", idx + 1
        for k, (text, a, b) in enumerate(cues):
            png = BUILD / f"sub{n}_{k}.png"
            shot(f"file://{sub_page}#{urllib.parse.quote(text)}", png, transparent=True)
            inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur}", "-i", str(png)]
            filters.append(f"[{last}][{idx}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[o{idx}]")
            last, idx = f"o{idx}", idx + 1
            srt.append((offset + a, offset + b, text))
        inputs += ["-i", str(audio)]
        filters.append(f"[{idx}:a]adelay={int(LEAD * 1000)}:all=1,apad[a]")
        filters.append(f"[{last}]format=yuv420p[vout]")

        seg = BUILD / f"seg{n}.mp4"
        run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters),
             "-map", "[vout]", "-map", "[a]", "-t", f"{dur}", "-r", str(FPS),
             "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", str(seg)])
        segs.append(seg); offset += dur
        print(f"s{n}  {dur:5.1f}초  (음성 {adur:.1f}초, 자막 {len(cues)}줄)")

    # 3) 이어 붙이기 + 자막 파일
    lst = BUILD / "concat.txt"
    lst.write_text("".join(f"file '{s}'\n" for s in segs), encoding="utf-8")
    out = BUILD / "gyeonhwon.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", "-movflags", "+faststart", str(out)])
    (BUILD / "gyeonhwon.srt").write_text(
        "".join(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(srt, 1)),
        encoding="utf-8")
    print(f"합계  {offset:5.1f}초 → {out}")

    if len(sys.argv) > 1:
        dst = Path(sys.argv[1]).expanduser()
        shutil.copy(out, dst); shutil.copy(BUILD / "gyeonhwon.srt", dst.with_suffix(".srt"))
        print(f"복사 → {dst}")


if __name__ == "__main__":
    main()
