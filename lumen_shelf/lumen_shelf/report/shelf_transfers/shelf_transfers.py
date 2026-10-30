"""Transfer suggestions: stock to move between warehouses, either to cover a
shortage before anything is bought, or to move stock that does not sell in one
outlet to an outlet where it sells."""

import frappe
from frappe import _

from lumen_shelf.restock import engine, views

REASON_FILTER = {"Running low there": engine.REASON_LOW, "Sells faster there": engine.REASON_FASTER}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	result, allowed = views.load("transfers", filters.company)
	rows = views.transfers(
		result,
		allowed,
		from_warehouse=filters.from_warehouse,
		to_warehouse=filters.to_warehouse,
		reason=REASON_FILTER.get(filters.reason or ""),
	)
	summary = [
		{"label": _("Transfers"), "value": len(rows), "indicator": "Blue", "datatype": "Int"},
		{
			"label": _("To cover a shortage"),
			"value": sum(1 for r in rows if r["reason_key"] == engine.REASON_LOW),
			"indicator": "Red",
			"datatype": "Int",
		},
		{
			"label": _("To where it sells"),
			"value": sum(1 for r in rows if r["reason_key"] == engine.REASON_FASTER),
			"indicator": "Blue",
			"datatype": "Int",
		},
	]
	return columns(), rows, views.describe(result), None, summary


def columns():
	return [
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 140},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "from_warehouse", "label": _("From warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"fieldname": "to_warehouse", "label": _("To warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"fieldname": "qty", "label": _("Qty"), "fieldtype": "Float", "width": 80},
		{"fieldname": "stock_uom", "label": _("UOM"), "fieldtype": "Data", "width": 70},
		{"fieldname": "reason", "label": _("Reason"), "fieldtype": "Data", "width": 210},
		{"fieldname": "from_on_shelf", "label": _("On shelf at source"), "fieldtype": "Float", "width": 125},
		{"fieldname": "from_daily_sales", "label": _("Daily sales at source"), "fieldtype": "Float", "precision": 2, "width": 140},
		{"fieldname": "to_on_shelf", "label": _("On shelf at destination"), "fieldtype": "Float", "width": 150},
		{"fieldname": "to_daily_sales", "label": _("Daily sales at destination"), "fieldtype": "Float", "precision": 2, "width": 165},
		{"fieldname": "to_days_left", "label": _("Days left at destination"), "fieldtype": "Float", "precision": 1, "width": 155},
	]
