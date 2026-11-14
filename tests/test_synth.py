import cv2
import numpy as np

from lightaudit.grid import angle_deg
from lightaudit.synth import get_sample, light_at_angle, make_scene, paste
from lightaudit.synth import render as rd
from lightaudit.synth.scenes import OBJ_CAR, simulate_normals


def test_rerender_and_light_convention():
    s = get_sample(4000, "normal")
    lin = rd.shade(s.G, s.scene, s.lights_cam(), s.shadows)
    assert np.allclose(lin, s.rgb_lin)
    assert np.allclose(s.light_cam, s.scene.R @ s.scene.l_world, atol=1e-6)
    R = s.scene.R
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-6)
    assert (R @ [0, 1, 0])[1] > 0.95 and (R @ [0, 1, 0])[2] > 0  # pitched down: world up leans toward the viewer
    assert np.allclose(R @ [1, 0, 0], [1, 0, 0])
    # visible normals face the camera; the ground normal is "up" in camera space
    assert (s.normals_gt[s.labels > 0][:, 2] > -0.05).mean() > 0.99
    assert s.normals_gt[s.labels == 1][:, 1].mean() > 0.9
    assert get_sample(4000, "normal").rgb.tobytes() == s.rgb.tobytes()  # deterministic


def test_masks_and_dent():
    s = get_sample(4021, "damage")
    assert s.dent_mask.sum() >= 600 and (s.labels[s.dent_mask] == OBJ_CAR).all()
    assert (s.labels[~s.G["hit"]] == 0).all() and (s.labels[s.G["hit"]] > 0).all()
    a = rd.render_gbuffer(make_scene(4021, "damage"), 88, 128)
    b = rd.render_gbuffer(make_scene(4021, "damage", dent=False), 88, 128)
    ang = angle_deg(a["normal"].reshape(-1, 3) + 1e-9, b["normal"].reshape(-1, 3) + 1e-9).reshape(88, 128)
    both = a["hit"] & b["hit"] & (a["obj"] == b["obj"])
    assert ang[both & a["dent"]].max() > 5
    assert np.percentile(ang[both & ~a["dent"]], 99) < 2


def test_composite():
    s = get_sample(4000, "normal")
    lB = light_at_angle(s.scene.l_world, 110, 1)
    assert abs(angle_deg(lB, s.scene.l_world) - 110) < 0.01
    c = paste(s, "car", lB)
    assert abs(c["delta_deg"] - 110) < 0.01
    changed = (c["rgb"] != s.rgb).any(-1)
    near = cv2.dilate(c["mask"].astype(np.uint8), np.ones((19, 19), np.uint8)).astype(bool)  # JPEG blocks leak a bit
    assert changed[c["mask"]].mean() > 0.5 and not changed[~near].any()


def test_simulated_normals():
    s = get_sample(4000, "normal")
    n, unc = simulate_normals(s.normals_gt, s.labels, 8, 1)
    err = angle_deg(n[s.labels > 0], s.normals_gt[s.labels > 0])
    assert 5 < np.median(err) < 20 and unc.min() >= 4
    n0, unc0 = simulate_normals(s.normals_gt, s.labels, 0, 1)
    assert np.array_equal(n0, s.normals_gt) and (unc0 == 4).all()
