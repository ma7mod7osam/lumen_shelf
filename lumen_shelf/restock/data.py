"""Bulk reads from ERPNext's own tables. One query per kind of fact for a whole
company, never one per item, so a chain with thousands of items and many
outlets reads in seconds.

Every number comes from where ERPNext itself keeps it:
  on the shelf      Bin.actual_qty, less submitted POS Invoices not yet
                    consolidated (ERPNext's get_pos_reserved_qty: a POS Invoice
                    moves no stock until its shift's closing entry)
  on order          Bin.ordered_qty (open Purchase Orders) + Bin.indented_qty
                    (open Material Requests, purchase and transfer)
  reserved          Bin.reserved_qty (Sales Orders)
  requested out     submitted Material Requests (Material Transfer) not yet
                    transferred, by the warehouse they come from: ERPNext
                    counts them on order at the receiving end only
  sales             POS Invoice items, and Sales Invoice items whose invoice is
                    not a POS consolidation (is_consolidated = 0), or every POS
                    sale would count twice; bundle parts through Packed Item
  stock by day      Stock Ledger Entry.qty_after_transaction
"""

import frappe
from frappe.utils import flt, getdate


def _in(values):
	return tuple(values) if values else ("",)


def _items_clause(items, column="item_code"):
	return (" and %s in %%(items)s" % column) if items else ""


def warehouses(company):
	has_rejected = frappe.db.has_column("Warehouse", "is_rejected_warehouse")
	rows = frappe.db.sql(
		"""select name, warehouse_type, {rej} as is_rejected
		from `tabWarehouse`
		where company=%s and is_group=0 and disabled=0
		order by name""".format(rej="is_rejected_warehouse" if has_rejected else "0"),
		(company,),
		as_dict=True,
	)
	return rows


def item_master(item_codes):
	"""Stock items that can be restocked: enabled, kept in stock, not a template."""
	if not item_codes:
		return {}
	rows = frappe.db.sql(
		"""select i.name, i.item_name, i.item_group, i.stock_uom, i.purchase_uom,
			i.min_order_qty, i.lead_time_days, i.is_purchase_item, i.last_purchase_rate,
			i.brand, i.shelf_life_in_days, i.has_batch_no, i.has_expiry_date,
			ifnull(u.must_be_whole_number, 0) as whole
		from `tabItem` i left join `tabUOM` u on u.name = i.stock_uom
		where i.name in %(items)s and i.is_stock_item=1 and i.disabled=0 and i.has_variants=0""",
		{"items": _in(item_codes)},
		as_dict=True,
	)
	out = {r.name: r for r in rows}
	if out:
		packs = frappe.db.sql(
			"""select d.parent, d.uom, d.conversion_factor from `tabUOM Conversion Detail` d
			where d.parenttype='Item' and d.parent in %(items)s""",
			{"items": _in(list(out))},
		)
		factors = {(p, u): flt(f) for p, u, f in packs}
		for code, r in out.items():
			pack = 0.0
			if r.purchase_uom and r.purchase_uom != r.stock_uom:
				pack = factors.get((code, r.purchase_uom), 0.0)
			r["pack"] = pack if pack > 0 else 0.0
			r["whole"] = 1 if r.get("whole") else 0
	return out


def bins(whs, items=None):
	rows = frappe.db.sql(
		"""select item_code, warehouse, actual_qty, ordered_qty, indented_qty, reserved_qty,
			valuation_rate, stock_value
		from `tabBin` where warehouse in %(whs)s""" + _items_clause(items),
		{"whs": _in(whs), "items": _in(items or [])},
		as_dict=True,
	)
	return {(r.item_code, r.warehouse): r for r in rows}


def requested_out(whs, items=None):
	"""Stock already asked of a warehouse by a submitted transfer request and
	not yet moved, per item and sending warehouse. The same conditions as
	ERPNext's get_indented_qty, read from the sending side."""
	rows = frappe.db.sql(
		"""select i.item_code, i.from_warehouse, sum(i.stock_qty - i.ordered_qty)
		from `tabMaterial Request Item` i join `tabMaterial Request` r on r.name = i.parent
		where r.docstatus = 1 and r.status != 'Stopped' and r.material_request_type = 'Material Transfer'
			and i.stock_qty > i.ordered_qty and i.from_warehouse in %(whs)s"""
		+ _items_clause(items, "i.item_code")
		+ " group by i.item_code, i.from_warehouse",
		{"whs": _in(whs), "items": _in(items or [])},
	)
	return {(i, w): flt(q) for i, w, q in rows}


