"""Bought together: pairs of items that appear on the same invoice in the
history window. Confidence: of the invoices with the item, the share that also
had the partner. Lift: how many times more often than chance."""

import frappe
from frappe import _

from lumen_shelf.restock import views


def execute(filters=None):
	filters = frappe._dict(filters or {})
	result, allowed = views.load("bought_together", filters.company)
	rows = views.bought_together(result, allowed, item=filters.item_code)
	summary = [{"label": _("Pairs"), "value": len(rows), "indicator": "Blue", "datatype": "Int"}]
	message = _(
		"Invoices from {0} to {1}. A pair shows when both items were on at least 3 invoices together. Lift above 1: bought together more often than chance."
	).format(
		frappe.format(result["window"][0], {"fieldtype": "Date"}), frappe.format(result["window"][1], {"fieldtype": "Date"})
	)
	return columns(), rows, message, None, summary


def columns():
	return [
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 140},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 170},
		# Data, not a Link: Frappe v16 titles every Item link in a row with that
		# row's item_name, so the partner showed the first item's name
		{"fieldname": "partner", "label": _("Bought with"), "fieldtype": "Data", "width": 140},
		{"fieldname": "partner_name", "label": _("Name of the other item"), "fieldtype": "Data", "width": 170},
		{"fieldname": "together", "label": _("Invoices together"), "fieldtype": "Int", "width": 130},
		{"fieldname": "confidence", "label": _("Confidence (%)"), "fieldtype": "Float", "precision": 1, "width": 120},
		{"fieldname": "lift", "label": _("Lift"), "fieldtype": "Float", "precision": 2, "width": 80},
	]
