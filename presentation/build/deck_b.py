"""Deck B, "Prism": bright editorial slides. One white beam enters a prism and splits into a spectrum; the spectral
rays are the motif (one ray that bends away = the pasted region). Prism transitions between sections, Morph within.

    python presentation/build/deck_b.py      -> presentation/LightAudit_B_Prism.pptx
"""
from pathlib import Path

from pptx.enum.shapes import MSO_SHAPE

import pptlib as L

HERE = Path(__file__).resolve().parent
A = HERE / "assets"
OUT = HERE.parent / "LightAudit_B_Prism.pptx"

BG, CARD, LINE = "F7F7F5", "FFFFFF", "E3E3DF"
INK, MUTED, DIM = "15171C", "555B66", "8A909A"
RED, ORANGE, YELLOW, GREEN, BLUE, VIOLET = "E5484D", "F76B15", "E0A100", "2F9E44", "0B6BDE", "6E56CF"
SPEC = [RED, ORANGE, YELLOW, GREEN, BLUE, VIOLET]
GREY = "6B7280"
H, B = "Georgia", "Segoe UI"

prs = L.new_deck()
N = [0]


def prism(s, x, y, w, beam_from=None, fan=True, fan_w=None, odd=False):
    """The motif: a glass prism at (x, y) with width w; a white-ink beam entering from the left and the spectrum leaving right."""
    h = w * 0.87
    parts = {}
    if beam_from is not None:
        parts["beam"] = L.line(s, beam_from, y + h * 0.62, x + w * 0.30, y + h * 0.58, INK, 2.25, name="!!beam")
    if fan:
        fw = fan_w or w * 3.2
        parts["fan"] = L.pic(s, A / ("spectrum_fan_odd.png" if odd else "spectrum_fan.png"), x + w * 0.62, y + h * 0.55 - fw * 0.29, fw, fw * 0.583, name="!!fan")
    parts["prism"] = L.rect(s, x, y, w, h, "FFFFFF", alpha=0.55, shape=MSO_SHAPE.ISOSCELES_TRIANGLE, line=INK, line_w=1.5, name="!!prism")
    return parts


def slide(trans="morph", kicker=None, title=None, kicker_color=BLUE, footer=True, title_w=8.2):
    s = L.blank(prs, BG)
    N[0] += 1
    tl = L.Timeline(s)
    if N[0] > 1:
        if trans == "prism":
            L.transition(s, "prism", 1500, isContent="1")
        else:
            L.transition(s, "morph", 1500)
    if footer:
        L.text(s, 0.75, 7.0, 4, 0.3, "LightAudit", 10, DIM, B, name=f"foot{N[0]}")
        L.text(s, 11.6, 7.0, 1, 0.3, str(N[0]), 10, DIM, B, align="r", name=f"num{N[0]}")
    t = 300
    if kicker:
        k = L.text(s, 0.75, 0.6, 8, 0.35, kicker, 12, kicker_color, B, bold=True, char_spacing=1.2)
        tl.add(k, "fade", t, 500)
        t += 120
    if title:
        tt = L.text(s, 0.75, 0.95, title_w, 1.4, title, 34, INK, H, line_spacing=1.0)
        tl.add(tt, "rise", t, 700)
        t += 350
    return s, tl, t


def card(s, x, y, w, h):
    return L.rect(s, x, y, w, h, CARD, radius=0.12, line=LINE)


def corner_prism(s, tl):
    """Small prism in the top-right corner on content slides; Morph carries it between positions."""
    p = prism(s, 11.55, 0.45, 1.05, fan=True, fan_w=2.2)
    tl.add(p["fan"], "breathe", 0, 2600, to=0.55, repeat="indefinite")
    return p


