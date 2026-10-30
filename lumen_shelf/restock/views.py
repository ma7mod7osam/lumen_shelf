"""The rows each screen and the API show, cut from one engine result and
limited to the warehouses the person may see."""

import datetime

import frappe
from frappe import _
from frappe.utils import flt, getdate

from lumen_shelf.restock import access, data, engine, model

SOURCE_TRANSFER = "Transfer"
SOURCE_BUY = "Buy"
SOURCE_BOTH = "Transfer and buy"
SOURCE_WAIT = "Wait for main warehouse"

# What the screens show for each source. Own wording rather than the bare words
# "Transfer" and "Buy", which ERPNext already translates its own way.
SOURCE_LABELS = {
	SOURCE_TRANSFER: "By transfer",
	SOURCE_BUY: "By purchase",
	SOURCE_BOTH: "Transfer and purchase",
	SOURCE_WAIT: "Wait for main warehouse",
}

REASONS = {
	engine.REASON_LOW: "Running low there",
	engine.REASON_FASTER: "Sells faster there",
}

TRENDS = (engine.TREND_RISING, engine.TREND_FALLING)

STATUSES = (
	engine.STATUS_NO_SALES,
	engine.STATUS_SLOW,
	engine.STATUS_OVERSTOCK,
	engine.STATUS_NEW,
	engine.STATUS_OK,
)


def _r(x, n=2):
	return None if x is None else round(flt(x), n)


def _q(x):
	"""A quantity, blank when there is none, so the eye goes to what matters."""
	return round(flt(x), 3) or None


def _visible(allowed, *warehouses):
	if allowed is None:
		return True
	return any(w in allowed for w in warehouses if w)


def load(feature, company, as_of=None, items=None, use_cache=True):
	"""Check the person, then compute. Returns (result, allowed warehouses)."""
	access.check_view(feature)
	access.check_company(company)
	result = engine.compute(company, as_of=as_of, items=items, use_cache=use_cache)
	return result, access.allowed_warehouses()


def _priority(row, p):
	"""Budget order: what runs out within its lead time first, then A items
	before B and C, then the profit lost per day while it is missing."""
	urgent = 0 if (row["days_left"] or 0.0) <= (row["lead_time"] or 0.0) + model.EPS else 1
	price = p["sales_value"] / p["sold_qty"] if p["sold_qty"] > model.EPS else 0.0
	margin = max(price - p["unit_cost"], 0.0)
	return (urgent, {"A": 0, "B": 1}.get(p.get("abc"), 2), -(p.get("forecast", p["speed"]) * margin), row["warehouse"], row["item_code"])


