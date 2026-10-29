"""Test data, built only through ERPNext's own documents, dated over the past
weeks: Stock Entries, Sales Invoices (with a return and a bundle), POS
Invoices consolidated by ERPNext's own POS Invoice Merge Log, Purchase Orders
received by Purchase Receipts, Material Requests and a Sales Order.

Everything lives in a fresh company made for the run, so the numbers cannot be
disturbed by anything else on the site. The dataset is built once a day and
reused (frappe global DATASET_KEY), so a re-run, or a mutation run, takes
seconds instead of minutes.

Days are written as N = days before today: d(56) is 56 days ago. The window
of the default settings is d(56) to d(1).
"""

import random
import string

import frappe
from frappe.utils import add_days, getdate, nowdate

DATASET_KEY = "lumen_restock_test_dataset"
DATASET_VERSION = 12

WAREHOUSES = {
	"O1": "RS Out1",
	"O2": "RS Out2",
	"O3": "RS Out3",
	"M": "RS Main",
	"AB": "RS ABC",
	"HL": "RS Health",
}


def today():
	return getdate(nowdate())


def d(n):
	return add_days(today(), -n)


# ------------------------------------------------------------------ masters


def ensure_fiscal_years(from_date, to_date):
	for year in range(getdate(from_date).year, getdate(to_date).year + 1):
		start, end = "%d-01-01" % year, "%d-12-31" % year
		covered = frappe.db.sql(
			"select name from `tabFiscal Year` where year_start_date<=%s and year_end_date>=%s", (start, end)
		)
		if covered:
			continue
		name = str(year)
		if frappe.db.exists("Fiscal Year", name):
			name = "RS %d" % year
		frappe.get_doc(
			{"doctype": "Fiscal Year", "year": name, "year_start_date": start, "year_end_date": end}
		).insert(ignore_permissions=True)


def cc(company):
	return frappe.get_cached_value("Company", company, "cost_center")


def make_company(suffix, abbr=None):
	if not frappe.db.exists("Warehouse Type", "Transit"):
		frappe.get_doc({"doctype": "Warehouse Type", "name": "Transit", "__newname": "Transit"}).insert(ignore_permissions=True)
	name = "RS Test %s" % suffix
	abbr = abbr or ("R" + suffix[:4].upper())
	if not frappe.db.exists("Company", name):
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": name,
				"abbr": abbr,
				"default_currency": "USD",
				"country": "United States",
				"chart_of_accounts": "Standard",
				"create_chart_of_accounts_based_on": "Standard Template",
			}
		).insert(ignore_permissions=True)
	return name, frappe.db.get_value("Company", name, "abbr")


def make_warehouse(company, abbr, label):
	name = "%s - %s" % (label, abbr)
	if not frappe.db.exists("Warehouse", name):
		frappe.get_doc({"doctype": "Warehouse", "warehouse_name": label, "company": company}).insert(
			ignore_permissions=True
		)
	return name


def ensure_item_group():
	if not frappe.db.exists("Item Group", "RS Test Items"):
		frappe.get_doc(
			{"doctype": "Item Group", "item_group_name": "RS Test Items", "parent_item_group": "All Item Groups", "is_group": 0}
		).insert(ignore_permissions=True)
	return "RS Test Items"


def make_item(code, company, stock=True, purchase_uom=None, factor=None, min_order=0, lead=0, supplier=None, warehouse=None):
	doc = {
		"doctype": "Item",
		"item_code": code,
		"item_name": code,
		"item_group": ensure_item_group(),
		"stock_uom": "Nos",
		"is_stock_item": 1 if stock else 0,
		"include_item_in_manufacturing": 0,
		"is_purchase_item": 1,
		"is_sales_item": 1,
		"valuation_rate": 10,
		"min_order_qty": min_order,
		"lead_time_days": lead,
		"item_defaults": [{"company": company, "default_supplier": supplier, "default_warehouse": warehouse}] if supplier else [],
	}
	if purchase_uom:
		doc["purchase_uom"] = purchase_uom
		doc["uoms"] = [{"uom": "Nos", "conversion_factor": 1}, {"uom": purchase_uom, "conversion_factor": factor}]
	frappe.get_doc(doc).insert(ignore_permissions=True)
	return code


