import numpy as np
from PIL import Image

from lightaudit.imageio import load_rgb


def test_16bit_png_not_white(tmp_path):
    a = (np.arange(64 * 64).reshape(64, 64) * 8).astype(np.uint16)  # 0..32760
    p = tmp_path / "g16.png"
    Image.fromarray(a).save(p)
    rgb = load_rgb(p)
    assert rgb.shape == (64, 64, 3) and rgb.min() == 0 and 200 < rgb.max() <= 255


def test_exif_rotation_applied(tmp_path):
    im = Image.new("RGB", (40, 20))
    exif = im.getexif()
    exif[0x0112] = 6  # rotate 90 on display
    p = tmp_path / "r.jpg"
    im.save(p, exif=exif)
    assert load_rgb(p).shape[:2] == (40, 20)
