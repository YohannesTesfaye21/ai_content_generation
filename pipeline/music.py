"""Music stage: prepare outputs/music/score.wav for assembly.

music.source = "file":        use the ACE-Step track chosen on Kaggle (kaggle/ace_step.py), path in music.file
music.source = "placeholder": synthesise a soft drone pad in FFmpeg (temp track for the radio cut)
"""
import sys

from common import OUT, ROOT, cached, ensure_dirs, input_hash, load_storyboard, mark, run, shot_durations

sb = load_storyboard()
ensure_dirs("music")
m = sb["music"]
total = sum(shot_durations(sb).values()) + sb.get("timing", {}).get("end_card_s", 3) + 2
dst = OUT / "music" / "score.wav"

if m["source"] == "file":
    src = ROOT / m.get("file", "outputs/music/ace_step_choice.wav")
    if not src.exists():
        sys.exit(f"music.file {src} not found - download your chosen ACE-Step track there")
    h = input_hash("music-file-v1", src.name, src.stat().st_size, src.stat().st_mtime)
    if cached(dst, h):
        print("music: cache hit")
        raise SystemExit
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ar", "48000", "-ac", "2", str(dst)])
    mark(dst, h)
    print(f"music: using {src.name}")
else:
    h = input_hash("music-placeholder-v1", round(total))
    if cached(dst, h):
        print("music: cache hit")
        raise SystemExit
    # Am - F - C - G roots, 8 s each, root + fifth + octave, with a slow swell that hides chord changes.
    c = "floor(mod(t,32)/8)"
    r = f"(110*eq({c},0)+87.31*eq({c},1)+130.81*eq({c},2)+98*eq({c},3))"
    expr = (f"0.18*(0.5-0.5*cos(2*PI*mod(t,8)/8))*(sin(2*PI*{r}*t)+0.5*sin(2*PI*{r}*1.5*t)"
            f"+0.35*sin(2*PI*{r}*2*t)+0.15*sin(2*PI*{r}*3*t))")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"aevalsrc='{expr}':s=48000:d={total:.1f}",
         "-af", "lowpass=f=1800,aecho=0.8:0.7:120|260:0.35|0.25,afade=t=in:d=2,pan=stereo|c0=c0|c1=c0",
         str(dst)])
    mark(dst, h)
    print(f"music: placeholder pad, {total:.0f}s (replace with ACE-Step - see kaggle/ace_step.py)")
