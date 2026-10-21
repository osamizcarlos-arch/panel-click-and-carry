#!/usr/bin/env python3
"""Actualiza locales/index.html con las ventas, vendedoras y stock de Tienda Cabildo y Tienda DOT
(Odoo, Punto de venta de Ecotrade). Misma estructura de datos que el panel de Mercado Libre.
La clave de Odoo se pasa por la variable de entorno ODOO_KEY. Nunca se guarda en este repo (es público)."""
import os, sys, re, json, collections, datetime as dt, xmlrpc.client

URL = "https://parisnight.odoo.com"
DB = "parisnight-main-34324367"
USER = "Claude/integraciones"
DESDE = "2026-10-01"
VENTANA_DIAS = 30          # ventana para el ritmo de venta del stock
UBICACIONES = {"Cabildo": "CABIL/Existencias", "DOT": "DOT/Existencias"}
HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales", "index.html")

key = os.environ.get("ODOO_KEY")
if not key:
    sys.exit("Falta ODOO_KEY")
uid = xmlrpc.client.ServerProxy(URL + "/xmlrpc/2/common").authenticate(DB, USER, key, {})
if not uid:
    sys.exit("Odoo no autenticó: la clave venció o cambió. No se sube nada.")
o = xmlrpc.client.ServerProxy(URL + "/xmlrpc/2/object")
def x(m, f, a, k=None):
    k = dict(k or {}); k["context"] = {"allowed_company_ids": [1, 2]}
    return o.execute_kw(DB, uid, key, m, f, a, k)

orders = x("pos.order", "search_read",
           [[["company_id", "=", 2], ["state", "not in", ["cancel", "draft"]], ["amount_total", ">", 0]]],
           {"fields": ["date_order", "amount_total", "config_id", "seller_id"]})
if not orders:
    sys.exit("Odoo devolvió 0 órdenes. No se sube nada.")

def local_caja(nombre):
    local = "DOT" if "DOT" in nombre else "Cabildo"
    m = re.search(r"CAJA\s*(\d+)", nombre.upper())
    return local, ("Caja " + m.group(1)) if m else nombre

def corto(nombre):
    """Nombre y inicial del apellido (el panel es público): 'Mariana Nacimiento' -> 'Mariana N.'"""
    p = (nombre or "").split()
    if not p:
        return "Sin asignar"
    return p[0].title() + ((" " + p[-1][0].upper() + ".") if len(p) > 1 else "")

ahora = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)
ayer = ahora.date() - dt.timedelta(days=1)
inicio = max(dt.date.fromisoformat(DESDE), ayer - dt.timedelta(days=VENTANA_DIAS - 1))
dias_ventana = max(1, (ayer - inicio).days + 1)

info, ordenes, cajas = {}, [], collections.defaultdict(lambda: [0, 0.0])
for r in orders:
    d = dt.datetime.strptime(r["date_order"], "%Y-%m-%d %H:%M:%S") - dt.timedelta(hours=3)  # UTC -> Argentina
    f = d.date().isoformat()
    if f < DESDE:
        continue
    local, caja = local_caja(r["config_id"][1])
    info[r["id"]] = (f, local)
    ordenes.append([f, d.hour, round(r["amount_total"], 2), "paid", local, corto(r["seller_id"][1] if r["seller_id"] else None)])
    c = cajas[(f, local, caja)]; c[0] += 1; c[1] += r["amount_total"]

ids = list(info)
lineas_raw = []
for i in range(0, len(ids), 400):
    lineas_raw += x("pos.order.line", "search_read", [[["order_id", "in", ids[i:i + 400]]]],
                    {"fields": ["order_id", "product_id", "qty", "price_subtotal_incl"]})
# Tipo de producto: los descuentos son servicios y los combos no guardan stock propio
pids_all = sorted({l["product_id"][0] for l in lineas_raw if l["product_id"]})
servicio, con_stock = set(), set()
for i in range(0, len(pids_all), 400):
    for p in x("product.product", "read", [pids_all[i:i + 400]], {"fields": ["type", "is_storable"]}):
        if p["type"] == "service":
            servicio.add(p["id"])
        if p["type"] == "consu" and p.get("is_storable"):
            con_stock.add(p["id"])
