"""One page with what needs doing today (owner, 2026-11-02: "one page with
everything, like LumenPOS", not a screen per analysis). Four numbers, one list
of tasks with a button on each, and ideas for new products.

Nothing is worked out twice: the page takes the same engine result and the
same row builders (views.py) as the detail screens, so a number on the page
is always the number on its screen. Each part follows its own switch in Lumen
Shelf Settings, and the same gate (access.py) as its screen: role, Company
and Warehouse User Permissions."""

import frappe
from frappe import _
from frappe.utils import flt

from lumen_shelf.restock import access, compat, engine, model, trend_products, views

TASK_LIMIT = 40  # the rest is one click away on the detail screen
IDEA_LIMIT = 5
STUCK = (engine.STATUS_NO_SALES, engine.STATUS_SLOW, engine.STATUS_OVERSTOCK)

KIND_LOW = "low"
KIND_MOVE = "move"
KIND_EXPIRY = "expiry"
KIND_STUCK = "stuck"


def default_company():
	"""The person's default company if they may see it, else the first they may."""
	allowed = compat.allowed_docs("Company")
	mine = frappe.defaults.get_user_default("Company")
	if mine and frappe.db.exists("Company", mine) and (allowed is None or mine in allowed):
		return mine
	for d in frappe.get_all("Company", fields=["name"], order_by="name asc"):
		if allowed is None or d.name in allowed:
			return d.name
	return None


def _num(x):
	"""A quantity as people write it: 12, not 12.000."""
	x = round(flt(x), 3)
	return ("%d" % x) if x == int(x) else ("%s" % x)


def _about(x):
	"""A worked-out quantity, rounded the way people say it: 225, not 225.077
	(one decimal below 10, for goods sold by weight)."""
	x = flt(x)
	return _num(round(x)) if abs(x) >= 10 else _num(round(x, 1))


def _rate(speed):
	"""How fast it sells, in words a shop uses: 4 a day, or 2 a week when it
	sells less than one a day."""
	speed = flt(speed)
	if speed >= 1:
		return _("{0} a day").format(_num(round(speed, 1)))
	return _("{0} a week").format(_num(round(speed * 7, 1)))


def place(warehouse, abbr):
	"""A warehouse as people say it: "Stores", not "Stores - LUMD"."""
	if not warehouse or not abbr:
		return warehouse or ""
	end = " - " + abbr
	return ", ".join(w[: -len(end)] if w.endswith(end) else w for w in warehouse.split(", "))


def advice(action, target, abbr):
	"""What to do with stock that does not sell, as a sentence."""
	if action == model.ACTION_MOVE:
		return _("Move it to {0}, it sells there").format(place(target, abbr))
	if action == model.ACTION_RETURN:
		return _("Return it to {0}").format(target) if target else _("Return it to the supplier")
	if action == model.ACTION_BUNDLE:
		name = frappe.get_cached_value("Item", target, "item_name") if target else None
		return _("Sell it together with {0}, they are bought together").format(name or target)
	if action == model.ACTION_DISCOUNT:
		return _("Put it on offer or give a discount to sell it")
	return _("Look at it")


def _low_task(r, can_request, abbr):
	if (r["on_shelf"] or 0) <= 0:
		when = _("Already out of stock")
		why = _("Expected to sell {0} and none is left on the shelf.").format(_rate(r["forecast"]))
	else:
		when = _("Runs out in {0} days").format(_num(max(r["days_left"] or 0, 0)))
		why = _("Expected to sell {0}, {1} left on the shelf.").format(_rate(r["forecast"]), _num(r["on_shelf"]))
	if r["lead_time"]:
		why += " " + _("A new delivery takes about {0} days.").format(_num(r["lead_time"]))
	if r["on_order"]:
		why += " " + _("{0} already on order.").format(_num(r["on_order"]))
	src = r["source_key"]
	frm = place(r["transfer_from"], abbr)
	if src == views.SOURCE_WAIT:
		todo = _("Wait for main warehouse")
	elif src == views.SOURCE_TRANSFER:
		todo = _("Transfer {0} from {1}").format(_num(r["transfer_qty"]), frm)
	elif src == views.SOURCE_BOTH:
		todo = _("Transfer {0} from {1} and buy {2}").format(_num(r["transfer_qty"]), frm, _num(r["buy_qty"]))
	elif r["purchase_qty"] and r["purchase_uom"] and r["purchase_uom"] != r["stock_uom"]:
		todo = _("Buy {0} {1}").format(_num(r["purchase_qty"]), _(r["purchase_uom"]))
	else:
		todo = _("Buy {0}").format(_num(r["buy_qty"] or r["suggested_qty"]))
	if src in (views.SOURCE_BUY, views.SOURCE_BOTH) and r["supplier"]:
		todo += " " + _("from {0}").format(r["supplier"])
	task = {
		"kind": KIND_LOW,
		"tone": "danger" if (r["days_left"] or 0) <= (r["lead_time"] or 0) else "warning",
		"item_code": r["item_code"],
		"item_name": r["item_name"],
		"warehouse": r["warehouse"],
		"place": place(r["warehouse"], abbr),
		"when": when,
		"why": why,
		"todo": todo,
		"supplier": r["supplier"],
	}
	if can_request and src != views.SOURCE_WAIT and r["suggested_qty"]:
		task["request"] = {"scope": "running_low", "filters": {"warehouse": r["warehouse"], "item_code": r["item_code"]}}
	return task


