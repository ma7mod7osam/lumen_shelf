"""What ERPNext itself says, read through ERPNext's own functions and the
documents themselves, never through the app's SQL:

  on shelf     erpnext get_stock_availability (Bin less unconsolidated POS)
  stock by day erpnext get_stock_balance at the end of each day, and the
               day's own Stock Ledger Entries
  on order     the Bin row (ordered_qty + indented_qty), reserved_qty
  sales        every submitted POS Invoice and non-consolidated Sales Invoice,
               opened as a document: its items and its packed items
  lead times   every Purchase Receipt opened as a document, back to its
               Purchase Order

The rules applied on top (weights, safety, levels) are written here a second
time, independently, from the user guide's wording.
"""

import datetime
import math
import statistics

import frappe
from frappe.utils import flt, getdate


def on_shelf(item, warehouse):
	from erpnext.accounts.doctype.pos_invoice.pos_invoice import get_stock_availability

	return flt(get_stock_availability(item, warehouse)[0])


def bin_row(item, warehouse):
	row = frappe.db.get_value(
		"Bin",
		{"item_code": item, "warehouse": warehouse},
		["actual_qty", "ordered_qty", "indented_qty", "reserved_qty", "valuation_rate"],
		as_dict=True,
	)
	return row or frappe._dict(actual_qty=0, ordered_qty=0, indented_qty=0, reserved_qty=0, valuation_rate=0)


def balance_end_of(item, warehouse, day):
	from erpnext.stock.utils import get_stock_balance

	return flt(get_stock_balance(item, warehouse, day, "23:59:59"))


def highest_on(item, warehouse, day):
	rows = frappe.get_all(
		"Stock Ledger Entry",
		filters={"item_code": item, "warehouse": warehouse, "posting_date": day, "is_cancelled": 0},
		fields=["qty_after_transaction"],
	)
	return max([flt(r.qty_after_transaction) for r in rows] or [0.0])


def invoices(company, start, end):
	"""{(item, warehouse): {date: [qty, value]}} from the documents."""
	out = {}

	def add(item, wh, day, qty, value):
		cell = out.setdefault((item, wh), {}).setdefault(getdate(day), [0.0, 0.0])
		cell[0] += flt(qty)
		cell[1] += flt(value)

	for doctype, extra in (("POS Invoice", {}), ("Sales Invoice", {"is_consolidated": 0})):
		filters = {"company": company, "docstatus": 1, "posting_date": ["between", [start, end]]}
		filters.update(extra)
		for name in frappe.get_all(doctype, filters=filters, pluck="name"):
			doc = frappe.get_doc(doctype, name)
			for i in doc.items:
				add(i.item_code, i.warehouse, doc.posting_date, i.stock_qty, i.base_net_amount)
			for p in doc.get("packed_items") or []:
				add(p.item_code, p.warehouse, doc.posting_date, p.qty, 0)
	return out


def transfers_sent(company, source, start, end):
	"""{item: {date: qty}} sent from `source` by Material Transfer entries."""
	out = {}
	for name in frappe.get_all(
		"Stock Entry",
		filters={"company": company, "docstatus": 1, "purpose": "Material Transfer", "posting_date": ["between", [start, end]]},
		pluck="name",
	):
		doc = frappe.get_doc("Stock Entry", name)
		for i in doc.items:
			if i.s_warehouse == source and i.t_warehouse and i.t_warehouse != source:
				cell = out.setdefault(i.item_code, {})
				cell[getdate(doc.posting_date)] = cell.get(getdate(doc.posting_date), 0.0) + flt(i.transfer_qty)
	return out


def lead_days_by_supplier(company):
	"""{supplier: [days]} newest receipt first."""
	rows = []
	for name in frappe.get_all(
		"Purchase Receipt", filters={"company": company, "docstatus": 1, "is_return": 0}, pluck="name"
	):
		pr = frappe.get_doc("Purchase Receipt", name)
		for po_name in sorted({i.purchase_order for i in pr.items if i.purchase_order}):
			po = frappe.get_doc("Purchase Order", po_name)
			rows.append((getdate(pr.posting_date), pr.name, po.supplier, (getdate(pr.posting_date) - getdate(po.transaction_date)).days))
	rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
	out = {}
	for _d, _n, supplier, days in rows:
		out.setdefault(supplier, []).append(days)
	return out


def window(as_of, weeks):
	end = getdate(as_of) - datetime.timedelta(days=1)
	start = end - datetime.timedelta(days=weeks * 7 - 1)
	return start, end


def figures(item, warehouse, as_of, weeks, sold, extra_demand=None):
	"""The day by day picture for one item in one warehouse."""
	start, end = window(as_of, weeks)
	demand = {k: v[0] for k, v in sold.get((item, warehouse), {}).items()}
	for k, v in (extra_demand or {}).items():
		demand[k] = demand.get(k, 0.0) + v
	stocked = []
	day = start
	while day <= end:
		opening = balance_end_of(item, warehouse, day - datetime.timedelta(days=1))
		closing_high = highest_on(item, warehouse, day)
		q = demand.get(day, 0.0)
		if opening > 1e-9 or closing_high > 1e-9 or abs(q) > 1e-9:
			stocked.append(day)
		day += datetime.timedelta(days=1)
	weights = {}
	for day in stocked:
		weeks_back = (end - day).days // 7  # 0 for the last 7 days
		weights[day] = weeks - weeks_back
	values = [demand.get(day, 0.0) for day in stocked]
	total_w = sum(weights.values())
	speed = (sum(weights[day] * demand.get(day, 0.0) for day in stocked) / total_w) if total_w else 0.0
	sigma = statistics.stdev(values) if len(values) > 1 else 0.0
	return frappe._dict(
		in_stock_days=len(stocked),
		speed=max(speed, 0.0),
		sigma=sigma,
		sold_qty=sum(v[0] for v in sold.get((item, warehouse), {}).values()),
		sales_value=sum(v[1] for v in sold.get((item, warehouse), {}).values()),
	)


def levels(speed, sigma, lead, z, cover):
	safety = z * sigma * math.sqrt(lead)
	rop = speed * lead + safety
	return frappe._dict(safety=safety, rop=rop, target=rop + speed * cover)
