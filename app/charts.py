"""Server-rendered SVG strip charts (no JavaScript, no external libraries)."""
from html import escape
from math import ceil, floor

WIDTH = 720
LEFT = 110
RIGHT = 30
ROW_H = 56
TOP = 24
WINDOW = 0.035  # half-width of the axis around the class median, in f units


def _ticks(lo: float, hi: float) -> list:
    span = hi - lo
    step = 0.005 if span <= 0.04 else 0.01 if span <= 0.08 else 0.02 if span <= 0.2 else 0.05
    start = floor(lo / step) * step
    ticks, t = [], start
    while t <= hi + 1e-9:
        if t >= lo - 1e-9:
            ticks.append(round(t, 4))
        t += step
    return ticks


def strip_chart(rows: list, median: float, band: tuple, caption: str) -> str:
    """rows: [(row_label, [(point_label, value, highlight, flagged)], row_flagged)]

    Draws one horizontal strip per row, the class median as a line and the
    'consistent with the class' band (median ± 3 robust SD) as a shaded zone.
    """
    values = [p[1] for _, pts, _ in rows for p in pts] + [band[0], band[1]]
    pad = 0.004
    # Keep the scale readable: values further than WINDOW from the median are
    # drawn as arrows at the edge instead of stretching the axis.
    lo = max(min(values) - pad, median - WINDOW)
    hi = min(max(values) + pad, median + WINDOW)
    lo, hi = floor(lo * 200) / 200, ceil(hi * 200) / 200
    plot_w = WIDTH - LEFT - RIGHT

    def x(v: float) -> float:
        return LEFT + (v - lo) / (hi - lo) * plot_w

    height = TOP + ROW_H * len(rows) + 44
    bottom = TOP + ROW_H * len(rows)
    parts = [f'<svg viewBox="0 0 {WIDTH} {height}" class="chart" role="img" '
             f'aria-label="{escape(caption)}">']
    parts.append(f'<rect class="band" x="{x(band[0]):.1f}" y="{TOP}" '
                 f'width="{x(band[1]) - x(band[0]):.1f}" height="{bottom - TOP}"/>')
    for t in _ticks(lo, hi):
        parts.append(f'<line class="grid" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{TOP}" y2="{bottom}"/>')
        parts.append(f'<text class="tick" x="{x(t):.1f}" y="{bottom + 18}" text-anchor="middle">{t:.3f}</text>')
    parts.append(f'<line class="median" x1="{x(median):.1f}" x2="{x(median):.1f}" '
                 f'y1="{TOP - 6}" y2="{bottom}"/>')
    parts.append(f'<text class="note" x="{x(median) + 4:.1f}" y="{TOP - 10}">class median {median:.4f}</text>')

    for r, (row_label, points, row_flagged) in enumerate(rows):
        cy = TOP + ROW_H * r + ROW_H / 2
        cls = "rowlabel flagged" if row_flagged else "rowlabel"
        parts.append(f'<text class="{cls}" x="{LEFT - 12}" y="{cy + 4:.1f}" text-anchor="end">'
                     f'{escape(row_label)}</text>')
        for i, (label, value, highlight, flagged) in enumerate(points):
            jitter = ((i * 7) % 5 - 2) * 6
            kind = "me" if highlight else "out" if flagged else "dot"
            tip = f'<title>{escape(label)}: f = {value:.4f}</title>'
            y = cy + jitter
            if value > hi or value < lo:
                edge = x(hi) if value > hi else x(lo)
                d = 1 if value > hi else -1
                parts.append(f'<path class="{kind}" d="M{edge + 8 * d:.1f} {y:.1f}l{-10 * d} -6v12z">{tip}</path>')
                parts.append(f'<text class="offscale" x="{edge - 4 * d:.1f}" y="{y - 10:.1f}" '
                             f'text-anchor="{"end" if d > 0 else "start"}">{escape(label)} {value:.3f}</text>')
                continue
            radius = 7 if highlight else 5
            parts.append(f'<circle class="{kind}" cx="{x(value):.1f}" cy="{y:.1f}" r="{radius}">{tip}</circle>')
            if highlight:
                parts.append(f'<text class="melabel" x="{x(value):.1f}" y="{y - 12:.1f}" '
                             f'text-anchor="middle">{escape(label)}</text>')
    parts.append(f'<text class="axis" x="{LEFT + plot_w / 2:.1f}" y="{bottom + 38}" '
                 f'text-anchor="middle">factor f</text>')
    parts.append("</svg>")
    return "".join(parts)
