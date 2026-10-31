"""Phase 2: the suggestions on a screen become ERPNext Material Requests, with
one button.

Purchases: one Material Request (type Purchase) per supplier, a line per item
and warehouse, in the purchase unit. ERPNext's own Create > Purchase Order on
the request turns it into an order.
Transfers: one Material Request (type Material Transfer) per sending
warehouse, a line per item and receiving warehouse. ERPNext's own
Create > Transfer Material makes the Stock Entry.

The button asks for what the screen shows with its filters: on Running low
with a budget, only the purchases that fit it.

Nothing is asked twice. A submitted request is on order in ERPNext's Bin
(indented_qty) at the receiving warehouse, and is no longer spare at the
sending one (data.requested_out). A draft request counts for nothing in
ERPNext, so its quantities are taken off what the button asks for.

Saved with ERPNext's own permission checks (no ignore_permissions): a person
needs a role that may act (access.check_requests) and ERPNext's own right to
create and submit a Material Request. All requests are made in one database
transaction: if one fails, none is kept.
"""

import math

import frappe
from frappe import _
from frappe.utils import add_days, escape_html, flt, nowdate

from lumen_shelf.restock import access, data, engine, model, views

TYPE_PURCHASE = "Purchase"
TYPE_TRANSFER = "Material Transfer"
SCOPES = ("running_low", "transfers")


def _filters(filters):
	if isinstance(filters, str):
		filters = frappe.parse_json(filters) if filters else {}
	return frappe._dict(filters or {})


def chosen_lines(result, allowed, scope, filters):
	"""The engine's suggestions behind the rows a screen shows with these
	filters, and only those whose every warehouse this person may see."""
	f = _filters(filters)
	out = []
	if scope == "running_low":
		budget = flt(f.budget) if result["settings"].get("budget_plan") else 0.0
		rows = views.running_low(
			result, allowed, warehouse=f.warehouse, item_group=f.item_group, source=f.source, budget=budget
		)
		keys = {(r["item_code"], r["warehouse"]) for r in rows}
		fits = {(r["item_code"], r["warehouse"]) for r in rows if budget <= 0 or r["in_budget"]}
		for l in result["lines"]:
			key = (l["item_code"], l["to_warehouse"])
			if l["reason"] != engine.REASON_LOW or key not in keys:
				continue
			if l["kind"] == engine.KIND_BUY and (f.source == views.SOURCE_TRANSFER or key not in fits):
				continue
			if l["kind"] == engine.KIND_TRANSFER and f.source == views.SOURCE_BUY:
				continue
			out.append(l)
	elif scope == "transfers":
		from lumen_shelf.lumen_shelf.report.shelf_transfers.shelf_transfers import REASON_FILTER

		rows = views.transfers(
			result,
			allowed,
			from_warehouse=f.from_warehouse,
			to_warehouse=f.to_warehouse,
			reason=REASON_FILTER.get(f.reason or ""),
		)
		keys = {(r["item_code"], r["from_warehouse"], r["to_warehouse"], r["reason_key"]) for r in rows}
		out = [
			l
			for l in result["lines"]
			if l["kind"] == engine.KIND_TRANSFER
			and (l["item_code"], l["from_warehouse"], l["to_warehouse"], l["reason"]) in keys
		]
	else:
		frappe.throw(_("Unknown list."))
	if allowed is not None:
		out = [l for l in out if all(w in allowed for w in (l["from_warehouse"], l["to_warehouse"]) if w)]
	return out


def plan(result, lines, today=None):
	"""Group the lines into the requests to make. Returns a list of
	{type, supplier, from_warehouse, title, items}, purchases first."""
	today = today or nowdate()
	company = result["company"]
	transfer_days = result["settings"]["transfer_lead_time"]
	pairs = {(p["item_code"], p["warehouse"]): p for p in result["pairs"]}
	drafts = {
		TYPE_PURCHASE: data.draft_requests(company, TYPE_PURCHASE),
		TYPE_TRANSFER: data.draft_requests(company, TYPE_TRANSFER),
	}
	groups = {}
	for l in lines:
		p = pairs[(l["item_code"], l["to_warehouse"])]
		buy = l["kind"] == engine.KIND_BUY
		rtype = TYPE_PURCHASE if buy else TYPE_TRANSFER
		dkey = (l["item_code"], l["to_warehouse"], None if buy else l["from_warehouse"])
		have = drafts[rtype].get(dkey, 0.0)
		taken = min(have, l["qty"])
		drafts[rtype][dkey] = have - taken  # one draft covers one suggestion
		if buy:
			stock_qty = model.round_to_pack(l["qty"] - taken, p["pack"], 0.0)
		else:
			stock_qty = model.round_need(l["qty"] - taken, p["whole"])
		if stock_qty <= model.EPS:
			continue
		if buy and p["pack"]:
			uom, factor = p["purchase_uom"], p["pack"]
		else:
			uom, factor = p["stock_uom"], 1.0
		days = l["lead_time"] if buy else transfer_days
		key = (rtype, (l["supplier"] or "") if buy else l["from_warehouse"])
		g = groups.setdefault(
			key,
			{
				"type": rtype,
				"supplier": (l["supplier"] or None) if buy else None,
				"from_warehouse": None if buy else l["from_warehouse"],
				"items": [],
			},
		)
		g["items"].append(
			{
				"item_code": l["item_code"],
				"item_name": p["item_name"],
				"warehouse": l["to_warehouse"],
				"from_warehouse": None if buy else l["from_warehouse"],
				"qty": round(stock_qty / factor, 6),
				"uom": uom,
				"conversion_factor": factor,
				"stock_qty": stock_qty,
				"stock_uom": p["stock_uom"],
				"schedule_date": add_days(today, int(math.ceil(flt(days) - model.EPS)) if flt(days) > 0 else 0),
			}
		)
	out = []
	for key in sorted(groups, key=lambda k: (k[0] != TYPE_PURCHASE, k[1] == "", k[1])):
		g = groups[key]
		if g["type"] == TYPE_PURCHASE:
			name = frappe.db.get_value("Supplier", g["supplier"], "supplier_name") if g["supplier"] else None
			g["title"] = _("Restock from {0}").format(name or g["supplier"]) if g["supplier"] else _("Restock, supplier to choose")
		else:
			g["title"] = _("Restock from {0}").format(g["from_warehouse"])
		g["items"].sort(key=lambda i: (i["warehouse"], i["item_code"]))
		out.append(g)
	return out