def draft_requests(company, request_type):
	"""Quantities on draft Material Requests of one type, in stock units, per
	item, warehouse and sending warehouse. ERPNext counts a request only once
	it is submitted, so these are what someone has already asked for and not
	yet sent off."""
	rows = frappe.db.sql(
		"""select i.item_code, i.warehouse, ifnull(i.from_warehouse, ''), sum(i.stock_qty)
		from `tabMaterial Request Item` i join `tabMaterial Request` r on r.name = i.parent
		where r.docstatus = 0 and r.company = %s and r.material_request_type = %s
		group by i.item_code, i.warehouse, i.from_warehouse""",
		(company, request_type),
	)
	return {(i, w, f or None): flt(q) for i, w, f, q in rows}


def pos_reserved(whs, items=None):
	"""Sold at the till but not yet out of the Stock Ledger: submitted POS
	Invoices with no consolidated invoice yet, their own lines and the parts of
	any bundle (Packed Item), as ERPNext's get_pos_reserved_qty counts them."""
	out = {}
	q1 = frappe.db.sql(
		"""select i.item_code, i.warehouse, sum(i.stock_qty)
		from `tabPOS Invoice Item` i join `tabPOS Invoice` p on p.name = i.parent
		where p.docstatus=1 and ifnull(p.consolidated_invoice, '') = ''
			and i.warehouse in %(whs)s""" + _items_clause(items, "i.item_code") + """
		group by i.item_code, i.warehouse""",
		{"whs": _in(whs), "items": _in(items or [])},
	)
	q2 = frappe.db.sql(
		"""select i.item_code, i.warehouse, sum(i.qty)
		from `tabPacked Item` i join `tabPOS Invoice` p on p.name = i.parent
		where i.parenttype='POS Invoice' and p.docstatus=1 and ifnull(p.consolidated_invoice, '') = ''
			and i.warehouse in %(whs)s""" + _items_clause(items, "i.item_code") + """
		group by i.item_code, i.warehouse""",
		{"whs": _in(whs), "items": _in(items or [])},
	)
	for item, wh, qty in list(q1) + list(q2):
		out[(item, wh)] = out.get((item, wh), 0.0) + flt(qty)
	return out


def sales(company, whs, start, end, items=None):
	"""{(item, warehouse): {date: [qty, value]}} in stock units and company
	currency, net of returns. POS Invoices, plus Sales Invoices that are not a
	POS consolidation, plus the parts of bundles sold on either."""
	out = {}
	args = {"company": company, "whs": _in(whs), "start": start, "end": end, "items": _in(items or [])}

	def add(rows):
		for item, wh, day, qty, value in rows:
			d = out.setdefault((item, wh), {})
			cell = d.setdefault(getdate(day), [0.0, 0.0])
			cell[0] += flt(qty)
			cell[1] += flt(value)

	add(
		frappe.db.sql(
			"""select i.item_code, i.warehouse, p.posting_date, sum(i.stock_qty), sum(i.base_net_amount)
			from `tabPOS Invoice Item` i join `tabPOS Invoice` p on p.name = i.parent
			where p.docstatus=1 and p.company=%(company)s and p.posting_date between %(start)s and %(end)s
				and i.warehouse in %(whs)s""" + _items_clause(items, "i.item_code") + """
			group by i.item_code, i.warehouse, p.posting_date""",
			args,
		)
	)
	add(
		frappe.db.sql(
			"""select i.item_code, i.warehouse, s.posting_date, sum(i.stock_qty), sum(i.base_net_amount)
			from `tabSales Invoice Item` i join `tabSales Invoice` s on s.name = i.parent
			where s.docstatus=1 and s.is_consolidated=0 and s.company=%(company)s
				and s.posting_date between %(start)s and %(end)s
				and i.warehouse in %(whs)s""" + _items_clause(items, "i.item_code") + """
			group by i.item_code, i.warehouse, s.posting_date""",
			args,
		)
	)
	for parent in ("POS Invoice", "Sales Invoice"):
		cond = " and s.is_consolidated=0" if parent == "Sales Invoice" else ""
		add(
			frappe.db.sql(
				"""select i.item_code, i.warehouse, s.posting_date, sum(i.qty), 0
				from `tabPacked Item` i join `tab{parent}` s on s.name = i.parent
				where i.parenttype=%(parent)s and s.docstatus=1 and s.company=%(company)s{cond}
					and s.posting_date between %(start)s and %(end)s
					and i.warehouse in %(whs)s""".format(parent=parent, cond=cond)
				+ _items_clause(items, "i.item_code")
				+ """ group by i.item_code, i.warehouse, s.posting_date""",
				dict(args, parent=parent),
			)
		)
	return out