# 1 ---------------------------------------------------------------- title
s, tl, t = slide(footer=False)
p = prism(s, 7.45, 1.75, 2.9, beam_from=6.2, fan_w=7.5)
tl.add(p["beam"], "wipe", 200, 700, dir="right")
tl.add(p["prism"], "zoom", 750, 700, **{"from": 0.7})
tl.add(p["fan"], "wipe", 1300, 1600, dir="right")
tl.add(p["fan"], "breathe", 3000, 2800, to=0.6, repeat="indefinite")
for o, a in [
    (L.text(s, 0.8, 2.0, 6.4, 1.1, "LightAudit", 64, INK, H), ("rise", 400, 900)),
    (L.text(s, 0.82, 3.2, 6.4, 0.7, "Light leaves evidence.", 28, BLUE, H, italic=True), ("rise", 900, 800)),
    (L.text(s, 0.82, 4.05, 5.9, 1.0, "An explainable lighting-consistency audit for edited photos, built for reviewing damage photos in insurance claims", 16, MUTED, B, line_spacing=1.1), ("fade", 1400, 800)),
    (L.text(s, 0.82, 5.9, 6.5, 0.8, [[("Barath Dharshan", {"color": INK, "bold": True})], [("CS23I1005 · Interactive Computer Graphics · Semester 7", {})]], 13, MUTED, B), ("fade", 1800, 700)),
]:
    tl.add(o, a[0], a[1], a[2])
L.notes(s, "LightAudit starts from a simple fact: light leaves evidence. Every surface in a photo records the direction it was lit from. "
           "When part of a photo is pasted in from another picture, it brings its own light with it, and that disagreement can be measured "
           "and shown. The motivating case is reviewing damage photos in insurance claims.")
tl.write()

# 2 ---------------------------------------------------------------- problem
s, tl, t = slide(kicker="THE PROBLEM", title="Edited claim photos\npass the eye", kicker_color=RED)
corner_prism(s, tl)
photo = L.pic(s, A / "pear_light_photo.jpg", 8.1, 1.55, None, 4.85, radius=0.12, shadow={"blur": 28, "dist": 8, "alpha": 0.18})
tl.add(photo, "zoom", t, 900, **{"from": 0.88})
cap = L.text(s, 8.1, 6.5, 4.2, 0.4, "Real photo: the outlined area was pasted from a shot under another lamp", 11, DIM, B)
tl.add(cap, "fade", t + 500, 600)
rows = [(RED, "Edits are cheap", "A dent pasted onto a door; a whole car dropped into another scene."),
        (ORANGE, "Colour is easy to match", "Brightness and colour can be harmonised in seconds. The direction of the light cannot."),
        (BLUE, "Reviewers need a reason", "A bare “fake” score cannot be checked, argued or explained to a customer.")]
y = 2.75
for i, (c, h, d) in enumerate(rows):
    dot = L.rect(s, 0.8, y + 0.1, 0.22, 0.22, c, shape=MSO_SHAPE.OVAL)
    hh = L.text(s, 1.25, y, 6.2, 0.4, h, 19, INK, H)
    dd = L.text(s, 1.25, y + 0.45, 6.2, 0.7, d, 14.5, MUTED, B, line_spacing=1.07)
    for k, o in enumerate((dot, hh, dd)):
        tl.add(o, "zoom" if k == 0 else ("rise" if k == 1 else "fade"), t + 300 + i * 380 + k * 70, 600)
    y += 1.25
L.notes(s, "Claims are increasingly settled from photos, and photos are easy to edit. A dent can be pasted onto a door, or a damaged car "
           "dropped into another scene. Colour and brightness are easy to harmonise, so the edit passes the eye. What is hard to fake is "
           "the direction of the light, because it is spread across every surface in the picture. And a reviewer needs more than a bare "
           "fake score: they need a reason they can check. On the right, a real photo whose outlined area came from a shot under another lamp.")
tl.write()

