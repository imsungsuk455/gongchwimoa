#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""블로그 썸네일 일괄 생성기 — 단일 템플릿 (2026-10-19 확정)

레이아웃 (1200x630):
  · 흰 배경
  · 왼쪽 26px 세로 파란 바 (#0B5FFF)
  · 좌상단 브랜드 "공취모아" (회색, 40px)
  · 중앙 큰 제목 (검정 볼드, 최대 3줄, 62px)
  · 하단 좌측 "공취모아 블로그 N편" (회색, 30px)
모든 편이 같은 좌표·폰트·색을 쓴다. 제목만 바뀐다.

사용법: python3 blog_thumb.py          # 1~6편 전부 재생성
        python3 blog_thumb.py 7 8     # 지정 편만
"""
import os, re, sys
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "thumbnails")
BOLD = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
REG = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"

W, H = 1200, 630
BAR_W = 26
BAR_COLOR = "#0B5FFF"
BG = "#ffffff"
INK = "#101828"
MUTED = "#94a3b8"

PAD_L = 100          # 왼쪽 여백(바 제외)
TITLE_SIZE = 62
TITLE_LH = 88        # 줄 간격
MAX_LINES = 3
BRAND_SIZE = 40
FOOT_SIZE = 30


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def wrap(draw, text, f, max_w):
    """단어 경계 우선 줄바꿈. 한 단어가 폭을 넘으면 글자 단위로 쪼갠다."""
    lines, cur = [], ""
    for word in text.split(" "):
        cand = f"{cur} {word}".strip()
        if draw.textlength(cand, font=f) <= max_w:
            cur = cand
            continue
        if cur:
            lines.append(cur)
            cur = ""
        # 단어 하나가 폭을 넘는 경우 글자 단위로
        if draw.textlength(word, font=f) <= max_w:
            cur = word
        else:
            for ch in word:
                if draw.textlength(cur + ch, font=f) <= max_w:
                    cur += ch
                else:
                    lines.append(cur)
                    cur = ch
    if cur:
        lines.append(cur)
    # 한 글자 토막이 줄 끝에 홀로 남지 않게 다음 줄로 넘긴다 (예: "이 / 글만")
    for i in range(len(lines) - 1):
        toks = lines[i].split(" ")
        if len(toks) > 1 and len(toks[-1]) == 1:
            lines[i] = " ".join(toks[:-1])
            lines[i + 1] = (toks[-1] + " " + lines[i + 1]).strip()
    return [ln for ln in lines if ln.strip()]


def title_of(n):
    p = os.path.join(BASE, "blog", f"post-{n}.html")
    if not os.path.exists(p):
        return None
    t = open(p, encoding="utf-8").read()
    m = re.search(r"<h1>(.*?)</h1>", t)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else None


def render(n, title):
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    dr.rectangle([0, 0, BAR_W, H], fill=BAR_COLOR)

    f_brand = font(REG, BRAND_SIZE)
    f_title = font(BOLD, TITLE_SIZE)
    f_foot = font(REG, FOOT_SIZE)

    dr.text((PAD_L, 84), "공취모아", font=f_brand, fill=MUTED)

    lines = wrap(dr, title, f_title, W - PAD_L - 90)
    if len(lines) > MAX_LINES:
        # 3줄 초과 → 폰트를 줄여 재배치
        shrunk = TITLE_SIZE
        while len(lines) > MAX_LINES and shrunk > 40:
            shrunk -= 2
            f_try = font(BOLD, shrunk)
            lines = wrap(dr, title, f_try, W - PAD_L - 90)
        f_title = font(BOLD, shrunk)
    block_h = len(lines) * TITLE_LH
    y = (H - block_h) // 2 + 10
    for ln in lines:
        dr.text((PAD_L, y), ln, font=f_title, fill=INK)
        y += TITLE_LH

    dr.text((PAD_L, H - 82), f"공취모아 블로그 {n}편", font=f_foot, fill=MUTED)

    out = os.path.join(OUT_DIR, f"blog-{n}.png")
    img.save(out, optimize=True)
    return out


def main(nums):
    os.makedirs(OUT_DIR, exist_ok=True)
    n_ok = 0
    for n in nums:
        t = title_of(n)
        if not t:
            print(f"  skip {n}: post 없음")
            continue
        p = render(n, t)
        print(f"  {os.path.basename(p)} ← {t[:40]}")
        n_ok += 1
    print(f"생성 {n_ok}건")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        main([int(a) for a in args])
    else:
        nums = sorted(int(m.group(1)) for m in
                      (re.match(r"post-(\d+)\.html$", f) for f in os.listdir(os.path.join(BASE, "blog"))
                       if f.startswith("post-")) if m)
        main(nums)
