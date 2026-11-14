# Viewer smoke test (manual checklist)

Serve the project root and open the viewer:

```powershell
.venv\Scripts\python.exe -m http.server 8765        # from the project root
# open http://127.0.0.1:8765/viewer/index.html
node viewer/tests/parity.test.mjs                    # JS fusion == Python fusion (exit code 0)
```

Keep the browser console open (F12). Every step below must finish **without console errors or warnings**.

## Gallery
- [ ] Cards show thumbnail, verdict chip (icon + word), title, one-line description, bundle name.
- [ ] Intro states what the tool does and does not claim, including "send for human review".
- [ ] "Upload a photo" card is disabled with an explanatory tooltip under `http.server`; enabled under the FastAPI server (`python -m lightaudit.cli serve`), where an upload runs `/api/audit`, shows progress from `/api/jobs/{id}` and opens the new bundle.
- [ ] Theme toggle (top right) switches dark/light and is remembered after reload.

## Main view (`?bundle=demo_splice_car`, then `demo_damage_fake`, `demo_overcast`, `demo_multilight`)
- [ ] Verdict banner matches the gallery chip; the "Why" text names the flagged region; "send for human review" is visible.
- [ ] Image modes via tabs and keys `1`–`6`: Observed, Regions (hatched = excluded, red outline = flagged), Relit, Counterfactual, Residual, Normals.
- [ ] Residual mode shows the badge "Matches exported heat map: ≥ 95% of px within ±8/255" while your light is at the consensus (measured: 98.2–99.9% on all demo bundles).
- [ ] Drag the orange handle on the dome (or focus the dome and use the arrow keys): the light readout, Relit and Residual images, the "At your light" column and the what-if verdict update live; the audit verdict does not change.
- [ ] "Snap to consensus" / "Snap to selected" move the handle.
- [ ] Clicking a pixel selects its region (row highlighted, dome shows its map and thicker cone). Hover shows a tooltip with name, status, shortfall and pixel values.
- [ ] Unchecking "use" on the flagged region recomputes the verdict live (splice car: SUSPICIOUS -> CONSISTENT) and shows "live, your settings" with a Reset button.
- [ ] Tune popover: changing τ, w_min, w_glint, w_contour recomputes the verdict; "Reset to calibrated" restores the bundle verdict.
- [ ] Dome selector: selected map / consensus / all regions overlay / none; `C` toggles cones; below-horizon half is dimmed and labelled.
- [ ] Rank | LS baseline toggle (when the bundle has `landscapes_ls.bin`) swaps the dome maps, cones and consensus.
- [ ] Split button: draggable divider Observed | current mode (arrow keys move it when focused).
- [ ] Shadow tool (experimental badge): click object point then its shadow point, twice or more; a consistent set adds a "shadow pairs" row (cue P) to the table and to the fusion; inconsistent pairs show a warning and are not added. Esc closes the tool.
- [ ] Region table sorts by each column header.

## Overlays
- [ ] `E` / Explain: 7 steps, Next/Previous and ← → work, step 3 toggles the uncertainty map, step 5 shows the dome and the brightness vs n·l plot with ĝ, figures enlarge on click, Esc closes.
- [ ] `A` / Attack lab on `demo_splice_car`: variants T1, T3a (0/10/20°), T4 with verdict chips; swipe slider; heat-map toggle; dome shows the original cone dashed and the attacked map; metrics before -> after; interpretation sentence; tier summary or the "no evaluation summary yet" note. On a bundle without attacks: an empty state with links.
- [ ] `?` / Help: azimuth/elevation diagram, dome legend, triage, the section 21 limitations text verbatim, keyboard shortcuts.
- [ ] Every overlay closes with Esc and returns focus.

## Layout
- [ ] 1280×720 and 1440×900: no page scroll needed for the main panels.
- [ ] 1024 px wide: single-column layout, no horizontal scroll.
- [ ] `prefers-reduced-motion`: no pulsing outlines, no transitions.