# 3 ---------------------------------------------------------------- answer: one light in, every region must agree
s, tl, t = slide(trans="prism", kicker="OUR ANSWER", title="One light in.\nEvery region must agree.", title_w=6.2)
p = prism(s, 5.75, 2.55, 2.1, beam_from=5.15, fan_w=6.6, odd=True)
tl.add(p["beam"], "wipe", t, 600, dir="right")
tl.add(p["fan"], "wipe", t + 500, 1500, dir="right")
lab = L.text(s, 9.55, 5.55, 3.4, 0.7, [[("one region bends away:", {"color": BLUE, "bold": True})], [("its light came from somewhere else", {})]], 12.5, MUTED, B)
tl.add(lab, "fade", t + 2000, 700)
steps = [("1", "Read the light", "of every region, from its shading, highlights and outline"),
         ("2", "Find the agreement", "the light most regions share"),
         ("3", "Flag or abstain", "the region that does not fit, or “too little evidence”")]
y = 2.65
for i, (n, h, d) in enumerate(steps):
    nn = L.text(s, 0.8, y, 0.4, 0.4, n, 20, BLUE, H)
    hh = L.text(s, 1.25, y, 3.75, 0.4, h, 17, INK, H)
    dd = L.text(s, 1.25, y + 0.38, 3.75, 0.6, d, 13, MUTED, B, line_spacing=1.05)
    for k, o in enumerate((nn, hh, dd)):
        tl.add(o, "rise" if k == 1 else "fade", t + 300 + i * 330 + k * 70, 600)
    y += 1.05
verd = [("Consistent", GREEN), ("Suspicious", RED), ("Insufficient", GREY), ("Conflict", ORANGE)]
x = 0.8
for i, (w, c) in enumerate(verd):
    pill = L.rect(s, x, 6.1, 1.55, 0.42, CARD, radius=0.21, line=c, line_w=1.25)
    tx = L.text(s, x, 6.1, 1.55, 0.42, w, 12.5, c, B, bold=True, align="c", anchor="m")
    tl.add(pill, "zoom", t + 1500 + i * 150, 500)
    tl.add(tx, "fade", t + 1550 + i * 150, 500)
    x += 1.7
nv = L.text(s, 7.75, 6.13, 5.0, 0.4, "A flag means “send for human review”, never “fraud”", 12.5, DIM, B)
tl.add(nv, "fade", t + 2200, 600)
L.notes(s, "Here is the whole idea in one picture. One light enters the scene. Every region of an honest photo reflects that same light, "
           "like the rays of a spectrum leaving one prism in order. A pasted region carries the light of another photo, so its ray bends "
           "away. LightAudit reads the light of every region, finds the light most of them agree on, and flags the one that does not fit, "
           "or says there is too little evidence to judge. Four verdicts, and a flag always means send for human review, never fraud.")
tl.write()

# 4 ---------------------------------------------------------------- method as a spectrum
s, tl, t = slide(kicker="HOW IT WORKS", title="Six steps from photo to verdict")
corner_prism(s, tl)
steps = [("Regions", "SAM segments the photo into surfaces, or the reviewer marks an area"),
         ("Normals", "DSINE and Depth Anything predict each pixel's surface direction"),
         ("Light maps", "each region scores 8,192 light directions on a sphere"),
         ("Cues", "shading fit, specular highlights, silhouettes"),
         ("Consensus", "leave-one-out: how far each region falls from the others' light"),
         ("Verdict", "alert level calibrated on clean photos; abstain when evidence is weak")]
bar_y = 2.65
for i, (h, d) in enumerate(steps):
    x = 0.75 + i * 2.0
    seg = L.rect(s, x, bar_y, 1.85, 0.16, SPEC[i], radius=0.08)
    num = L.text(s, x, bar_y + 0.45, 1.85, 0.6, f"0{i + 1}", 30, SPEC[i], H)
    hh = L.text(s, x, bar_y + 1.2, 1.85, 0.4, h, 17, INK, H)
    dd = L.text(s, x, bar_y + 1.65, 1.8, 1.5, d, 12.5, MUTED, B, line_spacing=1.07)
    for k, o in enumerate((seg, num, hh, dd)):
        tl.add(o, "wipe" if k == 0 else ("rise" if k < 3 else "fade"), t + 200 + i * 300 + k * 70, 500 if k else 400, dir="right")
