"""Running low: per outlet, the items that will run out before a new delivery
can arrive, and what to do about it (transfer, buy, or both)."""

import frappe
from frappe import _

from lumen_restock.restock import views


def execute(filters=None):
	filters = frappe._dict(filters or {})
	result, allowed = views.load("running_low", filters.company)
	rows = views.running_low(
		result,
		allowed,
		warehouse=filters.warehouse,
		item_group=filters.item_group,
		source=filters.source,
	)
	n_transfer = sum(1 for r in rows if r["transfer_qty"])
	n_buy = sum(1 for r in rows if r["buy_qty"])
	summary = [
		{"label": _("Items running low"), "value": len(rows), "indicator": "Red" if rows else "Gray", "datatype": "Int"},
		{"label": _("To transfer"), "value": n_transfer, "indicator": "Blue", "datatype": "Int"},
		{"label": _("To buy"), "value": n_buy, "indicator": "Orange", "datatype": "Int"},
	]
	return columns(), rows, views.describe(result), None, summary


def columns():
	return [
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 140},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"fieldname": "on_shelf", "label": _("On shelf"), "fieldtype": "Float", "width": 90},
		{"fieldname": "daily_sales", "label": _("Daily sales"), "fieldtype": "Float", "precision": 2, "width": 95},
		{"fieldname": "days_left", "label": _("Days left"), "fieldtype": "Float", "precision": 1, "width": 85},
		{"fieldname": "on_order", "label": _("On order"), "fieldtype": "Float", "width": 85},
		{"fieldname": "reorder_point", "label": _("Reorder point"), "fieldtype": "Float", "precision": 1, "width": 105},
		{"fieldname": "suggested_qty", "label": _("Suggested qty"), "fieldtype": "Float", "width": 110},
		{"fieldname": "stock_uom", "label": _("UOM"), "fieldtype": "Data", "width": 70},
		{"fieldname": "source", "label": _("Source"), "fieldtype": "Data", "width": 130},
		{"fieldname": "transfer_qty", "label": _("Transfer qty"), "fieldtype": "Float", "width": 95},
		{"fieldname": "transfer_from", "label": _("Transfer from"), "fieldtype": "Data", "width": 160},
		{"fieldname": "buy_qty", "label": _("Buy qty"), "fieldtype": "Float", "width": 85},
		{"fieldname": "supplier", "label": _("Supplier"), "fieldtype": "Data", "width": 140},
		{"fieldname": "purchase_qty", "label": _("Buy in purchase unit"), "fieldtype": "Float", "width": 130},
		{"fieldname": "purchase_uom", "label": _("Purchase unit"), "fieldtype": "Data", "width": 100},
		{"fieldname": "lead_time", "label": _("Lead time (days)"), "fieldtype": "Float", "precision": 1, "width": 115},
		{"fieldname": "history_days", "label": _("Days in stock"), "fieldtype": "Int", "width": 100},
	]
