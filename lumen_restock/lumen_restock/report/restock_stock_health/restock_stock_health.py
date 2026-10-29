"""Stock health: the ABC ranking (the items making 80% of sales first), slow
movers, items with no sales, and overstock with its value."""

import frappe
from frappe import _

from lumen_restock.restock import engine, views


def execute(filters=None):
	filters = frappe._dict(filters or {})
	result, allowed = views.load("stock_health", filters.company)
	rows = views.stock_health(
		result,
		allowed,
		warehouse=filters.warehouse,
		status=filters.status,
		abc=filters.abc,
	)
	currency = frappe.get_cached_value("Company", filters.company, "default_currency")
	for r in rows:
		r["currency"] = currency

	def count(status):
		return sum(1 for r in rows if r["status_key"] == status)

	summary = [
		{"label": _("No sales"), "value": count(engine.STATUS_NO_SALES), "indicator": "Red", "datatype": "Int"},
		{"label": _("Slow"), "value": count(engine.STATUS_SLOW), "indicator": "Orange", "datatype": "Int"},
		{"label": _("Overstock"), "value": count(engine.STATUS_OVERSTOCK), "indicator": "Orange", "datatype": "Int"},
		{
			"label": _("Value of excess stock"),
			"value": sum(r["excess_value"] or 0 for r in rows),
			"indicator": "Blue",
			"datatype": "Currency",
			"currency": currency,
		},
	]
	return columns(), rows, views.describe(result), None, summary


def columns():
	return [
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 140},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"fieldname": "abc", "label": _("ABC"), "fieldtype": "Data", "width": 60},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 115},
		{"fieldname": "on_shelf", "label": _("On shelf"), "fieldtype": "Float", "width": 90},
		{"fieldname": "daily_sales", "label": _("Daily sales"), "fieldtype": "Float", "precision": 2, "width": 95},
		{"fieldname": "days_left", "label": _("Days left"), "fieldtype": "Float", "precision": 1, "width": 85},
		{"fieldname": "sold_qty", "label": _("Sold"), "fieldtype": "Float", "width": 80},
		{"fieldname": "sales_value", "label": _("Sales value"), "fieldtype": "Currency", "options": "currency", "width": 120},
		{"fieldname": "history_days", "label": _("Days in stock"), "fieldtype": "Int", "width": 100},
		{"fieldname": "excess_qty", "label": _("Excess qty"), "fieldtype": "Float", "width": 90},
		{"fieldname": "excess_value", "label": _("Excess value"), "fieldtype": "Currency", "options": "currency", "width": 120},
		{"fieldname": "abc_company", "label": _("ABC (company)"), "fieldtype": "Data", "width": 110},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Data", "hidden": 1},
	]
