"""Forecast accuracy: what Lumen Shelf forecast 14 days ago for each outlet
and item, against what was sold since. Only items that stayed in stock the
whole 14 days count, so an empty shelf never reads as a bad forecast."""

import frappe
from frappe import _
from frappe.utils import flt

from lumen_shelf.restock import views


def execute(filters=None):
	filters = frappe._dict(filters or {})
	result, allowed = views.load("forecast_accuracy", filters.company)
	rows, stats = views.accuracy(result, allowed, warehouse=filters.warehouse)

	def pct(x):
		return None if x is None else round(flt(x) * 100.0, 1)

	summary = [
		{"label": _("Accuracy"), "value": pct(stats["accuracy"]), "indicator": "Blue", "datatype": "Percent"},
		{"label": _("Plain average accuracy"), "value": pct(stats["plain_accuracy"]), "indicator": "Gray", "datatype": "Percent"},
		# no minus sign: it reads "13.1%-" in Arabic, and words are clearer anyway
		{
			"label": _("Forecast above sales by") if (stats["bias"] or 0) >= 0 else _("Forecast below sales by"),
			"value": abs(pct(stats["bias"]) or 0),
			"indicator": "Orange",
			"datatype": "Percent",
		},
		{"label": _("Items compared"), "value": len(rows), "indicator": "Gray", "datatype": "Int"},
	]
	message = _(
		"Forecast made on {0} for the {1} days since, against what was sold. Items out of stock during those days are left out. The plain average divides the sales of the history window by its days."
	).format(frappe.format(stats["from"], {"fieldtype": "Date"}), stats["days"])
	return columns(), rows, message, None, summary


def columns():
	return [
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 140},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"fieldname": "forecast_qty", "label": _("Forecast qty"), "fieldtype": "Float", "precision": 1, "width": 95},
		{"fieldname": "actual_qty", "label": _("Sold"), "fieldtype": "Float", "width": 85},
		{"fieldname": "difference", "label": _("Difference"), "fieldtype": "Float", "precision": 1, "width": 100},
		{"fieldname": "error_pct", "label": _("Error (%)"), "fieldtype": "Float", "precision": 1, "width": 90},
		{"fieldname": "plain_qty", "label": _("Plain average"), "fieldtype": "Float", "precision": 1, "width": 110},
		{"fieldname": "season_factor", "label": _("Season effect"), "fieldtype": "Float", "precision": 2, "width": 105},
		{"fieldname": "stock_uom", "label": _("UOM"), "fieldtype": "Data", "width": 70},
	]