foot = L.text(s, 0.75, 5.9, 11.8, 0.5, [[("Correct on real light: ", {"color": INK, "bold": True}),
                                          ("given the true shape of a grey ball, the estimate is within 1–3° of the measured light in six real scenes. The weak link is the predicted shape.", {})]],
              13, MUTED, B, line_spacing=1.1)
tl.add(foot, "fade", t + 2300, 700)
L.notes(s, "The method in six steps. Segment the photo into regions, or take the area the reviewer marks. Predict surface directions with two "
           "networks. For each region, score 8,192 candidate light directions on a sphere, using three cues: how well the shading fits, where "
           "specular highlights sit, and the silhouette. Then the consensus: each region is scored by how far it falls from the light the "
           "others agree on. Finally the verdict, against an alert level calibrated on clean photos. The light estimator itself is accurate: "
           "with the true shape of a grey ball it lands within one to three degrees of the measured light. The weak link is predicted shape.")
tl.write()

# 5 ---------------------------------------------------------------- the evidence on screen
s, tl, t = slide(trans="prism", kicker="THE EVIDENCE, ON SCREEN", title="A verdict you can check")
corner_prism(s, tl)
shot = L.pic(s, A / "pear_light_full.jpg", 0.75, 2.0, None, 4.75, radius=0.1, shadow={"blur": 30, "dist": 10, "alpha": 0.18})
tl.add(shot, "zoom", t, 900, **{"from": 0.9})
scan = L.pic(s, A / "scan_blue.png", 0.75, 2.0, 0.45, 4.75, name="scan5")
tl.add(scan, "fade", t + 900, 400)
tl.add(scan, "path", t + 900, 4200, dx=0.52, dy=0.0, repeat="indefinite", autorev=True)
right_x = 0.75 + shot.width / 914400 + 0.45
feats = [(RED, "The verdict and the reason", "“The brightness of ROI is not predicted by the shading of the panel around it”"),
         (ORANGE, "Your own light", "drag the sun on the sky map; the photo is relit and the what-if verdict updates"),
         (BLUE, "Every region's vote", "the light dome shows each region's map and the consensus")]
y = 2.1
for i, (c, h, d) in enumerate(feats):
    dot = L.rect(s, right_x, y + 0.08, 0.18, 0.18, c, shape=MSO_SHAPE.OVAL)
    hh = L.text(s, right_x + 0.35, y, 12.6 - right_x - 0.35, 0.4, h, 16, INK, H)
    dd = L.text(s, right_x + 0.35, y + 0.4, 12.6 - right_x - 0.35, 1.0, d, 12.5, MUTED, B, line_spacing=1.07)
    for k, o in enumerate((dot, hh, dd)):
        tl.add(o, "zoom" if k == 0 else "fade", t + 600 + i * 350 + k * 70, 600)
    y += 1.45
L.notes(s, "This is the viewer on the pear photo. The rail on the left gives the verdict and the reason in a sentence. The sky map at the "
           "bottom right lets a reviewer move the sun and watch the photo relight and the what-if verdict update. The dome shows every "
           "region's light map. Nothing is a black box: every number on the screen can be inspected.")
tl.write()

# 6 ---------------------------------------------------------------- dent check
s, tl, t = slide(kicker="FOR DENTS", title="A marked area must share\nthe panel's light and paint")
corner_prism(s, tl)
photo = L.pic(s, A / "pear_light_photo.jpg", 0.75, 2.5, None, 3.9, radius=0.12, shadow={"blur": 24, "dist": 8, "alpha": 0.18})
tl.add(photo, "zoom", t, 800, **{"from": 0.88})
px = 0.75 + photo.width / 914400 + 0.45
cw = (12.6 - px - 0.3) / 2
tests = [(BLUE, "Shared light", "The area follows the panel's light with its own brightness and colour, so colour matching cannot hide it."),
         (VIOLET, "Shared material", "One light, gain and offset fitted on the ring around the area must also predict the area.")]
