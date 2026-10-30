"""One company's restocking picture, worked out from ERPNext's own data.

compute() returns plain dicts:
  pairs   one row per item and warehouse: on shelf, speed, days left, reorder
          point, target, whether it is running low, health status, ABC
  lines   the suggestions: transfers (from the main warehouse or another
          outlet) and purchases (from the item's supplier)

Where a shortage is filled from, in order (restock_source in the settings):
  Transfer first, then buy      main warehouse, other outlets' surplus, buy
  Buy from supplier             other outlets' surplus, buy
  Transfer from main warehouse  main warehouse, other outlets' surplus, and
                                what the main warehouse lacks it buys itself
Surplus in one outlet always covers a shortage in another before anything is
bought (the owner, 2026-10-29), unless outlet transfers are switched off.

Then the owner's other request: stock that does not move in one outlet but
sells in another is suggested to go where it sells. Guards: the outlet must
have had the item in stock for enough days (min_history_days) without selling
it well, only what is beyond its own cover moves, and the receiving outlet
takes no more than it can sell within its own cover.

The main warehouse's demand is its own sales plus what it sends to outlets;
it buys what it is left short after this round of transfers.
"""

import datetime
import hashlib
import json

import frappe
from frappe.utils import flt, getdate, nowdate

from lumen_shelf.restock import compat, data, model
from lumen_shelf.restock import settings as st

CACHE_SECONDS = 300
LEAD_SAMPLES = 10  # the newest receipts per supplier that make its lead time
LEAD_LOOKBACK_DAYS = 365
FEEDER_LOOKBACK_DAYS = 90
SELLS_FASTER = 2.0  # the receiving outlet must sell at least twice as fast

KIND_TRANSFER = "transfer"
KIND_BUY = "buy"
REASON_LOW = "running_low"
REASON_FASTER = "sells_faster"

STATUS_OK = "OK"
STATUS_NEW = "Too new"
STATUS_NO_SALES = "No sales"
STATUS_SLOW = "Slow"
STATUS_OVERSTOCK = "Overstock"


def _cache_key(company, as_of, items, s):
	blob = json.dumps(
		[company, str(as_of), sorted(items or []), {k: v for k, v in s.items() if k != "modified"}],
		sort_keys=True,
		default=str,
	)
	return "lumen_shelf:v1:" + hashlib.md5(blob.encode()).hexdigest()


def compute(company, as_of=None, items=None, use_cache=True):
	s = st.get_settings()
	as_of = getdate(as_of or nowdate())
	items = sorted(set(items)) if items else None
	key = _cache_key(company, as_of, items, s)
	if use_cache:
		hit = compat.cache_get(key)
		if hit:
			return hit
	result = _compute(company, as_of, items, s)
	if use_cache:
		compat.cache_set(key, result, CACHE_SECONDS)
	return result


def _main_warehouse(company, usable, roles, as_of):
	named = [w for w, r in roles.items() if r == st.ROLE_MAIN and w in usable]
	if named:
		return named[0], "set"
	found = data.busiest_feeder(company, usable, as_of - datetime.timedelta(days=FEEDER_LOOKBACK_DAYS))
	return (found, "detected") if found else (None, None)


