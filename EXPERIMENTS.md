# Experiments

Format: hypothesis → change → result → decision. Evidence is in `runs.jsonl`, the storyboard
history (git log) and the kept first versions in `outputs/keyframes_v1/` and
`outputs/narration_v1/`.

---

### E1 — FLUX.1 schnell vs FLUX.2 klein 4B for keyframes
- **Hypothesis:** schnell (the suggested default) with a fixed seed per shot gives reproducible keyframes.
- **Change:** sent `seed` to `@cf/black-forest-labs/flux-1-schnell`.
- **Result:** rejected — `AiError 5006: Additional or unevaluated properties '/seed' not allowed`.
  Schnell on Workers AI takes no seed and no reference image, so it can be neither reproducible
  nor conditioned. Probing the model catalogue found `flux-2-klein-4b` (Apache 2.0), whose
  multipart input accepts `seed`, `width`, `height` and `input_image_0..n`. Test call: 12.9 s
  text-only, 8.6 s with a reference image.
- **Decision:** klein 4B for all keyframes. Mean latency over 19 calls: ~9 s.

### E2 — Does a reference image keep the grandmother consistent?
- **Hypothesis:** passing one approved portrait (`reference.jpg`) as `input_image_0` keeps her
  face and clothing stable across shots better than repeating the text description alone.
- **Change:** generated `reference.jpg` first (seed 1000), then every `with_character` shot with it.
- **Result:** in v1 (`outputs/keyframes_v1/`) the face shape, silver hair, white netela and the
  green woven border were recognisably the same in all 7 character shots — including the wide
  family shot s06.
- **Decision:** keep. This is the "reference sheet before keyframes" practice, and it beat my
  instinct (I expected to need a LoRA).

### E3 — Reference leakage into close-up compositions
- **Hypothesis:** the reference controls identity only, so close-ups of hands still come out as close-ups.
- **Change:** none (observed in v1).
- **Result:** wrong. With the reference attached, s02 (hands roasting), s04 (hands grinding) and
  s05 (coffee pour) all came out as front-facing head-and-shoulders portraits holding the props —
  the reference's composition leaked in, and the shot-size variety the storyboard planned was lost.
- **Fix:** set `with_character: false` for the three insert shots and described the hands in
  text instead ("deep brown weathered hands, white cotton sleeves with a thin woven green border",
  "no face visible"). Result in v2: true overhead/insert framing, and the sleeve border still ties
  the hands to her.
- **Decision:** use the reference only for shots where her face is visible.

### E4 — Skin tone and ethnicity drift
- **Hypothesis:** "warm dark brown skin" in the character description is enough.
- **Result (v1):** the reference came out with a light-medium skin tone; the s06 family looked
  East Asian / Latin American rather than Ethiopian.
- **Change:** "an elderly **Habesha Ethiopian** grandmother with **deep dark brown** skin", and
  for s06 "an Ethiopian family of three generations with brown skin — children, parents and the
  grandmother at the center".
- **Result (v2):** grandmother noticeably darker and more accurate; s06 now has children and
  parents, but some faces still read as generic rather than Ethiopian.
- **Decision:** keep the v2 wording; open question for user test 2 (do Ethiopian viewers accept s06?).