def _move_task(r, can_request, abbr):
	to, frm = place(r["to_warehouse"], abbr), place(r["from_warehouse"], abbr)
	task = {
		"kind": KIND_MOVE,
		"tone": "blue",
		"item_code": r["item_code"],
		"item_name": r["item_name"],
		"warehouse": r["to_warehouse"],
		"place": to,
		"when": _("Sells faster in {0}").format(to),
		"why": _("Sells {0} in {1} and {2} in {3}.").format(_rate(r["to_daily_sales"]), to, _rate(r["from_daily_sales"]), frm),
		"todo": _("Move {0} from {1}").format(_num(r["qty"]), frm),
	}
	if can_request and not r["waits_for_stock"]:
		task["request"] = {
			"scope": "transfers",
			"filters": {
				"from_warehouse": r["from_warehouse"],
				"to_warehouse": r["to_warehouse"],
				"item_code": r["item_code"],
				"reason": "Sells faster there",
			},
		}
	return task


def _expiry_task(r, abbr):
	return {
		"kind": KIND_EXPIRY,
		"tone": "warning",
		"item_code": r["item_code"],
		"item_name": r["item_name"],
		"warehouse": r["warehouse"],
		"place": place(r["warehouse"], abbr),
		"when": _("{0} may expire before they sell").format(_num(r["expiry_risk_qty"])),
		"why": _("{0} on the shelf and it sells {1}, so some will pass their expiry date.").format(
			_num(r["on_shelf"]), _rate(r["daily_sales"])
		),
		"todo": advice(r["action_key"], r["action_target"], abbr) if r["action_key"] else _("Sell these first"),
		"value": r["expiry_risk_value"],
	}


def _stuck_task(r, abbr, weeks):
	status = r["status_key"]
	if status == engine.STATUS_NO_SALES:
		when = _("Not one sold in the last {0} weeks").format(weeks)
	elif status == engine.STATUS_SLOW:
		when = _("Sells slowly: {0} sold in {1} weeks").format(_num(r["sold_qty"]), weeks)
	else:
		when = _("More stock than it needs")
	return {
		"kind": KIND_STUCK,
		"tone": "muted",
		"item_code": r["item_code"],
		"item_name": r["item_name"],
		"warehouse": r["warehouse"],
		"place": place(r["warehouse"], abbr),
		"when": when,
		"why": _("{0} on the shelf, {1} more than it needs. The money is tied up in it.").format(
			_num(r["on_shelf"]), _about(r["excess_qty"])
		),
		"todo": advice(r["action_key"], r["action_target"], abbr),
		"value": r["excess_value"],
	}