def running_low(result, allowed, warehouse=None, item_group=None, source=None, budget=None):
	pairs = {(p["item_code"], p["warehouse"]): p for p in result["pairs"]}
	lines_by = {}
	for line in result["lines"]:
		if line["reason"] != engine.REASON_LOW:
			continue
		lines_by.setdefault((line["item_code"], line["to_warehouse"]), []).append(line)
	rows = []
	for key, p in sorted(pairs.items()):
		if not p.get("low"):
			continue
		if warehouse and p["warehouse"] != warehouse:
			continue
		if item_group and p["item_group"] != item_group:
			continue
		if not _visible(allowed, p["warehouse"]):
			continue
		lines = lines_by.get(key, [])
		moves = [l for l in lines if l["kind"] == engine.KIND_TRANSFER and not l["main_short"]]
		waits = [l for l in lines if l["kind"] == engine.KIND_TRANSFER and l["main_short"]]
		buys = [l for l in lines if l["kind"] == engine.KIND_BUY]
		transfer_qty = sum(l["qty"] for l in moves)
		wait_qty = sum(l["qty"] for l in waits)
		buy_qty = sum(l["qty"] for l in buys)
		if moves and buys:
			src = SOURCE_BOTH
		elif buys:
			src = SOURCE_BUY
		elif moves:
			src = SOURCE_TRANSFER
		elif waits:
			src = SOURCE_WAIT
		else:
			src = SOURCE_BUY
		if source == SOURCE_TRANSFER and not (moves or waits):
			continue
		if source == SOURCE_BUY and not buys:
			continue
		purchase_qty = sum(flt(l.get("purchase_qty")) for l in buys)
		rows.append(
			{
				"item_code": p["item_code"],
				"item_name": p["item_name"],
				"warehouse": p["warehouse"],
				"on_shelf": _r(p["on_shelf"], 3),
				"daily_sales": _r(p["speed"], 3),
				"forecast": _r(p.get("forecast", p["speed"]), 3),
				"season_factor": _r(p.get("season_factor"), 2) if p.get("season_basis") else None,
				"season_basis": p.get("season_basis"),
				"days_left": _r(p["days_left"], 1),
				"on_order": _q(p["on_order"]),
				"reorder_point": _r(p["rop"], 2),
				"target": _r(p["target"], 2),
				"suggested_qty": _r(transfer_qty + wait_qty + buy_qty, 3),
				"stock_uom": p["stock_uom"],
				"source_key": src,
				"source": _(SOURCE_LABELS[src]),
				"transfer_qty": _q(transfer_qty + wait_qty),
				"transfer_from": ", ".join(sorted({l["from_warehouse"] for l in moves + waits})),
				"buy_qty": _q(buy_qty),
				"supplier": buys[0]["supplier"] if buys else None,
				"purchase_qty": _r(purchase_qty, 3) if buys else None,
				"purchase_uom": p["purchase_uom"] if buys else None,
				"lead_time": _r(p["lead_time"], 1),
				"lead_basis": p["lead_basis"] if p["plan"] == "buy" else "transfer",
				"history_days": p["in_stock_days"],
				"is_main": p["is_main"],
				"unit_cost": _r(p["unit_cost"], 2) if buys else None,
				"buy_cost": _r(buy_qty * p["unit_cost"], 2) if buys else None,
				"in_budget": None,
				"running_total": None,
			}
		)
	if budget and flt(budget) > 0 and result["settings"].get("budget_plan"):
		order = sorted(rows, key=lambda r: _priority(r, pairs[(r["item_code"], r["warehouse"])]))
		buying = [{"row": r, "cost": r["buy_cost"] or 0.0} for r in order if r["buy_qty"]]
		model.fit_budget(buying, flt(budget))
		for b in buying:
			b["row"]["in_budget"] = b["in_budget"]
			b["row"]["running_total"] = _r(b["running_total"], 2)
		return order
	rows.sort(key=lambda r: (r["days_left"] if r["days_left"] is not None else 0.0, r["warehouse"], r["item_code"]))
	return rows


def transfers(result, allowed, from_warehouse=None, to_warehouse=None, reason=None):
	pairs = {(p["item_code"], p["warehouse"]): p for p in result["pairs"]}
	rows = []
	for l in result["lines"]:
		if l["kind"] != engine.KIND_TRANSFER:
			continue
		if from_warehouse and l["from_warehouse"] != from_warehouse:
			continue
		if to_warehouse and l["to_warehouse"] != to_warehouse:
			continue
		if reason and l["reason"] != reason:
			continue
		if not _visible(allowed, l["from_warehouse"], l["to_warehouse"]):
			continue
		src = pairs.get((l["item_code"], l["from_warehouse"])) or {}
		dst = pairs.get((l["item_code"], l["to_warehouse"])) or {}
		rows.append(
			{
				"item_code": l["item_code"],
				"item_name": dst.get("item_name") or src.get("item_name"),
				"from_warehouse": l["from_warehouse"],
				"to_warehouse": l["to_warehouse"],
				"qty": _r(l["qty"], 3),
				"stock_uom": dst.get("stock_uom") or src.get("stock_uom"),
				"reason_key": l["reason"],
				"reason": _(REASONS[l["reason"]]),
				"waits_for_stock": l["main_short"],
				"from_on_shelf": _r(src.get("on_shelf"), 3),
				"from_daily_sales": _r(src.get("speed"), 3),
				"to_on_shelf": _r(dst.get("on_shelf"), 3),
				"to_daily_sales": _r(dst.get("speed"), 3),
				"to_days_left": _r(dst.get("days_left"), 1),
			}
		)
	return rows


