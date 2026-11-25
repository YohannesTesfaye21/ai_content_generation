"""Moving-shot stage: turn each keyframe into a clip, in both aspect ratios.

Two sources, chosen per shot:
  1. outputs/wan/<id>.mp4  - a Wan 2.2 image-to-video clip made on Kaggle (kaggle/wan_i2v.py)
  2. otherwise             - a Ken Burns pan/zoom over the keyframe, rendered locally with FFmpeg

Each clip is stretched to the shot's final length (narration sets the pace).
Cached by hash(source file, duration, camera, aspect).
"""
import sys

from common import OUT, cached, ensure_dirs, input_hash, load_storyboard, mark, run, shot_durations

FPS = 24
ASPECTS = {"16x9": (1280, 720), "9x16": (720, 1280)}

sb = load_storyboard()
ensure_dirs("shots/16x9", "shots/9x16", "wan")
durations = shot_durations(sb)
only = set(sys.argv[1:])


def crop_for(aspect):
    # Keyframes are square and composed centre-out, so both crops keep the subject.
    return "crop=iw:iw*9/16" if aspect == "16x9" else "crop=ih*9/16:ih"


def ken_burns(src, dst, dur, cam, aspect):
    w, h = ASPECTS[aspect]
    n = int(round(dur * FPS))
    zoom, pan = cam.get("zoom", "in"), cam.get("pan", "none")
    z = {"in": f"1+0.14*on/{n}", "out": f"1.14-0.14*on/{n}", "none": "1.1"}[zoom]
    cx, cy = "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"
    x = {"left": f"(iw-iw/zoom)*(1-on/{n})", "right": f"(iw-iw/zoom)*on/{n}"}.get(pan, cx)
    y = {"up": f"(ih-ih/zoom)*(1-on/{n})", "down": f"(ih-ih/zoom)*on/{n}"}.get(pan, cy)
    vf = (f"{crop_for(aspect)},scale={w * 2}:{h * 2}:flags=lanczos,"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={w}x{h}:fps={FPS},format=yuv420p")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", vf, "-frames:v", str(n),
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", str(FPS), str(dst)])


def from_wan(src, dst, dur, aspect):
    """Fit a Wan clip to the aspect, trim its weak first 0.3 s, hold the last frame if too short."""
    w, h = ASPECTS[aspect]
    vf = (f"trim=start=0.3,setpts=PTS-STARTPTS,fps={FPS},"
          f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
          f"tpad=stop_mode=clone:stop_duration={dur},trim=duration={dur},format=yuv420p")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", vf, "-an",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", str(FPS), str(dst)])


for s in sb["shots"]:
    if only and s["id"] not in only:
        continue
    key = OUT / "keyframes" / f"{s['id']}.jpg"
    wan = OUT / "wan" / f"{s['id']}.mp4"
    src = wan if wan.exists() else key
    if not src.exists():
        sys.exit(f"{s['id']}: no keyframe yet - run `make keyframes`")
    st = src.stat()
    for aspect in ASPECTS:
        dst = OUT / "shots" / aspect / f"{s['id']}.mp4"
        h = input_hash("shot-v1", src.name, st.st_size, st.st_mtime, durations[s["id"]], s["camera"], aspect)
        if cached(dst, h):
            print(f"  {s['id']} {aspect}: cache hit")
            continue
        if src == wan:
            from_wan(src, dst, durations[s["id"]], aspect)
            how = "wan 2.2 clip"
        else:
            ken_burns(src, dst, durations[s["id"]], s["camera"], aspect)
            how = "ken burns"
        mark(dst, h)
        print(f"  {s['id']} {aspect}: {how}, {durations[s['id']]:.1f}s")
print("shots: done")
