# One command: `make film` runs the whole pipeline from storyboard.json.
# Every stage is cached by a hash of its inputs, so re-running only regenerates what changed.

PY := .venv/bin/python
P  := cd pipeline && ../$(PY)

.PHONY: film setup validate script narration keyframes shots music radio assemble costs clean

film: validate script narration keyframes shots music assemble
	@echo "Done: outputs/film/the_film_16x9.mp4 and outputs/film/the_film_9x16.mp4"

setup: $(PY)
$(PY):
	python3 -m venv .venv
	$(PY) -m pip install -q -r requirements.txt

validate: setup
	@$(P) validate.py

script: validate
	@$(P) script.py

narration: script
	@$(P) narration.py

keyframes: validate
	@$(P) keyframes.py

shots: keyframes narration
	@$(P) shots.py

music: validate
	@$(P) music.py

# Phase 1 prototype: narration + temp music over black, for the first user test
radio: narration music
	@$(P) assemble.py radio

assemble: shots music
	@$(P) assemble.py

costs:
	@$(P) costs.py

# Regenerate one shot, e.g. `make shot S=s03` (keyframe + narration + clip), then `make assemble`
shot: validate
	@$(P) keyframes.py $(S) && $(P) narration.py $(S) && $(P) shots.py $(S)

clean:
	rm -rf outputs/segments outputs/subs outputs/audio outputs/film