def leaf_group(doctype, name, parent_field, root):
	"""A non-group record under the tree's root (ERPNext refuses a group one)."""
	if not frappe.db.exists(doctype, name):
		name_field = frappe.scrub(doctype) + "_name"
		frappe.get_doc({"doctype": doctype, name_field: name, parent_field: root, "is_group": 0}).insert(
			ignore_permissions=True
		)
	return name


def make_supplier(name):
	if not frappe.db.exists("Supplier", name):
		group = leaf_group("Supplier Group", "RS Suppliers", "parent_supplier_group", "All Supplier Groups")
		frappe.get_doc({"doctype": "Supplier", "supplier_name": name, "supplier_group": group}).insert(
			ignore_permissions=True
		)
	return name


def make_customer(name):
	if not frappe.db.exists("Customer", name):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_group": leaf_group("Customer Group", "RS Customers", "parent_customer_group", "All Customer Groups"),
				"territory": leaf_group("Territory", "RS Territory", "parent_territory", "All Territories"),
			}
		).insert(ignore_permissions=True)
	return name


# ------------------------------------------------------------- transactions


def receipt(company, lines, day, time="08:00:00"):
	"""Material Receipt. lines: [(item, warehouse, qty)]"""
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt",
			"company": company,
			"set_posting_time": 1,
			"posting_date": day,
			"posting_time": time,
			"items": [
				{"item_code": i, "qty": q, "t_warehouse": w, "basic_rate": 10, "conversion_factor": 1, "uom": "Nos", "cost_center": cc(company)}
				for i, w, q in lines
			],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se.name


def transfer(company, lines, day, time="10:00:00"):
	"""Material Transfer. lines: [(item, from, to, qty)]"""
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Transfer",
			"purpose": "Material Transfer",
			"company": company,
			"set_posting_time": 1,
			"posting_date": day,
			"posting_time": time,
			"items": [
				{"item_code": i, "qty": q, "s_warehouse": s, "t_warehouse": t, "conversion_factor": 1, "uom": "Nos", "cost_center": cc(company)}
				for i, s, t, q in lines
			],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se.name


def sales_invoice(company, customer, lines, day, time="12:00:00"):
	"""lines: [(item, warehouse, qty, rate)]"""
	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": company,
			"customer": customer,
			"set_posting_time": 1,
			"posting_date": day,
			"posting_time": time,
			"due_date": day,
			"update_stock": 1,
			"items": [{"item_code": i, "qty": q, "rate": r, "warehouse": w, "cost_center": cc(company)} for i, w, q, r in lines],
		}
	)
	si.insert(ignore_permissions=True)
	si.submit()
	return si.name


def sales_return(original, item, qty, day):
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

	ret = make_sales_return(original)
	ret.items = [i for i in ret.items if i.item_code == item]
	for i in ret.items:
		i.qty = -abs(qty)
	ret.set_posting_time = 1
	ret.posting_date = day
	ret.posting_time = "15:00:00"
	ret.due_date = day
	ret.insert(ignore_permissions=True)
	ret.submit()
	return ret.name


def purchase_order(company, supplier, lines, day):
	"""lines: [(item, warehouse, qty)]"""
	po = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"company": company,
			"supplier": supplier,
			"transaction_date": day,
			"schedule_date": add_days(day, 7),
			"items": [
				{"item_code": i, "qty": q, "rate": 10, "warehouse": w, "schedule_date": add_days(day, 7), "cost_center": cc(company)}
				for i, w, q in lines
			],
		}
	)
	po.insert(ignore_permissions=True)
	po.submit()
	return po.name


def receive(po_name, day):
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

	pr = make_purchase_receipt(po_name)
	pr.set_posting_time = 1
	pr.posting_date = day
	pr.posting_time = "09:00:00"
	pr.insert(ignore_permissions=True)
	pr.submit()
	return pr.name