def stock_health(result, allowed, warehouse=None, status=None, abc=None, trend=None):
	rows = []
	for p in result["pairs"]:
		if warehouse and p["warehouse"] != warehouse:
			continue
		if not _visible(allowed, p["warehouse"]):
			continue
		if p["on_shelf"] <= 0 and p["sold_qty"] == 0:
			continue  # nothing on the shelf and nothing sold: nothing to say
		if status and p["status"] != status:
			continue
		if abc and p["abc"] != abc:
			continue
		if trend and p.get("trend_status") != trend:
			continue
		rows.append(
			{
				"item_code": p["item_code"],
				"item_name": p["item_name"],
				"warehouse": p["warehouse"],
				"abc": p["abc"],
				"abc_company": p["abc_company"],
				"status_key": p["status"],
				"status": _(p["status"]),
				"on_shelf": _r(p["on_shelf"], 3),
				"daily_sales": _r(p["speed"], 3),
				"days_left": _r(p["days_left"], 1),
				"sold_qty": _r(p["sold_qty"], 3),
				"sales_value": _r(p["sales_value"], 2),
				"history_days": p["in_stock_days"],
				"excess_qty": _r(p["excess_qty"], 3),
				"excess_value": _r(p["excess_value"], 2),
				"stock_uom": p["stock_uom"],
				"trend": _r(p["trend"] * 100.0, 1) if p.get("trend") is not None else None,
				"trend_key": p.get("trend_status") or "",
				"trend_status": _(p["trend_status"]) if p.get("trend_status") else "",
				"lost_qty": _q(p.get("lost_qty")),
				"lost_value": _q(p.get("lost_value")),
			}
		)
	rank = {"A": 0, "B": 1, "C": 2}
	rows.sort(key=lambda r: (r["warehouse"], rank.get(r["abc"], 3), -(r["sales_value"] or 0), r["item_code"]))
	return rows


def describe(result):
	"""One line above a report: what the numbers are based on."""
	parts = [
		_("Sales from {0} to {1}, days out of stock left out.").format(
			frappe.format(result["window"][0], {"fieldtype": "Date"}),
			frappe.format(result["window"][1], {"fieldtype": "Date"}),
		)
	]
	if result["main_warehouse"]:
		basis = _("named in the settings") if result["main_basis"] == "set" else _("found from the transfers it sends")
		parts.append(_("Main warehouse: {0} ({1}).").format(result["main_warehouse"], basis))
	else:
		parts.append(_("No main warehouse found."))
	parts.append(_("Restock from: {0}.").format(_(result["settings"]["restock_source"])))
	season = result.get("season") or {}
	if season.get("calendar"):
		cal = _(season["calendar"])
		if season.get("basis") == "chosen":
			parts.append(_("Seasons: {0} calendar, chosen because it predicted the last 8 weeks best.").format(cal))
		else:
			parts.append(_("Seasons: {0} calendar.").format(cal))
	elif season.get("basis") == "no history":
		parts.append(_("Seasons: not enough sales history from last year yet."))
	return " ".join(parts)


def accuracy(result, allowed, warehouse=None):
	"""The forecast the engine made 14 days ago against what was sold since,
	for every outlet and item that stayed in stock the whole 14 days."""
	days = engine.ACCURACY_DAYS
	as_of = getdate(result["as_of"])
	then = as_of - datetime.timedelta(days=days)
	old = engine.compute(result["company"], as_of=then)
	old_pairs = {(p["item_code"], p["warehouse"]): p for p in old["pairs"]}
	sold = data.sales(result["company"], result["warehouses"], then, as_of - datetime.timedelta(days=1))
	rows = []
	for p in result["pairs"]:
		if p["is_main"] or p["stocked_last"] < days:
			continue
		if warehouse and p["warehouse"] != warehouse:
			continue
		if not _visible(allowed, p["warehouse"]):
			continue
		o = old_pairs.get((p["item_code"], p["warehouse"]))
		if not o or o["is_main"]:
			continue
		f = o.get("forecast", o["speed"]) * days
		plain = o["plain_speed"] * days
		a = sum(v[0] for v in sold.get((p["item_code"], p["warehouse"]), {}).values())
		if f <= model.EPS and a <= model.EPS:
			continue
		rows.append(
			{
				"item_code": p["item_code"],
				"item_name": p["item_name"],
				"warehouse": p["warehouse"],
				"forecast_qty": _r(f, 2),
				"actual_qty": _r(a, 3),
				"difference": _r(f - a, 2),
				"error_pct": _r((f - a) / a * 100.0, 1) if a > model.EPS else None,
				"plain_qty": _r(plain, 2),
				"season_factor": _r(o.get("season_factor"), 2) if o.get("season_basis") else None,
				"stock_uom": p["stock_uom"],
				"_f": f,
				"_a": a,
				"_plain": plain,
			}
		)
	acc, bias = model.accuracy([(r["_f"], r["_a"]) for r in rows])
	plain_acc, _plain_bias = model.accuracy([(r["_plain"], r["_a"]) for r in rows])
	for r in rows:
		r.pop("_f"), r.pop("_a"), r.pop("_plain")
	rows.sort(key=lambda r: (-abs(r["difference"] or 0.0), r["warehouse"], r["item_code"]))
	return rows, {"accuracy": acc, "bias": bias, "plain_accuracy": plain_acc, "from": str(then), "days": days}
