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

DATASET_KEY = "lumen_shelf_test_dataset"
DATASET_VERSION = 19

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


def ensure_item_group(name="RS Test Items", parent="All Item Groups", is_group=0):
	if not frappe.db.exists("Item Group", name):
		frappe.get_doc(
			{"doctype": "Item Group", "item_group_name": name, "parent_item_group": parent, "is_group": is_group}
		).insert(ignore_permissions=True)
	return name


def putaway_rule(company, item, warehouse, capacity, disable=0):
	"""ERPNext's Putaway Rule: how much of an item the warehouse can hold. The
	stock-unit capacity is filled in too: ERPNext checks it against the stock
	on hand before working it out itself."""
	doc = frappe.get_doc(
		{
			"doctype": "Putaway Rule",
			"item_code": item,
			"warehouse": warehouse,
			"company": company,
			"capacity": capacity,
			"uom": frappe.db.get_value("Item", item, "stock_uom"),
			"conversion_factor": 1,
			"stock_capacity": capacity,
			"priority": 1,
			"disable": disable,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def pricing_rule(company, title, apply_on, values, start, end, warehouse=None, disable=0):
	"""An ERPNext selling Pricing Rule, 20% off. apply_on: Item Code, Item
	Group or Brand, with `values` for its table. end None: no end date."""
	table, field = {"Item Code": ("items", "item_code"), "Item Group": ("item_groups", "item_group"), "Brand": ("brands", "brand")}[apply_on]
	doc = frappe.get_doc(
		{
			"doctype": "Pricing Rule",
			"title": title,
			"apply_on": apply_on,
			table: [{field: v} for v in values],
			"selling": 1,
			"buying": 0,
			"company": company,
			"applicable_for": "",
			"price_or_product_discount": "Price",
			"rate_or_discount": "Discount Percentage",
			"discount_percentage": 20,
			"valid_from": start,
			"valid_upto": end,
			"warehouse": warehouse,
			"disable": disable,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def make_item(
	code,
	company,
	stock=True,
	purchase_uom=None,
	factor=None,
	min_order=0,
	lead=0,
	supplier=None,
	warehouse=None,
	group=None,
	brand=None,
	shelf_life=0,
	batches=False,
):
	doc = {
		"doctype": "Item",
		"item_code": code,
		"item_name": code,
		"item_group": ensure_item_group(group) if group else ensure_item_group(),
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
	if brand:
		if not frappe.db.exists("Brand", brand):
			frappe.get_doc({"doctype": "Brand", "brand": brand}).insert(ignore_permissions=True)
		doc["brand"] = brand
	if shelf_life:
		doc["shelf_life_in_days"] = shelf_life
	if batches:
		# ERPNext v16 allows batches only once Stock Settings switch them on
		meta = frappe.get_meta("Stock Settings")
		if meta.has_field("enable_serial_and_batch_no_for_item"):
			frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
		doc["has_batch_no"] = 1
		doc["has_expiry_date"] = 1
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


def _batch_fields(doctype, row, batch):
	"""Put a batch on a line. ERPNext v15+ keeps batches in a Serial and Batch
	Bundle: with use_serial_batch_fields it builds one from batch_no itself."""
	if batch:
		row["batch_no"] = batch
		if frappe.get_meta(doctype).has_field("use_serial_batch_fields"):
			row["use_serial_batch_fields"] = 1
	return row


def make_batch(item, name, expiry):
	frappe.get_doc({"doctype": "Batch", "batch_id": name, "item": item, "expiry_date": expiry}).insert(ignore_permissions=True)
	return name


def receipt(company, lines, day, time="08:00:00"):
	"""Material Receipt. lines: [(item, warehouse, qty)] or (item, warehouse, qty, batch)"""
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
				_batch_fields(
					"Stock Entry Detail",
					{"item_code": l[0], "qty": l[2], "t_warehouse": l[1], "basic_rate": 10, "conversion_factor": 1, "uom": "Nos", "cost_center": cc(company)},
					l[3] if len(l) > 3 else None,
				)
				for l in lines
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


def _price_fields(row, discount):
	"""discount None: just a rate. A number: the rate is the price list rate
	and the line is sold that many percent under it (0: at full price)."""
	if discount is not None:
		row["price_list_rate"] = row["rate"]
		row["discount_percentage"] = discount
		row["rate"] = row["rate"] * (100 - discount) / 100.0
	return row


def sales_invoice(company, customer, lines, day, time="12:00:00"):
	"""lines: [(item, warehouse, qty, rate)] or (item, warehouse, qty, rate,
	batch) or (item, warehouse, qty, rate, batch, discount %)"""
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
			"items": [
				_batch_fields(
					"Sales Invoice Item",
					_price_fields(
						{"item_code": l[0], "qty": l[2], "rate": l[3], "warehouse": l[1], "cost_center": cc(company)},
						l[5] if len(l) > 5 else None,
					),
					l[4] if len(l) > 4 else None,
				)
				for l in lines
			],
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


def purchase_order(company, supplier, lines, day, rate=10):
	"""lines: [(item, warehouse, qty)]"""
	po = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"company": company,
			"supplier": supplier,
			"transaction_date": day,
			"schedule_date": add_days(day, 7),
			"items": [
				{"item_code": i, "qty": q, "rate": rate, "warehouse": w, "schedule_date": add_days(day, 7), "cost_center": cc(company)}
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


PROMO_DAYS = (50, 43, 36, 29, 22)  # days ago PR1 to PR3 were on promotion


def every_day(first, last, step=1):
	"""Days d(first) down to d(last), every `step` days."""
	return list(range(first, last - 1, -step))


def build():
	"""The whole dataset. Returns a plain dict of names."""
	suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))
	frappe.set_user("Administrator")
	ensure_fiscal_years(d(440), today())
	company, abbr = make_company(suffix)
	wh = {k: make_warehouse(company, abbr, v) for k, v in WAREHOUSES.items()}
	customer = make_customer("RS Customer")
	s1 = make_supplier("RS Supplier One %s" % suffix)
	s2 = make_supplier("RS Supplier Two %s" % suffix)
	s3 = make_supplier("RS Supplier Three %s" % suffix)

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
	# seasons: their own item group, so the group fallback touches nothing else
	seasonal = "RS Seasonal %s" % suffix
	for n in ("S1", "S2", "S3"):
		it[n] = make_item(code(n), company, group=seasonal)
	for n in ("T1", "T2", "E1"):
		it[n] = make_item(code(n), company)
	# 0.3.0: patterns, new items, shelf life, batches, dead stock, gaps
	# 0.7.0 promotions: PR3 sits in a group under a parent group
	promo_parent = ensure_item_group("RS Promo %s" % suffix, is_group=1)
	promo_child = ensure_item_group("RS Promo Child %s" % suffix, parent=promo_parent)
	for n in ("PR1", "PR2"):
		it[n] = make_item(code(n), company)
	it["PR3"] = make_item(code("PR3"), company, group=promo_child)
	# 0.8.0 shelf capacity (ERPNext Putaway Rules, made at the end)
	for n in ("CP1", "CP3", "CP4"):
		it[n] = make_item(code(n), company)
	it["CP2"] = make_item(code("CP2"), company, purchase_uom="Box", factor=6)
	for n in ("I1", "LU1", "DS1", "DB1", "DP1", "AG1", "OLD1", "MS1"):
		it[n] = make_item(code(n), company)
	fresh, brand = "RS Fresh %s" % suffix, "RS Brand %s" % suffix
	for n in ("NB1", "NB2", "NB3", "N1"):
		it[n] = make_item(code(n), company, group=fresh, brand=brand)
	it["N2"] = make_item(code("N2"), company, group=fresh)
	it["SL1"] = make_item(code("SL1"), company, shelf_life=10)
	it["EX1"] = make_item(code("EX1"), company, batches=True)
	batch_a = make_batch(it["EX1"], "RSB-A-%s" % suffix, add_days(today(), 5))
	batch_b = make_batch(it["EX1"], "RSB-B-%s" % suffix, add_days(today(), 60))
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

	# --- seasons (0.2.0). S1: last year, 1 a day over the Gregorian window
	# weeks (364 days back) and 3 a day over the 3 weeks after them. S2: the
	# same on the Hijri year (354 days back). S3: no history, its group's.
	on(rec, 430, (it["S1"], wh["O1"], 400))
	sell("S1", "O1", every_day(420, 365), 1)
	sell("S1", "O1", every_day(364, 344), 3)
	sell("S1", "O1", every_day(56, 1, step=2), 2)  # swings, so safety stock counts
	on(rec, 430, (it["S2"], wh["O1"], 400))
	sell("S2", "O1", every_day(410, 355), 1)
	sell("S2", "O1", every_day(354, 334), 3)
	sell("S2", "O1", every_day(56, 1), 1)
	on(rec, 70, (it["S3"], wh["O1"], 200))
	sell("S3", "O1", every_day(56, 1), 1)

	# --- trend: T1 doubles in the recent half of the window, T2 halves
	on(rec, 70, (it["T1"], wh["O1"], 300))
	sell("T1", "O1", every_day(56, 29), 1)
	sell("T1", "O1", every_day(28, 1), 2)
	on(rec, 70, (it["T2"], wh["O1"], 300))
	sell("T2", "O1", every_day(56, 29), 2)
	sell("T2", "O1", every_day(28, 1), 1)

	# --- accuracy: E1 runs out from d(10) to d(6) and sells on either side
	on(rec, 60, (it["E1"], wh["O1"], 46))
	sell("E1", "O1", every_day(56, 11), 1)
	on(rec, 5, (it["E1"], wh["O1"], 20))
	sell("E1", "O1", every_day(5, 1), 1)

	# --- 0.3.0 patterns: I1 sells 2 every 4 days (intermittent), LU1 every
	# 3 days, 1 or 7 in turn (lumpy)
	on(rec, 70, (it["I1"], wh["O1"], 100))
	sell("I1", "O1", every_day(56, 1, step=4), 2)
	on(rec, 70, (it["LU1"], wh["O1"], 200))
	for k, n in enumerate(every_day(56, 1, step=3)):
		on(sales, n, (it["LU1"], wh["O1"], 1 if k % 2 == 0 else 7, 10))

	# --- new items: NB1 to NB3 sell 1, 2, 3 a day. N1 (same brand and group)
	# and N2 (same group, no brand) arrived 5 days ago
	for n, q in (("NB1", 1), ("NB2", 2), ("NB3", 3)):
		on(rec, 70, (it[n], wh["O1"], 300))
		sell(n, "O1", every_day(56, 1), q)
	for n in ("N1", "N2"):
		on(rec, 5, (it[n], wh["O1"], 30))
		sell(n, "O1", every_day(5, 1), 1)

	# --- shelf life 10 days
	on(rec, 70, (it["SL1"], wh["O1"], 100))
	sell("SL1", "O1", every_day(56, 1), 1)

	# --- batches: A (expires in 5 days) sells 1 a day, B (in 60 days) arrives later
	on(rec, 60, (it["EX1"], wh["O1"], 70, batch_a))
	for n in every_day(56, 1):
		on(sales, n, (it["EX1"], wh["O1"], 1, 10, batch_a))
	on(rec, 10, (it["EX1"], wh["O1"], 30, batch_b))

	# --- dead stock: DS1 bought from supplier three 30 days ago, never sold.
	# DB1 sold 3 times, on invoices with other items
	on(other, 32, ("po3", s3, it["DS1"], wh["O1"], 50, 30))
	on(rec, 70, (it["DB1"], wh["O1"], 100))
	sell("DB1", "O1", [50, 30, 10], 1)
	# DP1: dead too, and only ever bought with DB1: its strongest partner, never picked
	on(rec, 70, (it["DP1"], wh["O1"], 100))
	sell("DP1", "O1", [50, 30, 10], 1)
	# OLD1: in stock early in the window, empty since: not a new item
	on(rec, 56, (it["OLD1"], wh["O1"], 5))
	sell("OLD1", "O1", every_day(56, 52), 1)
	# MS1: the main warehouse sells too, and is still never an assortment gap
	on(rec, 70, (it["MS1"], wh["M"], 100))
	sell("MS1", "M", every_day(56, 1), 1)

	# --- promotions: 2 a day at full price, 6 a day on 5 days at 30% off
	for n in ("PR1", "PR2", "PR3"):
		on(rec, 70, (it[n], wh["O1"], 400))
		for k in every_day(56, 1):
			on_promo = k in PROMO_DAYS
			on(sales, k, (it[n], wh["O1"], 6 if on_promo else 2, 10, None, 30 if on_promo else 0))

	# --- shelf capacity: CP1, CP2, CP4 sell 1 a day and are left with 4.
	# CP3 is left with 6, exactly its capacity
	for n, got in (("CP1", 60), ("CP2", 60), ("CP3", 62), ("CP4", 60)):
		on(rec, 70, (it[n], wh["O1"], got))
		sell(n, "O1", every_day(56, 1), 1)

	# --- assortment gap: AG1 sells only in Outlet 2
	on(rec, 70, (it["AG1"], wh["O2"], 100))
	sell("AG1", "O2", every_day(56, 1), 1)

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
	receive_days = {e[5] for v in other.values() for e in v if e[0] in ("po", "po3")}
	for n in sorted(set(rec) | set(sales) | set(other) | set(pos_days) | receive_days, reverse=True):
		day = d(n)
		if n in rec:
			receipt(company, rec[n], day)
		for entry in other.get(n, []):
			if entry[0] == "po":
				_k, sup, item, w, qty, got = entry
				# bought at 12 while stock is valued at 10: the last purchase rate shows apart
				out.setdefault("pos_to_receive", []).append((purchase_order(company, sup, [(item, w, qty)], day, rate=12), got))
			elif entry[0] == "po3":
				_k, sup, item, w, qty, got = entry
				out.setdefault("pos_to_receive", []).append((purchase_order(company, sup, [(item, w, qty)], day), got))
			elif entry[0] == "transfer":
				_k, item, src, dst, qty = entry
				transfer(company, [(item, src, dst, qty)], day)
		for po_name, got in list(out.get("pos_to_receive", [])):
			if got == n:
				receive(po_name, day)
		if n in sales:
			lines = list(sales[n])
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

	# shelf capacity, set after the stock moved (ERPNext refuses a receipt
	# above a rule's capacity, as a shop adding rules later would find)
	putaway = {
		"CP1": putaway_rule(company, it["CP1"], wh["O1"], 15),
		"CP2": putaway_rule(company, it["CP2"], wh["O1"], 17),
		"CP3": putaway_rule(company, it["CP3"], wh["O1"], 6),
		"CP4": putaway_rule(company, it["CP4"], wh["O1"], 15, disable=1),
	}

	# planned promotions, made after the invoices so none of them prices one
	rules = {
		"PR2": pricing_rule(company, "RS PR2 week " + suffix, "Item Code", [it["PR2"]], add_days(today(), 3), add_days(today(), 7)),
		"PR3": pricing_rule(company, "RS PR3 group " + suffix, "Item Group", [promo_parent], add_days(today(), 1), add_days(today(), 2)),
		# none of these count for PR1 in O1
		"expired": pricing_rule(company, "RS PR1 old " + suffix, "Item Code", [it["PR1"]], add_days(today(), -20), add_days(today(), -10)),
		"standing": pricing_rule(company, "RS PR1 standing " + suffix, "Item Code", [it["PR1"]], add_days(today(), 1), None),
		"elsewhere": pricing_rule(company, "RS PR1 O2 " + suffix, "Item Code", [it["PR1"]], add_days(today(), 1), add_days(today(), 5), warehouse=wh["O2"]),
		"disabled": pricing_rule(company, "RS PR1 off " + suffix, "Item Code", [it["PR1"]], add_days(today(), 1), add_days(today(), 5), disable=1),
	}

	ds = {
		"version": DATASET_VERSION,
		"date": str(today()),
		"suffix": suffix,
		"company": company,
		"abbr": abbr,
		"warehouses": wh,
		"items": it,
		"customer": customer,
		"suppliers": {"S1": s1, "S2": s2, "S3": s3},
		"batches": {"A": batch_a, "B": batch_b},
		"pricing_rules": rules,
		"putaway_rules": putaway,
		"promo_parent": promo_parent,
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
	from lumen_shelf.tests.bootstrap import before_tests

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