def material_request(company, kind, lines, day):
	"""kind: Purchase or Material Transfer. lines: [(item, warehouse, qty)]"""
	mr = frappe.get_doc(
		{
			"doctype": "Material Request",
			"material_request_type": kind,
			"company": company,
			"transaction_date": day,
			"schedule_date": add_days(day, 7),
			"items": [
				{"item_code": i, "qty": q, "warehouse": w, "schedule_date": add_days(day, 7), "uom": "Nos", "conversion_factor": 1}
				for i, w, q in lines
			],
		}
	)
	mr.insert(ignore_permissions=True)
	mr.submit()
	return mr.name


def sales_order(company, customer, lines, day):
	so = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"company": company,
			"customer": customer,
			"transaction_date": day,
			"delivery_date": add_days(day, 7),
			"items": [
				{"item_code": i, "qty": q, "rate": 10, "warehouse": w, "delivery_date": add_days(day, 7)}
				for i, w, q in lines
			],
		}
	)
	so.insert(ignore_permissions=True)
	so.submit()
	return so.name


def product_bundle(parent, part, qty):
	frappe.get_doc(
		{"doctype": "Product Bundle", "new_item_code": parent, "items": [{"item_code": part, "qty": qty}]}
	).insert(ignore_permissions=True)


# ---------------------------------------------------------------------- POS


def pos_setup(company, abbr, warehouse, suffix):
	# ERPNext v16 defaults the till to Sales Invoice mode. The POS Invoice path is
	# the one with consolidation, so the tests use it.
	if frappe.get_meta("POS Settings").has_field("invoice_type"):
		frappe.db.set_single_value("POS Settings", "invoice_type", "POS Invoice")
	mop = frappe.get_doc("Mode of Payment", "Cash")
	if not any(a.company == company for a in mop.accounts):
		mop.append("accounts", {"company": company, "default_account": "Cash - %s" % abbr})
		mop.save(ignore_permissions=True)
	cost_center = frappe.db.get_value("Company", company, "cost_center")
	name = "RS POS %s" % suffix
	if not frappe.db.exists("POS Profile", name):
		profile = frappe.get_doc(
			{
				"doctype": "POS Profile",
				"__newname": name,
				"name": name,
				"company": company,
				"warehouse": warehouse,
				"currency": "USD",
				"write_off_account": "Write Off - %s" % abbr,
				"write_off_cost_center": cost_center,
				"cost_center": cost_center,
				"update_stock": 1,
				"payments": [{"mode_of_payment": "Cash", "default": 1}],
			}
		)
		profile.insert(ignore_permissions=True)
	return name


def pos_open(company, profile, day):
	"""Open the till. ERPNext v16 wants the opening dated today (backdated
	invoices are still accepted) and one open entry per cashier, so earlier
	test openings of this user are cancelled first."""
	for name in frappe.get_all("POS Opening Entry", filters={"user": frappe.session.user, "status": "Open", "docstatus": 1}, pluck="name"):
		frappe.get_doc("POS Opening Entry", name).cancel()
	op = frappe.get_doc(
		{
			"doctype": "POS Opening Entry",
			"company": company,
			"pos_profile": profile,
			"user": frappe.session.user,
			"period_start_date": "%s 07:00:00" % day,
			"posting_date": day,
			"balance_details": [{"mode_of_payment": "Cash", "opening_amount": 0}],
		}
	)
	op.insert(ignore_permissions=True)
	op.submit()
	return op.name


def pos_invoice(company, profile, customer, lines, day):
	"""lines: [(item, warehouse, qty, rate)]"""
	total = sum(q * r for _i, _w, q, r in lines)
	inv = frappe.get_doc(
		{
			"doctype": "POS Invoice",
			"company": company,
			"pos_profile": profile,
			"customer": customer,
			"is_pos": 1,
			"update_stock": 1,
			"set_posting_time": 1,
			"posting_date": day,
			"posting_time": "13:00:00",
			"items": [{"item_code": i, "qty": q, "rate": r, "warehouse": w, "cost_center": cc(company)} for i, w, q, r in lines],
			"payments": [{"mode_of_payment": "Cash", "amount": total, "default": 1}],
		}
	)
	inv.set_missing_values()
	inv.insert(ignore_permissions=True)
	inv.submit()
	return inv.name


