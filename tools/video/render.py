# -*- coding: utf-8 -*-
"""フレーム描画（Pillow）。1920x1080。図鑑サイトの配色と分類色を流用する。"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

W, H = 1920, 1080
PAPER = (244, 239, 228); PAPER2 = (239, 232, 216); CARD = (255, 253, 248)
INK = (42, 36, 64); INK_SOFT = (91, 84, 112); MUTED = (143, 134, 118); GOLD = (255, 210, 74)
KLASS = {
    "nt": dict(c=(107, 79, 184), soft=(239, 233, 251), jp="分析家"),
    "nf": dict(c=(200, 87, 126), soft=(251, 233, 240), jp="外交官"),
    "sj": dict(c=(63, 154, 140), soft=(230, 244, 241), jp="番人"),
    "sp": dict(c=(209, 144, 47), soft=(251, 241, 220), jp="探検家"),
}
TITLES = {"shin": "静かなる戦略家", "mamoru": "規律の番人", "riku": "行動の勝負師", "yume": "心の詩人", "teru": "導く陽"}


class Fonts:
    def __init__(self, font_dir):
        def pick(*names):
            for n in names:
                p = os.path.join(font_dir, n)
                if os.path.exists(p):
                    return p
            return "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"
        self.round_b = pick("ZenMaruGothic-Bold.ttf")
        self.round_m = pick("ZenMaruGothic-Medium.ttf", "ZenMaruGothic-Bold.ttf")
        self.min_b = pick("ShipporiMincho-Bold.ttf")
        self.min_m = pick("ShipporiMincho-Medium.ttf", "ShipporiMincho-Bold.ttf")
        self._cache = {}

    def get(self, path, size):
        k = (path, size)
        if k not in self._cache:
            self._cache[k] = ImageFont.truetype(path, size)
        return self._cache[k]


KINSOKU_HEAD = "、。，．・：；？！」』）】〕｝〉》…ー）)]"


def wrap(text, font, max_w):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        if font.getlength(cur + ch) <= max_w or not cur:
            cur += ch
        else:
            if ch in KINSOKU_HEAD and len(cur) > 1:
                lines.append(cur[:-1]); cur = cur[-1] + ch
            else:
                lines.append(cur); cur = ch
    if cur:
        lines.append(cur)
    return lines


def rrect(draw, box, r, fill):
    draw.rounded_rectangle(box, radius=r, fill=fill)


def alpha_draw(im, fn):
    """RGBA画像に半透明の図形を正しくブレンドして描く（ImageDraw直描きはアルファを合成しない）。"""
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    fn(ImageDraw.Draw(layer))
    im.alpha_composite(layer)


class Renderer:
    def __init__(self, chars, cast, fonts, source, title):
        self.chars = chars          # id -> RGBA Image
        self.cast = cast
        self.F = fonts
        self.source = source
        self.title = title
        self._bg = None
        self._scaled = {}

    # ── 共通部品 ─────────────────────────────────────────
    def base_paper(self):
        if self._bg is None:
            im = Image.new("RGB", (W, H), PAPER)
            d = ImageDraw.Draw(im)
            for y in range(0, H, 6):
                a = int(2 + 2 * ((y // 6) % 2))
                d.line([(0, y), (W, y)], fill=(PAPER[0] - a, PAPER[1] - a, PAPER[2] - a))
            grad = Image.new("L", (W, H), 0)
            gd = ImageDraw.Draw(grad)
            for i in range(60):
                gd.rectangle([i * 16, i * 9, W - i * 16, H - i * 9], outline=int(i * 1.2))
            grad = grad.filter(ImageFilter.GaussianBlur(80))
            dark = Image.new("RGB", (W, H), PAPER2)
            im = Image.composite(im, dark, grad)
            self._bg = im
        return self._bg.copy()

    def header(self, im, show_source=True):
        d = ImageDraw.Draw(im)
        f = self.F.get(self.F.round_b, 26)
        d.text((48, 30), "十六夜文庫", font=f, fill=INK)
        f2 = self.F.get(self.F.round_m, 22)
        d.text((48 + f.getlength("十六夜文庫") + 14, 34), "─ 16人の読み方", font=f2, fill=MUTED)
        if show_source:
            s = self.source
            w = f2.getlength(s)
            d.text((W - 48 - w, 34), s, font=f2, fill=MUTED)

    def char_img(self, cid, height, dim=False):
        k = (cid, height, dim)
        if k not in self._scaled:
            im = self.chars[cid]
            r = height / im.height
            s = im.resize((int(im.width * r), height), Image.LANCZOS)
            if dim:
                rgb = ImageEnhance.Color(s.convert("RGB")).enhance(0.35)
                rgb = ImageEnhance.Brightness(rgb).enhance(0.92)
                a = s.getchannel("A").point(lambda v: int(v * 0.8))
                s = rgb.convert("RGBA"); s.putalpha(a)
            self._scaled[k] = s
        return self._scaled[k]

    def paste_char(self, im, cid, cx, foot_y, height, dim=False, glow=None):
        s = self.char_img(cid, height, dim)
        if glow is not None:
            g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gd = ImageDraw.Draw(g)
            gw = int(s.width * 0.9)
            gd.ellipse([cx - gw // 2, foot_y - 26, cx + gw // 2, foot_y + 26], fill=glow + (120,))
            g = g.filter(ImageFilter.GaussianBlur(18))
            im.alpha_composite(g)
        im.alpha_composite(s, (int(cx - s.width / 2), int(foot_y - s.height)))

    def name_tag(self, im, x, y, cid, size=30):
        c = self.cast[cid]; col = KLASS[c["klass"]]["c"]
        d = ImageDraw.Draw(im)
        f = self.F.get(self.F.round_b, size); f2 = self.F.get(self.F.round_m, int(size * 0.72))
        t1 = c["name"]; t2 = c["mbti"]
        w = f.getlength(t1) + 18 + f2.getlength(t2) + 44
        rrect(d, [x, y, x + w, y + size + 22], 14, col)
        d.text((x + 22, y + 9), t1, font=f, fill=(255, 255, 255))
        d.text((x + 22 + f.getlength(t1) + 18, y + 9 + (size - int(size * 0.72)) // 2 + 2), t2, font=f2, fill=(255, 245, 250))
        return w

    def subtitle(self, im, cid, text):
        bar_top = H - 230
        alpha_draw(im, lambda d: rrect(d, [40, bar_top, W - 40, H - 40], 26, INK + (236,)))
        d = ImageDraw.Draw(im)
        self.name_tag(im, 72, bar_top - 26, cid, 30)
        f = self.F.get(self.F.round_b, 46)
        lines = wrap(text, f, W - 240)
        if len(lines) > 2:
            f = self.F.get(self.F.round_b, 38); lines = wrap(text, f, W - 240)
        lh = int(f.size * 1.45)
        y = bar_top + 40 + (3 - min(len(lines), 3)) * 8
        for ln in lines[:3]:
            d.text((100, y), ln, font=f, fill=(255, 253, 248))
            y += lh

    def telop_band(self, im, text, size=62, band=True):
        f = self.F.get(self.F.round_b, size)
        tw = f.getlength(text)
        cy = 430
        if band:
            def _b(d):
                d.rectangle([0, cy - 80, W, cy + 80], fill=INK + (225,))
                d.rectangle([0, cy - 80, W, cy - 76], fill=GOLD + (255,))
                d.rectangle([0, cy + 76, W, cy + 80], fill=GOLD + (255,))
            alpha_draw(im, _b)
        d = ImageDraw.Draw(im)
        d.text(((W - tw) / 2, cy - size / 2 - 6), text, font=f, fill=(255, 253, 248))

    # ── レイアウト ───────────────────────────────────────
    STAGE = {   # cid: (center_x, foot_y, height)
        "shin":   (540, 850, 560),
        "mamoru": (190, 820, 480),
        "riku":   (1380, 850, 560),
        "yume":   (1730, 820, 480),
        "teru":   (960, 880, 400),
    }

    def stage(self, speaker=None, dim_all=False):
        im = self.base_paper().convert("RGBA")
        self.header(im)
        f = self.F.get(self.F.round_b, 28)
        for label, x, col in (("無責任派", 360, KLASS["nt"]["c"]), ("英雄派", 1560, KLASS["sp"]["c"])):
            w = f.getlength(label) + 60
            alpha_draw(im, lambda d, x=x, w=w, col=col: rrect(d, [x - w / 2, 150, x + w / 2, 200], 25, col + (45,)))
            ImageDraw.Draw(im).text((x - f.getlength(label) / 2, 158), label, font=f, fill=col)
        order = ["mamoru", "yume", "shin", "riku", "teru"]
        for cid in order:
            cx, fy, h = self.STAGE[cid]
            active = (cid == speaker)
            hh = int(h * (1.08 if active else 0.95))
            glow = KLASS[self.cast[cid]["klass"]]["c"] if active else None
            self.paste_char(im, cid, cx, fy, hh, dim=(not active and (speaker is not None or dim_all)), glow=glow)
        return im

    def frame_line(self, speaker, text, scene="stage"):
        if scene == "cold" or scene == "end":
            im = Image.new("RGBA", (W, H), (21, 18, 31, 255))
            self.paste_char(im, speaker, 960, 760, 620, dim=False)
            # うっすら暗く
            alpha_draw(im, lambda d: d.rectangle([0, 0, W, H], fill=(21, 18, 31, 90)))
            self.subtitle(im, speaker, text)
            return im.convert("RGB")
        if scene.startswith("final:"):
            cid = scene.split(":")[1]
            return self.frame_final(cid, text)
        im = self.stage(speaker)
        self.subtitle(im, speaker, text)
        return im.convert("RGB")

    def frame_quote(self, speaker, text):
        im = self.stage(None, dim_all=True)
        box = [200, 190, W - 200, 640]
        def _q(d):
            d.rectangle([0, 0, W, H], fill=PAPER + (150,))
            rrect(d, box, 22, CARD + (250,))
        alpha_draw(im, _q)
        d = ImageDraw.Draw(im)
        d.rectangle([box[0], box[1] + 30, box[0] + 10, box[3] - 30], fill=GOLD)
        f = self.F.get(self.F.min_b, 44)
        lines = wrap("「" + text + "」", f, box[2] - box[0] - 140)
        if len(lines) > 5:
            f = self.F.get(self.F.min_b, 38); lines = wrap("「" + text + "」", f, box[2] - box[0] - 140)
        lh = int(f.size * 1.75)
        total = lh * len(lines)
        y = (box[1] + box[3]) / 2 - total / 2 - 10
        for ln in lines:
            d.text((box[0] + 70, y), ln, font=f, fill=INK); y += lh
        f2 = self.F.get(self.F.min_m, 26)
        d.text((box[2] - 70 - f2.getlength("— " + self.source), box[3] - 56), "— " + self.source, font=f2, fill=INK_SOFT)
        f3 = self.F.get(self.F.round_b, 22)
        rrect(d, [box[0], box[1] - 22, box[0] + 110, box[1] + 18], 12, INK)
        d.text((box[0] + 22, box[1] - 15), "本文引用", font=f3, fill=GOLD)
        self.subtitle(im, speaker, text)
        return im.convert("RGB")

    def frame_telop(self, text, scene="stage", speaker=None):
        if scene in ("cold", "end"):
            text = text.replace("─", "—")
            im = Image.new("RGB", (W, H), (21, 18, 31))
            d = ImageDraw.Draw(im)
            f = self.F.get(self.F.min_b, 72)
            lines = wrap(text, f, W - 300)
            lh = int(f.size * 1.6); y = H / 2 - lh * len(lines) / 2
            for ln in lines:
                d.text(((W - f.getlength(ln)) / 2, y), ln, font=f, fill=(244, 239, 228)); y += lh
            f2 = self.F.get(self.F.round_m, 24)
            s = "十六夜文庫 ─ 16人の読み方"
            d.text(((W - f2.getlength(s)) / 2, H - 90), s, font=f2, fill=MUTED)
            return im
        if scene.startswith("final:"):
            im = self.frame_final(scene.split(":")[1], None)
            im = im.convert("RGBA"); self.telop_band(im, text); return im.convert("RGB")
        im = self.stage(None)
        self.telop_band(im, text)
        return im.convert("RGB")

    def frame_tally(self, title, hero, irr, note):
        im = self.base_paper().convert("RGBA")
        self.header(im)
        cols = ((irr, "無責任派", KLASS["nt"]["c"], 520), (hero, "英雄派", KLASS["sp"]["c"], 1400))
        alpha_draw(im, lambda d: [rrect(d, [cx - 380, 230, cx + 380, 900], 30, CARD + (235,)) for _, _, _, cx in cols])
        d = ImageDraw.Draw(im)
        f = self.F.get(self.F.round_b, 54)
        d.text(((W - f.getlength(title)) / 2, 120), title, font=f, fill=INK)
        for members, label, col, cx in cols:
            fl = self.F.get(self.F.round_b, 44)
            d.text((cx - fl.getlength(label) / 2, 262), label, font=fl, fill=col)
            fn = self.F.get(self.F.round_b, 120)
            d.text((cx - fn.getlength(str(len(members))) / 2, 320), str(len(members)), font=fn, fill=col)
            n = len(members); gap = 300
            for i, cid in enumerate(members):
                x = cx + (i - (n - 1) / 2) * gap
                self.paste_char(im, cid, x, 850, 330)
                self.name_tag(im, int(x - 70), 860, cid, 24)
        fv = self.F.get(self.F.round_b, 60)
        d.text(((W - fv.getlength("×")) / 2, 500), "×", font=fv, fill=MUTED)
        f2 = self.F.get(self.F.round_m, 32)
        d.text(((W - f2.getlength(note)) / 2, 960), note, font=f2, fill=INK_SOFT)
        return im.convert("RGB")

    def frame_final(self, cid, text):
        c = self.cast[cid]; k = KLASS[c["klass"]]
        im = Image.new("RGBA", (W, H), k["soft"] + (255,))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, W, 14], fill=k["c"])
        self.header(im)
        self.paste_char(im, cid, 520, 850, 720, glow=k["c"])
        f = self.F.get(self.F.round_b, 40)
        d.text((980, 230), "最終弁論", font=f, fill=k["c"])
        d.text((980 + f.getlength("最終弁論") + 24, 238), "一人30秒", font=self.F.get(self.F.round_m, 28), fill=MUTED)
        fn = self.F.get(self.F.round_b, 110)
        d.text((976, 290), c["name"], font=fn, fill=INK)
        fm = self.F.get(self.F.round_b, 48)
        d.text((980, 430), c["mbti"], font=fm, fill=k["c"])
        d.text((980 + fm.getlength(c["mbti"]) + 28, 440), TITLES.get(cid, ""), font=self.F.get(self.F.min_b, 40), fill=INK_SOFT)
        d.text((980, 520), c["role"], font=self.F.get(self.F.round_m, 30), fill=MUTED)
        if text is not None:
            self.subtitle(im, cid, text)
        return im.convert("RGB")

    def thumbnail(self, big, small, left, right):
        small = small.replace("─", "—")
        im = self.base_paper().convert("RGBA")
        for i, cid in enumerate(left):
            self.paste_char(im, cid, 210 + i * 300, 1060, 620)
        for i, cid in enumerate(right):
            self.paste_char(im, cid, 1710 - i * 300, 1060, 620)
        f = self.F.get(self.F.round_b, 150)
        bw = f.getlength(big) + 120
        alpha_draw(im, lambda d: rrect(d, [W / 2 - bw / 2, 180, W / 2 + bw / 2, 400], 30, INK + (240,)))
        d = ImageDraw.Draw(im)
        d.text(((W - f.getlength(big)) / 2, 192), big, font=f, fill=GOLD)
        f2 = self.F.get(self.F.min_b, 60)
        sw = f2.getlength(small) + 100
        alpha_draw(im, lambda d: rrect(d, [W / 2 - sw / 2, 450, W / 2 + sw / 2, 570], 20, CARD + (245,)))
        d = ImageDraw.Draw(im)
        d.text(((W - f2.getlength(small)) / 2, 474), small, font=f2, fill=INK)
        return im.convert("RGB").resize((1280, 720), Image.LANCZOS)