for i, (c, h, d) in enumerate(tests):
    x = px + i * (cw + 0.3)
    cd = card(s, x, 2.5, cw, 2.05)
    bar = L.rect(s, x + 0.3, 2.78, 0.5, 0.08, c, radius=0.04)
    hh = L.text(s, x + 0.3, 2.98, cw - 0.6, 0.4, h, 18, INK, H)
    dd = L.text(s, x + 0.3, 3.45, cw - 0.55, 1.05, d, 12.5, MUTED, B, line_spacing=1.07)
    for k, o in enumerate((cd, bar, hh, dd)):
        tl.add(o, "rise" if k == 0 else "fade", t + 300 + i * 350 + k * 70, 600)
rc = card(s, px, 4.8, 2 * cw + 0.3, 1.6)
r1 = L.text(s, px + 0.3, 5.0, 2 * cw - 2.6, 1.3, [[("Paint is removed first, carefully. ", {"color": INK, "bold": True}),
                                                   ("Retinex separates paint from shading but is told never to read the area's own edge as paint, which would hide the paste.", {})]],
            12.5, MUTED, B, line_spacing=1.07)
r2 = L.text(s, px + 2 * cw - 2.3, 4.98, 2.3, 0.6, "0.74 → 0.86", 24, BLUE, H, align="r")
r3 = L.text(s, px + 2 * cw - 2.45, 5.6, 2.45, 0.6, "AUC, clean vs pasted, real objects", 11, DIM, B, align="r")
for k, o in enumerate((rc, r1, r2, r3)):
    tl.add(o, "rise" if k == 0 else "fade", t + 1100 + k * 120, 600)
L.notes(s, "A dent is too small and too shallow to have a light of its own, so for damage we ask whether the marked area shares the light "
           "and the paint of the panel around it. The shared-light test lets the area keep its own brightness and colour, so colour "
           "matching cannot hide a paste. The shared-material test asks a single model fitted on the ring to predict the area too. "
           "Paint is removed first with Retinex, but guarded at the area's edge; without that guard Retinex explains the paste boundary as "
           "paint. The guard lifts separation from 0.74 to 0.86 AUC on real objects.")
tl.write()

# 7 ---------------------------------------------------------------- results
s, tl, t = slide(trans="prism", kicker="ON REAL PHOTOS", title="The wider the light moved,\nthe more we catch")
corner_prism(s, tl)
big = L.text(s, 0.75, 2.55, 4.3, 1.3, "45%", 84, INK, H)
tl.add(big, "zoom", t, 900, **{"from": 0.6})
lab = L.text(s, 0.8, 3.95, 4.2, 0.9, [[("of pasted areas caught", {"color": INK, "bold": True})], [("at 5.2% false alarms on 10 held-out real objects", {})]], 13.5, MUTED, B, line_spacing=1.1)
tl.add(lab, "fade", t + 400, 600)
for i, (n, d) in enumerate([("32%", "still caught after colour and brightness matching"), ("34%", "caught at a stricter 2.2% false-alarm level")]):
    y = 5.05 + i * 0.7
    nn = L.text(s, 0.8, y, 1.0, 0.5, n, 20, BLUE, H)
    dd = L.text(s, 1.75, y + 0.06, 3.3, 0.6, d, 12.5, MUTED, B, line_spacing=1.05)
    tl.add(nn, "fade", t + 800 + i * 200, 600)
    tl.add(dd, "fade", t + 850 + i * 200, 600)
ch = L.bar_chart(s, 5.5, 2.1, 7.2, 4.45, ["0–25°", "25–50°", "50–80°", "≥80°"], [("Caught", (36, 41, 47, 57))],
                 [BLUE], MUTED, B, axis_max=70, name="chart7b", gap=70, label_size=13)