### E5 — A long TTS style instruction is spoken aloud
- **Hypothesis:** a descriptive instruction ("Read this in Amharic as a grandchild fondly
  remembering their grandmother: calm, warm, unhurried, gentle pauses…") improves delivery.
- **Result:** every clip was 17.9–22.6 s for lines of 10–20 words (`outputs/narration_v1/`).
  `silencedetect` on s05 showed ~10 s of speech, a 1.5 s gap, then ~8 s more — the model read
  the English instruction aloud before the Amharic line.
- **Change:** short prefix ending in a colon: `Say warmly, at a gentle natural pace:`.
- **Result:** s05 went from 20.2 s to 9.3 s, containing only the Amharic line.
- **Decision:** keep style prefixes short; documented in the schema description of `voice.style`.

### E6 — Gemini 3.8 Flash TTS vs Flash Lite TTS
- **Hypothesis:** Lite is faster at similar quality.
- **Result (latency, from runs.jsonl):** Flash TTS mean 7.6 s/line (9 calls); Lite 4.7 s/line
  (9 calls). Quality comparison: _to fill after listening — compare `outputs/narration_v1/sNN.wav`
  (Flash, but with the instruction problem) and `outputs/narration/sNN.wav` (Lite)._
- **Decision:** Lite as primary (also because Flash's daily quota was used up, see FAILURES F5),
  Flash as fallback.

### E7 — Fitting the film under 90 seconds
- **Hypothesis:** 9 shots × ~8 s of Amharic narration fits in 90 s.
- **Result:** measured Amharic speech was ~86 s at speed 1.0 → ~98 s with lead, padding and end
  card. Amharic took ~1.2 words (English-equivalent) per second, slower than the 2–2.5 words/s rule of thumb.
- **Change:** (a) `voice.speed: 1.1` (pitch-preserving `atempo`), (b) padding 1.0 → 0.6 s,
  (c) cut shot s04 (the mortar) — the least essential beat, and re-voicing shorter lines was
  impossible that day because both TTS models were out of quota.
- **Result:** 88.5 s.
- **Decision:** keep. If the second user test says it feels rushed, shorten lines instead of speeding up.

### E8 — Prompt ambiguity: "smoking pan"
- **Result:** s03 "carrying a smoking roasting pan" produced a pan of stew.
- **Change:** "a flat iron pan of freshly roasted dark coffee beans with fragrant smoke rising from them".
- **Result:** correct — dark beans in the pan. One API call (cache hit for every other shot).

### E9 — Subtitle chunking
- **Hypothesis:** wrapping at 40 characters and taking two lines per card reads fine.
- **Result:** orphan cards ("coffee.", "began") and lines broken mid-phrase.
- **Change:** split at sentence/clause punctuation first, pack clauses into ≤ 80-character cards,
  then balance the two lines.
- **Result:** e.g. "The second cup, tona, was for talking." / "This is where all the family
  stories came out." — every card is a complete phrase.

### E10 — Two-pass loudness normalisation
- **Hypothesis:** two-pass `loudnorm` lands closer to −14 LUFS than single-pass.
- **Result:** pre-mix measured −13.55 LUFS; after the second pass the final film measures
  **−14.0 LUFS integrated, peak −2.2 dBFS** (`ebur128`).
- **Decision:** keep two-pass; cost is ~5 s.

### E11 — Style drift toward photorealism (open)
- **Observation:** with the reference attached, s03 and s06 drift from "hand-painted gouache"
  toward a semi-photographic look, while non-reference shots (s01, s02) stay painterly.
- **Next hypothesis:** regenerate the reference itself in a stronger painted style (or add
  "visible brush strokes, paper texture" to the style block) so the reference carries the style too.

### E12 — Generic prompts produce generic (not Ethiopian) images
- **Hypothesis:** "Ethiopian grandmother", "thatched house", "coffee pot" are enough for an
  Ethiopian audience to recognise their own world.
- **Result (v2, `outputs/keyframes_v2/`):** pan-African or even Latin-American-looking scenes: a
  generic round hut, a plain white shawl, Western cups, a family that did not read as Habesha.
  For the intended audience (Ethiopians, DESIGN.md) this breaks the "that was my grandmother's
  house" feeling the film exists for.
- **Change:** named the specific cultural objects and features instead of categories:
  Amhara highland *tukul* with teff terraces and eucalyptus; Habesha facial features, thin braids,
  a faint traditional cross tattoo; *netela* and *habesha kemis* with *tibeb* borders;
  *menkeshkesh* roasting pan on a *kesel* charcoal stove; *rekebot* tray, *sini* cups, fresh
  *ketema* grass and meskel daisies, frankincense burner; *kolo* and popcorn; father in a *gabi*,
  mother with *shuruba* braids; Addis Ababa skyline with the Entoto hills for the last shot.
  The style block now also says "authentic Ethiopian setting and people" and adds
  "visible brush strokes and paper texture" (E11).
- **Result (v3):** every frame now carries recognisable Ethiopian detail; the painterly style
  holds better on reference shots too. The s06 family came out with light-skinned children on
  the first try; adding "everyone with deep dark brown skin and Ethiopian facial features" and
  a new seed (1206) fixed it.
- **Decision:** specific nouns beat adjectives. Ask Ethiopian viewers in user test 2 whether any
  detail looks wrong.

### E13 — The model does not know what a jebena looks like
- **Result:** "black clay jebena coffee pot" gave a vase (s08) and then a European jug (s05).
- **Change:** describe the geometry instead of the name: "shaped like a gourd, a perfectly
  spherical round base, a tall narrow straight neck rising from it like a bottle, a short spout
  sticking out sideways from the round base, a small handle joining neck to base, a woven straw
  stopper".
- **Result:** both shots now show a recognisable jebena (round base, tall neck, straw stopper);
  s05 has the side spout, s08 still lacks it. 2 calls, every other shot a cache hit.
- **Lesson:** for culturally specific objects that are rare in training data, name it *and*
  describe its shape.

### E14 — A real photo as an object reference for the jebena
- **Hypothesis:** describing the jebena's geometry (E13) is not enough; a real photo passed as a
  second reference image will make every jebena match the real object.
- **Change:** added `references/jebena.jpg` (a photo of a traditional jebena on its woven ring
  stand). New storyboard fields `references` and `reference_notes` per shot; `keyframes.py` sends
  the character reference as `input_image_0` and object references after it. Prompt text now
  matches the photo: round body on a woven ring stand, tall neck with a clay lid, spout rising
  from the lower body, handle from neck to shoulder. Attached to s05, s06, s08, s09.
- **Result:** the jebena now matches the real object in all four shots, including the
  colourful ring stand that no text prompt had produced. Two new problems appeared:
  1. s05 got unrelated robed figures in the background → "plain mud wall background, no people", new seed.
  2. When asked for a hand *pouring* from the jebena (s05, s09), the model kept the reference's
     upright pose and invented a second small pot pouring into it — twice, on two seeds.
- **Change 2:** stopped fighting the reference: the jebena stands upright with steam rising from
  its spout, and a hand lifts a freshly poured sini cup. Narration still fits.
- **Result 2:** one correct jebena per shot. Remaining flaw: the cups have handles (real sini are handleless).
- **Lesson:** a reference image fixes an object's *appearance* but also pulls in its *pose*;
  write the action so it agrees with the reference instead of contradicting it.

### E15 — A pose reference for pouring
- **Hypothesis:** the upright-jebena reference (E14) cannot produce pouring because it fixes the
  pose; a second photo of a jebena *being poured* (`references/jebena_pouring.jpg`: a hand tilting
  the jebena by its handle, a stream from the spout into handleless patterned sini cups) will.
- **Change:** s05 and s09 use the pouring reference instead of the upright one, with the action
  written back into the prompt.
- **Result s05:** first seed: correct pose, but the stream missed the cup and one cup had a handle.
  Second seed with "stream falling straight down into the opening of the cup directly below it",
  "hand with deep dark brown Ethiopian skin", "every cup is handleless": the image now matches
  the real ceremony — tilted jebena, stream into a cup, handleless painted sini cups. Kept.
- **Result s09:** three attempts all failed differently: (1) light-skinned hand, stream beside
  the cup; (2) a whole row of cups (copied from the reference) with the stream into a pot;
  (3) coffee poured onto the table, light hand, the cup turned into a plant pot.
- **Decision:** after three attempts, fall back (the "three attempts, then a fallback" practice):
  s09 returns to the upright jebena from E14 with a dark-skinned hand holding one sini cup.
  The reference's *crowd of cups* fights the shot's meaning (one person, alone, in the city), so
  the upright reference is the right one for this shot.
- **Lesson:** choose the reference whose composition matches the shot's story, not just its object.