def _compute(company, as_of, items, s):
	weeks = s["history_weeks"]
	end = as_of - datetime.timedelta(days=1)
	days = model.window_days(end, weeks)
	start = days[0]
	z = s["z"]
	cover = s["cover_days"]

	roles = {r["warehouse"]: r["warehouse_role"] for r in s["warehouse_roles"] if r.get("company") == company}
	wh_rows = data.warehouses(company)
	usable = [
		w.name
		for w in wh_rows
		if (w.warehouse_type or "") != "Transit" and not w.is_rejected and roles.get(w.name) != st.ROLE_LEAVE_OUT
	]
	main, main_basis = _main_warehouse(company, usable, roles, as_of) if usable else (None, None)

	result = {
		"company": company,
		"as_of": str(as_of),
		"window": [str(start), str(end)],
		"main_warehouse": main,
		"main_basis": main_basis,
		"warehouses": usable,
		"settings": {k: s[k] for k in st.DEFAULTS},
		"pairs": [],
		"lines": [],
	}
	if not usable:
		return result

	bins = data.bins(usable, items)
	pos_res = data.pos_reserved(usable, items)
	sold = data.sales(company, usable, start, end, items)
	opening = data.ledger_opening(usable, start, items)
	ledger = data.ledger_days(usable, start, end, items)
	main_out = data.transfers_out(company, main, [w for w in usable if w != main], start, end, items) if main else {}

	keys = set(bins) | set(sold) | set(ledger) | set(pos_res) | {(i, main) for i in main_out}
	master = data.item_master(sorted({k[0] for k in keys}))
	keys = {k for k in keys if k[0] in master}
	pref = s["restock_source"]
	use_main = bool(main) and pref in (st.SOURCE_TRANSFER_FIRST, st.SOURCE_TRANSFER)
	if use_main:
		# outlets restock from it, so it needs a row for every item, even one it
		# has never held: it is the one that buys what it is short of
		keys |= {(k[0], main) for k in keys}
	keys = sorted(keys)
	codes = sorted({k[0] for k in keys})
	default_sup = data.default_suppliers(company, codes)
	last_sup = data.last_po_suppliers(company, codes)
	samples = data.lead_samples(company, as_of - datetime.timedelta(days=LEAD_LOOKBACK_DAYS))

	def buy_lead(item):
		sup = default_sup.get(item) or last_sup.get(item)
		got = samples.get(sup) if sup else None
		if got:
			return sup, model.median(got[:LEAD_SAMPLES]), "learned"
		if master[item].lead_time_days and master[item].lead_time_days > 0:
			return sup, float(master[item].lead_time_days), "item"
		return sup, float(s["default_lead_time"]), "default"

	pairs = {}
	for item, wh in keys:
		it = master[item]
		b = bins.get((item, wh)) or {}
		on_shelf = flt(b.get("actual_qty")) - pos_res.get((item, wh), 0.0)
		on_order = flt(b.get("ordered_qty")) + flt(b.get("indented_qty"))
		so_reserved = flt(b.get("reserved_qty"))
		by_day = sold.get((item, wh), {})
		sold_by_day = {d: v[0] for d, v in by_day.items()}
		demand = dict(sold_by_day)
		if wh == main:
			for d, q in main_out.get(item, {}).items():
				demand[d] = demand.get(d, 0.0) + q
		stocked = model.in_stock_days(days, opening.get((item, wh), 0.0), ledger.get((item, wh), {}), demand)
		speed, sigma, n = model.speed_and_sigma(days, stocked, demand, end, weeks)
		supplier, lead_buy, lead_basis = buy_lead(item)
		pairs[(item, wh)] = {
			"item_code": item,
			"item_name": it.item_name,
			"item_group": it.item_group,
			"warehouse": wh,
			"is_main": 1 if wh == main else 0,
			"stock_uom": it.stock_uom,
			"purchase_uom": it.purchase_uom or it.stock_uom,
			"pack": it.pack,
			"min_order_qty": flt(it.min_order_qty),
			"whole": it.whole,
			"actual_qty": flt(b.get("actual_qty")),
			"pos_reserved": pos_res.get((item, wh), 0.0),
			"on_shelf": on_shelf,
			"on_order": on_order,
			"so_reserved": so_reserved,
			"position": on_shelf + on_order - so_reserved,
			"sold_qty": sum(sold_by_day.values()),
			"sales_value": sum(v[1] for v in by_day.values()),
			"in_stock_days": n,
			"speed": speed,
			"sigma": sigma,
			"supplier": supplier,
			"lead_buy": lead_buy,
			"lead_basis": lead_basis,
			"valuation_rate": flt(b.get("valuation_rate")),
			"eligible": 1 if n >= s["min_history_days"] else 0,
			"_sold_by_day": sold_by_day,
			"_stocked": stocked,
		}

	lines = []

	# 1. the plan, lead time and levels for every warehouse but the main one
	for (item, wh), p in pairs.items():
		if wh == main:
			continue
		main_spare_now = pairs.get((item, main), {}).get("on_shelf", 0.0) if main else 0.0
		if use_main and (pref == st.SOURCE_TRANSFER or main_spare_now > model.EPS):
			p["plan"], lead = "transfer", float(s["transfer_lead_time"])
		else:
			p["plan"], lead = "buy", p["lead_buy"]
		_levels(p, lead, z, cover)

	# 2. the main warehouse: what it can give now, beyond what its own sales need
	if main:
		for (item, wh), p in pairs.items():
			if wh != main:
				continue
			own_speed, own_sigma, _n = model.speed_and_sigma(days, p["_stocked"], p["_sold_by_day"], end, weeks)
			own_rop = model.reorder_point(own_speed, p["lead_buy"], model.safety_stock(z, own_sigma, p["lead_buy"]))
			own_target = model.order_up_to(own_rop, own_speed, cover)
			p["spare"] = model.round_surplus(p["on_shelf"] - p["so_reserved"] - own_target, p["whole"])

	# 3. every other outlet's surplus beyond its own cover, if it has the history
	for (item, wh), p in pairs.items():
		if wh == main:
			continue
		p["spare"] = 0.0
		if s["outlet_transfers"] and p["eligible"] and not p["low"]:
			p["spare"] = model.round_surplus(p["on_shelf"] - p["so_reserved"] - p["target"], p["whole"])
		p["incoming"] = 0.0

	by_item = {}
	for (item, wh), p in pairs.items():
		by_item.setdefault(item, []).append(p)

	for item in sorted(by_item):
		rows = by_item[item]
		mp = pairs.get((item, main)) if main else None
		short_from_main = 0.0
		low = sorted(
			[p for p in rows if p["warehouse"] != main and p["low"]],
			key=lambda p: (model.days_left(p["on_shelf"], p["speed"]) or 0.0, p["warehouse"]),
		)
		for p in low:
			remaining = p["need"]
			if use_main and mp and mp.get("spare", 0.0) > model.EPS and remaining > model.EPS:
				give = min(remaining, mp["spare"])
				give = model.round_surplus(give, p["whole"])
				if give > model.EPS:
					mp["spare"] -= give
					remaining -= give
					lines.append(_transfer(item, main, p["warehouse"], give, REASON_LOW))
			if s["outlet_transfers"] and remaining > model.EPS:
				donors = sorted(
					[d for d in rows if d["warehouse"] not in (main, p["warehouse"]) and d["spare"] > model.EPS],
					key=lambda d: (-_cover_days(d), d["warehouse"]),
				)
				for d in donors:
					if remaining <= model.EPS:
						break
					give = model.round_surplus(min(remaining, d["spare"]), p["whole"])
					if give <= model.EPS:
						continue
					d["spare"] -= give
					remaining -= give
					lines.append(_transfer(item, d["warehouse"], p["warehouse"], give, REASON_LOW))
			if remaining > model.EPS:
				if pref == st.SOURCE_TRANSFER and main:
					# The shop restocks outlets from the main warehouse only: it
					# waits for the main warehouse, which buys (step 5).
					line = _transfer(item, main, p["warehouse"], model.round_need(remaining, p["whole"]), REASON_LOW)
					line["main_short"] = 1
					short_from_main += line["qty"]
					lines.append(line)
				else:
					lines.append(_buy(item, p["warehouse"], remaining, p))
			p["incoming"] = p["need"]

		# 4. stock that sits in one outlet and sells in another
		if s["outlet_transfers"]:
			slow = sorted(
				[d for d in rows if d["warehouse"] != main and d["spare"] > model.EPS and _is_slow(d, s)],
				key=lambda d: (d["speed"], d["warehouse"]),
			)
			for d in slow:
				takers = sorted(
					[
						r
						for r in rows
						if r["warehouse"] not in (main, d["warehouse"])
						and r["eligible"]
						and r["speed"] > model.EPS
						and r["speed"] >= SELLS_FASTER * d["speed"] - model.EPS
						and r["speed"] > d["speed"]
					],
					key=lambda r: (-r["speed"], r["warehouse"]),
				)
				for r in takers:
					if d["spare"] <= model.EPS:
						break
					room = model.round_surplus(r["target"] - (r["position"] + r["incoming"]), r["whole"])
					give = model.round_surplus(min(room, d["spare"]), d["whole"])
					if give <= model.EPS:
						continue
					d["spare"] -= give
					r["incoming"] += give
					lines.append(_transfer(item, d["warehouse"], r["warehouse"], give, REASON_FASTER))

		# 5. the main warehouse buys for itself and for what it sends out
		if mp:
			sent = sum(l["qty"] for l in lines if l["item_code"] == item and l["from_warehouse"] == main)
			_levels(mp, mp["lead_buy"], z, cover, position=mp["position"] - sent)
			mp["plan"] = "buy"
			if mp["low"] or mp["position_after"] < -model.EPS:
				mp["low"] = 1
				mp["need"] = model.round_need(mp["target"] - mp["position_after"], mp["whole"])
				if mp["need"] > model.EPS:
					lines.append(_buy(item, main, mp["need"], mp))

	_health(pairs, s)
	_abc(pairs)

	for p in pairs.values():
		p.pop("_sold_by_day", None)
		p.pop("_stocked", None)
		p["days_left"] = model.days_left(p["on_shelf"], p["speed"])
	result["pairs"] = [pairs[k] for k in sorted(pairs)]
	result["lines"] = lines
	return result