arts = collections.defaultdict(lambda: [0.0, 0.0])
nombres, ventana = {}, collections.defaultdict(float)
for l in lineas_raw:
    if not l["product_id"] or l["product_id"][0] in servicio:
        continue
    pid, nom = l["product_id"]
    f, local = info[l["order_id"][0]]
    nombres[pid] = nom
    a = arts[(f, local, pid)]; a[0] += l["qty"]; a[1] += l["price_subtotal_incl"]
    if pid in con_stock and inicio.isoformat() <= f <= ayer.isoformat():
        ventana[(local, pid)] += l["qty"]

# Stock por local (ubicación "Existencias" y sus hijas) y mínimos cargados en Odoo (reglas de reposición)
stock_rows, aviso = [], None
try:
    locs = {r["complete_name"]: r["id"] for r in x("stock.location", "search_read",
            [[["complete_name", "in", list(UBICACIONES.values())]]], {"fields": ["complete_name"]})}
    lid = {loc: locs[nom] for loc, nom in UBICACIONES.items()}
    minimos = {}
    for r in x("stock.warehouse.orderpoint", "search_read",
               [[["location_id", "in", list(lid.values())], ["product_min_qty", ">", 0]]],
               {"fields": ["product_id", "location_id", "product_min_qty"]}):
        loc = next(k for k, v in lid.items() if v == r["location_id"][0])
        minimos[(loc, r["product_id"][0])] = r["product_min_qty"]
        nombres.setdefault(r["product_id"][0], r["product_id"][1])
    for loc in UBICACIONES:
        pids = sorted({p for (l, p) in list(ventana) + list(minimos) if l == loc})
        st = collections.defaultdict(float)
        for i in range(0, len(pids), 400):
            for q in x("stock.quant", "search_read",
                       [[["location_id", "child_of", lid[loc]], ["product_id", "in", pids[i:i + 400]]]],
                       {"fields": ["product_id", "quantity"]}):
                st[q["product_id"][0]] += q["quantity"]
        for p in pids:
            v, m = ventana.get((loc, p), 0.0), minimos.get((loc, p), 0)
            if v > 0 or m > 0:
                stock_rows.append([loc, str(p), nombres[p], round(st.get(p, 0.0), 2), m, round(v, 2), dias_ventana])
except Exception as e:  # el panel sigue con ventas aunque falle el stock
    aviso = str(e)[:160].replace("\n", " ")
    stock_rows = []

raw = {
    "ordenes": {"cols": ["fecha", "hora", "venta", "estado", "local", "vendedora"], "rows": ordenes},
    "lineas": {"cols": ["fecha", "item", "articulo", "cantidad", "venta", "local"],
               "rows": [[f, str(p), nombres[p], round(v[0], 2), round(v[1]), local] for (f, local, p), v in sorted(arts.items())]},
    "ciudades": {"cols": ["fecha", "provincia", "ciudad", "ordenes", "venta"],
                 "rows": [[f, local, caja, v[0], round(v[1])] for (f, local, caja), v in sorted(cajas.items())]},
    "stock": {"cols": ["local", "item", "articulo", "stock", "minimo", "vendidas", "dias"], "rows": stock_rows},
}
data = json.dumps(raw, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
html = open(HTML, encoding="utf-8").read()
estampa = ahora.strftime("%d/%m/%Y %H:%M")
html, n1 = re.subn(r"/\*DATA\*/.*?/\*END\*/", lambda m: "/*DATA*/" + data + "/*END*/", html, count=1, flags=re.S)
html, n2 = re.subn(r"(<p class=\"note foot\">Actualizado: )[^<]*(</p>)", lambda m: m.group(1) + estampa + m.group(2), html, count=1)
if n1 != 1 or n2 != 1:
    sys.exit("No encontré los marcadores en locales/index.html. No se sube nada.")
open(HTML, "w", encoding="utf-8").write(html)
if aviso:
    print("AVISO: stock no disponible:", aviso)
print("OK", estampa, len(ordenes), "órdenes", len(raw["lineas"]["rows"]), "filas de artículos", len(stock_rows), "filas de stock")
