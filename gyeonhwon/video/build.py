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
# speed "fit": 원본 전체를 슬라이드 길이에 맞춰 배속 재생. None: 1배속(짧으면 반복).
SLIDE_VIDEOS = {
    4: [("assets/kintex-loop.mp4", 1178, 225, 342, 280, None)],
    5: [("assets/gameplay.mp4", 160, 108, 1280, 720, None)],
    6: [("assets/gameplay-fishing.mp4", 80, 230, 830, 467, None),
        ("assets/kintex-loop.mp4", 960, 230, 560, 467, None)],
}
MIN_DUR = {5: 25.0}  # 플레이 영상은 최소 25초 보여 줌

# 단계 강조: 이 단어로 시작하는 자막 줄이 나올 때 덱의 data-step 카드가 차례로 떠오른다
STEPS = {3: ["첫째", "둘째", "셋째"]}
STEP_ANIM, STEP_FRAMES = 0.45, 9  # 강조 전환 길이(초), 전환 중간 프레임 수

# 녹화용 사본에서 ?lv=1:0.5,2:1 처럼 카드별 강조 정도(0~1)를 고정한다
REC_JS = """<script>(function(){
const q=new URLSearchParams(location.search).get('lv'); if(!q) return;
const els=document.querySelector('.slide.active').querySelectorAll('[data-step]');
els.forEach(e=>{e.style.transition='none';e.style.setProperty('--lv','0');});
q.split(',').forEach(kv=>{const [k,v]=kv.split(':');
  els.forEach(e=>{if(e.dataset.step===k)e.style.setProperty('--lv',v);});});
})();</script>"""

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


def step_states(n, cues, dur, rec):
    """배경 이미지 목록 [(png, 길이)] — 단계 강조가 있으면 전환 프레임까지 캡처."""
    def capture(levels, name):
        png = BUILD / f"slide{n}_{name}.png"
        q = ",".join(f"{k}:{v:.3f}" for k, v in levels.items())
        shot(f"file://{rec}?lv={q}#{n}", png)
        return png

    if n not in STEPS:
        png = BUILD / f"slide{n}.png"
        shot(f"file://{rec}#{n}", png)
        return [(png, dur)]
    starts = [next(a for text, a, _ in cues if text.startswith(w)) for w in STEPS[n]]
    seq, t, prev = [], 0.0, 0
    for k, start in enumerate(starts, 1):
        seq.append((capture({}, "0") if prev == 0 else seq[-1][0], start - t))
        dt = STEP_ANIM / STEP_FRAMES
        for i in range(1, STEP_FRAMES + 1):
            p = i / STEP_FRAMES; p = p * p * (3 - 2 * p)  # ease in-out
            lv = {k: p} if prev == 0 else {prev: 1 - p, k: p}
            seq.append((capture(lv, f"{k}_{i}"), dt))
        t, prev = start + STEP_ANIM, k
    seq.append((seq[-1][0], dur - t))
    return [(png, d) for png, d in seq if d > 0]


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def main():
    BUILD.mkdir(exist_ok=True)
    slides = parse_script()

    # 슬라이드 배경은 UI·영상을 숨긴 임시 사본으로 캡처
    rec = DECK / ".record.html"
    rec.write_text((DECK / "index.html").read_text(encoding="utf-8")
                   .replace("</head>", HIDE_UI + "</head>", 1)
                   .replace("</body>", REC_JS + "</body>", 1), encoding="utf-8")
    sub_page = BUILD / "sub.html"
    sub_page.write_text(SUB_HTML, encoding="utf-8")
    try:
        build(slides, rec, sub_page)
    finally:
        rec.unlink()


def build(slides, rec, sub_page):

    # 2) 슬라이드별 구간 영상
    srt, offset, segs = [], 0.0, []
    for n, lines in slides.items():
        audio = HERE / "audio" / f"s{n}.m4a"
        adur = duration(audio)
        dur = max(LEAD + adur + TAIL, MIN_DUR.get(n, 0))
        cues = cue_times(lines, LEAD, adur)

        bg = BUILD / f"bg{n}.txt"
        seq = step_states(n, cues, dur, rec)
        bg.write_text("ffconcat version 1.0\n" + "".join(f"file '{p}'\nduration {d:.4f}\n" for p, d in seq)
                      + f"file '{seq[-1][0]}'\n", encoding="utf-8")
        inputs = ["-f", "concat", "-safe", "0", "-i", str(bg)]
        filters, last, idx = [f"[0:v]fps={FPS},scale={W}:{H},setsar=1[bg]"], "bg", 1
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
