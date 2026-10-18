#!/usr/bin/env python3
"""Clickable web links for the generated HTML pages (STATUS.html, REPORT.html).

linkify_html(html) walks already-escaped HTML and:
  * turns every bare http(s) URL in TEXT into <a href target=_blank rel="noopener noreferrer"> with a short readable label
    (domain + path, truncated; the full URL is in the title), also inside brackets such as "[FATTO https://..., letto ...]";
  * gives existing external links target=_blank and rel=noopener, and shortens their label when the label is the raw URL;
  * never touches attributes, <script>, <style>, <textarea>, <code>, <pre>, <title> or text already inside a link.
Only http and https become links; everything else stays text. The input must already be escaped HTML (the text was passed
through html.escape): the URL is unescaped, cut at the first quote or angle bracket, and escaped again in href and label,
so a TODO line cannot inject markup through a URL.
"""
from __future__ import annotations

import html
import re
from urllib.parse import unquote, urlsplit

TAG = re.compile(r"(<!--.*?-->|<[^>]*>)", re.S)
URL = re.compile(r"https?://[^\s<]+", re.I)
SAFE = re.compile(r"^https?://[^\s\"'<>`]+$", re.I)
SKIP = {"a", "script", "style", "textarea", "code", "pre", "title", "button", "svg"}
TRAIL = ".,;:!?»"


def short_url(url: str, n: int = 38) -> str:
    """'https://docs.google.com/forms/d/e/1FAIpQ.../viewform' -> 'docs.google.com/forms/d/e/1FAIpQ…' (at most ~n chars)."""
    try:
        p = urlsplit(url)
    except ValueError:
        return url[:n]
    host = (p.hostname or "").removeprefix("www.")
    path = unquote(p.path or "").rstrip("/")
    s = host + path
    if len(s) <= n:
        return s or url[:n]
    keep = max(n - len(host) - 2, 8)
    return host + (path[:keep] + "…" if path else "")


def _split_url(raw: str) -> tuple[str, str]:
    """(url, rest): cut at quotes/brackets, drop trailing punctuation and unbalanced closing brackets."""
    m = re.search(r"[\"'<>`]", raw)
    url, rest = (raw[:m.start()], raw[m.start():]) if m else (raw, "")
    while url and (url[-1] in TRAIL or (url[-1] == ")" and url.count("(") < url.count(")")) or (url[-1] == "]" and url.count("[") < url.count("]"))):
        rest, url = url[-1] + rest, url[:-1]
    return url, rest


def anchor(url: str, label: str | None = None) -> str:
    """A safe external link; plain escaped text when the URL is not http(s)."""
    if not SAFE.match(url or ""):
        return html.escape(label or url or "")
    return (f'<a class="ext" href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer" title="{html.escape(url, quote=True)}">'
            f'{html.escape(label or short_url(url))}</a>')


def linkify_text(escaped: str) -> str:
    """Bare URLs in a piece of escaped text -> links."""
    def sub(m):
        url, rest = _split_url(html.unescape(m.group(0)))
        if len(url) < 12 or not SAFE.match(url):
            return m.group(0)
        return anchor(url) + html.escape(rest, quote=False)
    return URL.sub(sub, escaped)


def linkify_html(doc: str) -> str:
    out, stack = [], []
    for part in TAG.split(doc):
        if not part:
            continue
        if part.startswith("<"):
            m = re.match(r"<(/?)([a-zA-Z][\w-]*)", part)
            if m:
                name, closing = m.group(2).lower(), m.group(1) == "/"
                if name == "a" and not closing and re.search(r'href="https?://', part, re.I):
                    if "target=" not in part:
                        part = part[:-1].rstrip("/") + ' target="_blank">'
                    if "rel=" not in part:
                        part = part[:-1] + ' rel="noopener noreferrer">'
                    elif "noopener" not in part:
                        part = re.sub(r'rel="([^"]*)"', r'rel="\1 noopener"', part, count=1)
                if name in SKIP and not part.endswith("/>"):
                    if closing:
                        if name in stack:
                            while stack and stack.pop() != name:
                                pass
                    else:
                        stack.append(name)
            out.append(part)
            continue
        if stack:
            if stack[-1] == "a" and SAFE.match(html.unescape(part.strip())) and len(part.strip()) > 40:
                part = html.escape(short_url(html.unescape(part.strip())))      # a link whose label is the raw long URL
            out.append(part)
            continue
        out.append(linkify_text(part))
    return "".join(out)
