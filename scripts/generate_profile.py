#!/usr/bin/env python3
"""Generate Renato's GitHub profile SVGs.

Outputs (dark + light for each):
  profile/bento-*.svg          "Bento" main card
  profile/api-*.svg            "API Response" main card (alternative layout)
  profile/<style>-project-N-*  featured project cards (clickable in README)
  profile/<style>-btn-*        social buttons (clickable in README)

Data sources:
  GitHub GraphQL  -> GITHUB_TOKEN (or GH_PAT to also count private contributions)
  WakaTime        -> WAKATIME_API_KEY for last 30 days; falls back to public all-time stats

Icons live in assets/icons (devicon + simple-icons) and are embedded as data URIs,
so the SVGs have no external dependencies. Stdlib only:
  python scripts/generate_profile.py
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import json
import math
import os
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "profile"
ICONS = ROOT / "assets" / "icons"
OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "RenatoMAP77")
BRT = dt.timezone(dt.timedelta(hours=-3))

# ---------------------------------------------------------------- content ---

PROFILE = {
    "name": "Renato Matos",
    "role": "Full Stack Software Engineer",
    "tagline": "Backend-focused · integrations, async events & APIs",
    "company": "SEIDOR Brasil",
    "position": "SAP ABAP Developer",
    "graduation": "Dec 2026",
    "location": "Belo Horizonte, BR",
}

STACK = ["Java", "Spring Boot", "React", "Next.js", "Node.js", "TypeScript", "ABAP",
         "Python", "Azure", "Dart", "Flutter", "MySQL", "Docker"]

# repo -> (description override or None, language override or None)
FEATURED = {
    "Carona-ti": ("Carpool system for PUC Minas. Spring Boot API with JWT auth, RabbitMQ, WebSockets and MySQL.", "Java"),
    "delivery-app": ("Microservices delivery platform + Flutter app, with async events on Azure Service Bus & Functions.", None),
    "nfse-builder": ("Python automation that generates ABAP classes for NFS-e fiscal integrations.", None),
}

LINKS = {
    "linkedin": "https://www.linkedin.com/in/renato-matos-alves-penna-646108276/",
    "email": "mailto:renatomapbusiness@gmail.com",
}

WAKA_EXCLUDE = {
    "other", "markdown", "text", "json", "json with comments", "yaml", "xml",
    "toml", "ini", "csv", "git config", "git", "batchfile", "powershell",
    "docker", "dockerfile", "makefile", "properties", "java properties",
    "image (png)", "image (svg)", "image (jpeg)", "log", "env", "tsconfig",
}

LANG_COLORS = {
    "Java": "#b07219", "ABAP": "#0FAAFF", "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a", "Python": "#3572A5", "Dart": "#00B4AB",
    "HTML": "#e34c26", "CSS": "#663399", "SQL": "#e38c00", "C": "#555555",
    "C++": "#f34b7d", "Kotlin": "#A97BFF", "Go": "#00ADD8", "Shell": "#89e051",
    "TSX": "#3178c6", "JSX": "#f1e05a", "Vue.js": "#41b883",
}

ICON_FILES = {
    "Java": "java", "Spring Boot": "spring", "Spring": "spring", "React": "react",
    "Next.js": "nextjs", "Node.js": "nodejs", "TypeScript": "typescript", "TSX": "typescript",
    "ABAP": "sap", "Python": "python", "Azure": "azure", "Dart": "dart", "Flutter": "flutter",
    "MySQL": "mysql", "JavaScript": "javascript", "JSX": "javascript", "C": "c",
    "HTML": "html5", "CSS": "css3", "Docker": "docker",
}

SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"

THEMES = {
    "api": {
        "dark": dict(bg="#0d1117", bar="#161b22", border="#30363d", text="#e6edf3",
                     muted="#8b949e", faint="#484f58", key="#7ee787", num="#d2a8ff",
                     punct="#6e7681", ok="#3fb950", method_bg="#238636", method_fg="#ffffff",
                     track="#21262d", spark="#3fb950", tile="#161b22", chip="#161b22"),
        "light": dict(bg="#ffffff", bar="#f6f8fa", border="#d0d7de", text="#1f2328",
                      muted="#656d76", faint="#afb8c1", key="#1a7f37", num="#8250df",
                      punct="#8c959f", ok="#1a7f37", method_bg="#1f883d", method_fg="#ffffff",
                      track="#eaeef2", spark="#1a7f37", tile="#f6f8fa", chip="#f6f8fa"),
    },
    "bento": {
        "dark": dict(card="#18181b", border="#27272a", text="#fafafa", muted="#a1a1aa",
                     faint="#52525b", accent="#34d399", track="#27272a", chip="#1f1f23",
                     glow="#34d399"),
        "light": dict(card="#ffffff", border="#e4e4e7", text="#18181b", muted="#71717a",
                      faint="#d4d4d8", accent="#059669", track="#f4f4f5", chip="#fafafa",
                      glow="#10b981"),
    },
}

# ------------------------------------------------------------------ fetch ---


def _get(url: str, headers: dict | None = None, data: bytes | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "profile-generator", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_github() -> dict:
    token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN (or GH_PAT) is required")
    repo_fields = "name url description stargazerCount primaryLanguage { name color }"
    repos = " ".join(
        f'r{i}: repository(owner: "{OWNER}", name: "{n}") {{ {repo_fields} }}' for i, n in enumerate(FEATURED)
    )
    query = f"""{{
      user(login: "{OWNER}") {{
        repositories(ownerAffiliations: OWNER, privacy: PUBLIC) {{ totalCount }}
        pullRequests {{ totalCount }}
        contributionsCollection {{
          contributionCalendar {{ totalContributions weeks {{ contributionDays {{ date contributionCount }} }} }}
        }}
      }}
      {repos}
    }}"""
    d = _get("https://api.github.com/graphql", {"Authorization": f"bearer {token}", "Content-Type": "application/json"},
             json.dumps({"query": query}).encode())
    if "errors" in d:
        raise SystemExit(f"GraphQL error: {d['errors']}")
    data = d["data"]
    user = data["user"]
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [sum(day["contributionCount"] for day in w["contributionDays"]) for w in cal["weeks"]]

    projects = []
    for i, name in enumerate(FEATURED):
        r = data.get(f"r{i}")
        if not r:
            continue
        desc, lang_override = FEATURED[name]
        lang = lang_override or (r["primaryLanguage"] or {}).get("name", "")
        projects.append({
            "name": r["name"], "url": r["url"], "stars": r["stargazerCount"],
            "desc": desc or r["description"] or "", "lang": lang,
            "color": LANG_COLORS.get(lang) or (r["primaryLanguage"] or {}).get("color") or "#8b949e",
        })

    return {
        "contributions": cal["totalContributions"],
        "weeks": weeks,
        "repos": user["repositories"]["totalCount"],
        "prs": user["pullRequests"]["totalCount"],
        "projects": projects,
    }


def fetch_wakatime() -> dict:
    key = os.environ.get("WAKATIME_API_KEY")
    try:
        if key:
            auth = base64.b64encode(key.encode()).decode()
            d = _get("https://wakatime.com/api/v1/users/current/stats/last_30_days", {"Authorization": f"Basic {auth}"})
            label = "last 30 days"
        else:
            d = _get(f"https://wakatime.com/api/v1/users/{OWNER}/stats/all_time")
            label = "all time"
    except Exception as e:  # keep generating even if WakaTime is down
        print(f"WakaTime unavailable: {e}")
        return {"label": "unavailable", "langs": [], "hours": 0}
    langs = [l for l in d["data"].get("languages", []) if l["name"].lower() not in WAKA_EXCLUDE]
    total = sum(l["total_seconds"] for l in langs) or 1
    top = [{"name": l["name"], "pct": 100 * l["total_seconds"] / total, "hours": l["total_seconds"] / 3600}
           for l in langs[:5]]
    peak = max((l["pct"] for l in top), default=1) or 1
    for l in top:
        l["fill"] = l["pct"] / peak  # bar length relative to the most used language
    return {"label": label, "langs": top, "hours": total / 3600}


# ---------------------------------------------------------------- helpers ---

_icon_cache: dict[tuple[str, str], str] = {}
# icons whose brand colour is too dark to read on a dark background
DARK_RECOLOR = {"#0074BD": "#4FA8F0", "#00618A": "#3DA5D9"}


def icon(name: str, x: float, y: float, size: float, theme: str) -> str:
    """Embedded <image> for a language/tool icon, or '' if there is none."""
    key = ICON_FILES.get(name)
    if not key:
        return ""
    if (key, theme) not in _icon_cache:
        path = ICONS / f"{key}.svg"
        if not path.exists():
            return ""
        raw = path.read_text(encoding="utf-8")
        if key == "sap":  # monochrome simple-icon -> SAP blue
            raw = raw.replace("<path ", '<path fill="#0FAAFF" ', 1)
        if theme == "dark":
            for old, new in DARK_RECOLOR.items():
                raw = raw.replace(old, new)
        _icon_cache[(key, theme)] = "data:image/svg+xml;base64," + base64.b64encode(raw.encode()).decode()
    return f'<image x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" href="{_icon_cache[(key, theme)]}"/>'


def lang_mark(name: str, cx: float, cy: float, size: float, fallback: str, theme: str) -> str:
    return icon(name, cx - size / 2, cy - size / 2, size, theme) or f'<circle cx="{cx}" cy="{cy}" r="{size / 3.2:.1f}" fill="{fallback}"/>'


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def fmt_int(n: int) -> str:
    return f"{n:,}"


def fmt_hours(h: float) -> str:
    return f"{int(h)}h" if h >= 10 else f"{int(h)}h {int((h % 1) * 60)}m"


def wrap(text: str, max_chars: int, max_lines: int) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + (1 if cur else 0) <= max_chars:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max_chars - 1].rstrip(" ,.") + "…"
    return lines


def svg(w: int, h: int, body: str, style: str = "", title: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(title)}"><title>{esc(title)}</title>'
            f'<style>{style}</style>{body}</svg>\n')


def sparkline(weeks: list[int], x: float, y: float, w: float, h: float, color: str, track: str, delay0=0.0) -> str:
    n = len(weeks) or 1
    gap = 2
    bw = (w - gap * (n - 1)) / n
    peak = math.sqrt(max(weeks) or 1)  # sqrt scale so a single busy week doesn't flatten the rest
    out = []
    for i, v in enumerate(weeks):
        r = math.sqrt(v) / peak
        bh = max(2, h * r) if v else 2
        op = 0.35 + 0.65 * r if v else 1
        out.append(f'<rect class="grow" style="animation-delay:{delay0 + i * 0.012:.3f}s" x="{x + i * (bw + gap):.1f}" '
                   f'y="{y + h - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="1" '
                   f'fill="{color if v else track}" fill-opacity="{op:.2f}"/>')
    return "".join(out)


def chips(items: list[str], x0: float, y0: float, avail: float, row_h: float, gap: float,
          fill: str, stroke: str, text_fill: str, rx: float, font: str, theme: str, center: bool = True) -> tuple[str, float]:
    """Icon + label pills, wrapped into centred rows. Returns (svg, bottom_y)."""
    def width(t):
        return 10 + 16 + 7 + len(t) * 7.2 + 12

    rows, cur, cur_w = [], [], 0.0
    for t in items:
        w = width(t)
        if cur and cur_w + gap + w > avail:
            rows.append(cur)
            cur, cur_w = [], 0.0
        cur_w += (gap if cur else 0) + w
        cur.append(t)
    if cur:
        rows.append(cur)

    out, k = [], 0
    for r, row in enumerate(rows):
        total = sum(width(t) for t in row) + gap * (len(row) - 1)
        x = x0 + ((avail - total) / 2 if center else 0)
        y = y0 + r * (row_h + 8)
        for t in row:
            w = width(t)
            out.append(f'<g class="fade" style="animation-delay:{0.2 + k * 0.04:.2f}s">'
                       f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{row_h}" rx="{rx}" fill="{fill}" stroke="{stroke}"/>'
                       f'{icon(t, x + 10, y + (row_h - 16) / 2, 16, theme)}'
                       f'<text x="{x + 33:.1f}" y="{y + row_h / 2 + 4.3:.1f}" style="font-family:{font}" font-size="12" '
                       f'fill="{text_fill}">{esc(t)}</text></g>')
            x += w + gap
            k += 1
    return "".join(out), y0 + len(rows) * (row_h + 8) - 8


ANIM = """
.fade{opacity:0;animation:fade .45s ease-out forwards}
@keyframes fade{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:none}}
.grow{transform-box:fill-box;transform-origin:bottom;animation:grow .6s ease-out both}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
.bar{transform-box:fill-box;transform-origin:left;animation:barx .9s cubic-bezier(.2,.8,.2,1) both}
@keyframes barx{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.blink{animation:blink 1.1s steps(1) infinite}
@keyframes blink{50%{opacity:0}}
.pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2s ease-out infinite}
@keyframes pulse{0%{transform:scale(1);opacity:.6}100%{transform:scale(2.6);opacity:0}}
@media (prefers-reduced-motion:reduce){.fade,.grow,.bar,.blink,.pulse{animation:none;opacity:1}}
"""

# ------------------------------------------------------ style: Bento card ---


def card(x, y, w, h, c) -> str:
    return f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" rx="16" fill="{c["card"]}" stroke="{c["border"]}"/>'


def render_bento(theme: str, gh: dict, waka: dict, updated: str) -> str:
    c = THEMES["bento"][theme]
    W, G = 845, 12
    style = ANIM + f"""