def pos_consolidate(company, customer, invoices, day):
	"""ERPNext's own consolidation: a POS Invoice Merge Log makes the Sales
	Invoice with is_consolidated = 1 and moves the stock."""
	log = frappe.get_doc(
		{
			"doctype": "POS Invoice Merge Log",
			"company": company,
			"customer": customer,
			"posting_date": day,
			"posting_time": "23:00:00",
			"merge_invoices_based_on": "Customer",
			"pos_invoices": [
				{
					"pos_invoice": name,
					"customer": customer,
					"posting_date": day,
					"grand_total": frappe.db.get_value("POS Invoice", name, "grand_total"),
				}
				for name in invoices
			],
		}
	)
	log.insert(ignore_permissions=True)
	log.submit()
	return frappe.db.get_value("POS Invoice", invoices[0], "consolidated_invoice")


# ------------------------------------------------------------------ dataset


def every_day(first, last, step=1):
	"""Days d(first) down to d(last), every `step` days."""
	return list(range(first, last - 1, -step))


def build():
	"""The whole dataset. Returns a plain dict of names."""
	suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))
	frappe.set_user("Administrator")
	ensure_fiscal_years(d(130), today())
	company, abbr = make_company(suffix)
	wh = {k: make_warehouse(company, abbr, v) for k, v in WAREHOUSES.items()}
	customer = make_customer("RS Customer")
	s1 = make_supplier("RS Supplier One %s" % suffix)
	s2 = make_supplier("RS Supplier Two %s" % suffix)

	def code(n):
		return "RS-%s-%s" % (suffix, n)

	it = {}
	for n in ("A1", "A2", "A4", "A6", "P1", "K1", "R1", "ON1", "SO1", "L3",
			"X1", "X2", "X3", "X4", "X5", "X6", "X7", "B1", "B2", "B3", "B4", "H1", "H2", "H3", "H4", "Z1"):
		it[n] = make_item(code(n), company)
	it["A3"] = make_item(code("A3"), company, purchase_uom="Box", factor=6)
	it["A5"] = make_item(code("A5"), company, purchase_uom="Box", factor=6, min_order=24)
	it["L1"] = make_item(code("L1"), company, supplier=s1, warehouse=wh["O1"])
	it["L2"] = make_item(code("L2"), company, lead=12, supplier=s2, warehouse=wh["O1"])
	it["BN"] = make_item(code("BN"), company, stock=False)
	product_bundle(it["BN"], it["K1"], 2)

	# what happens on each day: receipts, sales, POS, everything else
	rec, sales, other = {}, {}, {}

	def on(book, day, entry):
		book.setdefault(day, []).append(entry)

	def sell(name, w, days, qty, rate=10):
		for n in days:
			on(sales, n, (it[name], wh[w], qty, rate))

	# --- O1: speed, stock outs, packs, POS, bundles, returns, orders
	on(rec, 70, (it["A1"], wh["O1"], 200))
	sell("A1", "O1", every_day(56, 1), 2)
	on(rec, 70, (it["A2"], wh["O1"], 30))
	sell("A2", "O1", every_day(56, 47), 3)
	on(rec, 29, (it["A2"], wh["O1"], 60))
	sell("A2", "O1", every_day(29, 1), 1)
	on(rec, 60, (it["A3"], wh["O1"], 60))
	sell("A3", "O1", every_day(56, 1), 1)
	on(rec, 60, (it["A5"], wh["O1"], 60))
	sell("A5", "O1", every_day(56, 1), 1)
	on(rec, 70, (it["A4"], wh["O1"], 200))
	sell("A4", "O1", every_day(56, 29), 1)
	sell("A4", "O1", every_day(28, 1), 3)
	on(rec, 60, (it["A6"], wh["O1"], 128))
	sell("A6", "O1", every_day(56, 2, 2), 4)
	on(rec, 40, (it["P1"], wh["O1"], 50))
	on(rec, 60, (it["K1"], wh["O1"], 100))
	sell("BN", "O1", every_day(14, 1), 1)
	on(rec, 60, (it["R1"], wh["O1"], 50))
	sell("R1", "O1", [20], 5)
	on(rec, 60, (it["ON1"], wh["O1"], 62))
	sell("ON1", "O1", every_day(56, 1), 1)
	on(rec, 60, (it["SO1"], wh["O1"], 70))
	sell("SO1", "O1", every_day(56, 1), 1)

	# sold out before the window, restocked on a day with no sale
	on(rec, 80, (it["Z1"], wh["O1"], 10))
	sell("Z1", "O1", [70], 10)
	on(rec, 31, (it["Z1"], wh["O1"], 40))
	sell("Z1", "O1", every_day(30, 1), 1)

	# --- lead times: S1 receipts after 4, 6, 10 and 6 days
	for placed, got, item in ((100, 96, "L1"), (90, 84, "L1"), (80, 70, "L1"), (50, 44, "L3")):
		on(other, placed, ("po", s1, it[item], wh["O1"], 10, got))
	on(rec, 65, (it["L1"], wh["O1"], 31))
	sell("L1", "O1", every_day(56, 1), 1)
	on(rec, 60, (it["L2"], wh["O1"], 66))
	sell("L2", "O1", every_day(56, 1), 1)
	on(rec, 60, (it["L3"], wh["O1"], 50))
	sell("L3", "O1", every_day(56, 1), 1)

	# --- transfers: main M, outlets O2 and O3
	on(rec, 70, (it["X1"], wh["M"], 100))
	on(rec, 60, (it["X1"], wh["O2"], 115))
	sell("X1", "O2", every_day(56, 1), 2)
	on(rec, 60, (it["X1"], wh["O3"], 40))
	sell("X1", "O3", every_day(56, 4, 4), 1)
	on(rec, 60, (it["X2"], wh["O2"], 115))
	sell("X2", "O2", every_day(56, 1), 2)
	on(rec, 60, (it["X2"], wh["O3"], 40))
	sell("X2", "O3", every_day(56, 4, 4), 1)
	on(rec, 70, (it["X3"], wh["O2"], 30))
	on(rec, 60, (it["X3"], wh["O3"], 66))
	sell("X3", "O3", every_day(56, 1), 1)
	on(rec, 10, (it["X4"], wh["O2"], 30))
	on(rec, 60, (it["X4"], wh["O3"], 66))
	sell("X4", "O3", every_day(56, 1), 1)
	# too new in O2 (10 days), while O3 runs low: O2 must not give, O3 buys
	on(rec, 10, (it["X6"], wh["O2"], 30))
	on(rec, 60, (it["X6"], wh["O3"], 60))
	sell("X6", "O3", every_day(56, 1), 1)
	on(rec, 70, (it["X5"], wh["O2"], 100))
	sell("X5", "O2", every_day(56, 2, 2), 1)
	on(rec, 60, (it["X5"], wh["O3"], 55))
	sell("X5", "O3", [n for n in every_day(56, 1) if n % 5 != 0], 1)
	on(rec, 70, (it["X7"], wh["M"], 100))
	on(other, 20, ("transfer", it["X7"], wh["M"], wh["O3"], 50))

	# --- ABC: one sale each, values 700, 200, 60, 40
	for name, rate in (("B1", 700), ("B2", 200), ("B3", 60), ("B4", 40)):
		on(rec, 60, (it[name], wh["AB"], 100))
		sell(name, "AB", [30], 1, rate)

	# --- health
	on(rec, 70, (it["H1"], wh["HL"], 100))
	sell("H1", "HL", [40, 10], 1)
	on(rec, 70, (it["H2"], wh["HL"], 10))
	on(rec, 60, (it["H3"], wh["HL"], 136))
	sell("H3", "HL", every_day(56, 1), 1)
	on(rec, 5, (it["H4"], wh["HL"], 5))

	# --- run it, oldest day first
	out = {"r1_invoice": None, "pos": {}}
	profile = None
	pos_days = (10, 5, 1)
	receive_days = {e[5] for v in other.values() for e in v if e[0] == "po"}
	for n in sorted(set(rec) | set(sales) | set(other) | set(pos_days) | receive_days, reverse=True):
		day = d(n)
		if n in rec:
			receipt(company, rec[n], day)
		for entry in other.get(n, []):
			if entry[0] == "po":
				_k, sup, item, w, qty, got = entry
				out.setdefault("pos_to_receive", []).append((purchase_order(company, sup, [(item, w, qty)], day), got))
			elif entry[0] == "transfer":
				_k, item, src, dst, qty = entry
				transfer(company, [(item, src, dst, qty)], day)
		for po_name, got in list(out.get("pos_to_receive", [])):
			if got == n:
				receive(po_name, day)
		if n in sales:
			lines = [(i, w, q, r) for i, w, q, r in sales[n]]
			name = sales_invoice(company, customer, lines, day)
			if n == 20:
				out["r1_invoice"] = name
		if n == 10 and out["r1_invoice"]:
			sales_return(out["r1_invoice"], it["R1"], 2, day)
		if n in pos_days:
			if profile is None:
				profile = pos_setup(company, abbr, wh["O1"], suffix)
				pos_open(company, profile, today())
			qty = 3 if n == 1 else 2
			inv = pos_invoice(company, profile, customer, [(it["P1"], wh["O1"], qty, 10)], day)
			out["pos"][n] = inv
			if n != 1:
				pos_consolidate(company, customer, [inv], day)

	# --- today: still open orders, and a sale today that must not count
	purchase_order(company, s1, [(it["ON1"], wh["O1"], 10)], today())
	material_request(company, "Purchase", [(it["ON1"], wh["O1"], 5)], today())
	sales_order(company, customer, [(it["SO1"], wh["O1"], 10)], today())
	sales_invoice(company, customer, [(it["A1"], wh["O1"], 10, 10)], today(), time="09:00:00")

	ds = {
		"version": DATASET_VERSION,
		"date": str(today()),
		"suffix": suffix,
		"company": company,
		"abbr": abbr,
		"warehouses": wh,
		"items": it,
		"customer": customer,
		"suppliers": {"S1": s1, "S2": s2},
		"pos_invoices": out["pos"],
		"pos_profile": profile,
	}
	check_ledger_chain(company)
	frappe.db.set_global(DATASET_KEY, frappe.as_json(ds))
	frappe.db.commit()
	return ds


