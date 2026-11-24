"""Small helpers over python-pptx for the LightAudit decks: shapes with alpha, pictures, text, notes, and the
XML python-pptx does not write (Morph / Prism transitions, timed entrances, looping emphasis, motion paths).

Animation timing mirrors what PowerPoint writes for "After previous" effects that start with the slide: one group
triggered on slide entry, each effect in its own block at an absolute delay (ms).
"""
from __future__ import annotations

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

W_IN, H_IN = 13.333, 7.5
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def new_deck():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W_IN), Inches(H_IN)
    return prs


def blank(prs, bg):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = RGBColor.from_string(bg)
    return s


def _name(shape, name):
    if name:
        shape._element.xpath("./*[1]/p:cNvPr")[0].set("name", name)
    return shape


def _alpha(fill_el, alpha):
    """Add <a:alpha> (0..1 opacity) to the srgbClr inside a solidFill element."""
    if alpha is None or alpha >= 1:
        return
    clr = fill_el.find(qn("a:srgbClr"))
    a = etree.SubElement(clr, qn("a:alpha"))
    a.set("val", str(int(alpha * 100000)))


def rect(slide, x, y, w, h, fill, alpha=None, radius=None, name=None, line=None, line_w=0.75, shape=None, rot=0):
    kind = shape or (MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE)
    sp = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if radius and kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        sp.adjustments[0] = min(0.5, radius / min(w, h))
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid()
        sp.fill.fore_color.rgb = RGBColor.from_string(fill)
        _alpha(sp.fill._xPr.find(qn("a:solidFill")), alpha)
    if line:
        sp.line.color.rgb = RGBColor.from_string(line)
        sp.line.width = Pt(line_w)
    else:
        sp.line.fill.background()
    sp.shadow.inherit = False
    sp.rotation = rot
    if sp.has_text_frame:
        sp.text_frame.text = ""
    return _name(sp, name)


def line(slide, x1, y1, x2, y2, color, width=1.0, alpha=None, name=None, dash=None):
    ln = slide.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    ln.line.color.rgb = RGBColor.from_string(color)
    ln.line.width = Pt(width)
    if alpha is not None:
        _alpha(ln.line._ln.find(qn("a:solidFill")), alpha)
    if dash:
        ln.line.dash_style = dash
    return _name(ln, name)


def pic(slide, path, x, y, w=None, h=None, name=None, rot=0, shadow=None, radius=None, border=None):
    p = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    p.rotation = rot
    spPr = p._element.spPr
    if radius:  # rounded picture frame
        geom = spPr.find(qn("a:prstGeom"))
        geom.set("prst", "roundRect")
        av = geom.find(qn("a:avLst"))
        gd = etree.SubElement(av, qn("a:gd"))
        gd.set("name", "adj")
        gd.set("fmla", f"val {int(min(50000, radius / min(p.width, p.height) * Emu(914400) * 100000))}")
    if border:
        ln = etree.SubElement(spPr, qn("a:ln"))
        ln.set("w", str(int(Pt(border[1]))))
        sf = etree.SubElement(ln, qn("a:solidFill"))
        c = etree.SubElement(sf, qn("a:srgbClr"))
        c.set("val", border[0])
    if shadow:
        effect = etree.SubElement(spPr, qn("a:effectLst"))
        sh = etree.SubElement(effect, qn("a:outerShdw"))
        sh.set("blurRad", str(int(Pt(shadow.get("blur", 30)))))
        sh.set("dist", str(int(Pt(shadow.get("dist", 10)))))
        sh.set("dir", "5400000")
        sh.set("algn", "t")
        sh.set("rotWithShape", "0")
        c = etree.SubElement(sh, qn("a:srgbClr"))
        c.set("val", shadow.get("color", "000000"))
        a = etree.SubElement(c, qn("a:alpha"))
        a.set("val", str(int(shadow.get("alpha", 0.35) * 100000)))
    return _name(p, name)


