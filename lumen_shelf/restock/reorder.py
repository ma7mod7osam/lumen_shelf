"""Phase 3, automatic mode: Lumen Shelf keeps ERPNext's own reorder levels
(Item > Reorder Levels, the Item Reorder table) up to date from its forecast,
and ERPNext's own nightly job (erpnext.stock.reorder_item, 00:45) raises the
Material Requests. Lumen Shelf never creates a request in this mode.

Per item and warehouse, from the engine's figures:
  reorder level  the reorder point (sales during the lead time + safety)
  reorder qty    order-up-to target less the reorder point, rounded to whole
                 packs and the minimum order (purchases) or whole units
  type           Transfer when the outlet restocks from the main warehouse,
                 else Purchase
ERPNext raises a request when its projected qty is at or below the level, for
the reorder qty, or more if the stock fell further below the level.

Only rows Lumen Shelf set are touched: they carry the custom field
lumen_shelf_managed. A level the shop set itself for an item and warehouse is
kept, and Lumen Shelf sets none there. A level no longer needed (no forecast,
not enough history, warehouse left out) is removed. When automatic mode or the
app is switched off, every level Lumen Shelf set is removed, so ERPNext stops
acting on them.

The rows are written as child rows of Item (db_insert, set_value, delete),
not through Item.save(): one nightly save of every item would run all of
ERPNext's item checks and write a version of each item every day. The checks
that matter for this table are kept here: one row per warehouse, a reorder
qty whenever there is a level, warehouse_group = warehouse as ERPNext sets it.
"""

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from lumen_shelf.restock import access, data, engine, model
from lumen_shelf.restock import settings as st

FIELD = "lumen_shelf_managed"
TYPE_PURCHASE = "Purchase"
TYPE_TRANSFER = "Transfer"
ALERT_ROLE = "Shelf Manager"


def wanted(result):
	"""{(item, warehouse): (level, qty, type)} for every pair that should have a
	reorder level: a forecast, a reorder point, and enough history (or a new
	item forecast from similar items)."""
	out = {}
	for p in result["pairs"]:
		if "rop" not in p or p["rop"] <= model.EPS or p.get("forecast", 0.0) <= model.EPS:
			continue
		if not (p["eligible"] or p.get("base_basis") in ("similar brand", "similar group")):
			continue
		transfer = p.get("plan") == "transfer"
		gap = p["target"] - p["rop"]
		qty = model.round_need(gap, p["whole"]) if transfer else model.round_to_pack(gap, p["pack"], p["min_order_qty"])
		if qty <= model.EPS:
			continue
		out[(p["item_code"], p["warehouse"])] = (round(p["rop"], 3), round(qty, 3), TYPE_TRANSFER if transfer else TYPE_PURCHASE)
	return out


def _rows(warehouses):
	if not warehouses:
		return []
	return frappe.db.sql(
		"""select name, parent, warehouse, warehouse_reorder_level, warehouse_reorder_qty,
			material_request_type, ifnull({0}, 0) as managed, idx
		from `tabItem Reorder` where parenttype = 'Item' and warehouse in %(whs)s""".format(FIELD),
		{"whs": tuple(warehouses)},
		as_dict=True,
	)


def _forget_items(items):
	for item in items:
		try:
			frappe.clear_document_cache("Item", item)
		except Exception:
			pass


def apply(result, levels=None):
	"""Bring the company's Item Reorder rows in line. Returns counts."""
	levels = wanted(result) if levels is None else levels
	company_whs = [w.name for w in data.warehouses(result["company"])]
	rows = _rows(company_whs)
	manual = {(r.parent, r.warehouse) for r in rows if not cint(r.managed)}
	ours = {}
	for r in rows:
		if cint(r.managed):
			ours.setdefault((r.parent, r.warehouse), []).append(r)
	stats = {"set": 0, "unchanged": 0, "removed": 0, "kept": 0, "running_low": 0}
	touched = set()
	last_idx = {}
	for r in rows:
		last_idx[r.parent] = max(last_idx.get(r.parent, 0), cint(r.idx))
	pairs = {(p["item_code"], p["warehouse"]): p for p in result["pairs"]}

	for key, (level, qty, rtype) in sorted(levels.items()):
		item, wh = key
		mine = ours.pop(key, [])
		if key in manual:
			# the shop set its own level here: keep it, and none of ours beside it
			stats["kept"] += 1
			for r in mine:
				frappe.db.delete("Item Reorder", {"name": r.name})
				stats["removed"] += 1
				touched.add(item)
			continue
		if pairs.get(key, {}).get("low"):
			stats["running_low"] += 1
		for r in mine[1:]:
			frappe.db.delete("Item Reorder", {"name": r.name})
			touched.add(item)
		if mine:
			r = mine[0]
			same = (
				abs(float(r.warehouse_reorder_level or 0) - level) <= 1e-6
				and abs(float(r.warehouse_reorder_qty or 0) - qty) <= 1e-6
				and r.material_request_type == rtype
			)
			if same:
				stats["unchanged"] += 1
				continue
			frappe.db.set_value(
				"Item Reorder",
				r.name,
				{"warehouse_reorder_level": level, "warehouse_reorder_qty": qty, "material_request_type": rtype, "warehouse_group": wh},
				update_modified=False,
			)
		else:
			last_idx[item] = last_idx.get(item, 0) + 1
			frappe.get_doc(
				{
					"doctype": "Item Reorder",
					"parent": item,
					"parenttype": "Item",
					"parentfield": "reorder_levels",
					"idx": last_idx[item],
					"warehouse": wh,
					"warehouse_group": wh,
					"warehouse_reorder_level": level,
					"warehouse_reorder_qty": qty,
					"material_request_type": rtype,
					FIELD: 1,
				}
			).db_insert()
		stats["set"] += 1
		touched.add(item)

	# ours that are no longer wanted
	for key, mine in ours.items():
		for r in mine:
			frappe.db.delete("Item Reorder", {"name": r.name})
			stats["removed"] += 1
			touched.add(key[0])
	_forget_items(touched)
	return stats