def check_ledger_chain(company):
	"""Stop if ERPNext's running balance does not add up.

	ERPNext chains each ledger row to the one before by posting time, then
	creation. If the machine clock steps back while the data is built (seen
	once right after WSL restarted), a later row gets an earlier creation and
	the balances chain wrong. Every figure test would then fail for a reason
	that is not ours, so fail here with the reason instead.
	"""
	off = frappe.db.sql(
		"""select count(*) from (
			select qty_after_transaction q, sum(actual_qty) over (
				partition by item_code, warehouse
				order by posting_date, posting_time, creation
			) s
			from `tabStock Ledger Entry` where company=%s and is_cancelled=0
		) x where abs(q - s) > 0.0001""",
		company,
	)[0][0]
	if off:
		frappe.db.rollback()
		raise BrokenLedger(
			"Test data broken: %s Stock Ledger rows do not add up. "
			"The clock probably stepped back while building." % off
		)


class BrokenLedger(AssertionError):
	pass


def dataset():
	"""Today's dataset, built if missing."""
	from lumen_restock.tests.bootstrap import before_tests

	before_tests()  # Frappe v16 runs app before_tests hooks for its own test class only
	raw = frappe.db.get_global(DATASET_KEY)
	if raw:
		ds = frappe.parse_json(raw)
		if ds.get("version") == DATASET_VERSION and ds.get("date") == str(today()) and frappe.db.exists("Company", ds["company"]):
			return frappe._dict(ds)
	# through JSON, so a fresh build reads exactly like a reused one.
	# A build broken by the clock (see check_ledger_chain) is tried again.
	for attempt in range(3):
		try:
			return frappe._dict(frappe.parse_json(frappe.as_json(build())))
		except BrokenLedger:
			if attempt == 2:
				raise