def text(slide, x, y, w, h, content, size=16, color="FFFFFF", font=None, bold=False, align="l", anchor="t",
         name=None, line_spacing=None, space_after=0, italic=False, char_spacing=None):
    """content: a string (\\n = new paragraph) or a list of paragraphs, each a list of (text, {overrides})."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    paras = content.split("\n") if isinstance(content, str) else content
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        if line_spacing:
            p.line_spacing = line_spacing
        p.space_after = Pt(space_after)
        runs = [(para, {})] if isinstance(para, str) else para
        for t, o in runs:
            r = p.add_run()
            r.text = t
            f = r.font
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.name = o.get("font", font)
            f.color.rgb = RGBColor.from_string(o.get("color", color))
            cs = o.get("char_spacing", char_spacing)
            if cs is not None:
                r._r.get_or_add_rPr().set("spc", str(int(cs * 100)))
    return _name(tb, name)


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


def bar_chart(slide, x, y, w, h, cats, series, colors, label_color, font, axis_max=None, name=None, num_fmt='0"%"',
              gap=60, value_axis=False, label_size=12):
    data = CategoryChartData()
    data.categories = cats
    for nm, vals in series:
        data.add_series(nm, vals)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), data)
    ch = gf.chart
    ch.has_title = False
    ch.has_legend = len(series) > 1
    ch.font.name = font
    ch.font.size = Pt(label_size)
    ch.font.color.rgb = RGBColor.from_string(label_color)
    plot = ch.plots[0]
    plot.gap_width = gap
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format = num_fmt
    dl.number_format_is_linked = False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(label_size + 2)
    dl.font.bold = True
    dl.font.color.rgb = RGBColor.from_string(label_color)
    for i, s in enumerate(plot.series):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = RGBColor.from_string(colors[i % len(colors)])
    va = ch.value_axis
    va.visible = value_axis
    va.has_major_gridlines = False
    if axis_max:
        va.maximum_scale = axis_max
    va.minimum_scale = 0
    ca = ch.category_axis
    ca.format.line.color.rgb = RGBColor.from_string(label_color)
    ca.tick_labels.font.size = Pt(label_size)
    ca.tick_labels.font.color.rgb = RGBColor.from_string(label_color)
    if ch.has_legend:
        ch.legend.font.color.rgb = RGBColor.from_string(label_color)
        ch.legend.include_in_layout = False
    return _name(gf, name)


def per_point_colors(chart_shape, colors):
    s = chart_shape.chart.plots[0].series[0]
    for i, c in enumerate(colors):
        pt = s.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = RGBColor.from_string(c)


# ---------------------------------------------------------------- transitions
MORPH = ('<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
         '<mc:Choice xmlns:p159="http://schemas.microsoft.com/office/powerpoint/2015/09/main" Requires="p159">'
         '<p:transition xmlns:p="%s" spd="slow" xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" p14:dur="%d">'
         '<p159:morph option="byObject"/></p:transition></mc:Choice>'
         '<mc:Fallback><p:transition xmlns:p="%s" spd="slow"><p:fade/></p:transition></mc:Fallback></mc:AlternateContent>')
P14 = ('<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
       '<mc:Choice xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" Requires="p14">'
       '<p:transition xmlns:p="%s" spd="slow" p14:dur="%d">%s</p:transition></mc:Choice>'
       '<mc:Fallback><p:transition xmlns:p="%s" spd="slow"><p:fade/></p:transition></mc:Fallback></mc:AlternateContent>')


def _insert_after_clrmap(slide, el):
    sld = slide._element
    anchor = sld.find(qn("p:clrMapOvr"))
    if anchor is None:
        anchor = sld.find(qn("p:cSld"))
    anchor.addnext(el)


def transition(slide, kind="morph", dur=1600, **kw):
    if kind == "morph":
        xml = MORPH % (NS_P, dur, NS_P)
    elif kind == "fade":
        xml = '<p:transition xmlns:p="%s" spd="slow"><p:fade/></p:transition>' % NS_P
        _insert_after_clrmap(slide, etree.fromstring(xml))
        return
    else:  # a PowerPoint 2010 transition element: prism, vortex, ripple, glitter, shred, flash, ...
        attrs = " ".join(f'{k}="{v}"' for k, v in kw.items())
        xml = P14 % (NS_P, dur, f"<p14:{kind} {attrs}/>", NS_P)
    _insert_after_clrmap(slide, etree.fromstring(xml))


# ---------------------------------------------------------------- animations
class Timeline:
    """Collect effects for one slide, then write <p:timing>. Delays are absolute ms from slide entry."""

    def __init__(self, slide):
        self.slide, self.items, self._id = slide, [], 2

    def _nid(self):
        self._id += 1
        return self._id

    def add(self, shape, kind, delay=0, dur=700, **o):
        self.items.append((shape.shape_id, kind, delay, dur, o))
        return self

    def _vis(self, spid):
        return (f'<p:set><p:cBhvr><p:cTn id="{self._nid()}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
                f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>'
                f'</p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>')

    def _effect(self, spid, kind, dur, o):
        tgt = f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>'
        rep = f' repeatCount="{o["repeat"]}"' if o.get("repeat") else ""
        rev = ' autoRev="1"' if o.get("autorev") else ""
        if kind == "fade":
            return 10, "entr", 0, self._vis(spid) + (
                f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{self._nid()}" dur="{dur}"/>{tgt}</p:cBhvr></p:animEffect>')
        if kind == "wipe":
            d = o.get("dir", "right")  # direction of travel
            sub = {"up": 4, "down": 1, "left": 2, "right": 8}[d]
            return 22, "entr", sub, self._vis(spid) + (
                f'<p:animEffect transition="in" filter="wipe({d})"><p:cBhvr><p:cTn id="{self._nid()}" dur="{dur}"/>{tgt}</p:cBhvr></p:animEffect>')
        if kind == "rise":  # fade while sliding up a little (PowerPoint's "Rise up")
            dy = o.get("dy", 0.08)
            return 42, "entr", 0, self._vis(spid) + (
                f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{self._nid()}" dur="{dur}"/>{tgt}</p:cBhvr></p:animEffect>'
                f'<p:anim calcmode="lin" valueType="num"><p:cBhvr><p:cTn id="{self._nid()}" dur="{dur}" decel="100000" fill="hold"/>{tgt}'
                f'<p:attrNameLst><p:attrName>ppt_x</p:attrName></p:attrNameLst></p:cBhvr><p:tavLst><p:tav tm="0"><p:val><p:strVal val="#ppt_x"/></p:val></p:tav>'
                f'<p:tav tm="100000"><p:val><p:strVal val="#ppt_x"/></p:val></p:tav></p:tavLst></p:anim>'
                f'<p:anim calcmode="lin" valueType="num"><p:cBhvr><p:cTn id="{self._nid()}" dur="{dur}" decel="100000" fill="hold"/>{tgt}'
                f'<p:attrNameLst><p:attrName>ppt_y</p:attrName></p:attrNameLst></p:cBhvr><p:tavLst><p:tav tm="0"><p:val><p:strVal val="#ppt_y+{dy}"/></p:val></p:tav>'
                f'<p:tav tm="100000"><p:val><p:strVal val="#ppt_y"/></p:val></p:tav></p:tavLst></p:anim>')
        if kind == "zoom":  # fade in while growing from a smaller size
            s = o.get("from", 0.6)
            return 53, "entr", 16, self._vis(spid) + (
                f'<p:anim calcmode="lin" valueType="num"><p:cBhvr><p:cTn id="{self._nid()}" dur="{dur}" decel="100000" fill="hold"/>{tgt}'
                f'<p:attrNameLst><p:attrName>ppt_w</p:attrName></p:attrNameLst></p:cBhvr><p:tavLst><p:tav tm="0"><p:val><p:strVal val="#ppt_w*{s}"/></p:val></p:tav>'
                f'<p:tav tm="100000"><p:val><p:strVal val="#ppt_w"/></p:val></p:tav></p:tavLst></p:anim>'
                f'<p:anim calcmode="lin" valueType="num"><p:cBhvr><p:cTn id="{self._nid()}" dur="{dur}" decel="100000" fill="hold"/>{tgt}'
                f'<p:attrNameLst><p:attrName>ppt_h</p:attrName></p:attrNameLst></p:cBhvr><p:tavLst><p:tav tm="0"><p:val><p:strVal val="#ppt_h*{s}"/></p:val></p:tav>'
                f'<p:tav tm="100000"><p:val><p:strVal val="#ppt_h"/></p:val></p:tav></p:tavLst></p:anim>'
                f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{self._nid()}" dur="{dur}"/>{tgt}</p:cBhvr></p:animEffect>')
        if kind == "spin":  # emphasis: rotate by `deg`, optionally forever
            by = int(o.get("deg", 360) * 60000)
            return 8, "emph", 0, (f'<p:animRot by="{by}"><p:cBhvr><p:cTn id="{self._nid()}" dur="{dur}" fill="hold"{rep}{rev}/>{tgt}'
                                  f'<p:attrNameLst><p:attrName>r</p:attrName></p:attrNameLst></p:cBhvr></p:animRot>')
        if kind == "pulse":  # emphasis: grow/shrink by `scale` and back, optionally forever
            k = int(o.get("scale", 1.08) * 100000)
            return 6, "emph", 0, (f'<p:animScale><p:cBhvr><p:cTn id="{self._nid()}" dur="{dur}" fill="hold" autoRev="1"{rep}/>{tgt}'
                                  f'</p:cBhvr><p:by x="{k}" y="{k}"/></p:animScale>')
        if kind == "breathe":  # emphasis: transparency down to `to` and back
            return 9, "emph", 0, (f'<p:set><p:cBhvr><p:cTn id="{self._nid()}" dur="{dur}" fill="hold" autoRev="1"{rep}/>{tgt}'
                                  f'<p:attrNameLst><p:attrName>style.opacity</p:attrName></p:attrNameLst></p:cBhvr>'
                                  f'<p:to><p:strVal val="{o.get("to", 0.45)}"/></p:to></p:set>')
        if kind == "path":  # motion path, offsets as fractions of the slide
            dx, dy = o.get("dx", 0.0), o.get("dy", 0.0)
            return 0, "path", 0, (f'<p:animMotion origin="layout" path="M 0 0 L {dx} {dy} E" pathEditMode="relative" ptsTypes="AA">'
                                  f'<p:cBhvr><p:cTn id="{self._nid()}" dur="{dur}" fill="hold"{rep}{rev}/>{tgt}'
                                  f'<p:attrNameLst><p:attrName>ppt_x</p:attrName><p:attrName>ppt_y</p:attrName></p:attrNameLst></p:cBhvr></p:animMotion>')
        raise ValueError(kind)

    def write(self):
        if not self.items:
            return
        self._id = 3
        blocks = []
        for spid, kind, delay, dur, o in sorted(self.items, key=lambda t: t[2]):
            outer, inner = self._nid(), self._nid()
            pid, cls, sub, beh = self._effect(spid, kind, dur, o)
            blocks.append(f'<p:par><p:cTn id="{outer}" fill="hold"><p:stCondLst><p:cond delay="{int(delay)}"/></p:stCondLst><p:childTnLst>'
                          f'<p:par><p:cTn id="{inner}" presetID="{pid}" presetClass="{cls}" presetSubtype="{sub}" fill="hold" nodeType="withEffect">'
                          f'<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>{beh}</p:childTnLst></p:cTn></p:par>'
                          f'</p:childTnLst></p:cTn></p:par>')
        xml = (f'<p:timing xmlns:p="{NS_P}"><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
               f'<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
               f'<p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond>'
               f'</p:stCondLst><p:childTnLst>{"".join(blocks)}</p:childTnLst></p:cTn></p:par>'
               f'</p:childTnLst></p:cTn><p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
               f'<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq>'
               f'</p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>')
        el = etree.fromstring(xml)
        sld = self.slide._element
        tr = sld.find(qn("p:transition"))
        if tr is None:
            alt = sld.find("{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent")
            tr = alt
        if tr is not None:
            tr.addnext(el)
        else:
            _insert_after_clrmap(self.slide, el)
