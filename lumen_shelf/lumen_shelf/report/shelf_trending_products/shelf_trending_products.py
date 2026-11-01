"""Trending products: products rising in Google searches, in the company's
country and worldwide, that the shop does not sell yet. Found by Lumen's
trends service once a week (lumen_shelf.restock.trend_products)."""

import frappe
from frappe import _

from lumen_shelf.restock import trend_products as tp


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = tp.rows(filters.company, item_group=filters.item_group, region=filters.region)
	country = _(frappe.db.get_value("Company", filters.company, "country") or "")
	found = max((r["found_on"] for r in rows), default=None)
	if rows:
		message = _(
			"Products rising in Google searches in {0} and worldwide that you do not sell yet, found on {1}. Only the names of your item groups and items were sent to Lumen's trends service, never quantities, prices or customers."
		).format(country, frappe.format(found, {"fieldtype": "Date"}))
	elif not tp.configured():
		message = _("Lumen's trends service is not set up yet. Fill in its URL, API Key and API Secret in Lumen Shelf Settings > Trending products.")
	else:
		message = _("No trending products yet. They are refreshed once a week, or now from Lumen Shelf Settings.")
	note = tp.credit_note()
	if note:
		message = message + " " + note
	summary = [
		{"label": _("Products suggested"), "value": len(rows), "indicator": "Blue", "datatype": "Int"},
		{"label": _("In the country"), "value": sum(1 for r in rows if r["region"] == _(tp.REGION_LOCAL)), "indicator": "Blue", "datatype": "Int"},
		{"label": _("Worldwide"), "value": sum(1 for r in rows if r["region"] == _(tp.REGION_GLOBAL)), "indicator": "Grey", "datatype": "Int"},
	]
	if tp.configured():
		summary.append(
			{
				"label": _("Available to spend (USD)"),
				"value": frappe.db.get_single_value(tp.DOCTYPE, "trends_available") or 0,
				"indicator": "Orange" if note else "Blue",
				"datatype": "Float",
			}
		)
	return columns(), rows, message, None, summary


def columns():
	return [
		{"fieldname": "item_group", "label": _("Item Group"), "fieldtype": "Data", "width": 150},
		{"fieldname": "product", "label": _("Product"), "fieldtype": "Data", "width": 190},
		{"fieldname": "reason", "label": _("Why"), "fieldtype": "Data", "width": 380},
		{"fieldname": "region", "label": _("Where"), "fieldtype": "Data", "width": 110},
		{"fieldname": "search_term", "label": _("Google search"), "fieldtype": "Data", "width": 170},
		{"fieldname": "growth", "label": _("Search growth (%)"), "fieldtype": "Int", "width": 130},
		{"fieldname": "found_on", "label": _("Found on"), "fieldtype": "Date", "width": 100},
	]
