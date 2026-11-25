"""Validate storyboard.json against schema/storyboard.schema.json. Run before every stage."""
from common import load_storyboard

sb = load_storyboard()
words = sum(len(s["narration_en"].split()) for s in sb["shots"])
total = sum(s["duration"] for s in sb["shots"]) + sb.get("timing", {}).get("end_card_s", 3)
missing = [s["id"] for s in sb["shots"] if not s.get("narration")]
print(f"storyboard OK: '{sb['title']}', {len(sb['shots'])} shots, ~{total:.0f}s planned, {words} English words")
if missing:
    print(f"  narration in {sb.get('language_name', sb['language'])} missing for {', '.join(missing)} - run `make script`")
