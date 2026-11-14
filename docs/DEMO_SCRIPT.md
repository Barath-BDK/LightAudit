# Demo script (about 5 minutes)

All verdicts and numbers below are the ones stored in the built bundles (`bundles/*/manifest.json`,
calibration h = 18°, T = 1.5, alert level 4.95). If you rebuild the bundles, re-check them.

Start: `.\.venv\Scripts\python.exe -m lightaudit.cli serve`, open `http://127.0.0.1:8000`.
The first load of a bundle takes a few seconds.

## 0. Gallery (20 s)

Say: "LightAudit checks one physical thing: does a single light direction explain every part of the photo?
It is not an AI-image detector, and a flag only means *send for human review*."
Point at the verdict chips on the cards: four possible outcomes.

## 1. Clean scene — `Clean sunny scene` (30 s)

- Verdict **CONSISTENT**, image score 0.77 against the alert level 4.95, 3 reliable regions.
- On the dome, the cones of the regions overlap around the consensus marker.
- Region table: ground is "unreliable" (flat surface, no directional information); windows and wheels are
  excluded (glass and tyres are not diffuse). Say that the tool states what it could not use.

## 2. Spliced car — `Car pasted from another light` (90 s)

The car was rendered under a light 120° away from the scene's sun and pasted in.

- Verdict **SUSPICIOUS**: car body, shortfall 5.91 > 4.95; its estimate is 90° away from where the 4 other
  regions agree.
- Dome: click the car body row. Its light map sits on the other side of the sphere from the consensus.
- Press `5` (Residual): the heat map shows where the car does not fit the consensus light. The small note under
  the image confirms that the live shader reproduces the exported heat map.
- Press `4` (Counterfactual): how the car would look under the consensus light.
- Press `3` (Relit) and drag the orange handle on the dome: the image re-lights live, and the "at your light"
  bars in the table show which regions like that direction. "Snap to selected" puts the light where the car
  thinks it is; the other regions' bars collapse.
- Untick the car body row: the live fusion recomputes and the verdict changes. Tick it again.

## 3. Explain stepper — press `E` (40 s)

Walk the seven steps: photo → regions → surface directions → usable pixels → per-region light maps → do they
overlap → where it does not fit. Stop at the tone-curve illustration: the shading cue only uses the *rank
order* of brightness, so gamma, tone mapping and exposure do not matter.

## 4. Attack lab — press `A` (60 s)

"Now we attack our own detector." Same spliced car, attacked region = car body.

| Attack | Verdict after | Car body off the consensus | Shortfall |
|---|---|---|---|
| none (T0) | SUSPICIOUS | 90° | 5.9 |
| T1 colour transfer | SUSPICIOUS | 92° | 6.9 |
| T3a re-shade, exact light | CONSISTENT | 16° | 0.2 |
| T3a re-shade, ±10° error | CONSISTENT | 9° | 0.2 |
| T3a re-shade, ±20° error | CONSISTENT | 20° | 0.8 |
| T4 adaptive | CONSISTENT | 10° | 0.1 |

Say, honestly:
- Colour and brightness harmonisation does **not** help the forger: it is a monotone change and the rank order
  of the shading stays the same.
- A physics re-shade **does** fool the detector, even with a 20° error in the forger's light estimate. In this
  scene the highlight and silhouette cues do not rescue the verdict.
- The price: the re-shade changes the region's brightness by 0.16–0.18 on average (scale 0–1), above the 0.08
  fidelity budget, so the edit is visible when the original is at hand. Use the swipe slider to show it.
- Caveat to say out loud: the defender's surface normals here are simulated and independent of the edit, which
  is the best case for the attacker.

## 5. Damage panel mode (40 s)

- `Genuine dent (panel mode)`: the dent ROI and its ring agree with the scene, **CONSISTENT** (score 2.18).
- `Dent pasted from another light (panel mode)`: **SUSPICIOUS**, the ROI is 98° off, shortfall 5.44.
  Note that it took 10 seeds to find a scene where a pasted dent is caught: a dent is a small, shallow region
  and carries little shading evidence. The same attack table applies (T1 still flagged; T3a/T4 pass, but with
  the exact light the dent's estimate barely moves, 98° → 94°: the verdict flips because the evidence gets weak).

## 6. Abstention and limits (40 s)

- `Overcast`: **INSUFFICIENT** — only 2 reliable regions. The tool asks for a better photo instead of guessing.
  (Finding this took 12 seeds: many overcast scenes come out CONSISTENT, because the sky light still gives every
  region the same "up" direction.)
- `Two suns`: intended CONFLICT, actual verdict **CONSISTENT** (score 4.06, just under the alert level). Two
  strong lights are outside the one-light model, and at this alert level the tool does not notice. Shown as is.

## 7. Failure example (20 s)

`Failure example: a splice that passes`: the car was pasted from a light 120° away, verdict **CONSISTENT**. The
car body's shortfall is 3.48 (39° off the consensus), below the alert level 4.95. The alert level is set so that
5% of clean calibration scenes are flagged; the cost of that low false-alarm rate is missed splices like this.

## 8. Close (20 s)

Open Help (`?` button): read the first and the bold sentence of the limitations text. Mention the report for
the measured detection rates.

## Screenshots for the report

If `docs/figures/viewer_*.png` are missing, capture at 1440×900: the gallery (`viewer_gallery.png`), the
spliced-car bundle (`viewer_main.png`), the dome with the car selected (`viewer_dome.png`), the explain stepper
(`viewer_explain.png`) and the attack lab (`viewer_attack.png`).
