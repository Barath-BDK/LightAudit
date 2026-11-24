"""Deck A, "One Light": night-ink slides lit by a single sun that moves (Morph) from slide to slide.

    python presentation/build/deck_a.py           -> presentation/LightAudit_A_One_Light.pptx
    python presentation/build/deck_a.py photon    -> presentation/LightAudit_C_Photon.pptx

Photon mode: the mascot is a small photon that carries every transition. Between two slides an auto-advancing
keyframe slide holds the photon's light flooding the whole screen, so in Slide Show the photon bursts, the old slide
dissolves into its light, and the light collapses into the photon's next spot. Text then arrives in order of its
distance from the photon, drifting outward from it, as if lit by it.
"""
import math
import sys
from pathlib import Path

from lxml import etree
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

import pptlib as L

HERE = Path(__file__).resolve().parent
A = HERE / "assets"
PHOTON = len(sys.argv) > 1 and sys.argv[1] == "photon"
OUT = HERE.parent / ("LightAudit_C_Photon.pptx" if PHOTON else "LightAudit_A_One_Light.pptx")
# where the photon rests on each slide (inches); chosen in empty space next to the content
PHOTON_AT = {1: (10.6, 2.7), 2: (7.55, 0.85), 3: (2.2, 5.6), 4: (12.35, 1.15), 5: (7.45, 0.8), 6: (12.35, 1.05),
             7: (12.4, 1.05), 8: (11.6, 0.95), 9: (12.55, 0.95), 10: (12.35, 1.05), 11: (12.35, 1.05), 12: (6.67, 2.9)}

BG, PANEL, LINE = "0A0E1A", "131A2B", "27304A"
TXT, MUTED, DIM = "F5F1E8", "A3ACBD", "6E7890"
AMBER, EMBER, RED, GREEN, GREY = "FFB547", "FF8A2A", "FF6B5E", "4CC38A", "8E99A6"
H, B, LT = "Segoe UI Semibold", "Segoe UI", "Segoe UI Light"

prs = L.new_deck()
N = [0]


def soft_edge(shape, rad_in):
    spPr = shape._element.spPr
    eff = spPr.find(qn("a:effectLst"))  # rect() already wrote one (shadow off); a second one corrupts the file
    if eff is None:
        eff = etree.SubElement(spPr, qn("a:effectLst"))
    se = etree.SubElement(eff, qn("a:softEdge"))
    se.set("rad", str(int(rad_in * 914400)))


def flash(s, cx, cy, d, alpha):
    """The photon's light as a soft disc; Morph scales it from a speck to the whole screen and back."""
    o = L.rect(s, cx - d / 2, cy - d / 2, d, d, "FFE6B8", alpha=alpha, shape=MSO_SHAPE.OVAL, name="!!flash")
    soft_edge(o, max(0.02, d * 0.18))
    return o


def burst_keyframe(at):
    """Auto-advancing slide between two content slides: the photon's light fills the screen."""
    s = L.blank(prs, BG)
    cx, cy = L.W_IN / 2, L.H_IN / 2
    flash(s, cx, cy, 30.0, 0.97)
    L.pic(s, A / "ray_fan.png", cx - 16, cy - 16, 32, 32, name="!!rays", rot=40)
    L.pic(s, A / "sun_core.png", cx - 7, cy - 7, 14, 14, name="!!core")
    L.transition(s, "morph", 650, auto_ms=0)
    L.notes(s, "Transition keyframe: the photon's light fills the screen. This slide advances by itself; nothing to present.")


