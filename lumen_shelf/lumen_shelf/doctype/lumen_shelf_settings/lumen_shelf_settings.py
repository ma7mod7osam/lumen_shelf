import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from lumen_shelf.restock import settings as st

class LumenShelfSettings(Document):
	def validate(self):
		labels = {
			"cover_days": _("Days of cover"),
			"history_weeks": _("Weeks of sales history"),
			"default_lead_time": _("Supplier lead time (days)"),
			"transfer_lead_time": _("Transfer lead time (days)"),
			"min_history_days": _("Days in stock needed before judging an outlet"),
			"slow_days": _("Slow when stock lasts more than (days)"),
			"overstock_days": _("Overstock when stock lasts more than (days)"),
			"trend_threshold": _("Rising or falling from (%)"),
		}
		for field, (lo, hi) in st.LIMITS.items():
			value = self.get(field)
			if value in (None, ""):
				self.set(field, st.DEFAULTS[field])
				continue
			if not (lo <= cint(value) <= hi):
				frappe.throw(_("{0} must be between {1} and {2}.").format(labels[field], lo, hi))

		seen = set()
		mains = {}
		for row in self.get("warehouses") or []:
			wh_company = frappe.db.get_value("Warehouse", row.warehouse, "company")
			if wh_company != row.company:
				frappe.throw(
					_("Row {0}: warehouse {1} does not belong to company {2}.").format(row.idx, row.warehouse, row.company)
				)
			if row.warehouse in seen:
				frappe.throw(_("Row {0}: warehouse {1} is listed twice.").format(row.idx, row.warehouse))
			seen.add(row.warehouse)
			if row.warehouse_role == st.ROLE_MAIN:
				if row.company in mains:
					frappe.throw(_("Row {0}: company {1} already has a main warehouse.").format(row.idx, row.company))
				mains[row.company] = row.warehouse

		if cint(self.trend_products) and not (
			(self.trends_url or "").strip() and (self.trends_api_key or "").strip() and self.trends_api_secret
		):
			frappe.msgprint(
				_("Fill in the trends service URL, API Key and API Secret in Lumen Shelf Settings."),
				indicator="orange",
				alert=True,
			)

	def on_update(self):
		"""Automatic mode on: switch on ERPNext's own automatic material requests,
		which act on the levels. Off (or the app off): remove the levels Lumen
		Shelf set, so ERPNext stops acting on them."""
		from lumen_shelf.restock import reorder

		before = self.get_doc_before_save()
		was_on = bool(before and cint(before.get("enabled")) and cint(before.get("auto_reorder")))
		now_on = bool(cint(self.enabled) and cint(self.auto_reorder))
		if now_on and not cint(frappe.db.get_single_value("Stock Settings", "auto_indent")):
			frappe.db.set_value("Stock Settings", "Stock Settings", "auto_indent", 1)
			frappe.msgprint(
				_("ERPNext's automatic material requests (Stock Settings) have been switched on, so ERPNext acts on the reorder levels."),
				alert=True,
			)
		if was_on and not now_on:
			removed = reorder.clear_all()
			if removed:
				frappe.msgprint(_("The reorder levels Lumen Shelf had set were removed."), alert=True)


@frappe.whitelist()
def detected_setup():
	"""What the app found on its own, per company, shown on the settings page so
	the shop can see it works with nothing filled in."""
	frappe.only_for(("System Manager", "Shelf Manager"))

	from frappe.utils import getdate, nowdate

	from lumen_shelf.restock import data, engine

	s = st.get_settings()
	out = []
	for company in frappe.get_all("Company", pluck="name", order_by="name"):
		roles = {r["warehouse"]: r["warehouse_role"] for r in s["warehouse_roles"] if r.get("company") == company}
		usable = [
			w.name
			for w in data.warehouses(company)
			if (w.warehouse_type or "") != "Transit" and not w.is_rejected and roles.get(w.name) != st.ROLE_LEAVE_OUT
		]
		main, basis = engine._main_warehouse(company, usable, roles, getdate(nowdate())) if usable else (None, None)
		out.append(
			{
				"company": company,
				"main_warehouse": main,
				"basis": basis,
				"outlets": [w for w in usable if w != main],
			}
		)
	return out
