# Demo script (about 5 minutes)

All verdicts and numbers below are the ones stored in the built bundles (`bundles/*/manifest.json`), made with
the least-squares shading cue (calibration h = 14°, T = 1.5, alert level 6.35; the largest possible score is
about 6.9; soft-light threshold 0.42; panel alert 3.9). If you rebuild the bundles, re-check them.

Start: `.\.venv\Scripts\python.exe -m lightaudit.cli serve`, open `http://127.0.0.1:8000`.
The first load of a bundle takes a few seconds.

## 0. Gallery (20 s)

Say: "LightAudit checks one physical thing: does a single light direction explain every part of the photo?
It is not an AI-image detector, and a flag only means *send for human review*."

## 1. Clean scene — `Clean sunny scene` (30 s)

- Verdict **CONSISTENT**, image score 0.81 against the alert level 6.35, 3 reliable regions.
- On the dome, the cones of the regions overlap around the consensus marker.
- Region table: ground is "unreliable" (flat, no directional information); windows and wheels are excluded
  (glass and tyres are not diffuse). The tool states what it could not use.

## 2. Spliced car — `Car pasted from another light` (90 s)

The car was rendered under a light 120° away from the scene's sun and pasted in.

- Verdict **SUSPICIOUS**: car body, shortfall 6.86 > 6.35; its estimate is 86° away from where the other
  regions agree.
- Dome: click the car body row. Its light map sits far from the consensus.
- Press `5` (Residual): the heat map shows where the car does not fit the consensus light.
- Press `4` (Counterfactual): how the car would look under the consensus light.
- Press `3` (Relit) and move the orange light (arrow keys or drag): the image re-lights live, and the
  "at your light" bars show which regions like that direction.
- Untick the car body row: the live fusion recomputes and the verdict changes. Tick it again.
- "Audit cue / Baseline cue" above the dome switches between the least-squares maps and the rank-cue maps.

## 3. Explain stepper — press `E` (40 s)

Walk the seven steps: photo → regions → surface directions → usable pixels → per-region light maps → do they
overlap → where it does not fit.

## 4. Attack lab — press `A` (60 s)

"Now we attack our own detector." Same spliced car, attacked region = car body.

| Attack | Verdict after | Car body off the consensus | Shortfall |
|---|---|---|---|
| none (T0) | SUSPICIOUS | 86° | 6.9 |
| T1 colour transfer | CONSISTENT | 88° | 5.9 |
| T3a re-shade, exact light | CONSISTENT | 16° | 0.0 |
| T3a re-shade, ±10° error | CONSISTENT | 20° | 0.4 |
| T3a re-shade, ±20° error | CONSISTENT | 34° | 0.7 |
| T4 adaptive | CONSISTENT | 10–16° | 0.0 |

Say, honestly:
- A physics re-shade moves the car's estimate onto the consensus and fools the detector, even with a 20° error
  in the forger's light estimate. It changes the region's brightness by about 0.2 on a 0–1 scale, so the edit
  is visible when the original is at hand (swipe slider).
- Colour transfer does not move the estimate (86° → 88°), but it lowers the score just under the alert level,
  so this case passes too. That is a cost of the least-squares cue; the rank cue was immune to it.
- Caveat: the defender's surface normals are simulated and do not react to the edit, the best case for the
  attacker.

## 5. Damage panel mode (40 s)

In panel mode the dent is compared directly with the panel around it: same paint, same light, so the panel's
own shading curve should predict the dent's brightness.

- `Genuine dent (panel mode)`: **CONSISTENT**. Panel score 0.47, alert level 3.9.
- `Dent pasted from another light (panel mode)`: **SUSPICIOUS**. Panel score 5.5 > 3.9: "the brightness of the
  ROI does not follow the shading of the panel around it". The direction test alone would have passed it
  (shortfall 1.54), which is why this check exists.
- Attack lab on the dent: the re-shade attacks (T3a, T4) are **still flagged**, because re-shading the dent with
  its own curve does not make it match the panel. Colour transfer (T1) does pass here: matching the dent's
  brightness to its surroundings is exactly what this check measures.

## 6. Abstention and limits (40 s)

- `Overcast`: **INSUFFICIENT**, "the light looks diffuse". The shading contrast of the regions is 0.47, above
  the soft-light threshold 0.42: without a sun there is no light direction to test.
- `Two suns`: intended CONFLICT, actual verdict **CONSISTENT** (score 4.06). Two strong lights are outside the
  one-light model and the tool does not notice. A second-light test was tried and did not work. Shown as is.

## 7. Failure example (20 s)

`Failure example: a splice that passes`: the car was pasted from a light 120° away, verdict **CONSISTENT**. The
car body is 55° off the consensus with shortfall 3.80, below the alert level.

## 8. Real photos (30 s, optional)

Open one `real_*` card. Say that six unedited photos and one splice were tried: one unedited photo is flagged
(false alarm) and the splice is not flagged. Real-photo results are qualitative only.

## 9. Close (20 s)

Open Help: read the first and the bold sentence of the limitations text. Point to the report for the measured
detection rates.
