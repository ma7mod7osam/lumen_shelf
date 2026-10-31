"""Promotions: per outlet and item, the days it sold mostly at a discount, how
many times more it sold on them (the lift), and a promotion planned within
the lead time and cover, with the extra units it adds to the suggestion."""

import frappe
from frappe import _

from lumen_shelf.restock import views


def execute(filters=None):
	filters = frappe._dict(filters or {})
	result, allowed = views.load("promotions", filters.company)
	rows = views.promotions(result, allowed, warehouse=filters.warehouse)
	summary = [
		{"label": _("Items with a measured lift"), "value": sum(1 for r in rows if r["lift"]), "indicator": "Blue", "datatype": "Int"},
		{"label": _("Promotions ahead"), "value": sum(1 for r in rows if r["next_promotion"]), "indicator": "Orange", "datatype": "Int"},
		{"label": _("Extra qty planned"), "value": sum(r["extra_qty"] or 0 for r in rows), "indicator": "Blue", "datatype": "Float"},
	]
	message = _(
		"A promotion day: at least half of the day's sales at 5% or more under the price list. The lift compares those days with the other days in stock, from {0} to {1}. Planned promotions: ERPNext pricing rules with an end date, and LumenPOS promotions."
	).format(
		frappe.format(result["window"][0], {"fieldtype": "Date"}),
		frappe.format(result["window"][1], {"fieldtype": "Date"}),
	)
	return columns(), rows, message, None, summary


def columns():
	return [
		{"fieldname": "warehouse", "label": _("Outlet"), "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 140},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 170},
		{"fieldname": "promo_days", "label": _("Promotion days"), "fieldtype": "Int", "width": 115},
		{"fieldname": "normal_speed", "label": _("Daily sales, normal days"), "fieldtype": "Float", "precision": 2, "width": 150},
		{"fieldname": "promo_speed", "label": _("Daily sales on promotion"), "fieldtype": "Float", "precision": 2, "width": 160},
		{"fieldname": "lift", "label": _("Lift (times)"), "fieldtype": "Float", "precision": 2, "width": 95},
		{"fieldname": "next_promotion", "label": _("Next promotion"), "fieldtype": "Data", "width": 170},
		{"fieldname": "next_source", "label": _("Set in"), "fieldtype": "Data", "width": 150},
		{"fieldname": "next_from", "label": _("Starts"), "fieldtype": "Date", "width": 100},
		{"fieldname": "next_to", "label": _("Ends"), "fieldtype": "Date", "width": 100},
		{"fieldname": "promo_days_ahead", "label": _("Promotion days ahead"), "fieldtype": "Int", "width": 140},
		{"fieldname": "promo_factor", "label": _("Promotion effect"), "fieldtype": "Float", "precision": 2, "width": 120},
		{"fieldname": "extra_qty", "label": _("Extra qty planned"), "fieldtype": "Float", "width": 120},
		{"fieldname": "stock_uom", "label": _("UOM"), "fieldtype": "Data", "width": 70},
	]