L.per_point_colors(ch, [VIOLET, BLUE, GREEN, ORANGE])
tl.add(ch, "wipe", t + 500, 1200, dir="up")
cl = L.text(s, 5.7, 6.55, 6.9, 0.35, "how far the paste's light is from the scene's light", 12, DIM, B, align="c")
tl.add(cl, "fade", t + 1500, 500)
L.notes(s, "Measured on real photographs from the MIT Intrinsic Images set, where each object is shot under ten lamps, so part of one photo "
           "can be pasted into another under a different light. Thresholds come from ten objects; these rates are on ten others. At 5.2 "
           "percent false alarms we catch 45 percent of pasted areas, and 57 percent when the light moved by 80 degrees or more. After "
           "colour and brightness matching we still catch 32 percent.")
tl.write()

# 8 ---------------------------------------------------------------- four verdicts
s, tl, t = slide(kicker="FOUR VERDICTS", title="It knows when to say “I cannot tell”")
corner_prism(s, tl)
cards = [("consistent.png", "Consistent", GREEN, "One light explains every reliable region", "0 of 5 clean scenes flagged"),
         ("car_splice.png", "Suspicious", RED, "A region disagrees with the scene's light", "car pasted from 95° away"),
         ("overcast.png", "Insufficient", GREY, "Soft overcast light has no direction", "4 of 5 abstain"),
         ("twosuns.png", "Conflict", ORANGE, "Two lights: the references disagree", "3 of 5 called a conflict")]
for i, (img, w, c, d, n) in enumerate(cards):
    x = 0.75 + i * 3.0
    cd = card(s, x, 2.3, 2.8, 3.8)
    im = L.pic(s, A / img, x + 0.15, 2.45, 2.5, 1.7, radius=0.08)
    ww = L.text(s, x + 0.25, 4.3, 2.4, 0.4, w, 18, c, H)
    dd = L.text(s, x + 0.25, 4.75, 2.35, 0.9, d, 12.5, INK, B, line_spacing=1.07)
    nn = L.text(s, x + 0.25, 5.75, 2.35, 0.6, n, 11.5, MUTED, B)
    for k, o in enumerate((cd, im, ww, dd, nn)):
        tl.add(o, "rise" if k == 0 else "fade", t + 200 + i * 300 + k * 60, 600)
L.notes(s, "Four verdicts. Consistent when one light explains every reliable region: clean rendered scenes were never flagged. Suspicious "
           "when a region disagrees, like this car pasted from a light 95 degrees away. Insufficient when the light has no direction, as "
           "under an overcast sky, where LightAudit abstains in four of five scenes. Conflict when there are two lights, spotted from two "
           "levels of cast shadow in three of five scenes. The bottom-line numbers here are from rendered test scenes.")
tl.write()

# 9 ---------------------------------------------------------------- limits
s, tl, t = slide(trans="prism", kicker="STRESS-TESTED BY US", title="Where it breaks, in numbers", kicker_color=RED)
corner_prism(s, tl)
ch = L.bar_chart(s, 0.6, 2.05, 6.3, 4.35, ["Plain paste", "8 px feather", "Poisson blend"], [("Caught", (38.5, 25.8, 4.8))],
                 [BLUE], MUTED, B, axis_max=50, name="chart9b", gap=80, num_fmt='0.0"%"', label_size=13)
L.per_point_colors(ch, [BLUE, VIOLET, RED])
tl.add(ch, "wipe", t, 1200, dir="up")
cl = L.text(s, 0.75, 6.4, 6.1, 0.35, "marked-area check, held-out real objects, same alert level", 12, DIM, B, align="c")
tl.add(cl, "fade", t + 700, 500)
lims = [("Re-shaded pastes pass", "A forger who re-renders the object under the scene's light: 0 of 8 caught."),
        ("Whole objects in real rooms", "At chance today (AUC 0.49–0.59): predicted surface shape is too rough."),
        ("Tried and dropped", "A boundary-seam test and a light-colour test: measured, did not hold up, removed.")]