def _ideas(result, allowed, s, company, warehouse, abbr):
	ideas = []
	if s.get("trend_products") and trend_products.configured():
		rows = trend_products.rows(company)
		rows.sort(key=lambda r: -(r["growth"] or 0))
		ideas.append(
			{
				"key": "trending",
				"title": _("Trending in the market"),
				"help": _("Products people search for more and more in your country, that you do not sell yet."),
				"report": "Shelf Trending Products",
				"count": len(rows),
				"items": [{"text": r["product"], "note": r["reason"] or r["item_group"]} for r in rows[:IDEA_LIMIT]],
			}
		)
	if s.get("assortment_gaps"):
		rows = views.assortment_gaps(result, allowed, warehouse=warehouse)
		rows.sort(key=lambda r: (-(r["daily_sales"] or 0), r["warehouse"], r["item_code"]))
		ideas.append(
			{
				"key": "gaps",
				"title": _("Sells in another branch, missing here"),
				"help": _("Items that sell well in one branch and that another branch does not stock at all."),
				"report": "Shelf Assortment Gaps",
				"count": len(rows),
				"items": [
					{"text": r["item_name"] or r["item_code"], "note": _("Sells in {0}, not in {1}").format(place(r["sells_in"], abbr), place(r["warehouse"], abbr))}
					for r in rows[:IDEA_LIMIT]
				],
			}
		)
	if s.get("bought_together"):
		rows = views.bought_together(result, allowed)
		ideas.append(
			{
				"key": "together",
				"title": _("Often bought together"),
				"help": _("Customers buy these on the same invoice. Put them side by side, or sell them as a set."),
				"report": "Shelf Bought Together",
				"count": len(rows),
				"items": [
					{
						"text": "{0} + {1}".format(r["item_name"] or r["item_code"], r["partner_name"] or r["partner"]),
						"note": _("On {0} invoices together").format(r["together"]),
					}
					for r in rows[:IDEA_LIMIT]
				],
			}
		)
	return ideas


@frappe.whitelist()
def overview(company=None, warehouse=None):
	s = access.check_view("running_low")
	company = company or default_company()
	if not company:
		frappe.throw(_("Please choose a company."))
	result, allowed = views.load("running_low", company)
	warehouse = warehouse or None
	if warehouse and allowed is not None and warehouse not in allowed:
		frappe.throw(_("You are not permitted to see this warehouse."), frappe.PermissionError)
	can_request = access.can_request()
	abbr = frappe.get_cached_value("Company", company, "abbr")
	weeks = result["settings"]["history_weeks"]

	low = views.running_low(result, allowed, warehouse=warehouse)
	tasks = [_low_task(r, can_request, abbr) for r in low]
	cards = [
		{
			"key": "low",
			"label": _("Need restocking"),
			"count": len(low),
			"note": _("{0} out of stock").format(sum(1 for r in low if (r["on_shelf"] or 0) <= 0)),
			"tone": "danger",
			"help": _("Items that will run out before a new delivery can arrive."),
			"report": "Shelf Running Low",
		}
	]
	if s.get("outlet_transfers"):
		moves = [
			r
			for r in views.transfers(result, allowed)
			if not warehouse or warehouse in (r["from_warehouse"], r["to_warehouse"])
		]
		faster = [r for r in moves if r["reason_key"] == engine.REASON_FASTER]
		tasks += [_move_task(r, can_request, abbr) for r in faster]
		cards.append(
			{
				"key": "move",
				"label": _("Move between branches"),
				"count": len(moves),
				"note": _("instead of buying"),
				"tone": "blue",
				"help": _("Stock one branch can send to another, instead of buying more."),
				"report": "Shelf Transfers",
			}
		)
	if s.get("stock_health"):
		health = views.stock_health(result, allowed, warehouse=warehouse)
		stuck = sorted((r for r in health if r["status_key"] in STUCK), key=lambda r: -(r["excess_value"] or 0))
		if s.get("expiry"):
			expiring = sorted((r for r in health if r["expiry_risk_qty"]), key=lambda r: -(r["expiry_risk_value"] or 0))
			tasks += [_expiry_task(r, abbr) for r in expiring]
			cards.append(
				{
					"key": "expiry",
					"label": _("May expire"),
					"count": len(expiring),
					"value": flt(sum(r["expiry_risk_value"] or 0 for r in expiring), 2),
					"tone": "warning",
					"help": _("Stock that may pass its expiry date before it sells."),
					"report": "Shelf Stock Health",
				}
			)
		tasks += [_stuck_task(r, abbr, weeks) for r in stuck]
		cards.append(
			{
				"key": "stuck",
				"label": _("Not selling"),
				"count": len(stuck),
				"value": flt(sum(r["excess_value"] or 0 for r in stuck), 2),
				"tone": "warning",
				"help": _("Stock that sells little or nothing. Money is tied up in it."),
				"report": "Shelf Stock Health",
			}
		)
	return {
		"company": company,
		"warehouse": warehouse,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"intro": _("Based on your sales in the last {0} weeks, up to yesterday, and the stock you have now.").format(weeks),
		"basis": views.describe(result),
		"cards": cards,
		"tasks": tasks[:TASK_LIMIT],
		"more_tasks": max(len(tasks) - TASK_LIMIT, 0),
		"ideas": _ideas(result, allowed, s, company, warehouse, abbr),
		"can_request": 1 if can_request else 0,
		"can_settings": 1 if access.has_settings_role() else 0,
	}