class PhotonTimeline(L.Timeline):
    """Entrances arrive in order of distance from the photon and drift outward from it."""

    def __init__(self, slide, at):
        super().__init__(slide)
        self.at = at

    def add(self, shape, kind, delay=0, dur=700, **o):
        if kind in ("spin", "pulse", "breathe", "path") or shape.name.startswith("!!") or shape.name == "sun2":
            return super().add(shape, kind, delay, dur, **o)
        cx = (shape.left + shape.width / 2) / 914400
        cy = (shape.top + shape.height / 2) / 914400
        dx, dy = cx - self.at[0], cy - self.at[1]
        dist = math.hypot(dx, dy) or 1.0
        d = 150 + dist * 125 + delay * 0.08  # light reaches nearer things first; the authored order breaks ties
        if kind in ("rise", "fade"):
            kind = "drift"
            o = dict(o, dx=dx / dist * 0.5 / L.W_IN, dy=dy / dist * 0.5 / L.H_IN)  # arrive from 0.5" closer to the photon
        return super().add(shape, kind, d, max(dur, 750), **o)


def slide(sun_xy, fan=8.0, core=None, title=None, kicker=None, footer=True):
    """New slide with the sun at sun_xy (inches); returns (slide, timeline, content delay start)."""
    if PHOTON and N[0] >= 1:
        burst_keyframe(PHOTON_AT[N[0] + 1])
    s = L.blank(prs, BG)
    N[0] += 1
    if PHOTON:  # the mascot: a small photon, not a sun
        cx, cy = PHOTON_AT[N[0]]
        hero = N[0] in (1, 12)
        fan, core = (5.2, 1.5) if hero else (2.6, 0.85)
        flash(s, cx, cy, 0.3, 0.0)
    else:
        cx, cy = sun_xy
    rays = L.pic(s, A / "ray_fan.png", cx - fan / 2, cy - fan / 2, fan, fan, name="!!rays")
    c = core or fan * 0.30
    corep = L.pic(s, A / "sun_core.png", cx - c / 2, cy - c / 2, c, c, name="!!core")
    tl = PhotonTimeline(s, (cx, cy)) if PHOTON else L.Timeline(s)
    tl.add(rays, "spin", 0, 140000 if not PHOTON else 40000, deg=360, repeat="indefinite")
    tl.add(corep, "pulse", 0, 2600 if not PHOTON else 1800, scale=1.10 if not PHOTON else 1.18, repeat="indefinite")
    if N[0] > 1:
        L.transition(s, "morph", 1800 if not PHOTON else 900)
    if footer:
        L.text(s, 0.75, 7.0, 4, 0.3, "LightAudit", 10, DIM, B, name=f"foot{N[0]}")
        L.text(s, 11.6, 7.0, 1, 0.3, str(N[0]), 10, DIM, B, align="r", name=f"num{N[0]}")
    t = 350
    if kicker:
        k = L.text(s, 0.75, 0.55, 8, 0.35, kicker, 13, AMBER, H, char_spacing=1.5)
        tl.add(k, "fade", t, 500)
        t += 150
    if title:
        tt = L.text(s, 0.75, 0.9, 8.6, 1.4, title, 36, TXT, H, line_spacing=0.95)
        tl.add(tt, "rise", t, 700)
        t += 350
    return s, tl, t


# 1 ---------------------------------------------------------------- title
s, tl, t = slide((10.4, 1.7), fan=11.5, core=3.2, footer=False)
for i, (o, args) in enumerate([
    (L.text(s, 0.8, 1.9, 8, 1.2, "LightAudit", 72, TXT, H), ("rise", 300, 900)),
    (L.text(s, 0.8, 3.25, 8, 0.7, "Does one light explain this photo?", 30, AMBER, LT), ("rise", 750, 800)),
    (L.text(s, 0.8, 4.05, 7.2, 0.9, "An explainable lighting-consistency audit for edited photos, built for reviewing damage photos in insurance claims", 17, MUTED, B, line_spacing=1.1), ("fade", 1200, 800)),
    (L.text(s, 0.8, 5.85, 6, 0.8, [[("Barath Dharshan", {"color": TXT, "font": H})], [("CS23I1005 · Interactive Computer Graphics · Semester 7", {})]], 14, MUTED, B), ("fade", 1600, 700)),
]):
    tl.add(o, *args[:1], args[1], args[2])
