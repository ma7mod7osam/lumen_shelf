"""Stock health: the ABC ranking (the items making 80% of sales first), slow
movers, items with no sales, overstock with its value, items rising or
falling, and what was lost while items were out of stock."""

import frappe
from frappe import _

from lumen_shelf.restock import engine, views


def execute(filters=None):
	filters = frappe._dict(filters or {})
	result, allowed = views.load("stock_health", filters.company)
	s = result["settings"]
	rows = views.stock_health(
		result,
		allowed,
		warehouse=filters.warehouse,
		status=filters.status,
		abc=filters.abc,
		trend=filters.trend if s.get("trends") else None,
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
	if s.get("trends"):
		summary += [
			{
				"label": _("Rising"),
				"value": sum(1 for r in rows if r["trend_key"] == engine.TREND_RISING),
				"indicator": "Blue",
				"datatype": "Int",
			},
			{
				"label": _("Falling"),
				"value": sum(1 for r in rows if r["trend_key"] == engine.TREND_FALLING),
				"indicator": "Orange",
				"datatype": "Int",
			},
		]
	if s.get("expiry"):
		summary.append(
			{
				"label": _("Stock that will expire before it sells"),
				"value": sum(r["expiry_risk_value"] or 0 for r in rows),
				"indicator": "Red",
				"datatype": "Currency",
				"currency": currency,
			}
		)
	if s.get("lost_sales"):
		summary.append(
			{
				"label": _("Sales lost while out of stock"),
				"value": sum(r["lost_value"] or 0 for r in rows),
				"indicator": "Red",
				"datatype": "Currency",
				"currency": currency,
			}
		)
	return columns(s), rows, views.describe(result), None, summary


def columns(s=None):
	s = s or {"trends": 1, "lost_sales": 1, "expiry": 1, "dead_stock_actions": 1, "demand_patterns": 1}
	cols = [
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 140},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"fieldname": "abc", "label": _("ABC"), "fieldtype": "Data", "width": 60},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 115},
	]
	if s.get("dead_stock_actions"):
		cols.append({"fieldname": "action", "label": _("Suggested action"), "fieldtype": "Data", "width": 200})
	if s.get("demand_patterns"):
		cols.append({"fieldname": "pattern", "label": _("Demand pattern"), "fieldtype": "Data", "width": 115})
	if s.get("trends"):
		cols += [
			{"fieldname": "trend_status", "label": _("Trend"), "fieldtype": "Data", "width": 95},
			{"fieldname": "trend", "label": _("Change (%)"), "fieldtype": "Float", "precision": 1, "width": 95},
		]
	cols += [
		{"fieldname": "on_shelf", "label": _("On shelf"), "fieldtype": "Float", "width": 90},
		{"fieldname": "daily_sales", "label": _("Daily sales"), "fieldtype": "Float", "precision": 2, "width": 95},
		{"fieldname": "days_left", "label": _("Days left"), "fieldtype": "Float", "precision": 1, "width": 85},
		{"fieldname": "sold_qty", "label": _("Sold"), "fieldtype": "Float", "width": 80},
		{"fieldname": "sales_value", "label": _("Sales value"), "fieldtype": "Currency", "options": "currency", "width": 120},
	]
	if s.get("expiry"):
		cols += [
			{"fieldname": "expiry_risk_qty", "label": _("Will expire unsold"), "fieldtype": "Float", "precision": 1, "width": 130},
			{"fieldname": "expiry_risk_value", "label": _("Expiry risk value"), "fieldtype": "Currency", "options": "currency", "width": 130},
		]
	if s.get("lost_sales"):
		cols += [
			{"fieldname": "lost_qty", "label": _("Lost qty"), "fieldtype": "Float", "precision": 1, "width": 90},
			{"fieldname": "lost_value", "label": _("Lost sales"), "fieldtype": "Currency", "options": "currency", "width": 110},
		]
	cols += [
		{"fieldname": "history_days", "label": _("Days in stock"), "fieldtype": "Int", "width": 100},
		{"fieldname": "excess_qty", "label": _("Excess qty"), "fieldtype": "Float", "width": 90},
		{"fieldname": "excess_value", "label": _("Excess value"), "fieldtype": "Currency", "options": "currency", "width": 120},
		{"fieldname": "abc_company", "label": _("ABC (company)"), "fieldtype": "Data", "width": 110},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Data", "hidden": 1},
	]
	return cols