def clear_all():
	"""Remove every level Lumen Shelf set. Returns how many."""
	if not frappe.db.has_column("Item Reorder", FIELD):
		return 0
	items = frappe.db.sql_list("select distinct parent from `tabItem Reorder` where {0} = 1".format(FIELD))
	n = frappe.db.count("Item Reorder", {FIELD: 1})
	if n:
		frappe.db.delete("Item Reorder", {FIELD: 1})
		_forget_items(items)
	return n


def run(companies=None):
	"""Update every company's levels now. Returns the totals and records them
	on the settings page. Sends the daily alert when that is switched on."""
	s = st.get_settings()
	if not (s["enabled"] and s["auto_reorder"]):
		return {"removed": clear_all()}
	totals = {"set": 0, "unchanged": 0, "removed": 0, "kept": 0, "running_low": 0}
	for company in companies or frappe.get_all("Company", pluck="name", order_by="name"):
		result = engine.compute(company, use_cache=False)
		if not result["pairs"]:
			continue
		for k, v in apply(result).items():
			totals[k] += v
	text = summary(totals)
	frappe.db.set_value(st.DOCTYPE, st.DOCTYPE, {"last_reorder_run": now_datetime(), "last_reorder_result": text}, update_modified=False)
	if s["reorder_alerts"]:
		alert(text)
	return totals


def summary(t):
	return _("Reorder levels set or changed: {0}. Unchanged: {1}. Removed: {2}. Kept as set by the shop: {3}. Running low now: {4}.").format(
		t["set"], t["unchanged"], t["removed"], t["kept"], t["running_low"]
	)


def alert_users():
	users = frappe.db.sql_list(
		"""select distinct u.name from `tabUser` u join `tabHas Role` r on r.parent = u.name
		where r.role = %s and r.parenttype = 'User' and u.enabled = 1 and u.name != 'Guest'""",
		ALERT_ROLE,
	)
	return sorted(users)


def alert(text):
	"""A bell notification (ERPNext's Notification Log) to every Shelf Manager."""
	users = alert_users()
	if not users:
		return []
	from frappe.desk.doctype.notification_log.notification_log import make_notification_logs

	make_notification_logs(
		frappe._dict(
			{
				"type": "Alert",
				"document_type": st.DOCTYPE,
				"document_name": st.DOCTYPE,
				"subject": _("Lumen Shelf updated ERPNext's reorder levels."),
				"email_content": text,
				"from_user": "Administrator",
			}
		),  # v13 reads doc.type: a frappe._dict, not a plain dict
		users,
	)
	return users


def nightly():
	"""Scheduled at 00:15, before ERPNext's own reorder job at 00:45. Does the
	work in the long queue, so a large shop is never cut off by a time limit."""
	s = st.get_settings()
	if not (s["enabled"] and s["auto_reorder"]):
		clear_all()
		return
	frappe.enqueue("lumen_shelf.restock.reorder.run", queue="long", timeout=3600)


@frappe.whitelist()
def update_now():
	"""The settings page button: update the levels right away."""
	s = st.get_settings()
	if not s["enabled"] or not s["auto_reorder"]:
		frappe.throw(_("Automatic mode is switched off in Lumen Shelf Settings."), title=_("Switched off"))
	user = frappe.session.user
	if user != "Administrator" and not (set(access.SETTINGS_ROLES) & set(frappe.get_roles(user))):
		frappe.throw(_("You do not have a role that may change the reorder levels."), frappe.PermissionError)
	if not frappe.has_permission("Item", "write"):
		frappe.throw(_("You are not permitted to change items in ERPNext."), frappe.PermissionError)
	return summary(run())