L.notes(s, "LightAudit asks one question about a photo: could a single light have lit every part of it? "
           "When someone edits a photo, for example pastes a dent into a car door or drops a whole car into a scene, "
           "the pasted part keeps the light of the photo it came from. LightAudit finds that disagreement, shows the evidence, "
           "and says plainly when the photo carries too little lighting evidence to judge. The motivating case is damage photos in insurance claims.")
tl.write()

# 2 ---------------------------------------------------------------- problem
s, tl, t = slide((12.6, 0.6), fan=6.5, kicker="THE PROBLEM", title="A pasted dent looks real.\nThe light does not.")
photo = L.pic(s, A / "pear_dark_photo.jpg", 8.45, 1.2, None, 4.75, radius=0.12, shadow={"blur": 40, "dist": 14, "alpha": 0.5})
tl.add(photo, "zoom", t, 900, **{"from": 0.85})
cap = L.text(s, 8.45, 6.1, 3.9, 0.6,
             [[("Real photo, marked area pasted from the same object under another lamp", {})]], 12, MUTED, B)
tl.add(cap, "fade", t + 500, 600)
rows = [("Claim photos get edited", "A dent is pasted onto a door, or a whole car is dropped into a scene."),
        ("The eye does not catch it", "Colour and brightness are easy to match. The direction of the light is not."),
        ("A bare “fake” score is not enough", "Pixel detectors can flag an image, but a reviewer needs a reason they can check.")]
y = 2.75
for i, (h, d) in enumerate(rows):
    n = L.text(s, 0.75, y, 0.6, 0.5, f"0{i + 1}", 22, AMBER, LT)
    hh = L.text(s, 1.45, y, 6.2, 0.4, h, 19, TXT, H)
    dd = L.text(s, 1.45, y + 0.42, 6.1, 0.7, d, 15, MUTED, B, line_spacing=1.05)
    for k, o in enumerate((n, hh, dd)):
        tl.add(o, "rise" if k == 1 else "fade", t + 250 + i * 380 + k * 80, 600)
    y += 1.3
L.notes(s, "Insurance claims are often settled from photos. Editing those photos is easy: a dent can be pasted onto a door, "
           "or a damaged car can be placed into a different scene. Matching colour and brightness is easy, so the eye is fooled. "
           "Matching the direction the light comes from is hard, because it is spread across every surface in the picture. "
           "Pixel-level detectors can say an image looks manipulated, but a claims reviewer needs a reason they can check. "
           "On the right is a real photograph where the marked area was pasted from the same object lit by a different lamp.")
tl.write()

# 3 ---------------------------------------------------------------- answer
s, tl, t = slide((2.2, 5.9), fan=7.0, kicker="OUR ANSWER", title="Ask the light.")
sub = L.text(s, 0.75, 1.95, 11.5, 0.9, "Every region carries evidence of where its light came from. One light must explain them all.",
             20, MUTED, LT, line_spacing=1.05)
tl.add(sub, "fade", t, 700)
steps = [("Estimate", "the light direction for every region, from shading, highlights and silhouettes"),
         ("Agree", "on the light most regions share: the consensus"),
         ("Flag or abstain", "the region that does not fit, or say the evidence is too weak to judge")]
for i, (h, d) in enumerate(steps):
    x = 4.35 + i * 2.95
    card = L.rect(s, x, 3.0, 2.7, 1.85, PANEL, radius=0.14, line=LINE)
    num = L.text(s, x + 0.25, 3.18, 0.6, 0.4, str(i + 1), 18, AMBER, H)
    hh = L.text(s, x + 0.25, 3.58, 2.25, 0.4, h, 18, TXT, H)
    dd = L.text(s, x + 0.25, 3.98, 2.25, 0.85, d, 13, MUTED, B, line_spacing=1.05)
    for k, o in enumerate((card, num, hh, dd)):
        tl.add(o, "rise" if k == 0 else "fade", t + 300 + i * 300 + k * 60, 600)
verd = [("Consistent", GREEN, "one light explains every reliable region"),
        ("Suspicious", RED, "a region disagrees: send for human review"),
        ("Insufficient", GREY, "too little lighting evidence to judge"),
        ("Conflict", AMBER, "the references disagree among themselves")]