def make(groups, company, submit, today=None):
	"""Save (and submit) one Material Request per group. Returns their names."""
	today = today or nowdate()
	cost_center = frappe.get_cached_value("Company", company, "cost_center")
	made = []
	for g in groups:
		doc = frappe.new_doc("Material Request")
		doc.material_request_type = g["type"]
		doc.company = company
		doc.transaction_date = today
		doc.schedule_date = min(i["schedule_date"] for i in g["items"])
		doc.title = g["title"][:140]
		if g["from_warehouse"]:
			doc.set_from_warehouse = g["from_warehouse"]
		for i in g["items"]:
			row = {
				"item_code": i["item_code"],
				"qty": i["qty"],
				"uom": i["uom"],
				"conversion_factor": i["conversion_factor"],
				"stock_uom": i["stock_uom"],
				"warehouse": i["warehouse"],
				"schedule_date": i["schedule_date"],
			}
			if i["from_warehouse"]:
				row["from_warehouse"] = i["from_warehouse"]
			if cost_center:
				row["cost_center"] = cost_center
			doc.append("items", row)
		doc.insert()
		if submit:
			doc.submit()
		doc.add_comment("Info", _("Made by Lumen Shelf from its restock suggestions."))
		made.append({"name": doc.name, "type": g["type"], "title": doc.title, "lines": len(g["items"]), "docstatus": doc.docstatus})
	if made:
		engine.forget(company)
	return made


def _table(rows, link):
	head = "<tr><th>{0}</th><th>{1}</th><th style='text-align: end'>{2}</th></tr>".format(
		escape_html(_("Request")), escape_html(_("Type")), escape_html(_("Lines"))
	)
	body = []
	for r in rows:
		title = escape_html(r["title"])
		if link:
			title = "<a href='/app/material-request/{0}'>{1}</a> <span class='text-muted'>{0}</span>".format(
				escape_html(r["name"]), title
			)
		kind = _("Purchase request") if r["type"] == TYPE_PURCHASE else _("Transfer request")
		body.append(
			"<tr><td>{0}</td><td style='white-space: nowrap'>{1}</td><td style='text-align: end'>{2}</td></tr>".format(
				title, escape_html(kind), len(r["items"]) if "items" in r else r["lines"]
			)
		)
	return "<table class='table table-bordered table-condensed'><thead>{0}</thead><tbody>{1}</tbody></table>".format(
		head, "".join(body)
	)


def _plan(scope, filters, use_cache):
	if scope not in SCOPES:
		frappe.throw(_("Unknown list."))
	f = _filters(filters)
	s = access.check_requests(scope)
	result, allowed = views.load(scope, f.company, use_cache=use_cache)
	return plan(result, chosen_lines(result, allowed, scope, f)), s, f.company


@frappe.whitelist()
def can_create(scope="running_low"):
	"""For the screen: show the button or not. Never raises."""
	try:
		s = access.check_requests(scope if scope in SCOPES else "running_low")
		return {"ok": 1, "submit": 1 if s.get("submit_requests") else 0}
	except Exception:
		frappe.clear_messages()
		return {"ok": 0, "submit": 0}


@frappe.whitelist()
def preview(scope, filters=None):
	groups, s, _company = _plan(scope, filters, use_cache=True)
	if not groups:
		return {"count": 0, "message": escape_html(_("Nothing to request. Everything suggested here is already requested or on order."))}
	note = (
		_("They will be submitted. From each request, ERPNext makes the purchase order or the stock transfer.")
		if s.get("submit_requests")
		else _("They will be saved as drafts for someone to check and submit.")
	)
	message = "<p>{0}</p>{1}<p class='text-muted'>{2}</p>".format(
		escape_html(_("Lumen Shelf will create these material requests in ERPNext:")), _table(groups, False), escape_html(note)
	)
	return {"count": len(groups), "message": message}


@frappe.whitelist()
def create(scope, filters=None):
	# worked out again from fresh figures, not from the cached screen
	groups, s, company = _plan(scope, filters, use_cache=False)
	made = make(groups, company, s.get("submit_requests"))
	# ERPNext's own notes from saving each request (such as "Item rates have
	# been updated based on the selected Buying Price List"), one pop-up per
	# request: the table below says what was made, so leave them out.
	frappe.clear_messages()
	if not made:
		return {"count": 0, "names": [], "message": escape_html(_("Nothing to request. Everything suggested here is already requested or on order."))}
	message = "<p>{0}</p>{1}".format(escape_html(_("These material requests were created:")), _table(made, True))
	return {"count": len(made), "names": [m["name"] for m in made], "message": message}