y = 2.15
for i, (h, d) in enumerate(lims):
    cd = card(s, 7.35, y, 5.25, 1.15)
    hh = L.text(s, 7.6, y + 0.15, 4.8, 0.4, h, 15.5, INK, H)
    dd = L.text(s, 7.6, y + 0.53, 4.85, 0.6, d, 12, MUTED, B, line_spacing=1.05)
    for k, o in enumerate((cd, hh, dd)):
        tl.add(o, "rise" if k == 0 else "fade", t + 500 + i * 320 + k * 70, 600)
    y += 1.32
end = L.text(s, 7.35, 6.15, 5.3, 0.5, [[("Lighting is necessary, not sufficient: ", {"color": RED, "bold": True}), ("one strong check among several.", {})]], 13, INK, B)
tl.add(end, "fade", t + 1600, 600)
L.notes(s, "We attacked our own detector. Feathering the paste over 8 pixels lowers detection from 38.5 to 25.8 percent; Poisson blending "
           "brings it to 4.8. Re-rendering the pasted object under the scene's light passes completely, and judging whole pasted objects in "
           "real indoor scenes is at chance with today's shape predictors. Two ideas we tried, a seam test and a light-colour test, were "
           "measured and dropped. Lighting evidence is necessary, not sufficient.")
tl.write()

# 10 ---------------------------------------------------------------- roadmap
s, tl, t = slide(kicker="NEXT", title="Toward real claims")
corner_prism(s, tl)
line_y = 2.95
ln = L.line(s, 0.9, line_y, 12.4, line_y, LINE, 2.0)
tl.add(ln, "wipe", t, 1000, dir="right")
nxt = [(VIOLET, "Cast shadows", "Object–shadow lines must meet at one light; no shape model needed. Rendered tests: 0/60 false alarms, 92–93% caught at ≥60°."),
       (BLUE, "Real dents", "Genuine damage photos (CarDD) to measure false alarms on scratches, dirt and primer."),
       (GREEN, "Learned paint removal", "A learned intrinsic decomposition in place of Retinex, benchmark under way."),
       (ORANGE, "Real car photos", "Directional-light car photos and self-made splices, end to end.")]
for i, (c, h, d) in enumerate(nxt):
    x = 0.9 + i * 2.95
    dot = L.rect(s, x, line_y - 0.16, 0.32, 0.32, c, shape=MSO_SHAPE.OVAL)
    hh = L.text(s, x, line_y + 0.45, 2.75, 0.4, h, 17, INK, H)
    dd = L.text(s, x, line_y + 0.92, 2.7, 1.9, d, 12.5, MUTED, B, line_spacing=1.08)
    for k, o in enumerate((dot, hh, dd)):
        tl.add(o, "zoom" if k == 0 else "fade", t + 500 + i * 380 + k * 70, 600)
L.notes(s, "Next: cast-shadow geometry, which needs no shape model and on rendered tests had no false alarms; genuine dent photos from the "
           "CarDD dataset; a learned paint-and-shading decomposition; and real car photos to test the target domain end to end.")
tl.write()

# 11 ---------------------------------------------------------------- close
s, tl, t = slide(footer=False)
p = prism(s, 5.25, 0.9, 2.8, beam_from=1.8, fan_w=7.6)
tl.add(p["fan"], "breathe", 0, 2800, to=0.6, repeat="indefinite")
th = L.text(s, 1.0, 4.35, 11.33, 0.9, "Thank you", 44, INK, H, align="c")
tl.add(th, "rise", 500, 900)
q = L.text(s, 1.0, 5.25, 11.33, 0.5, "Light leaves evidence. LightAudit shows it.", 18, BLUE, H, italic=True, align="c")
tl.add(q, "fade", 1100, 700)
lk = L.text(s, 1.0, 5.95, 11.33, 0.8, [[("github.com/Barath-BDK/LightAudit", {"color": INK})], [("Barath Dharshan · CS23I1005", {})]], 13, MUTED, B, align="c", line_spacing=1.2)
tl.add(lk, "fade", 1500, 700)
L.notes(s, "Light leaves evidence, and LightAudit shows it. The code, benchmarks and viewer are on GitHub. Thank you.")
tl.write()

prs.save(OUT)
print("saved", OUT)