for i, (w, c, d) in enumerate(verd):
    x = 4.35 + i * 2.21
    dot = L.rect(s, x, 5.35, 0.16, 0.16, c, shape=MSO_SHAPE.OVAL)
    ww = L.text(s, x + 0.26, 5.24, 1.9, 0.35, w, 15, c, H)
    dd = L.text(s, x + 0.26, 5.6, 1.9, 0.7, d, 11.5, MUTED, B, line_spacing=1.0)
    for k, o in enumerate((dot, ww, dd)):
        tl.add(o, "fade", t + 1400 + i * 200 + k * 60, 500)
never = L.text(s, 4.35, 6.45, 8.4, 0.4, [[("A flag means “send for human review”, never “this is fraud”.", {"color": TXT})]], 13, MUTED, B)
tl.add(never, "fade", t + 2400, 600)
L.notes(s, "Our answer is to ask the light. Every region of a photo, a door panel, a tyre, a wall, carries evidence of where its light "
           "came from, in its shading, its highlights and its outline. In an honest photo one light explains all of them. "
           "LightAudit estimates the light for each region, finds the light most regions agree on, and flags the region that does not fit. "
           "When the evidence is too weak, for example on an overcast day, it abstains instead of guessing. There are four verdicts, "
           "and a flag always means send for human review, never that the claim is fraud. These three slides are the whole idea; the rest shows how and how well.")
tl.write()

# 4 ---------------------------------------------------------------- pipeline
s, tl, t = slide((-0.4, 3.33), fan=5.5, kicker="HOW IT WORKS", title="From pixels to a verdict, in five steps")
beam = L.pic(s, A / "beam.png", 0.0, 2.6, 6.0, 1.45, name="beam4")
tl.add(beam, "fade", t, 600)
tl.add(beam, "path", t, 5200, dx=0.62, dy=0.0, repeat="indefinite")
steps = [("Regions", "Segment the photo into surfaces (SAM), or use the area the reviewer marks"),
         ("Surface normals", "Predict each pixel's surface direction (DSINE, Depth Anything)"),
         ("Light maps", "Per region: which of 8,192 light directions fit its shading, highlights and silhouette"),
         ("Consensus", "Combine the maps; score each region by how far it falls from the others' light"),
         ("Verdict", "Compare with an alert level calibrated on clean photos, or abstain")]
for i, (h, d) in enumerate(steps):
    x = 0.75 + i * 2.45
    ring = L.rect(s, x, 2.88, 0.9, 0.9, BG, shape=MSO_SHAPE.OVAL, line=AMBER, line_w=1.5)
    num = L.text(s, x, 2.88, 0.9, 0.9, str(i + 1), 22, AMBER, H, align="c", anchor="m")
    hh = L.text(s, x, 4.1, 2.2, 0.4, h, 17, TXT, H)
    dd = L.text(s, x, 4.55, 2.2, 1.6, d, 13.5, MUTED, B, line_spacing=1.07)
    for k, o in enumerate((ring, num, hh, dd)):
        tl.add(o, "zoom" if k < 2 else "fade", t + 400 + i * 420 + k * 70, 600)
L.notes(s, "Here is the pipeline. First the photo is split into regions: automatically with the Segment Anything model, or around the "
           "area a reviewer marks. Second, a network predicts the surface direction at every pixel. Third, for each region we test 8,192 "
           "candidate light directions and keep a map of the ones that fit its shading, its specular highlights and its silhouette. "
           "Fourth, the maps are combined, and each region gets a leave-one-out score: how far it falls from the light the other regions agree on. "
           "Fifth, that score is compared with an alert level calibrated on clean photos, so the false-alarm rate is set in advance.")
tl.write()

