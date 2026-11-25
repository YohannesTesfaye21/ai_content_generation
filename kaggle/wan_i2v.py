"""Wan 2.2 TI2V-5B image-to-video on a Kaggle GPU notebook (2x T4). UNTESTED in this repo so far.

How to use (Kaggle → New notebook → Accelerator: GPU T4 x2 → Internet on):
  1. Upload storyboard.json and outputs/keyframes/*.jpg as a Kaggle dataset named `heritage-short`.
  2. Paste this file into a cell and run it. It writes /kaggle/working/wan/sNN.mp4.
  3. Download the clips into outputs/wan/ locally and run `make shots assemble`:
     shots.py uses a Wan clip automatically when outputs/wan/sNN.mp4 exists.

Draft at the default 704x1280 / 1280x704 only for the shots you choose (SHOTS below), because a
5 s clip takes many minutes on a T4. Log each run's minutes in COSTS.md.
"""
import json
import subprocess
import time
from pathlib import Path

DATA = Path("/kaggle/input/heritage-short")
WORK = Path("/kaggle/working")
SHOTS = ["s05", "s07"]          # start with 1-2 shots; add more if quota allows
SIZE = "1280*704"               # Wan 2.2 TI2V-5B's 720p landscape size; keyframes are square, centre-cropped later

def sh(cmd):
    print("$", cmd)
    subprocess.run(cmd, shell=True, check=True)

if not (WORK / "Wan2.2").exists():
    sh(f"cd {WORK} && git clone --depth 1 https://github.com/Wan-Video/Wan2.2.git")
    sh(f"cd {WORK}/Wan2.2 && pip install -q -r requirements.txt")
    sh(f"pip install -q 'huggingface_hub[cli]' && huggingface-cli download Wan-AI/Wan2.2-TI2V-5B "
       f"--local-dir {WORK}/Wan2.2-TI2V-5B")

sb = json.loads((DATA / "storyboard.json").read_text())
(WORK / "wan").mkdir(exist_ok=True)
log = []
for s in sb["shots"]:
    if s["id"] not in SHOTS:
        continue
    out = WORK / "wan" / f"{s['id']}.mp4"
    t0 = time.time()
    # Image-to-video: the keyframe already holds subject and light, so the prompt is motion + camera only.
    sh(f"cd {WORK}/Wan2.2 && python generate.py --task ti2v-5B --size '{SIZE}' "
       f"--ckpt_dir {WORK}/Wan2.2-TI2V-5B --offload_model True --convert_model_dtype --t5_cpu "
       f"--image {DATA / (s['id'] + '.jpg')} --prompt \"{s['motion_prompt']}\" --base_seed {s.get('seed', 0)} "
       f"--save_file {out}")
    minutes = round((time.time() - t0) / 60, 1)
    log.append({"stage": "shots", "shot": s["id"], "model": "Wan2.2-TI2V-5B", "provider": "kaggle-t4",
                "params": {"size": SIZE, "prompt": s["motion_prompt"]}, "seed": s.get("seed", 0),
                "latency_s": minutes * 60, "gpu_minutes": minutes, "status": "ok"})
    print(f"{s['id']}: {minutes} GPU minutes")

# Append these lines to runs.jsonl in the repo so the GPU calls are logged like every other call.
(WORK / "wan" / "runs_wan.jsonl").write_text("".join(json.dumps(r) + "\n" for r in log))