text{{font-family:{SANS};fill:{c['text']}}}
.mono{{font-family:{MONO}}}
.mut{{fill:{c['muted']}}}
.eyebrow{{font-size:11px;letter-spacing:1.6px;fill:{c['muted']};font-weight:600}}
"""
    HW, R1 = 520, 196
    b = [f"""<defs>
<linearGradient id="ng" x1="0" x2="1"><stop offset="0" stop-color="{c['text']}"/><stop offset="1" stop-color="{c['accent']}"/></linearGradient>
<radialGradient id="glow" cx="1" cy="0" r="1"><stop offset="0" stop-color="{c['glow']}" stop-opacity=".22"/><stop offset="1" stop-color="{c['glow']}" stop-opacity="0"/></radialGradient>
<clipPath id="hero"><rect x="0" y="0" width="{HW}" height="{R1}" rx="16"/></clipPath>
</defs>"""]

    # Row 1: hero + coding time
    b.append(card(0, 0, HW, R1, c))
    b.append(f'<rect clip-path="url(#hero)" x="200" y="-120" width="420" height="320" fill="url(#glow)"/>')
    b.append(f'<text class="eyebrow fade" x="28" y="40">{esc(PROFILE["role"].upper())}</text>')
    b.append(f'<text class="fade" style="animation-delay:.1s" x="26" y="88" font-size="40" font-weight="800" '
             f'letter-spacing="-1" fill="url(#ng)">{esc(PROFILE["name"])}</text>')
    b.append(f'<text class="fade mut" style="animation-delay:.2s" x="28" y="118" font-size="14.5">{esc(PROFILE["tagline"])}</text>')
    b.append(f'<circle cx="34" cy="155" r="4" fill="{c["accent"]}"/><circle class="pulse" cx="34" cy="155" r="4" fill="{c["accent"]}"/>')
    b.append(f'<text class="fade" style="animation-delay:.3s" x="46" y="159.5" font-size="13.5">'
             f'{esc(PROFILE["position"])} <tspan class="mut">@</tspan> <tspan font-weight="700">{esc(PROFILE["company"])}</tspan></text>')
    b.append(f'<text class="fade mut" style="animation-delay:.35s" x="28" y="181" font-size="12.5">'
             f'PUC Minas · Software Eng. ({esc(PROFILE["graduation"])}) · {esc(PROFILE["location"])}</text>')

    WX, WW = HW + G, W - HW - G
    b.append(card(WX, 0, WW, R1, c))
    b.append(f'<text class="eyebrow" x="{WX + 22}" y="34">CODING TIME</text>')
    if waka["hours"]:
        b.append(f'<text class="mono" x="{WX + WW - 22}" y="34" text-anchor="end" font-size="12" fill="{c["accent"]}" '
                 f'font-weight="700">{fmt_hours(waka["hours"])} <tspan class="mut" font-weight="400">{esc(waka["label"])}</tspan></text>')
    y = 62
    for i, l in enumerate(waka["langs"]):
        col = LANG_COLORS.get(l["name"], c["muted"])
        # icon spans the whole row (name + bar) so it reads as one unit
        b.append(lang_mark(l["name"], WX + 33, y + 0.5, 22, col, theme))
        b.append(f'<text x="{WX + 52}" y="{y}" font-size="13" font-weight="500">{esc(l["name"])}</text>')
        b.append(f'<text class="mono mut" x="{WX + WW - 22}" y="{y}" text-anchor="end" font-size="11.5">{l["pct"]:.0f}%</text>')
        bx, bw = WX + 52, WW - 74
        b.append(f'<rect x="{bx}" y="{y + 7}" width="{bw}" height="4" rx="2" fill="{c["track"]}"/>')
        b.append(f'<rect class="bar" style="animation-delay:{0.25 + i * 0.1:.2f}s" x="{bx}" y="{y + 7}" '
                 f'width="{max(3, bw * l["fill"]):.1f}" height="4" rx="2" fill="{col}"/>')
        y += 27

    # Row 2: contributions (wide) + PRs + repos
    Y2, R2, CW = R1 + G, 100, 420
    b.append(card(0, Y2, CW, R2, c))
    b.append(f'<text class="eyebrow" x="22" y="{Y2 + 30}">CONTRIBUTIONS · 12 MONTHS</text>')
    b.append(f'<text x="22" y="{Y2 + 74}" font-size="32" font-weight="800" letter-spacing="-.5">{fmt_int(gh["contributions"])}</text>')
    b.append(sparkline(gh["weeks"], 150, Y2 + 44, CW - 172, 36, c["accent"], c["track"], 0.3))
    SW = (W - CW - 2 * G) / 2
    for i, (label, val) in enumerate((("PULL REQUESTS", gh["prs"]), ("PUBLIC REPOS", gh["repos"]))):
        sx = CW + G + i * (SW + G)
        b.append(card(sx, Y2, SW, R2, c))
        b.append(f'<text class="eyebrow" x="{sx + 22}" y="{Y2 + 30}">{label}</text>')
        b.append(f'<text x="{sx + 22}" y="{Y2 + 74}" font-size="32" font-weight="800">{val}</text>')

    # Row 3: stack chips with icons
    Y3 = Y2 + R2 + G
    b.append(f'<text class="eyebrow" x="22" y="{Y3 + 32}">STACK</text>')
    chip_svg, bottom = chips(STACK, 22, Y3 + 46, W - 44, 30, 7, c["chip"], c["border"], c["text"], 15, SANS, theme)
    R3 = bottom - Y3 + 20
    b.insert(len(b) - 1, card(0, Y3, W, R3, c))
    b.append(chip_svg)
    return svg(W, int(Y3 + R3), "".join(b), style, f"{PROFILE['name']} — GitHub profile")


# -------------------------------------------------------- style: API card ---


def json_lines() -> list[list[tuple[str, str]]]:
    """Tokenised pretty JSON: list of lines, each a list of (token_class, text)."""
    L: list[list[tuple[str, str]]] = [[("p", "{")]]

    def kv(k, v, last=False):
        line = [("p", "  "), ("k", f'"{k}"'), ("p", ": ")]
        if isinstance(v, list):
            line.append(("p", "["))
            for i, item in enumerate(v):
                line += [("q", '"'), ("s", item), ("q", '"')]
                if i < len(v) - 1:
                    line.append(("p", ", "))
            line.append(("p", "]"))
        else:
            line += [("q", '"'), ("s", v), ("q", '"')]
        if not last:
            line.append(("p", ","))
        L.append(line)

    kv("focus", ["backend", "integrations", "async events"])
    kv("domain", "fiscal documents · NF-e, NFS-e")
    kv("education", "Software Engineering @ PUC Minas")
    kv("graduation", PROFILE["graduation"])
    kv("location", PROFILE["location"], last=True)
    L.append([("p", "}")])
    return L


def render_api(theme: str, gh: dict, waka: dict, updated: str) -> str:
    c = THEMES["api"][theme]
    W, TB, PAD = 845, 44, 22
    RX = 520
    RW = W - RX - PAD
    style = ANIM + f"""
