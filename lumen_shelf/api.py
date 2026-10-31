"""The contract other apps call (LumenPOS first). Versioned: a caller checks
CONTRACT_VERSION (or `contract` in state()) before it relies on a field.

Contract 1 (Lumen Shelf 0.1.0):

  lumen_shelf.api.state()
      {app, version, contract, enabled, can_view}
      never raises; for a caller deciding whether to show the list or an
      "install / switch on" card

  lumen_shelf.api.running_low(company=None, warehouse=None)
  lumen_shelf.api.transfers(company=None, warehouse=None)
      {status: "ok", contract, company, as_of, window: [from, to],
       main_warehouse, rows: [...]}
      or {status: "disabled" | "forbidden" | "error", contract, message}
      Refusals come back as a status and a message, never as an exception,
      so the caller can show them as they are.

      `company` defaults to the warehouse's company, then the person's default.
      `warehouse` limits the rows to one outlet (running_low: that outlet;
      transfers: moves from or to it).

      running_low row: item_code, item_name, warehouse, on_shelf, daily_sales,
        days_left, on_order, reorder_point, suggested_qty, stock_uom,
        source_key ("Transfer", "Buy", "Transfer and buy",
        "Wait for main warehouse"), source (translated), transfer_qty,
        transfer_from, buy_qty, supplier, purchase_qty, purchase_uom,
        lead_time, history_days
        Added in 0.2.0 (still contract 1, only new fields): forecast
        (expected daily sales, after the season effect; days_left and the
        suggestion use it), season_factor (blank when no season applies),
        season_basis ("item" or "group"), unit_cost, buy_cost
        From 0.4.0, on_shelf is unchanged but a warehouse's spare (what it can
        send) leaves out stock already asked of it by a submitted transfer
        Material Request. The screens' Create material requests button is not
        part of the contract.
      transfers row: item_code, item_name, from_warehouse, to_warehouse, qty,
        stock_uom, reason_key ("running_low", "sells_faster"), reason
        (translated), from_on_shelf, from_daily_sales, to_on_shelf,
        to_daily_sales, to_days_left

Permission: the same gates as the screens (lumen_shelf.restock.access). An
app may add roles for these lists with the hook `lumen_shelf_viewer_roles`.
Warehouse User Permissions still limit which outlets a person sees.
"""

import frappe
from frappe import _

from lumen_shelf import __version__
from lumen_shelf.restock import access, views
from lumen_shelf.restock.settings import get_settings

CONTRACT_VERSION = 1


@frappe.whitelist()
def state():
	out = {"app": "lumen_shelf", "version": __version__, "contract": CONTRACT_VERSION, "enabled": 0, "can_view": 0}
	try:
		out["enabled"] = 1 if get_settings()["enabled"] else 0
		out["can_view"] = 1 if access.can_view() else 0
	except Exception:
		pass
	return out


def _company(company, warehouse):
	if company:
		return company
	if warehouse:
		c = frappe.db.get_value("Warehouse", warehouse, "company")
		if c:
			return c
	return frappe.defaults.get_user_default("Company")


def _guarded(feature, company, warehouse, cut):
	company = _company(company, warehouse)
	try:
		if not get_settings()["enabled"]:
			return {"status": "disabled", "contract": CONTRACT_VERSION, "message": _("Lumen Shelf is switched off.")}
		result, allowed = views.load(feature, company)
		if warehouse and allowed is not None and warehouse not in allowed:
			raise frappe.PermissionError
		rows = cut(result, allowed)
	except frappe.PermissionError:
		frappe.clear_messages()
		return {"status": "forbidden", "contract": CONTRACT_VERSION, "message": _("You may not see restock suggestions here.")}
	except frappe.ValidationError as e:
		frappe.clear_messages()
		status = "disabled" if not get_settings()["enabled"] else "error"
		return {"status": status, "contract": CONTRACT_VERSION, "message": str(e)}
	return {
		"status": "ok",
		"contract": CONTRACT_VERSION,
		"company": company,
		"as_of": result["as_of"],
		"window": result["window"],
		"main_warehouse": result["main_warehouse"],
		"rows": rows,
	}


@frappe.whitelist()
def running_low(company=None, warehouse=None):
	return _guarded(
		"running_low",
		company,
		warehouse,
		lambda result, allowed: views.running_low(result, allowed, warehouse=warehouse),
	)


@frappe.whitelist()
def transfers(company=None, warehouse=None):
	def cut(result, allowed):
		rows = views.transfers(result, allowed)
		if warehouse:
			rows = [r for r in rows if warehouse in (r["from_warehouse"], r["to_warehouse"])]
		return rows

	return _guarded("transfers", company, warehouse, cut)