def _levels(p, lead, z, cover, position=None):
	p["lead_time"] = lead
	p["safety"] = model.safety_stock(z, p["sigma"], lead)
	p["rop"] = model.reorder_point(p["speed"], lead, p["safety"])
	p["target"] = model.order_up_to(p["rop"], p["speed"], cover)
	pos = p["position"] if position is None else position
	p["position_after"] = pos
	p["low"] = 1 if model.is_running_low(p["speed"], pos, p["rop"]) else 0
	p["need"] = model.round_need(p["target"] - pos, p["whole"]) if p["low"] else 0.0


def _cover_days(p):
	if p["speed"] <= model.EPS:
		return 1e12
	return p["on_shelf"] / p["speed"]


def _is_slow(p, s):
	if not p["eligible"]:
		return False
	if p["speed"] <= model.EPS:
		return True
	return p["on_shelf"] / p["speed"] > s["slow_days"]


def _transfer(item, src, dst, qty, reason):
	return {
		"kind": KIND_TRANSFER,
		"item_code": item,
		"from_warehouse": src,
		"to_warehouse": dst,
		"warehouse": dst,
		"qty": qty,
		"reason": reason,
		"main_short": 0,
		"supplier": None,
	}


def _buy(item, wh, qty, p):
	stock_qty = model.round_to_pack(qty, p["pack"], p["min_order_qty"])
	return {
		"kind": KIND_BUY,
		"item_code": item,
		"from_warehouse": None,
		"to_warehouse": wh,
		"warehouse": wh,
		"qty": stock_qty,
		"reason": REASON_LOW,
		"main_short": 0,
		"supplier": p["supplier"],
		"purchase_uom": p["purchase_uom"],
		"purchase_qty": (stock_qty / p["pack"]) if p["pack"] else stock_qty,
		"lead_time": p["lead_buy"],
		"lead_basis": p["lead_basis"],
	}