# 5 ---------------------------------------------------------------- dome
s, tl, t = slide((7.2, 0.35), fan=5.0, kicker="THE EVIDENCE", title="Every region votes for\nwhere the light can be")
dome = L.pic(s, A / "pear_dark_dome.jpg", 8.1, 1.15, None, 5.6, radius=0.14, shadow={"blur": 40, "dist": 12, "alpha": 0.5})
tl.add(dome, "zoom", t, 900, **{"from": 0.8})
pts = [("A light map per region", "The coloured shell on the dome: every direction that could have lit this region."),
       ("Overlap is consensus", "Where the regions' maps meet is the light they share."),
       ("The paste sits apart", "In the pear, the marked area points 40° away from the rest. Shortfall 2.39, flagged.")]
y = 2.55
for i, (h, d) in enumerate(pts):
    hh = L.text(s, 0.75, y, 6.0, 0.4, h, 19, TXT, H)
    dd = L.text(s, 0.75, y + 0.42, 6.0, 0.75, d, 15, MUTED, B, line_spacing=1.05)
    tl.add(hh, "rise", t + 300 + i * 380, 600)
    tl.add(dd, "fade", t + 400 + i * 380, 600)
    y += 1.35
L.notes(s, "This is the light dome from our viewer. Around the photo is a sphere of light directions. Each region paints the directions "
           "that could explain its shading. Where the regions' maps overlap is the consensus light. In the pear example the marked area "
           "points 40 degrees away from the rest of the object, so its maps do not overlap and it is flagged. The reviewer sees exactly why.")
tl.write()

# 6 ---------------------------------------------------------------- dent check
s, tl, t = slide((12.9, 6.9), fan=6.0, kicker="FOR DENTS", title="Does the marked area share\nthe panel's light?")
photo = L.pic(s, A / "pear_dark_photo.jpg", 0.75, 2.45, None, 4.0, radius=0.12, shadow={"blur": 30, "dist": 10, "alpha": 0.5})
tl.add(photo, "zoom", t, 800, **{"from": 0.85})
tests = [("Shared light", "The area must follow the panel's light. It keeps its own brightness and colour, so colour matching cannot hide it."),
         ("Shared material", "One light, gain and offset fitted on the ring around the area must also predict the area itself.")]
for i, (h, d) in enumerate(tests):
    x = 4.85 + i * 3.95
    card = L.rect(s, x, 2.45, 3.7, 2.2, PANEL, radius=0.14, line=LINE)
    hh = L.text(s, x + 0.3, 2.7, 3.1, 0.4, h, 19, AMBER, H)
    dd = L.text(s, x + 0.3, 3.2, 3.15, 1.35, d, 14, MUTED, B, line_spacing=1.07)
    for k, o in enumerate((card, hh, dd)):
        tl.add(o, "rise" if k == 0 else "fade", t + 300 + i * 350 + k * 80, 600)
ret = L.rect(s, 4.85, 4.95, 7.65, 1.5, PANEL, radius=0.14, line=LINE)
r1 = L.text(s, 5.15, 5.15, 4.4, 1.2, [[("Paint is removed first.", {"color": TXT, "font": H})],
                                       [("Retinex separates paint from shading, guarded at the area's edge so the paste boundary is never mistaken for paint.", {})]],
            13.5, MUTED, B, line_spacing=1.05)
r2 = L.text(s, 9.75, 5.12, 2.6, 0.6, "0.74 → 0.86", 26, AMBER, LT, align="r")
r3 = L.text(s, 9.55, 5.72, 2.8, 0.6, "separation of clean and pasted areas (AUC)", 11, MUTED, B, align="r")
for k, o in enumerate((ret, r1, r2, r3)):
    tl.add(o, "rise" if k == 0 else "fade", t + 1100 + k * 120, 600)
L.notes(s, "Dents are too small to estimate a light of their own, so for damage we ask a narrower question: does the marked area share "
           "the light and the material of the panel around it? Two statistics test this. The shared-light test only asks that the area "
           "follows the panel's light, with its own brightness and colour, so a forger who matches colour cannot hide from it. The "
           "shared-material test asks one model fitted on the ring to also predict the area. Paint is removed first with Retinex, but "
           "guarded at the area's edge: unguarded Retinex calls the paste boundary paint and hides the splice. Guarding lifts the "
           "separation from 0.74 to 0.86 AUC on real objects.")