def week_bounds(ref, k_lo, k_hi):
	"""The dates of weeks k_lo..k_hi counted back from `ref`: week 0 is the 7
	days before ref, week -1 the 7 days from ref on."""
	import datetime

	return ref - datetime.timedelta(days=7 * k_hi + 7), ref - datetime.timedelta(days=7 * k_lo + 1)


def weekly_sales(company, whs, ref, k_lo, k_hi, items=None):
	"""Units sold per item and week, counted back from `ref` (see week_bounds),
	in every warehouse of `whs` together: {item: {week: qty}} plus each item's
	group: {item: item_group}. Sales as in sales(). Weekly totals from the
	database, never a year of daily rows."""
	start, end = week_bounds(ref, k_lo, k_hi)
	args = {"company": company, "whs": _in(whs), "start": start, "end": end, "ref": ref, "items": _in(items or [])}
	week = "floor((datediff(%(ref)s, s.posting_date) - 1) / 7)"
	out, groups = {}, {}
	sources = [
		("`tabPOS Invoice Item`", "`tabPOS Invoice`", "i.stock_qty", "", ""),
		("`tabSales Invoice Item`", "`tabSales Invoice`", "i.stock_qty", " and s.is_consolidated=0", ""),
		("`tabPacked Item`", "`tabPOS Invoice`", "i.qty", "", " and i.parenttype='POS Invoice'"),
		("`tabPacked Item`", "`tabSales Invoice`", "i.qty", " and s.is_consolidated=0", " and i.parenttype='Sales Invoice'"),
	]
	for child, parent, qty, cond, ptype in sources:
		rows = frappe.db.sql(
			"""select i.item_code, it.item_group, {week} as wk, sum({qty})
			from {child} i join {parent} s on s.name = i.parent
				join `tabItem` it on it.name = i.item_code
			where s.docstatus=1 and s.company=%(company)s{cond}{ptype}
				and s.posting_date between %(start)s and %(end)s
				and i.warehouse in %(whs)s""".format(week=week, qty=qty, child=child, parent=parent, cond=cond, ptype=ptype)
			+ _items_clause(items, "i.item_code")
			+ " group by i.item_code, it.item_group, wk",
			args,
		)
		for item, group, wk, q in rows:
			cell = out.setdefault(item, {})
			cell[int(wk)] = cell.get(int(wk), 0.0) + flt(q)
			groups[item] = group
	return out, groups


def batches(pairs):
	"""{(item, warehouse): [(expiry date, qty)]} for items kept in batches with
	an expiry date. The quantities come from ERPNext's own get_batch_qty, so
	they are right on every version (v15+ keeps batches in Serial and Batch
	Bundles, older versions on the Stock Ledger)."""
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	out = {}
	expiry = {}
	for item, wh in pairs:
		rows = get_batch_qty(warehouse=wh, item_code=item) or []
		got = []
		for r in rows:
			qty = flt(r.get("qty"))
			if qty <= 0:
				continue
			b = r.get("batch_no")
			if b not in expiry:
				expiry[b] = frappe.db.get_value("Batch", b, "expiry_date")
			if expiry[b]:
				got.append((getdate(expiry[b]), qty))
		if got:
			out[(item, wh)] = got
	return out


