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

Contract 2 (Lumen Shelf 0.6.0): contract 1 unchanged, plus material requests
from the suggestions, for a till button.

  state() also returns can_request (1 when this person may create requests)
  and submit_requests (1: requests are submitted, 0: saved as drafts).

  lumen_shelf.api.preview_requests(company=None, warehouse=None, scope="running_low")
      {status: "ok", contract, company, submit_requests, requests: [...]}
      What create_requests would make now. scope "running_low": the
      shortages of `warehouse` (or of every outlet the person may see),
      purchases and transfers. scope "transfers": the moves from or to
      `warehouse`.
      request: type ("Purchase" | "Material Transfer"), type_label
        (translated), title, supplier, from_warehouse, lines: [{item_code,
        item_name, warehouse, from_warehouse, qty, uom, conversion_factor,
        stock_qty, stock_uom, schedule_date}]
      An empty list: nothing to request (all on order already).

  lumen_shelf.api.create_requests(company=None, warehouse=None, scope="running_low")
      POST only. Works the figures out again, then makes the ERPNext Material
      Requests: purchases one per supplier, transfers one per sending
      warehouse. {status: "ok", contract, company, created: [{name, type,
      title, lines, docstatus}]}. All or nothing: if one request fails, none
      is kept and the status is "error" with ERPNext's message.

  Both: {status: "disabled" | "forbidden" | "error", contract, message} as in
  contract 1. "disabled" also when creating requests is switched off.

Permission: the same gates as the screens (lumen_shelf.restock.access). An
app may add roles for these lists with the hook `lumen_shelf_viewer_roles`,
and roles that may create requests with `lumen_shelf_request_roles` (with
ERPNext's own permission to create, and submit, a Material Request on top).
Warehouse User Permissions still limit which outlets a person sees, and a
request line is made only when the person may see every warehouse on it.
"""

import frappe
from frappe import _

from lumen_shelf import __version__
from lumen_shelf.restock import access, requests, views
from lumen_shelf.restock.settings import get_settings

CONTRACT_VERSION = 2


@frappe.whitelist()
def state():
	out = {
		"app": "lumen_shelf",
		"version": __version__,
		"contract": CONTRACT_VERSION,
		"enabled": 0,
		"can_view": 0,
		"can_request": 0,
		"submit_requests": 0,
	}
	try:
		s = get_settings()
		out["enabled"] = 1 if s["enabled"] else 0
		out["can_view"] = 1 if access.can_view() else 0
		out["can_request"] = 1 if access.can_request() else 0
		out["submit_requests"] = 1 if s["submit_requests"] else 0
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


def _request_groups(scope, company, warehouse, fresh):
	s = access.check_requests(scope)
	result, allowed = views.load(scope, company, use_cache=not fresh)
	if warehouse and allowed is not None and warehouse not in allowed:
		raise frappe.PermissionError
	filters = {"company": company, "warehouse": warehouse if scope == "running_low" else None}
	lines = requests.chosen_lines(result, allowed, scope, filters)
	if scope == "transfers" and warehouse:
		lines = [l for l in lines if warehouse in (l["from_warehouse"], l["to_warehouse"])]
	return requests.plan(result, lines), s


def _refusal(e):
	frappe.clear_messages()
	s = get_settings()
	if isinstance(e, frappe.PermissionError):
		return {"status": "forbidden", "contract": CONTRACT_VERSION, "message": _("You may not create material requests here.")}
	status = "disabled" if not (s["enabled"] and s["material_requests"]) else "error"
	return {"status": status, "contract": CONTRACT_VERSION, "message": str(e)}


@frappe.whitelist()
def preview_requests(company=None, warehouse=None, scope="running_low"):
	company = _company(company, warehouse)
	if scope not in requests.SCOPES:
		return {"status": "error", "contract": CONTRACT_VERSION, "message": _("Unknown list.")}
	try:
		groups, s = _request_groups(scope, company, warehouse, fresh=False)
	except (frappe.PermissionError, frappe.ValidationError) as e:
		return _refusal(e)
	for g in groups:
		g["type_label"] = _("Purchase request") if g["type"] == requests.TYPE_PURCHASE else _("Transfer request")
		g["lines"] = [dict(i, schedule_date=str(i["schedule_date"])) for i in g.pop("items")]
	return {
		"status": "ok",
		"contract": CONTRACT_VERSION,
		"company": company,
		"submit_requests": 1 if s.get("submit_requests") else 0,
		"requests": groups,
	}


@frappe.whitelist(methods=["POST"])
def create_requests(company=None, warehouse=None, scope="running_low"):
	company = _company(company, warehouse)
	if scope not in requests.SCOPES:
		return {"status": "error", "contract": CONTRACT_VERSION, "message": _("Unknown list.")}
	# All or nothing. A refusal is returned, not raised, so Frappe would keep
	# the requests made before the one that failed: roll back to here.
	frappe.db.savepoint("lumen_shelf_create")
	try:
		groups, s = _request_groups(scope, company, warehouse, fresh=True)
		made = requests.make(groups, company, s.get("submit_requests"))
	except (frappe.PermissionError, frappe.ValidationError) as e:
		frappe.db.rollback(save_point="lumen_shelf_create")
		return _refusal(e)
	frappe.clear_messages()
	return {"status": "ok", "contract": CONTRACT_VERSION, "company": company, "created": made}