tl.write()

# 7 ---------------------------------------------------------------- results
s, tl, t = slide((12.9, 7.4), fan=6.5, kicker="ON REAL PHOTOS", title="Pasted areas caught, by\nhow far the light moved")
big = L.text(s, 0.75, 2.45, 4.2, 1.4, "45%", 96, AMBER, LT)
tl.add(big, "zoom", t, 900, **{"from": 0.6})
lab = L.text(s, 0.8, 3.95, 4.0, 1.0, [[("of pasted areas caught", {"color": TXT, "font": H})],
                                      [("at 5.2% false alarms, 10 held-out real objects, 400 clean and 400 pasted", {})]], 14, MUTED, B, line_spacing=1.1)
tl.add(lab, "fade", t + 400, 600)
extra = L.text(s, 0.8, 5.15, 4.1, 1.4, [[("32%", {"color": AMBER, "font": H, "size": 20}), ("  still caught after colour and brightness matching", {})],
                                        [("34%", {"color": AMBER, "font": H, "size": 20}), ("  caught at a stricter 2.2% false-alarm level", {})]],
              13.5, MUTED, B, line_spacing=1.2, space_after=6)
tl.add(extra, "fade", t + 800, 700)
ch = L.bar_chart(s, 5.4, 2.0, 7.3, 4.6, ["0–25°", "25–50°", "50–80°", "≥80°"], [("Caught", (36, 41, 47, 57))],
                 [AMBER], MUTED, B, axis_max=70, name="chart7", gap=70, label_size=13)
L.per_point_colors(ch, ["8A6A3A", "B8853F", "E39E44", AMBER])
tl.add(ch, "wipe", t + 500, 1200, dir="up")
cl = L.text(s, 5.6, 6.55, 7.0, 0.35, "angle between the paste's light and the scene's light", 12, DIM, B, align="c")
tl.add(cl, "fade", t + 1500, 500)
L.notes(s, "These are real photographs, not renders: the MIT Intrinsic Images objects, each shot under ten lamps, so we can paste part "
           "of an object from one lamp into a photo under another. Thresholds were set on ten objects and tested on ten others. "
           "At a 5.2 percent false-alarm rate the check catches 45 percent of pasted areas, rising to 57 percent when the light moved by "
           "80 degrees or more. After the forger matches colour and brightness it still catches 32 percent. These numbers are honest and "
           "modest; the next slides show where the method stops.")
tl.write()

# 8 ---------------------------------------------------------------- abstain
s, tl, t = slide((6.3, -0.35), fan=5.0, kicker="KNOWING WHEN NOT TO ANSWER", title="It says when the light cannot decide")
sun2 = L.pic(s, A / "sun_core.png", 9.9 - 0.8, -0.75, 1.6, 1.6, name="sun2")
tl.add(sun2, "zoom", t + 1400, 900, **{"from": 0.2})
tl.add(sun2, "pulse", t + 2300, 2200, scale=1.12, repeat="indefinite")
cards = [("consistent.png", "Consistent", GREEN, "One sun, clean scene", "0 of 5 clean scenes flagged"),
         ("overcast.png", "Insufficient", GREY, "Overcast: soft light, no direction", "4 of 5 abstain"),
         ("twosuns.png", "Conflict", AMBER, "Two light sources", "3 of 5 called a conflict, 2 abstain")]
for i, (img, w, c, d, n) in enumerate(cards):
    x = 0.75 + i * 4.05
    im = L.pic(s, A / img, x, 2.2, 3.75, 2.55, radius=0.12)
    ww = L.text(s, x, 4.95, 3.75, 0.4, w, 19, c, H)
    dd = L.text(s, x, 5.38, 3.75, 0.4, d, 14, TXT, B)
    nn = L.text(s, x, 5.78, 3.75, 0.4, n, 13, MUTED, B)
    for k, o in enumerate((im, ww, dd, nn)):
        tl.add(o, "rise" if k == 0 else "fade", t + 200 + i * 350 + k * 80, 650)
