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

from lumen_shelf.restock import access, compat, engine, trend_products, views

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


def _low_task(r, can_request):
	if (r["on_shelf"] or 0) <= 0:
		when = _("Already out of stock")
	else:
		when = _("Runs out in {0} days").format(_num(max(r["days_left"] or 0, 0)))
	src = r["source_key"]
	if src == views.SOURCE_WAIT:
		todo = _("Wait for main warehouse")
	elif src == views.SOURCE_TRANSFER:
		todo = _("Transfer {0} from {1}").format(_num(r["transfer_qty"]), r["transfer_from"])
	elif src == views.SOURCE_BOTH:
		todo = _("Transfer {0} from {1} and buy {2}").format(_num(r["transfer_qty"]), r["transfer_from"], _num(r["buy_qty"]))
	elif r["purchase_qty"] and r["purchase_uom"] and r["purchase_uom"] != r["stock_uom"]:
		todo = _("Buy {0} {1}").format(_num(r["purchase_qty"]), _(r["purchase_uom"]))
	else:
		todo = _("Buy {0}").format(_num(r["buy_qty"] or r["suggested_qty"]))
	task = {
		"kind": KIND_LOW,
		"tone": "danger" if (r["days_left"] or 0) <= (r["lead_time"] or 0) else "warning",
		"item_code": r["item_code"],
		"item_name": r["item_name"],
		"warehouse": r["warehouse"],
		"when": when,
		"todo": todo,
		"supplier": r["supplier"],
	}
	if can_request and src != views.SOURCE_WAIT and r["suggested_qty"]:
		task["request"] = {"scope": "running_low", "filters": {"warehouse": r["warehouse"], "item_code": r["item_code"]}}
	return task


def _move_task(r, can_request):
	task = {
		"kind": KIND_MOVE,
		"tone": "blue",
		"item_code": r["item_code"],
		"item_name": r["item_name"],
		"warehouse": r["to_warehouse"],
		"when": _("Sells faster in {0}").format(r["to_warehouse"]),
		"todo": _("Move {0} from {1}").format(_num(r["qty"]), r["from_warehouse"]),
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


def _expiry_task(r):
	return {
		"kind": KIND_EXPIRY,
		"tone": "warning",
		"item_code": r["item_code"],
		"item_name": r["item_name"],
		"warehouse": r["warehouse"],
		"when": _("{0} may expire before they sell").format(_num(r["expiry_risk_qty"])),
		"todo": r["action"] or _("Sell these first"),
		"value": r["expiry_risk_value"],
	}


def _stuck_task(r):
	return {
		"kind": KIND_STUCK,
		"tone": "muted",
		"item_code": r["item_code"],
		"item_name": r["item_name"],
		"warehouse": r["warehouse"],
		"when": r["status"],
		"todo": r["action"] or _("Look at it"),
		"value": r["excess_value"],
	}


def _ideas(result, allowed, s, company, warehouse):
	ideas = []
	if s.get("trend_products") and trend_products.configured():
		rows = trend_products.rows(company)
		rows.sort(key=lambda r: -(r["growth"] or 0))
		ideas.append(
			{
				"key": "trending",
				"title": _("Trending in the market"),
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
				"report": "Shelf Assortment Gaps",
				"count": len(rows),
				"items": [
					{"text": r["item_name"] or r["item_code"], "note": _("Sells in {0}, not in {1}").format(r["sells_in"], r["warehouse"])}
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

	low = views.running_low(result, allowed, warehouse=warehouse)
	tasks = [_low_task(r, can_request) for r in low]
	cards = [
		{
			"key": "low",
			"label": _("Need restocking"),
			"count": len(low),
			"note": _("{0} out of stock").format(sum(1 for r in low if (r["on_shelf"] or 0) <= 0)),
			"tone": "danger",
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
		tasks += [_move_task(r, can_request) for r in faster]
		cards.append(
			{
				"key": "move",
				"label": _("Move between branches"),
				"count": len(moves),
				"note": _("instead of buying"),
				"tone": "blue",
				"report": "Shelf Transfers",
			}
		)
	if s.get("stock_health"):
		health = views.stock_health(result, allowed, warehouse=warehouse)
		stuck = sorted((r for r in health if r["status_key"] in STUCK), key=lambda r: -(r["excess_value"] or 0))
		if s.get("expiry"):
			expiring = sorted((r for r in health if r["expiry_risk_qty"]), key=lambda r: -(r["expiry_risk_value"] or 0))
			tasks += [_expiry_task(r) for r in expiring]
			cards.append(
				{
					"key": "expiry",
					"label": _("May expire"),
					"count": len(expiring),
					"value": flt(sum(r["expiry_risk_value"] or 0 for r in expiring), 2),
					"tone": "warning",
					"report": "Shelf Stock Health",
				}
			)
		tasks += [_stuck_task(r) for r in stuck]
		cards.append(
			{
				"key": "stuck",
				"label": _("Not selling"),
				"count": len(stuck),
				"value": flt(sum(r["excess_value"] or 0 for r in stuck), 2),
				"tone": "warning",
				"report": "Shelf Stock Health",
			}
		)
	return {
		"company": company,
		"warehouse": warehouse,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"basis": views.describe(result),
		"cards": cards,
		"tasks": tasks[:TASK_LIMIT],
		"more_tasks": max(len(tasks) - TASK_LIMIT, 0),
		"ideas": _ideas(result, allowed, s, company, warehouse),
		"can_request": 1 if can_request else 0,
		"can_settings": 1 if access.has_settings_role() else 0,
	}
