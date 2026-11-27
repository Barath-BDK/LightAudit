# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Primary: an insurance claims reviewer checking a submitted vehicle-damage photo. They upload the photo, mark the
damage area, read a verdict, see why, and decide whether to send the claim for human review.
Secondary: a professor and classmates at a live course demo (Interactive Computer Graphics, semester 7). The landing
page explains the tool to them; the workspace is built as the reviewer's real tool. (Confirmed: "both, tool first".)

## Product Purpose
Checks whether one light explains every part of a photo. A region lit from a different direction (a pasted dent,
a pasted object) is flagged for human review. When the photo carries too little lighting evidence, it says so
instead of guessing. Success: a reviewer can trust a flag and trust an abstention.

## Positioning
A physics check, not a learned "fake detector": it estimates where the light comes from in each region and tests
whether one sun explains them all, shows that evidence in 3D, and attacks itself to measure how a forger could pass.

## Operating Context
Runs locally (FastAPI server on 127.0.0.1, static viewer). An audit of a new photo takes about 5-7 minutes on a laptop
CPU. Shown live at a course demo on a laptop screen and projector.

## Capabilities and Constraints
- Verdicts: CONSISTENT, SUSPICIOUS (with flagged regions), INSUFFICIENT (not enough lighting evidence), CONFLICT
  (regions disagree: several lights or bad geometry).
- Marked-area (panel) check: the measured real-photo result. Whole-scene check: weak on real photos, must be shown
  honestly.
- Viewer: static ES modules, vanilla JS/CSS, Three.js vendored, no build step. WebGL2 required.
- The unforgettable moment (confirmed): **moving the light** — dragging the sun and watching the genuine parts relight
  correctly while the pasted part stays wrong.

## Brand Commitments
- Name: LightAudit.
- "A flag means send for human review, never fraud."
- User's binding direction: must not look AI-generated/templated; must be unique and impress the professor.

## Evidence on Hand
- 26 audited bundles in `bundles/` (19 real photos incl. 6 outdoor cars and 12 MIT tabletop objects; 7 synthetic).
- Real marked-area benchmark (10 held-out real tabletop objects, 400 clean + 400 pasted areas, not cars): 5.2% false
  alarms, 45% caught, 57% at 80°+ light difference, 32% after colour matching. `HANDOVER.md` §5.
- Absent, must not be fabricated: real car photos with real or pasted damage, any user study, any customer.
- Real photos from Wikimedia Commons (CC BY / CC BY-SA) need attribution when shown.

## Product Principles
1. Every number on screen comes from a bundle or a logged measurement.
2. Abstaining is a feature: INSUFFICIENT and CONFLICT are shown as honest outcomes, not errors.
3. The light is the interface: interacting with the light direction is how the user understands the verdict.
4. Real photos lead; synthetic renders are labelled as such.
