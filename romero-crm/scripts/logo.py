"""Genera el logo de Romero Xandre CRM (python3 scripts/logo.py <salida.svg> [full|mark|mono]): dos ramitas de romero que crecen y se cruzan formando una X.
La verde sube como una línea de tendencia y termina en una chispa (lo que está caliente)."""
import math, sys

def bezier(p, t):
    p0, p1, p2, p3 = p
    u = 1 - t
    x = u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0]
    y = u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1]
    dx = 3*u*u*(p1[0]-p0[0]) + 6*u*t*(p2[0]-p1[0]) + 3*t*t*(p3[0]-p2[0])
    dy = 3*u*u*(p1[1]-p0[1]) + 6*u*t*(p2[1]-p1[1]) + 3*t*t*(p3[1]-p2[1])
    return x, y, math.atan2(dy, dx)

def leaf(x, y, angle, length, width):
    tip = (x + length*math.cos(angle), y + length*math.sin(angle))
    nx, ny = -math.sin(angle), math.cos(angle)
    a = (x + 0.42*length*math.cos(angle) + nx*width, y + 0.42*length*math.sin(angle) + ny*width)
    b = (x + 0.42*length*math.cos(angle) - nx*width, y + 0.42*length*math.sin(angle) - ny*width)
    return (f"M{x:.1f},{y:.1f} Q{a[0]:.1f},{a[1]:.1f} {tip[0]:.1f},{tip[1]:.1f} "
            f"Q{b[0]:.1f},{b[1]:.1f} {x:.1f},{y:.1f}Z")

def sprig(p, n, length, width, spread, start=0.08, end=0.9, shrink=0.5):
    stem = f"M{p[0][0]},{p[0][1]} C{p[1][0]},{p[1][1]} {p[2][0]},{p[2][1]} {p[3][0]},{p[3][1]}"
    leaves = []
    for i in range(n):
        t = start + (end - start) * i / (n - 1)
        x, y, a = bezier(p, t)
        k = 1 - shrink * (i / (n - 1))
        for side in (1, -1):
            jitter = 0.06 if (i + (side > 0)) % 2 else -0.04
            leaves.append(leaf(x, y, a + side * (spread + jitter), length * k, width * k))
    return stem, leaves

def star(cx, cy, r, inner):
    pts = []
    for i in range(8):
        ang = -math.pi/2 + i * math.pi/4
        rad = r if i % 2 == 0 else inner
        pts.append((cx + rad*math.cos(ang), cy + rad*math.sin(ang)))
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(1, 9):
        p = pts[i % 8]
        prev = pts[(i - 1) % 8]
        # curvas suaves hacia el centro para una chispa elegante
        mx, my = (prev[0] + p[0]) / 2, (prev[1] + p[1]) / 2
        cxp, cyp = cx + (mx - cx) * 0.35, cy + (my - cy) * 0.35
        d += f" Q{cxp:.1f},{cyp:.1f} {p[0]:.1f},{p[1]:.1f}"
    return d + "Z"

def svg(size=1024, background=True, mono=None, spark=True):
    up = ((292, 772), (400, 650), (548, 470), (706, 318))
    up2 = ((732, 772), (624, 650), (476, 470), (318, 318))
    s_up, l_up = sprig(up, n=13, length=124, width=21, spread=0.5)
    s_dn, l_dn = sprig(up2, n=12, length=112, width=19, spread=0.52)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="{size}" height="{size}">']
    out.append('''<defs>
  <linearGradient id="bg" x1="0.15" y1="0" x2="0.85" y2="1">
    <stop offset="0" stop-color="#2A2163"/><stop offset="0.5" stop-color="#15123A"/><stop offset="1" stop-color="#090913"/>
  </linearGradient>
  <radialGradient id="glow" cx="0.3" cy="0.12" r="0.75">
    <stop offset="0" stop-color="#9D8BFF" stop-opacity="0.38"/><stop offset="1" stop-color="#9D8BFF" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#FFFFFF" stop-opacity="0.10"/><stop offset="0.5" stop-color="#FFFFFF" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="leafUp" gradientUnits="userSpaceOnUse" x1="292" y1="772" x2="706" y2="318">
    <stop offset="0" stop-color="#2FB384"/><stop offset="0.55" stop-color="#6FDDA9"/><stop offset="1" stop-color="#D9F7C2"/>
  </linearGradient>
  <linearGradient id="leafDown" gradientUnits="userSpaceOnUse" x1="732" y1="772" x2="318" y2="318">
    <stop offset="0" stop-color="#6A55E8"/><stop offset="1" stop-color="#C7B8FF"/>
  </linearGradient>
  <radialGradient id="spark" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="#FFFBEA"/><stop offset="0.45" stop-color="#FFD27A"/><stop offset="1" stop-color="#FF8A3D"/>
  </radialGradient>
  <radialGradient id="halo" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="#FFB547" stop-opacity="0.75"/><stop offset="0.45" stop-color="#FF8A3D" stop-opacity="0.22"/><stop offset="1" stop-color="#FF8A3D" stop-opacity="0"/>
  </radialGradient>
  <filter id="tile" x="-0.1" y="-0.1" width="1.2" height="1.25"><feDropShadow dx="0" dy="14" stdDeviation="18" flood-color="#000" flood-opacity="0.28"/></filter>
  <filter id="lift" x="-0.2" y="-0.2" width="1.4" height="1.4"><feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#05040F" flood-opacity="0.55"/></filter>
</defs>''')
    if background:
        out.append('<rect x="100" y="100" width="824" height="824" rx="186" fill="url(#bg)" filter="url(#tile)"/>')
        out.append('<rect x="100" y="100" width="824" height="824" rx="186" fill="url(#glow)"/>')
        out.append('<rect x="100" y="100" width="824" height="824" rx="186" fill="url(#sheen)"/>')
        out.append('<rect x="101.5" y="101.5" width="821" height="821" rx="185" fill="none" stroke="#FFFFFF" stroke-opacity="0.12" stroke-width="3"/>')
    up_fill = mono or "url(#leafUp)"
    dn_fill = mono or "url(#leafDown)"
    out.append('<g filter="url(#lift)">')
    out.append(f'<g fill="{dn_fill}">' + "".join(f'<path d="{d}"/>' for d in l_dn) + '</g>')
    out.append(f'<path d="{s_dn}" fill="none" stroke="{dn_fill}" stroke-width="22" stroke-linecap="round"/>')
    out.append(f'<g fill="{up_fill}">' + "".join(f'<path d="{d}"/>' for d in l_up) + '</g>')
    out.append(f'<path d="{s_up}" fill="none" stroke="{up_fill}" stroke-width="24" stroke-linecap="round"/>')
    out.append('</g>')
    if spark:
        out.append('<circle cx="712" cy="304" r="120" fill="url(#halo)"/>')
        out.append(f'<path d="{star(712, 304, 66, 15)}" fill="{mono or "url(#spark)"}"/>')
    out.append('</svg>')
    return "\n".join(out)

if __name__ == "__main__":
    kind = sys.argv[2] if len(sys.argv) > 2 else "full"
    if kind == "full":
        open(sys.argv[1], "w").write(svg())
    elif kind == "mark":
        open(sys.argv[1], "w").write(svg(background=False))
    elif kind == "mono":
        open(sys.argv[1], "w").write(svg(background=False, mono="#000000"))
