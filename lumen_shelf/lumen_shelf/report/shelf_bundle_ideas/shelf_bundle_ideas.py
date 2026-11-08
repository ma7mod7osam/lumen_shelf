"""Bundle ideas: pairs of items bought together that make a natural set,
with a name and a price. Checked by Lumen's AI service once a week
(lumen_shelf.restock.bundles). Made into a Product Bundle from the app."""

import frappe
from frappe import _

from lumen_shelf.restock import bundles, trend_products as tp


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = bundles.rows(filters.company, status=filters.status)
	new = [r for r in rows if r["status_key"] == bundles.STATUS_NEW]
	if rows:
		message = _(
			"Pairs your customers buy on the same invoice, checked by Lumen's AI service. Only item names and item groups were sent, never quantities, prices or customers. The bundle price is the two prices less {0}%, with a profit of at least {1}% kept (Lumen Shelf Settings)."
		).format(bundles.get_settings()["bundle_discount"], bundles.get_settings()["bundle_min_margin"])
	elif not tp.configured():
		message = _("Lumen's AI service is not set up yet. Fill in its URL, API Key and API Secret in Lumen Shelf Settings.")
	else:
		message = _("No bundle ideas yet. They are refreshed once a week, or now with Ask for new ideas.")
	note = tp.credit_note()
	if note:
		message = message + " " + note
	summary = [
		{"label": _("Bundle ideas"), "value": len(new), "indicator": "Blue", "datatype": "Int"},
		{"label": _("Made into bundles"), "value": sum(1 for r in rows if r["status_key"] == bundles.STATUS_CREATED), "indicator": "Grey", "datatype": "Int"},
		{"label": _("Not a match"), "value": sum(1 for r in rows if r["status_key"] == bundles.STATUS_REJECTED), "indicator": "Grey", "datatype": "Int"},
	]
	return columns(), rows, message, None, summary


def columns():
	return [
		{"fieldname": "bundle_name", "label": _("Bundle name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "item_name", "label": _("First item"), "fieldtype": "Data", "width": 170},
		{"fieldname": "partner_name", "label": _("Bought with"), "fieldtype": "Data", "width": 170},
		{"fieldname": "together", "label": _("Invoices together"), "fieldtype": "Int", "width": 120},
		{"fieldname": "full_price", "label": _("Price of the two"), "fieldtype": "Currency", "options": "currency", "width": 120},
		{"fieldname": "bundle_price", "label": _("Bundle price"), "fieldtype": "Currency", "options": "currency", "width": 120},
		{"fieldname": "discount", "label": _("Discount (%)"), "fieldtype": "Float", "precision": 1, "width": 100},
		{"fieldname": "margin", "label": _("Bundle profit (%)"), "fieldtype": "Float", "precision": 1, "width": 120},
		{"fieldname": "reason", "label": _("Why"), "fieldtype": "Data", "width": 320},
		{"fieldname": "note", "label": _("Note"), "fieldtype": "Data", "width": 260},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 100},
		{"fieldname": "found_on", "label": _("Found on"), "fieldtype": "Date", "width": 100},
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Data", "hidden": 1},
		{"fieldname": "partner", "label": _("Item Code"), "fieldtype": "Data", "hidden": 1},
		{"fieldname": "status_key", "label": _("Status"), "fieldtype": "Data", "hidden": 1},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Data", "hidden": 1},
		{"fieldname": "can_create", "label": _("Create bundle"), "fieldtype": "Check", "hidden": 1},
	]
