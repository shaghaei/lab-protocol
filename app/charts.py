"""Server-rendered SVG strip charts (no JavaScript, no external libraries)."""
from html import escape
from math import floor, log10

WIDTH = 720
LEFT = 116
RIGHT = 34
ROW_H = 58
TOP = 30


def nice_step(span: float) -> float:
    raw = span / 6
    power = 10 ** floor(log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * power:
            return m * power
    return 10 * power


def strip_chart(rows: list, median: float, band: tuple, spread: float, caption: str,
                decimals: int, axis_label: str) -> str:
    """rows: [(row_label, [(point_label, value, highlight, flagged)], row_flagged)]

    One horizontal strip per row, the class median as a dashed line and the zone
    'consistent with the class' (median ± 3 robust SD) shaded. Values far outside
    the window are drawn as arrows at the edge so they do not squeeze the scale.
    """
    window = max(8 * spread, 0.02 * abs(median))
    values = [p[1] for _, pts, _ in rows for p in pts] + list(band)
    lo = max(min(values), median - window)
    hi = min(max(values), median + window)
    pad = (hi - lo) * 0.06 or abs(median) * 0.01 or 1
    lo, hi = lo - pad, hi + pad
    step = nice_step(hi - lo)
    tick_dec = max(0, -floor(log10(step)) + (1 if step / 10 ** floor(log10(step)) == 2.5 else 0))
    plot_w = WIDTH - LEFT - RIGHT

    def x(v: float) -> float:
        return LEFT + (v - lo) / (hi - lo) * plot_w

    bottom = TOP + ROW_H * len(rows)
    height = bottom + 48
    out = [f'<svg viewBox="0 0 {WIDTH} {height}" class="chart" role="img" aria-label="{escape(caption)}">']
    out.append(f'<rect class="band" x="{x(max(band[0], lo)):.1f}" y="{TOP}" '
               f'width="{x(min(band[1], hi)) - x(max(band[0], lo)):.1f}" height="{bottom - TOP}"/>')
    t = floor(lo / step) * step
    while t <= hi + 1e-12:
        if t >= lo:
            out.append(f'<line class="grid" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{TOP}" y2="{bottom}"/>')
            out.append(f'<text class="tick" x="{x(t):.1f}" y="{bottom + 18}" text-anchor="middle">'
                       f'{t:.{tick_dec}f}</text>')
        t += step
    out.append(f'<line class="median" x1="{x(median):.1f}" x2="{x(median):.1f}" y1="{TOP - 8}" y2="{bottom}"/>')
    anchor = "end" if x(median) > LEFT + plot_w * 0.7 else "start"
    dx = -6 if anchor == "end" else 6
    out.append(f'<text class="note" x="{x(median) + dx:.1f}" y="{TOP - 12}" text-anchor="{anchor}">'
               f'class median {median:.{decimals}f}</text>')

    for r, (row_label, points, row_flagged) in enumerate(rows):
        cy = TOP + ROW_H * r + ROW_H / 2
        if r:
            out.append(f'<line class="rowrule" x1="{LEFT}" x2="{LEFT + plot_w}" y1="{TOP + ROW_H * r}" '
                       f'y2="{TOP + ROW_H * r}"/>')
        cls = "rowlabel flagged" if row_flagged else "rowlabel"
        out.append(f'<text class="{cls}" x="{LEFT - 14}" y="{cy + 4:.1f}" text-anchor="end">'
                   f'{escape(row_label)}</text>')
        for i, (label, value, highlight, flagged) in enumerate(points):
            y = cy + ((i * 7) % 5 - 2) * 6
            kind = "me" if highlight else "out" if flagged else "dot"
            tip = f"<title>{escape(label)}: {value:.{decimals}f}</title>"
            if value > hi or value < lo:
                edge, d = (x(hi), 1) if value > hi else (x(lo), -1)
                out.append(f'<path class="{kind}" d="M{edge + 8 * d:.1f} {y:.1f}l{-10 * d} -6v12z">{tip}</path>')
                out.append(f'<text class="offscale" x="{edge + 10 * d:.1f}" y="{y + 22:.1f}" '
                           f'text-anchor="{"end" if d > 0 else "start"}">{escape(label)} '
                           f'{value:.{decimals}f}</text>')
                continue
            radius = 7.5 if highlight else 5
            out.append(f'<circle class="{kind}" cx="{x(value):.1f}" cy="{y:.1f}" r="{radius}">{tip}</circle>')
            if highlight:
                out.append(f'<text class="melabel" x="{x(value):.1f}" y="{y - 13:.1f}" '
                           f'text-anchor="middle">{escape(label)}</text>')
    out.append(f'<text class="axis" x="{LEFT + plot_w / 2:.1f}" y="{bottom + 40}" '
               f'text-anchor="middle">{escape(axis_label)}</text>')
    out.append("</svg>")
    return "".join(out)
