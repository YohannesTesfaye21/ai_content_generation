"""Assembly stage (FFmpeg, deterministic): the finished film, both aspect ratios.

  python assemble.py         -> outputs/film/the_film_16x9.mp4 and the_film_9x16.mp4
  python assemble.py radio   -> outputs/film/radio_cut.mp4 (narration + music over black)

Steps, all driven by storyboard.json:
  1. voice track: each narration line placed at its shot's start (+ lead), padded to the shot length
  2. music: score levelled, faded, ducked under the voice with sidechaincompress
  3. mix normalised to -14 LUFS / -1 dBTP with a two-pass loudnorm
  4. picture: shot clips + burned-in English subtitles (Pillow PNGs) + AI end card
  5. English .srt written alongside
"""
import json
import re
import sys

from cards import chunk_subtitle, end_card_png, subtitle_png
from common import OUT, ensure_dirs, load_storyboard, media_duration, run, shot_durations

FPS = 24
ASPECTS = {"16x9": (1280, 720), "9x16": (720, 1280)}
radio = "radio" in sys.argv[1:]

sb = load_storyboard()
ensure_dirs("film", "audio", "subs/16x9", "subs/9x16", "segments/16x9", "segments/9x16")
tm = sb.get("timing", {})
LEAD, END = tm.get("narration_lead_s", 0.4), tm.get("end_card_s", 3)
dur = shot_durations(sb)
shots = sb["shots"]
total = round(sum(dur.values()) + END, 2)
music_credit = ("ACE-Step 1.5 (open weights)" if sb["music"]["source"] == "file"
                else "placeholder pad synthesised in FFmpeg")

# ---- 1. voice track -------------------------------------------------------------------------
voice = OUT / "audio" / "voice.wav"
inputs, chains = [], []
for i, s in enumerate(shots):
    wav = OUT / "narration" / f"{s['id']}.wav"
    if not wav.exists():
        sys.exit(f"{s['id']}: no narration - run `make narration`")
    inputs += ["-i", str(wav)]
    chains.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,adelay={int(LEAD * 1000)}:all=1,"
                  f"apad=whole_dur={dur[s['id']]},atrim=0:{dur[s['id']]}[a{i}]")
graph = ";".join(chains) + ";" + "".join(f"[a{i}]" for i in range(len(shots))) + \
        f"concat=n={len(shots)}:v=0:a=1,apad=whole_dur={total}[v]"
run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", graph, "-map", "[v]", str(voice)])

# ---- 2 + 3. duck music under voice, normalise -------------------------------------------------
score = OUT / "music" / "score.wav"
if not score.exists():
    sys.exit("no score - run `make music`")
mix_graph = (
    f"[0:a]loudnorm=I=-16:TP=-2,aresample=48000,pan=stereo|c0=c0|c1=c0,asplit=2[vsc][vmix];"
    f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{total},loudnorm=I=-24:TP=-4,aresample=48000,"
    f"afade=t=in:d=2,afade=t=out:st={total - 3}:d=3[mus];"
    f"[mus][vsc]sidechaincompress=threshold=0.02:ratio=6:attack=300:release=1500[duck];"
    f"[duck][vmix]amix=inputs=2:normalize=0:duration=first"
)
premix = OUT / "audio" / "premix.wav"
run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice), "-i", str(score),
     "-filter_complex", mix_graph, "-ar", "48000", str(premix)])
# two-pass loudnorm: measure, then apply with the measured values (more accurate than one pass)
stats = run(["ffmpeg", "-hide_banner", "-i", str(premix), "-af",
             "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"])
m = json.loads(re.findall(r"\{[^{}]+\}", stats)[-1])
mix = OUT / "audio" / "mix.wav"
run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(premix), "-af",
     f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
     f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true",
     "-ar", "48000", str(mix)])
print(f"audio: {total:.1f}s, input {m['input_i']} LUFS -> -14 LUFS target")

if radio:
    out = OUT / "film" / "radio_cut.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=black:s=1280x720:r={FPS}:d={total}",
         "-i", str(mix), "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
         "-shortest", "-movflags", "+faststart", str(out)])
    print(f"radio cut: {out.relative_to(OUT.parent)} ({total:.1f}s)")
    raise SystemExit

# ---- 4. subtitles timing + SRT ---------------------------------------------------------------
def ts(t):
    h, rem = divmod(t, 3600)
    mnt, sec = divmod(rem, 60)
    return f"{int(h):02}:{int(mnt):02}:{int(sec):02},{int(round((sec % 1) * 1000)):03}"


cues, t0 = [], 0.0  # (shot_id, start_in_shot, end_in_shot, text, abs_start, abs_end)
for s in shots:
    speech = media_duration(OUT / "narration" / f"{s['id']}.wav")
    chunks = chunk_subtitle(s["narration_en"])
    weights = [len(c) for c in chunks]
    t = LEAD
    for c, wgt in zip(chunks, weights):
        span = speech * wgt / sum(weights)
        end = t + span + (0.5 if c is chunks[-1] else 0)
        cues.append((s["id"], round(t, 2), round(min(end, dur[s["id"]]), 2), c,
                     t0 + t, t0 + min(end, dur[s["id"]])))
        t += span
    t0 += dur[s["id"]]
srt = OUT / "film" / "subtitles_en.srt"
srt.write_text("\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{txt}\n" for i, (_, _, _, txt, a, b) in enumerate(cues, 1)),
               encoding="utf-8")

# ---- 4b. picture, per aspect -------------------------------------------------------------------
for aspect, size in ASPECTS.items():
    vertical = aspect == "9x16"
    segs = []
    for s in shots:
        clip = OUT / "shots" / aspect / f"{s['id']}.mp4"
        if not clip.exists():
            sys.exit(f"{clip} missing - run `make shots`")
        mine = [c for c in cues if c[0] == s["id"]]
        args, graph, last = ["-i", str(clip)], [], "0:v"
        for k, (_, a, b, txt, _, _) in enumerate(mine, 1):
            png = OUT / "subs" / aspect / f"{s['id']}_{k}.png"
            subtitle_png(txt, size, png, vertical)
            args += ["-i", str(png)]
            graph.append(f"[{last}][{k}:v]overlay=0:0:enable='between(t,{a},{b})'[o{k}]")
            last = f"o{k}"
        seg = OUT / "segments" / aspect / f"{s['id']}.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex", ";".join(graph) or "null",
             "-map", f"[{last}]", "-t", str(dur[s["id"]]), "-c:v", "libx264", "-preset", "medium",
             "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), str(seg)])
        segs.append(seg)
    card_png = OUT / "segments" / aspect / "end_card.png"
    end_card_png(sb, size, card_png, music_credit)
    card = OUT / "segments" / aspect / "end_card.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(card_png), "-t", str(END),
         "-vf", f"fade=t=in:d=0.6,fade=t=out:st={END - 0.6}:d=0.6,format=yuv420p", "-c:v", "libx264",
         "-r", str(FPS), str(card)])
    segs.append(card)
    lst = OUT / "segments" / aspect / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in segs))
    out = OUT / "film" / f"the_film_{aspect}.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(mix),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
         "-movflags", "+faststart", str(out)])
    print(f"film: {out.relative_to(OUT.parent)} ({media_duration(out):.1f}s)")
print(f"subtitles: {srt.relative_to(OUT.parent)}")
