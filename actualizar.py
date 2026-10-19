#!/usr/bin/env python3
"""Actualiza index.html con las ventas de Mercado Libre de los ultimos 2 dias.
Uso: ML_ACCESS_TOKEN=... python3 actualizar.py   (corre dentro de la carpeta del repo)"""
import os, re, json, time, collections, datetime as dt, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
TOK = os.environ["ML_ACCESS_TOKEN"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
TZ = dt.timezone(dt.timedelta(hours=-3))
SELLER = 2702415919

def get(url, h=None):
    for i in range(6):
        try:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOK}", "User-Agent": UA, **(h or {})})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception:
            time.sleep(1.2 * (i + 1))
    return None

def day(d):
    s = dt.datetime.combine(d, dt.time(0, 0), TZ); e = dt.datetime.combine(d, dt.time(23, 59, 59), TZ)
    out, off = [], 0
    while True:
        r = get("https://api.mercadolibre.com/orders/search?" + urllib.parse.urlencode({
            "seller": SELLER, "order.date_created.from": s.isoformat(timespec="milliseconds"),
            "order.date_created.to": e.isoformat(timespec="milliseconds"), "sort": "date_asc", "limit": 50, "offset": off}))
        if r is None:
            raise SystemExit(f"Fallo al leer ordenes de {d}")
        res = r.get("results", []); out += res; off += 50
        if not res or off >= r.get("paging", {}).get("total", 0):
            return out

now = dt.datetime.now(TZ)
cut = now.date() - dt.timedelta(days=1)
days = [cut + dt.timedelta(n) for n in range((now.date() - cut).days + 1)]
orders = {}
for d in days:
    for o in day(d):
        orders.setdefault(o["id"], o)
orders = {k: o for k, o in orders.items() if o["status"] != "cancelled"}

def ship(sid):
    sh = get(f"https://api.mercadolibre.com/shipments/{sid}", {"x-format-new": "true"})
    if not sh:
        return sid, None
    ra = (sh.get("destination") or {}).get("shipping_address") or {}
    c, s = ra.get("city"), ra.get("state")
    c = c.get("name") if isinstance(c, dict) else c
    s = s.get("name") if isinstance(s, dict) else s
    return sid, (s or "Sin dato", c or "Sin dato")
sids = sorted({(o.get("shipping") or {}).get("id") for o in orders.values()} - {None})
with ThreadPoolExecutor(16) as ex:
    loc = {sid: v for sid, v in ex.map(ship, sids) if v}
if sids and len(loc) < 0.9 * len(sids):
    raise SystemExit("Demasiados envios sin resolver; no se actualiza")

ord_rows, lin_rows, agg = [], [], collections.defaultdict(lambda: [0, 0])
for o in orders.values():
    t = dt.datetime.fromisoformat(o["date_created"]).astimezone(TZ)
    f = t.strftime("%Y-%m-%d"); v = round(o.get("total_amount", 0))
    ord_rows.append([f, t.hour, v, o["status"]])
    for it in o.get("order_items", []):
        lin_rows.append([f, it["item"]["id"], it["item"]["title"][:70], it["quantity"], round(it["quantity"] * it["unit_price"])])
    p, c = loc.get((o.get("shipping") or {}).get("id"), ("Sin dato", "Sin dato"))
    a = agg[(f, p, c)]; a[0] += 1; a[1] += v
ciu_rows = [[f, p, c, n, v] for (f, p, c), (n, v) in sorted(agg.items())]

html = open("index.html", encoding="utf-8").read()
m = re.search(r"window\.__RAW=(\{.*?\});\n</script>", html, re.S)
raw = json.loads(m.group(1))
for k, new in (("ordenes", ord_rows), ("lineas", lin_rows), ("ciudades", ciu_rows)):
    keep = [r for r in raw[k]["rows"] if r[0] < cut.isoformat()]
    raw[k]["rows"] = keep + new
html = html[:m.start(1)] + json.dumps(raw, ensure_ascii=False, separators=(",", ":")) + html[m.end(1):]
d = now
html = re.sub(r"1/1 al \d+/\d+/\d{4} \(el \d+/\d+ es parcial\)", f"1/1 al {d.day}/{d.month}/{d.year} (el {d.day}/{d.month} es parcial)", html)
open("index.html", "w", encoding="utf-8").write(html)
tot = sum(r[2] for r in ord_rows if r[0] == now.strftime("%Y-%m-%d"))
print("ok", now.strftime("%Y-%m-%d %H:%M"), "ordenes ventana", len(ord_rows), "venta hoy", tot)