def last_receipts(company, since):
	"""{(item, warehouse): (latest date, supplier)} of submitted Purchase
	Receipts (not returns) since `since`."""
	rows = frappe.db.sql(
		"""select i.item_code, i.warehouse, r.posting_date, r.supplier
		from `tabPurchase Receipt Item` i join `tabPurchase Receipt` r on r.name = i.parent
		where r.docstatus=1 and r.is_return=0 and r.company=%s and r.posting_date >= %s
		order by r.posting_date""",
		(company, since),
	)
	return {(item, wh): (getdate(day), sup) for item, wh, day, sup in rows}


def baskets(company, whs, start, end):
	"""[set of items] per invoice: POS Invoices and Sales Invoices that are not
	a POS consolidation, not returns, in the window, lines in `whs`."""
	out = {}
	for child, parent, cond in (
		("`tabPOS Invoice Item`", "`tabPOS Invoice`", ""),
		("`tabSales Invoice Item`", "`tabSales Invoice`", " and s.is_consolidated=0"),
	):
		rows = frappe.db.sql(
			"""select s.name, i.item_code from {child} i join {parent} s on s.name = i.parent
			where s.docstatus=1 and s.is_return=0 and s.company=%(company)s{cond}
				and s.posting_date between %(start)s and %(end)s
				and i.warehouse in %(whs)s""".format(child=child, parent=parent, cond=cond),
			{"company": company, "whs": _in(whs), "start": start, "end": end},
		)
		for name, item in rows:
			out.setdefault((parent, name), set()).add(item)
	return list(out.values())


def _by_datetime():
	"""ERPNext v15 and later keep posting_datetime on every Stock Ledger Entry
	and index (item_code, warehouse, posting_datetime, creation). Older
	versions order by posting_date, posting_time, creation."""
	import erpnext

	major = int(str(getattr(erpnext, "__version__", "13")).split(".")[0] or 13)
	return major >= 15 and frappe.db.has_column("Stock Ledger Entry", "posting_datetime")


# ERPNext's own order of the Stock Ledger, newest first
ORDER_NEW = "s.posting_datetime desc, s.creation desc"
ORDER_OLD = "s.posting_date desc, s.posting_time desc, s.creation desc"


def ledger_opening(whs, start, items=None):
	"""{(item, warehouse): qty} on the shelf just before `start`: the last
	Stock Ledger Entry before it, in ERPNext's own order. One indexed lookup
	per Bin row, never a sort of the whole history."""
	if _by_datetime():
		before, order = "s.posting_datetime < %(start)s", ORDER_NEW
	else:
		before, order = "s.posting_date < %(start)s", ORDER_OLD
	rows = frappe.db.sql(
		"""select b.item_code, b.warehouse,
			(select s.qty_after_transaction from `tabStock Ledger Entry` s
				where s.item_code = b.item_code and s.warehouse = b.warehouse
					and s.is_cancelled = 0 and {before}
				order by {order} limit 1) as q
		from `tabBin` b where b.warehouse in %(whs)s""".format(before=before, order=order)
		+ _items_clause(items, "b.item_code"),
		{"whs": _in(whs), "start": start, "items": _in(items or [])},
	)
	return {(i, w): flt(q) for i, w, q in rows if q is not None}


def ledger_days(whs, start, end, items=None):
	"""{(item, warehouse): {date: (closing qty, highest qty that day)}} for
	days with a Stock Ledger movement inside the window."""
	if _by_datetime():
		span = "posting_datetime >= %(start)s and posting_datetime < %(after)s"
	else:
		span = "posting_date between %(start)s and %(end)s"
	import datetime

	rows = frappe.db.sql(
		"""select item_code, warehouse, posting_date, qty_after_transaction, mx from (
			select item_code, warehouse, posting_date, qty_after_transaction,
				max(qty_after_transaction) over (partition by item_code, warehouse, posting_date) as mx,
				row_number() over (partition by item_code, warehouse, posting_date
					order by posting_time desc, creation desc) as rn
			from `tabStock Ledger Entry`
			where is_cancelled=0 and warehouse in %(whs)s and {span}""".format(span=span)
		+ _items_clause(items)
		+ """) t where rn=1""",
		{
			"whs": _in(whs),
			"start": start,
			"end": end,
			"after": getdate(end) + datetime.timedelta(days=1),
			"items": _in(items or []),
		},
	)
	out = {}
	for item, wh, day, close, mx in rows:
		out.setdefault((item, wh), {})[getdate(day)] = (flt(close), flt(mx))
	return out


