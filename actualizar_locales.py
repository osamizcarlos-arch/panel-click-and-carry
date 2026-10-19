#!/usr/bin/env python3
"""Actualiza locales/index.html con las ventas de Tienda Cabildo y Tienda DOT
(Odoo, Punto de venta de Ecotrade). Misma estructura de datos que el panel de Mercado Libre.
La clave de Odoo se pasa por la variable de entorno ODOO_KEY. Nunca se guarda en este repo (es público)."""
import os, sys, re, json, collections, datetime as dt, xmlrpc.client

URL = "https://parisnight.odoo.com"
DB = "parisnight-main-34324367"
USER = "Claude/integraciones"
DESDE = "2026-10-01"
HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales", "index.html")

key = os.environ.get("ODOO_KEY")
if not key:
    sys.exit("Falta ODOO_KEY")
uid = xmlrpc.client.ServerProxy(URL + "/xmlrpc/2/common").authenticate(DB, USER, key, {})
if not uid:
    sys.exit("Odoo no autenticó: la clave venció o cambió. No se sube nada.")
o = xmlrpc.client.ServerProxy(URL + "/xmlrpc/2/object")
def x(m, f, a, k):
    k["context"] = {"allowed_company_ids": [1, 2]}
    return o.execute_kw(DB, uid, key, m, f, a, k)

orders = x("pos.order", "search_read",
           [[["company_id", "=", 2], ["state", "not in", ["cancel", "draft"]], ["amount_total", ">", 0]]],
           {"fields": ["date_order", "amount_total", "config_id"]})
if not orders:
    sys.exit("Odoo devolvió 0 órdenes. No se sube nada.")

def local_caja(nombre):
    local = "DOT" if "DOT" in nombre else "Cabildo"
    m = re.search(r"CAJA\s*(\d+)", nombre.upper())
    return local, ("Caja " + m.group(1)) if m else nombre

info, ordenes, cajas = {}, [], collections.defaultdict(lambda: [0, 0.0])
for r in orders:
    d = dt.datetime.strptime(r["date_order"], "%Y-%m-%d %H:%M:%S") - dt.timedelta(hours=3)  # UTC -> Argentina
    f = d.date().isoformat()
    if f < DESDE:
        continue
    local, caja = local_caja(r["config_id"][1])
    info[r["id"]] = (f, local)
    ordenes.append([f, d.hour, round(r["amount_total"], 2), "paid", local])
    c = cajas[(f, local, caja)]; c[0] += 1; c[1] += r["amount_total"]

ids = list(info)
arts = collections.defaultdict(lambda: [0.0, 0.0])
for i in range(0, len(ids), 400):
    for l in x("pos.order.line", "search_read", [[["order_id", "in", ids[i:i + 400]]]],
               {"fields": ["order_id", "full_product_name", "qty", "price_subtotal_incl"]}):
        f, local = info[l["order_id"][0]]
        a = arts[(f, local, l["full_product_name"])]; a[0] += l["qty"]; a[1] += l["price_subtotal_incl"]

raw = {
    "ordenes": {"cols": ["fecha", "hora", "venta", "estado", "local"], "rows": ordenes},
    "lineas": {"cols": ["fecha", "item", "articulo", "cantidad", "venta", "local"],
               "rows": [[f, n, n, round(v[0], 2), round(v[1]), local] for (f, local, n), v in sorted(arts.items())]},
    "ciudades": {"cols": ["fecha", "provincia", "ciudad", "ordenes", "venta"],
                 "rows": [[f, local, caja, v[0], round(v[1])] for (f, local, caja), v in sorted(cajas.items())]},
}
data = json.dumps(raw, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
html = open(HTML, encoding="utf-8").read()
ahora = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
html, n1 = re.subn(r"/\*DATA\*/.*?/\*END\*/", lambda m: "/*DATA*/" + data + "/*END*/", html, count=1, flags=re.S)
html, n2 = re.subn(r"(<p class=\"note foot\">Actualizado: )[^<]*(</p>)", lambda m: m.group(1) + ahora + m.group(2), html, count=1)
if n1 != 1 or n2 != 1:
    sys.exit("No encontré los marcadores en locales/index.html. No se sube nada.")
open(HTML, "w", encoding="utf-8").write(html)
print("OK", ahora, len(ordenes), "órdenes", len(raw["lineas"]["rows"]), "filas de artículos")
