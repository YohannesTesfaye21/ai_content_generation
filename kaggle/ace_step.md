# Score with ACE-Step 1.5 on Kaggle

Steps to replace the synthesised placeholder score with an ACE-Step track:

1. Open a Kaggle notebook (Accelerator: GPU T4, Internet on) and set up ACE-Step 1.5 following
   the repository's README: https://github.com/ACE-Step/ACE-Step-1.5
2. Use the values from `storyboard.json → music`:
   - **caption:** `instrumental, gentle Ethiopian folk underscore, soft krar plucks and warm low strings, slow and tender, sparse texture, no lead melody, nostalgic, intimate`
   - **bpm:** 68 and **key:** A minor. Put these in the metadata fields, not in the caption.
   - **duration:** 90 s (the film is 88.5 s). If 90 s is unstable, make two 45 s sections.
   - **instrumental** on, so no vocals compete with the narrator.
3. Generate **3 candidates** with different seeds. Write down each seed and how long it took.
4. Listen to each one at low volume under the radio cut. Choose one and write down why in
   EXPERIMENTS.md (for example: "seed 2: the krar texture leaves room for the voice; seed 1
   had a lead melody fighting the narration").
5. Download the chosen file to `outputs/music/ace_step_choice.wav`, then in `storyboard.json` set:
   ```json
   "music": { "source": "file", "file": "outputs/music/ace_step_choice.wav", ... }
   ```
6. Run `make music assemble`. The end card credit changes to ACE-Step automatically.
7. Add one line per generation to `runs.jsonl`
   (`{"stage":"music","model":"ACE-Step-1.5","provider":"kaggle-t4","seed":…,"latency_s":…,"gpu_minutes":…,"status":"ok"}`),
   and the GPU minutes to COSTS.md.