def _health(pairs, s):
	for p in pairs.values():
		target = p.get("target", 0.0)
		excess = max(0.0, p["on_shelf"] - p["so_reserved"] - target)
		dl = model.days_left(p["on_shelf"], p["speed"])
		if not p["eligible"]:
			status = STATUS_NEW
		elif p["speed"] <= model.EPS:
			status = STATUS_NO_SALES if p["on_shelf"] > model.EPS else STATUS_OK
		elif dl is not None and dl > s["slow_days"]:
			status = STATUS_SLOW
		elif dl is not None and dl > s["overstock_days"] and excess > model.EPS:
			status = STATUS_OVERSTOCK
		else:
			status = STATUS_OK
		p["status"] = status
		p["excess_qty"] = excess if status in (STATUS_NO_SALES, STATUS_SLOW, STATUS_OVERSTOCK) else 0.0
		p["excess_value"] = p["excess_qty"] * p["valuation_rate"]


def _abc(pairs):
	by_wh = {}
	by_item = {}
	for (item, wh), p in pairs.items():
		by_wh.setdefault(wh, {})[item] = p["sales_value"]
		by_item[item] = by_item.get(item, 0.0) + p["sales_value"]
	company = model.abc_classes(by_item)
	for wh, values in by_wh.items():
		classes = model.abc_classes(values)
		for item in values:
			pairs[(item, wh)]["abc"] = classes[item]
			pairs[(item, wh)]["abc_company"] = company[item]
