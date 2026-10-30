"""Assortment gaps: items that sell in one outlet and that another outlet does
not carry at all (no stock, no sale, nothing on order in the whole history
window). Starting qty: the typical daily sales where it sells, for the lead
time and the days of cover."""

import frappe
from frappe import _

from lumen_shelf.restock import views


def execute(filters=None):
	filters = frappe._dict(filters or {})
	result, allowed = views.load("assortment_gaps", filters.company)
	rows = views.assortment_gaps(result, allowed, warehouse=filters.warehouse)
	summary = [
		{"label": _("Items to try"), "value": len(rows), "indicator": "Blue", "datatype": "Int"},
		{"label": _("Outlets"), "value": len({r["warehouse"] for r in rows}), "indicator": "Gray", "datatype": "Int"},
	]
	message = _(
		"Items selling at least {0} a day in another outlet that this outlet did not stock or sell from {1} to {2}."
	).format(
		views.GAP_MIN_SPEED,
		frappe.format(result["window"][0], {"fieldtype": "Date"}),
		frappe.format(result["window"][1], {"fieldtype": "Date"}),
	)
	return columns(), rows, message, None, summary


def columns():
	return [
		{"fieldname": "warehouse", "label": _("Outlet"), "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 140},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "item_group", "label": _("Item Group"), "fieldtype": "Data", "width": 140},
		{"fieldname": "sells_in", "label": _("Sells in"), "fieldtype": "Data", "width": 200},
		{"fieldname": "daily_sales", "label": _("Daily sales there"), "fieldtype": "Float", "precision": 2, "width": 120},
		{"fieldname": "start_qty", "label": _("Starting qty"), "fieldtype": "Float", "width": 110},
		{"fieldname": "stock_uom", "label": _("UOM"), "fieldtype": "Data", "width": 70},
	]