note = L.text(s, 0.75, 6.35, 11.8, 0.4, "Rendered test scenes. A wrong guess costs more than “not enough evidence”, so abstaining is a feature.",
              12.5, DIM, B)
tl.add(note, "fade", t + 1800, 600)
L.notes(s, "A good auditor knows when not to answer. Under an overcast sky the light has no direction, and the soft-light check makes "
           "LightAudit abstain in four of five such scenes instead of guessing. With two suns there is no single light to agree on; a "
           "cast-shadow check spots the two shadow levels and calls a conflict in three of five, abstaining on the other two. Clean "
           "one-sun scenes were never flagged. These are rendered scenes from our test suite. Notice the second sun that appeared on this slide.")
tl.write()

# 9 ---------------------------------------------------------------- viewer
s, tl, t = slide((13.4, 1.2), fan=5.5, kicker="EXPLAINABLE BY DESIGN", title="Every number can be inspected")
shot = L.pic(s, A / "car_dark_full.jpg", 0.75, 2.05, None, 4.75, radius=0.1, shadow={"blur": 40, "dist": 14, "alpha": 0.55})
tl.add(shot, "zoom", t, 900, **{"from": 0.9})
feats = [("Verdict and why", "the score, the alert level and the reason in plain words"),
         ("Relight the photo", "re-shade each region under any light you choose"),
         ("Light dome", "each region's light map, the consensus, credible cones"),
         ("Sky map", "drag the sun; the photo and the verdict update live")]
y = 2.1
for i, (h, d) in enumerate(feats):
    hh = L.text(s, 9.65, y, 3.0, 0.4, h, 16, TXT, H)
    dd = L.text(s, 9.65, y + 0.38, 3.0, 0.7, d, 12.5, MUTED, B, line_spacing=1.05)
    tl.add(hh, "rise", t + 500 + i * 300, 600)
    tl.add(dd, "fade", t + 600 + i * 300, 600)
    y += 1.15
L.notes(s, "Everything the audit computes is visible in the viewer. The left rail gives the verdict, the score against the alert level "
           "and the reason in plain words. The photo can be relit under any light. The dome shows every region's light map and the consensus. "
           "The sky map lets a reviewer drag the sun and watch the photo and the what-if verdict change. Here a car was pasted from a light "
           "95 degrees away, and the viewer says so in one sentence.")
tl.write()

# 10 ---------------------------------------------------------------- limits
s, tl, t = slide((6.7, 7.6), fan=6.5, kicker="WE ATTACK OURSELVES", title="Where it breaks, measured")
ch = L.bar_chart(s, 0.6, 2.0, 6.2, 4.4, ["Plain paste", "8 px feather", "Poisson blend"], [("Caught", (38.5, 25.8, 4.8))],
                 [AMBER], MUTED, B, axis_max=50, name="chart10", gap=80, num_fmt='0.0"%"', label_size=13)
L.per_point_colors(ch, [AMBER, "B8853F", RED])
tl.add(ch, "wipe", t, 1200, dir="up")
cl = L.text(s, 0.75, 6.4, 6.0, 0.35, "marked-area check, held-out real objects, same alert level", 12, DIM, B, align="c")
tl.add(cl, "fade", t + 700, 500)
lims = [("Re-shading", "A forger who re-renders the pasted object under the scene's light passes: 0 of 8 caught."),
        ("Whole objects in real scenes", "Telling a pasted object from a real one is at chance on real indoor scenes (AUC 0.49–0.59)."),
        ("Blending", "Poisson blending hides the paste edge that the dent check relies on.")]
y = 2.1
for i, (h, d) in enumerate(lims):
    hh = L.text(s, 7.4, y, 5.3, 0.4, h, 17, TXT, H)
    dd = L.text(s, 7.4, y + 0.4, 5.3, 0.8, d, 13.5, MUTED, B, line_spacing=1.05)
    tl.add(hh, "rise", t + 600 + i * 350, 600)
    tl.add(dd, "fade", t + 700 + i * 350, 600)
    y += 1.3