text{{font-family:{MONO}}}
.k{{fill:{c['key']}}}.s{{fill:{c['text']}}}.q,.p{{fill:{c['punct']}}}
.ln{{fill:{c['faint']};font-size:12px}}
.cm{{fill:{c['muted']};font-size:11.5px}}
.lbl{{fill:{c['muted']};font-size:11px}}
.val{{fill:{c['text']};font-size:19px;font-weight:700}}
.sm{{fill:{c['text']};font-size:12.5px}}
"""
    b = [f"""<defs><linearGradient id="ng" x1="0" x2="1"><stop offset="0" stop-color="{c['text']}"/>
<stop offset="1" stop-color="{c['key']}"/></linearGradient></defs>"""]

    def divider(y, dashed=False):
        dash = ' stroke-dasharray="3 4"' if dashed else ""
        b.append(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{c["border"]}"{dash}/>')

    # placeholder for window background (height known at the end)
    b.append("{WINDOW}")

    # title bar
    for i, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        b.append(f'<circle cx="{22 + i * 18}" cy="{TB / 2}" r="5.5" fill="{col}"/>')
    b.append(f'<rect x="84" y="12" width="44" height="20" rx="5" fill="{c["method_bg"]}"/>'
             f'<text x="106" y="26" text-anchor="middle" font-size="11.5" font-weight="700" fill="{c["method_fg"]}">GET</text>')
    b.append(f'<text x="140" y="26.5" font-size="13.5" fill="{c["text"]}">/users/<tspan font-weight="700">{esc(OWNER)}</tspan></text>')
    b.append(f'<circle cx="{W - 198}" cy="{TB / 2}" r="4" fill="{c["ok"]}"/>'
             f'<circle class="pulse" cx="{W - 198}" cy="{TB / 2}" r="4" fill="{c["ok"]}"/>')
    b.append(f'<text x="{W - 188}" y="26.5" font-size="12.5" font-weight="700" fill="{c["ok"]}">200 OK</text>')
    b.append(f'<text x="{W - PAD}" y="26.5" text-anchor="end" font-size="11.5" fill="{c["muted"]}">application/json</text>')

    # hero: big name + role, stat tiles on the right
    b.append(f'<text class="fade" x="{PAD + 2}" y="{TB + 62}" font-size="42" font-weight="800" '
             f'letter-spacing="-1" fill="url(#ng)">{esc(PROFILE["name"])}</text>')
    b.append(f'<text class="fade" style="animation-delay:.1s" x="{PAD + 4}" y="{TB + 92}" font-size="14.5" '
             f'font-weight="700" fill="{c["key"]}">{esc(PROFILE["role"])}</text>')
    b.append(f'<text class="fade" style="animation-delay:.2s" x="{PAD + 4}" y="{TB + 118}" font-family="{SANS}" '
             f'font-size="14" fill="{c["muted"]}">{esc(PROFILE["position"])} @ '
             f'<tspan font-weight="700" fill="{c["text"]}">{esc(PROFILE["company"])}</tspan></text>')
    tiles = [
        ("contributions · 12m", fmt_int(gh["contributions"])),
        ("coding time", fmt_hours(waka["hours"]) if waka["hours"] else "—"),
        ("public repos", str(gh["repos"])),
        ("pull requests", str(gh["prs"])),
    ]
    tw, th, gap = (RW - 10) / 2, 48, 10
    for i, (lbl, val) in enumerate(tiles):
        tx = RX + (i % 2) * (tw + gap)
        ty = TB + 20 + (i // 2) * (th + 8)
        b.append(f'<rect x="{tx:.1f}" y="{ty}" width="{tw:.1f}" height="{th}" rx="8" fill="{c["tile"]}" stroke="{c["border"]}"/>')
        b.append(f'<text class="lbl" x="{tx + 12:.1f}" y="{ty + 18}">{esc(lbl)}</text>')
        b.append(f'<text class="val" x="{tx + 12:.1f}" y="{ty + 39}">{esc(val)}</text>')

    # body: JSON (left) + wakatime (right)
    y_div = TB + 146
    divider(y_div)
    lines = json_lines()
    lh, y0 = 23, y_div + 30
    for i, line in enumerate(lines):
        y = y0 + i * lh
        b.append(f'<text class="ln" x="{PAD + 12}" y="{y}" text-anchor="end">{i + 1}</text>')
        spans = "".join(f'<tspan class="{cls}">{esc(t)}</tspan>' for cls, t in line)
        b.append(f'<text class="fade" style="animation-delay:{0.25 + i * 0.07:.2f}s" x="{PAD + 26}" y="{y}" '
                 f'font-size="13.5" xml:space="preserve">{spans}</text>')
    last_y = y0 + (len(lines) - 1) * lh
    b.append(f'<rect class="blink" x="{PAD + 36}" y="{last_y - 12}" width="8" height="15" fill="{c["key"]}" fill-opacity=".8"/>')

    b.append(f'<line x1="{RX - 18}" y1="{y_div + 14}" x2="{RX - 18}" y2="{last_y + 8}" stroke="{c["border"]}" stroke-dasharray="3 4"/>')
    y = y_div + 30
    b.append(f'<text class="cm" x="{RX}" y="{y}">// wakatime · {esc(waka["label"])}</text>')
    y += 25
    for i, l in enumerate(waka["langs"]):
        col = LANG_COLORS.get(l["name"], c["muted"])
        b.append(lang_mark(l["name"], RX + 8, y - 4, 16, col, theme))
        b.append(f'<text class="sm" x="{RX + 24}" y="{y}">{esc(l["name"])}</text>')
        bx = RX + 118
        bw = RW - 118 - 46
        b.append(f'<rect x="{bx}" y="{y - 8}" width="{bw}" height="8" rx="4" fill="{c["track"]}"/>')
        b.append(f'<rect class="bar" style="animation-delay:{0.3 + i * 0.1:.2f}s" x="{bx}" y="{y - 8}" '
                 f'width="{max(4, bw * l["fill"]):.1f}" height="8" rx="4" fill="{col}"/>')
        b.append(f'<text class="lbl" x="{RX + RW}" y="{y}" text-anchor="end">{l["pct"]:.1f}%</text>')
        y += 23

    # stack
    y_stack = max(last_y, y - 23) + 22
    divider(y_stack)
    b.append(f'<text class="cm" x="{PAD}" y="{y_stack + 26}">// stack</text>')
    chip_svg, bottom = chips(STACK, PAD, y_stack + 40, W - 2 * PAD, 28, 7, c["chip"], c["border"], c["text"], 6, MONO, theme)
    b.append(chip_svg)

    # footer: weekly contributions
    fy = bottom + 20
    divider(fy)
    b.append(f'<text class="cm" x="{PAD}" y="{fy + 24}">// contributions per week</text>')
    b.append(f'<text class="cm" x="{W - PAD}" y="{fy + 24}" text-anchor="end">updated {esc(updated)}</text>')
    b.append(sparkline(gh["weeks"], PAD, fy + 34, W - 2 * PAD, 40, c["spark"], c["track"], 0.4))
    H = int(fy + 34 + 40 + 18)

    window = (f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{c["bg"]}" stroke="{c["border"]}"/>'
              f'<path d="M.5 12.5a12 12 0 0 1 12-12h{W - 25}a12 12 0 0 1 12 12V{TB}H.5z" fill="{c["bar"]}"/>'
              f'<line x1="0" y1="{TB}" x2="{W}" y2="{TB}" stroke="{c["border"]}"/>')
    body = "".join(b).replace("{WINDOW}", window)
    return svg(W, H, body, style, f"{PROFILE['name']} — GitHub profile")


# ------------------------------------------- project cards & social buttons ---


def render_project(style_name: str, theme: str, p: dict) -> str:
    W, H = 273, 118
    if style_name == "api":
        c = THEMES["api"][theme]
        bg, border, text, muted = c["bg"], c["border"], c["text"], c["muted"]
        title = (f'<text x="16" y="28" font-family="{MONO}" font-size="12" fill="{c["ok"]}" font-weight="700">GET</text>'
                 f'<text x="46" y="28" font-family="{MONO}" font-size="13" fill="{text}" font-weight="700">/{esc(p["name"])}</text>')
        dfont, dsize, lines, rx = MONO, 11, wrap(p["desc"], 36, 3), 10
    else:
        c = THEMES["bento"][theme]
        bg, border, text, muted = c["card"], c["border"], c["text"], c["muted"]
        title = f'<text x="16" y="29" font-family="{SANS}" font-size="15" fill="{text}" font-weight="700">{esc(p["name"])}</text>'
        dfont, dsize, lines, rx = SANS, 12, wrap(p["desc"], 40, 3), 14
    b = [f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="{rx}" fill="{bg}" stroke="{border}"/>', title]
    for i, ln in enumerate(lines):
        b.append(f'<text x="16" y="{50 + i * 16}" font-family="{dfont}" font-size="{dsize}" fill="{muted}">{esc(ln)}</text>')
    b.append(lang_mark(p["lang"], 23, H - 17, 14, p["color"], theme))
    b.append(f'<text x="35" y="{H - 13}" font-family="{SANS}" font-size="11.5" fill="{muted}">{esc(p["lang"])}</text>')
    b.append(f'<text x="{W - 16}" y="{H - 13}" text-anchor="end" font-family="{SANS}" font-size="11.5" fill="{muted}">'
             f'★ {p["stars"]}</text>')
    return svg(W, H, "".join(b), "", f'{p["name"]}: {p["desc"]}')


def render_button(style_name: str, theme: str, kind: str) -> str:
    label = {"linkedin": "LinkedIn", "email": "Email"}[kind]
    if style_name == "api":
        c = THEMES["api"][theme]
        bg, border, text, acc, font, rx = c["bg"], c["border"], c["text"], c["key"], MONO, 8
    else:
        c = THEMES["bento"][theme]
        bg, border, text, acc, font, rx = c["card"], c["border"], c["text"], c["accent"], SANS, 17
    W, H = (118 if kind == "linkedin" else 96), 34
    if kind == "linkedin":
        mark = (f'<rect x="14" y="9" width="16" height="16" rx="3" fill="#0a66c2"/>'
                f'<text x="22" y="21.5" text-anchor="middle" font-family="{SANS}" font-size="11" font-weight="800" fill="#fff">in</text>')
    else:
        mark = (f'<rect x="14" y="11" width="16" height="12" rx="2" fill="none" stroke="{acc}" stroke-width="1.6"/>'
                f'<path d="M14.8 12l7.2 5.6 7.2-5.6" fill="none" stroke="{acc}" stroke-width="1.6"/>')
    body = (f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="{rx}" fill="{bg}" stroke="{border}"/>{mark}'
            f'<text x="38" y="21.5" font-family="{font}" font-size="12.5" font-weight="600" fill="{text}">{label}</text>')
    return svg(W, H, body, "", label)


# ------------------------------------------------------------------- main ---


def main() -> None:
    gh = fetch_github()
    waka = fetch_wakatime()
    updated = dt.datetime.now(BRT).strftime("%d %b %Y")
    OUT.mkdir(exist_ok=True)

    def write(name: str, content: str) -> None:
        (OUT / name).write_text(content, encoding="utf-8")

    for theme in ("dark", "light"):
        write(f"api-{theme}.svg", render_api(theme, gh, waka, updated))
        write(f"bento-{theme}.svg", render_bento(theme, gh, waka, updated))
        for style_name in ("api", "bento"):
            for i, p in enumerate(gh["projects"], 1):
                write(f"{style_name}-project-{i}-{theme}.svg", render_project(style_name, theme, p))
            for kind in LINKS:
                write(f"{style_name}-btn-{kind}-{theme}.svg", render_button(style_name, theme, kind))
    print(f"ok - {gh['contributions']} contributions - waka {waka['label']} - {len(gh['projects'])} projects")


if __name__ == "__main__":
    main()