def transfers_out(company, wh, others, start, end, items=None):
	"""{item: {date: qty}} sent from `wh` to the company's other warehouses by
	Material Transfer stock entries: what a main warehouse supplies to outlets
	is its demand."""
	if not others:
		return {}
	rows = frappe.db.sql(
		"""select d.item_code, e.posting_date, sum(d.transfer_qty)
		from `tabStock Entry Detail` d join `tabStock Entry` e on e.name = d.parent
		where e.docstatus=1 and e.company=%(company)s and e.purpose='Material Transfer'
			and e.posting_date between %(start)s and %(end)s
			and d.s_warehouse=%(wh)s and d.t_warehouse in %(others)s"""
		+ _items_clause(items, "d.item_code")
		+ """ group by d.item_code, e.posting_date""",
		{"company": company, "wh": wh, "others": _in(others), "start": start, "end": end, "items": _in(items or [])},
	)
	out = {}
	for item, day, qty in rows:
		out.setdefault(item, {})[getdate(day)] = flt(qty)
	return out


def busiest_feeder(company, whs, since):
	"""The warehouse that sent the most stock to the company's other warehouses
	by Material Transfer since `since`, or None. Used to find the main
	warehouse when the shop has not named one."""
	if len(whs) < 2:
		return None
	row = frappe.db.sql(
		"""select d.s_warehouse, sum(d.transfer_qty) as q
		from `tabStock Entry Detail` d join `tabStock Entry` e on e.name = d.parent
		where e.docstatus=1 and e.company=%(company)s and e.purpose='Material Transfer'
			and e.posting_date >= %(since)s and d.s_warehouse in %(whs)s and d.t_warehouse in %(whs)s
			and d.s_warehouse != d.t_warehouse
		group by d.s_warehouse order by q desc, d.s_warehouse limit 1""",
		{"company": company, "whs": _in(whs), "since": since},
	)
	return row[0][0] if row else None


def default_suppliers(company, items):
	"""{item: supplier} from the Item Default row for this company."""
	if not items:
		return {}
	rows = frappe.db.sql(
		"""select parent, default_supplier from `tabItem Default`
		where parenttype='Item' and company=%(company)s and parent in %(items)s
			and ifnull(default_supplier, '') != ''""",
		{"company": company, "items": _in(items)},
	)
	return dict(rows)


def last_po_suppliers(company, items):
	"""{item: supplier} of the most recent submitted Purchase Order for it."""
	if not items:
		return {}
	rows = frappe.db.sql(
		"""select item_code, supplier from (
			select i.item_code, p.supplier,
				row_number() over (partition by i.item_code
					order by p.transaction_date desc, p.creation desc) as rn
			from `tabPurchase Order Item` i join `tabPurchase Order` p on p.name = i.parent
			where p.docstatus=1 and p.company=%(company)s and i.item_code in %(items)s
		) t where rn=1""",
		{"company": company, "items": _in(items)},
	)
	return dict(rows)


def lead_samples(company, since):
	"""{supplier: [days, ...]} newest first: Purchase Order date to Purchase
	Receipt date, for receipts made against an order since `since`."""
	rows = frappe.db.sql(
		"""select distinct po.supplier, pr.name, po.name, pr.posting_date, po.transaction_date
		from `tabPurchase Receipt Item` i
			join `tabPurchase Receipt` pr on pr.name = i.parent
			join `tabPurchase Order` po on po.name = i.purchase_order
		where pr.docstatus=1 and pr.is_return=0 and pr.company=%(company)s
			and pr.posting_date >= %(since)s and ifnull(i.purchase_order, '') != ''
		order by pr.posting_date desc, pr.name""",
		{"company": company, "since": since},
	)
	out = {}
	for supplier, _pr, _po, received, ordered in rows:
		days = (getdate(received) - getdate(ordered)).days
		if days >= 0:
			out.setdefault(supplier, []).append(days)
	return out