end = L.text(s, 7.4, 6.05, 5.3, 0.6, [[("Necessary, not sufficient: ", {"color": AMBER, "font": H}), ("one strong check among several.", {"color": TXT})]], 14, TXT, B)
tl.add(end, "fade", t + 1900, 600)
L.notes(s, "We built an attack lab and ran it against our own detector. A forger who blends the paste over 8 pixels lowers detection "
           "from 38.5 to 25.8 percent, and Poisson blending brings it to 4.8. A forger who re-renders the pasted object under the scene's "
           "light passes completely. And deciding whether a whole object was pasted into a real indoor scene is at chance with today's "
           "surface-normal predictors. So lighting is a necessary check, not a sufficient one, and we say so.")
tl.write()

# 11 ---------------------------------------------------------------- next
s, tl, t = slide((10.8, 0.9), fan=6.0, kicker="WHAT IS NEXT", title="Four steps toward real claims")
nxt = [("Cast-shadow geometry", "Object–shadow pairs must meet at one light. No surface normals needed. Rendered tests: 0 of 60 false alarms, 92–93% caught at ≥60°."),
       ("Real dents", "Run genuine damage photos (CarDD, 4,000 images) to measure false alarms on real scratches, dirt and primer."),
       ("Learned paint removal", "Swap Retinex for a learned intrinsic decomposition; the benchmark is measured and being compared."),
       ("Real car photos", "Clean directional-light car photos and self-made splices, to test the target domain end to end.")]
for i, (h, d) in enumerate(nxt):
    x = 0.75 + (i % 2) * 6.05
    y = 2.3 + (i // 2) * 2.1
    card = L.rect(s, x, y, 5.75, 1.8, PANEL, radius=0.14, line=LINE)
    num = L.text(s, x + 0.3, y + 0.25, 0.5, 0.4, f"0{i + 1}", 18, AMBER, LT)
    hh = L.text(s, x + 0.85, y + 0.25, 4.6, 0.4, h, 18, TXT, H)
    dd = L.text(s, x + 0.85, y + 0.72, 4.6, 1.2, d, 13, MUTED, B, line_spacing=1.07)
    for k, o in enumerate((card, num, hh, dd)):
        tl.add(o, "rise" if k == 0 else "fade", t + 200 + i * 300 + k * 70, 600)
L.notes(s, "Four next steps. First, cast-shadow geometry: lines from object points through their shadows must meet at one light, and "
           "this needs no surface normals at all; on rendered tests it had no false alarms and caught over 90 percent of second-sun "
           "objects at 60 degrees or more. Second, real dent photos from the CarDD dataset, to measure false alarms on genuine damage. "
           "Third, a learned paint-and-shading decomposition in place of Retinex. Fourth, real car photos to test the target domain.")
tl.write()

# 12 ---------------------------------------------------------------- close
s, tl, t = slide((6.67, 3.1), fan=12.0, core=3.4, footer=False)
q = L.text(s, 1.0, 4.65, 11.33, 0.9, "One light. Every region. Shown, not asserted.", 34, TXT, LT, align="c")
tl.add(q, "rise", 600, 900)
nm = L.text(s, 1.0, 5.6, 11.33, 0.5, "LightAudit", 22, AMBER, H, align="c")
tl.add(nm, "fade", 1200, 700)
lk = L.text(s, 1.0, 6.15, 11.33, 0.8, [[("github.com/Barath-BDK/LightAudit", {"color": TXT})], [("Barath Dharshan · CS23I1005", {})]], 14, MUTED, B, align="c", line_spacing=1.2)
tl.add(lk, "fade", 1600, 700)
L.notes(s, "LightAudit: one light, every region, and every conclusion shown rather than asserted. The code, the benchmarks and the "
           "viewer are on GitHub. Thank you.")
tl.write()

prs.save(OUT)
print("saved", OUT)
