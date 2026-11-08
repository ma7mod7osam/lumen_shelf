"""Bundle ideas (0.13.0): pairs of items customers buy on the same invoice
that make a natural set, with a name and a price, ready to become an ERPNext
Product Bundle in one click.

The pairs come from our own figures (the "bought together" pairs of the
engine). Which of them make sense as a set (tea and sugar, not jeans and a
phone) is asked of Lumen's AI service (the hub, the same service as trending
products). It gets names only: the country and, per pair, the two item names
and their item groups. Never a quantity, a price, a customer or the shop's
name.

The price is ours, never the AI's: the two items' selling prices less the
discount in the settings, raised when needed so the profit margin stays at
least the minimum in the settings. Worked out again when the bundle is made.

Once a week (and on the button) the pairs are sent and the answers kept in
Shelf Bundle Suggestion: New (a set), Not a match (the AI says they do not
belong together), Created (made into a bundle) and Dismissed (the shop said
not interested, never suggested again). Off by default.
"""

import math

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from lumen_shelf.restock import access, compat, engine, trend_products as tp
from lumen_shelf.restock.settings import DOCTYPE, get_settings

KIND = "bundles"
SUGGESTION = "Shelf Bundle Suggestion"
STATUS_NEW = "New"
STATUS_REJECTED = "Not a match"
STATUS_CREATED = "Created"
STATUS_DISMISSED = "Dismissed"
LIFT_MIN = 1.5  # bought together at least 1.5 times as often as by chance
TOGETHER_MIN = 3  # invoices
MAX_PAIRS = 30
STUCK = (engine.STATUS_NO_SALES, engine.STATUS_SLOW, engine.STATUS_OVERSTOCK)
NOTE_NO_PRICE = "no_price"
NOTE_NO_ROOM = "no_room"
NOTE_RAISED = "raised"
NOTE_NO_COST = "no_cost"


def _pair(a, b):
	return tuple(sorted((a, b)))


# ---- which pairs are asked about

def sellable(codes):
	"""{item code: (item_name, item_group, stock_uom)} of enabled stock sales
	items that are not templates (a bundle's own item is not a stock item)."""
	if not codes:
		return {}
	rows = frappe.get_all(
		"Item",
		filters={"name": ("in", list(codes)), "disabled": 0, "is_stock_item": 1, "is_sales_item": 1, "has_variants": 0},
		fields=["name", "item_name", "item_group", "stock_uom"],
	)
	return {r.name: (r.item_name or r.name, r.item_group or "", r.stock_uom) for r in rows}


def bundled_pairs():
	"""Pairs already sold together in a Product Bundle."""
	by = {}
	for parent, code in frappe.db.sql("select parent, item_code from `tabProduct Bundle Item` where parenttype='Product Bundle'"):
		by.setdefault(parent, set()).add(code)
	out = set()
	for codes in by.values():
		codes = sorted(codes)
		for i, a in enumerate(codes):
			for b in codes[i + 1 :]:
				out.add((a, b))
	return out


def candidates(company, result=None):
	"""The pairs worth asking about, at most MAX_PAIRS: bought together on
	TOGETHER_MIN+ invoices and LIFT_MIN+ times as often as chance, both items
	sellable and in stock, not already a bundle, not made or dismissed here.
	Pairs with an item that does not sell (No sales, Slow, Overstock) first: a
	set helps it sell. Then the most invoices together."""
	result = result or engine.compute(company)
	strong = {}
	for t in result.get("together") or []:
		if t["together"] < TOGETHER_MIN or t["lift"] < LIFT_MIN:
			continue
		key = _pair(t["item"], t["partner"])
		strong.setdefault(key, t["together"])
	if not strong:
		return []
	shelf, stuck = {}, set()
	for p in result["pairs"]:
		shelf[p["item_code"]] = shelf.get(p["item_code"], 0.0) + flt(p.get("on_shelf"))
		if p.get("status") in STUCK:
			stuck.add(p["item_code"])
	items = sellable({c for k in strong for c in k})
	done = bundled_pairs()
	for a, b in frappe.get_all(
		SUGGESTION,
		filters={"company": company, "status": ("in", (STATUS_CREATED, STATUS_DISMISSED))},
		fields=["item_a", "item_b"],
		as_list=True,
	):
		done.add(_pair(a, b))
	out = []
	for (a, b), together in strong.items():
		if a not in items or b not in items or (a, b) in done:
			continue
		if shelf.get(a, 0.0) <= 0 or shelf.get(b, 0.0) <= 0:
			continue
		out.append({"a": a, "b": b, "together": together, "stuck": a in stuck or b in stuck})
	out.sort(key=lambda r: (0 if r["stuck"] else 1, -r["together"], r["a"], r["b"]))
	return out[:MAX_PAIRS]


def payload(company, pairs):
	"""What leaves the site: names only."""
	country = frappe.db.get_value("Company", company, "country")
	if not country:
		raise tp.HubError(_("Set the country on company {0}: the trends are read for that country.").format(company))
	items = sellable({c for p in pairs for c in (p["a"], p["b"])})
	return {
		"contract": tp.CONTRACT,
		"kind": KIND,
		"country": country,
		"pairs": [
			{"a": {"name": items[p["a"]][0], "group": items[p["a"]][1]}, "b": {"name": items[p["b"]][0], "group": items[p["b"]][1]}}
			for p in pairs
		],
	}


# ---- keeping the answers

def store(company, pairs, answers, today=None):
	"""Replace the company's New and Not a match rows with the hub's answers.
	An answer counts only for a pair that was sent, matched by its place and
	its two names. Created and Dismissed rows stay."""
	names = sellable({c for p in pairs for c in (p["a"], p["b"])})
	frappe.db.delete(SUGGESTION, {"company": company, "status": ("in", (STATUS_NEW, STATUS_REJECTED))})
	kept, seen = 0, set()
	for r in answers or []:
		if not isinstance(r, dict):
			continue
		i = r.get("index")
		if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(pairs) or i in seen:
			continue
		p = pairs[i]
		if p["a"] not in names or p["b"] not in names or (r.get("a"), r.get("b")) != (names[p["a"]][0], names[p["b"]][0]):
			continue
		seen.add(i)
		fits = r.get("fits") is True and bool((r.get("name_en") or "").strip())
		frappe.get_doc(
			{
				"doctype": SUGGESTION,
				"company": company,
				"item_a": p["a"],
				"item_b": p["b"],
				"together": cint(p["together"]),
				"bundle_name": (r.get("name_en") or "").strip()[:140] if fits else "",
				"bundle_name_ar": (r.get("name_ar") or r.get("name_en") or "").strip()[:140] if fits else "",
				"reason": (r.get("reason_en") or "")[:500],
				"reason_ar": (r.get("reason_ar") or "")[:500],
				"status": STATUS_NEW if fits else STATUS_REJECTED,
				"found_on": getdate(today or nowdate()),
			}
		).insert(ignore_permissions=True)
		kept += 1 if fits else 0
	return kept


def ask(company, s=None, wait=True):
	"""(pairs sent, the hub's answers). No pair: nothing is sent."""
	pairs = candidates(company)
	if not pairs:
		return [], []
	res = tp.exchange(payload(company, pairs), wait=wait)
	return pairs, res.get("bundles") or []


def refresh(company, s=None, wait=True):
	"""One line for the settings page saying what happened."""
	s = s or get_settings()
	if not (s["enabled"] and s["bundle_ideas"]):
		return _("{0}: bundle ideas are switched off.").format(company)
	try:
		pairs, answers = ask(company, s, wait=wait)
	except tp.HubError as e:
		return "%s: %s" % (company, e)
	if not pairs:
		return _("{0}: no new pairs of items bought together to ask about.").format(company)
	kept = store(company, pairs, answers)
	line = _("{0}: {1} bundle ideas from {2} pairs.").format(company, kept, len(pairs))
	note = tp.credit_note()
	return line + " " + note if note else line


def run(companies):
	lines = []
	for c in companies:
		try:
			lines.append(refresh(c))
		except Exception:
			frappe.log_error(title="Lumen Shelf bundle ideas: %s" % c)
			lines.append(_("{0}: something went wrong, see the Error Log.").format(c))
	frappe.db.set_value(
		DOCTYPE, DOCTYPE, {"last_bundles_run": now_datetime(), "last_bundles_result": "\n".join(lines)[:1000]}, update_modified=False
	)
	if not frappe.flags.in_test:
		frappe.db.commit()
	return lines


def weekly():
	"""Scheduler, once a week: every company, in a background job."""
	s = get_settings()
	if not (s["enabled"] and s["bundle_ideas"] and tp.configured()):
		return
	companies = frappe.get_all("Company", pluck="name", order_by="name")
	frappe.enqueue("lumen_shelf.restock.bundles.run", queue="long", timeout=3600, companies=companies)


def bundles_sell():
	"""ERPNext 13's point of sale fails while any enabled Product Bundle
	exists (its item list and its stock check read a field v13 does not
	have), so no bundle is made there. LumenPOS read the code, 2026-11-05."""
	return compat.erpnext_major() >= 14


def _check_manager():
	if not access.has_settings_role():
		frappe.throw(_("Only a Shelf Manager may do this with bundle ideas."), frappe.PermissionError)


@frappe.whitelist()
def refresh_now(company=None):
	"""Ask for new ideas: Shelf Manager or System Manager, the switches on,
	the service set up. Runs in the background."""
	access.check_view("bundle_ideas")
	_check_manager()
	if company:
		access.check_company(company)
		companies = [company]
	else:
		allowed = compat.allowed_docs("Company")
		companies = [c for c in frappe.get_all("Company", pluck="name", order_by="name") if allowed is None or c in allowed]
	if not tp.configured():
		frappe.throw(_("Fill in the trends service URL, API Key and API Secret in Lumen Shelf Settings."))
	frappe.enqueue("lumen_shelf.restock.bundles.run", queue="long", timeout=3600, companies=companies)
	return _("Asked Lumen's AI service. The bundle ideas appear here in a few minutes.")


# ---- the price

def price_list():
	return frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"


def selling_price(item, uom, pl, today=None):
	"""The item's price in the price list: not a customer's own price, valid
	today, in its stock unit (or no unit given). The latest valid_from wins."""
	row = frappe.db.sql(
		"""select price_list_rate from `tabItem Price`
		where price_list=%(pl)s and item_code=%(item)s and ifnull(customer, '')=''
			and (ifnull(uom, '')='' or uom=%(uom)s)
			and (valid_from is null or valid_from <= %(today)s)
			and (valid_upto is null or valid_upto >= %(today)s)
		order by valid_from desc, modified desc limit 1""",
		{"pl": pl, "item": item, "uom": uom, "today": getdate(today or nowdate())},
	)
	return flt(row[0][0]) if row else 0.0


def unit_cost(company, item):
	"""What one costs the shop: the last purchase rate, else the valuation
	rate in the company's warehouses."""
	rate = flt(frappe.db.get_value("Item", item, "last_purchase_rate"))
	if rate > 0:
		return rate
	row = frappe.db.sql(
		"""select max(b.valuation_rate) from `tabBin` b join `tabWarehouse` w on w.name = b.warehouse
		where b.item_code=%s and w.company=%s""",
		(item, company),
	)
	return flt(row[0][0]) if row else 0.0


def price(company, a, b, s=None, today=None):
	"""The bundle's price. The two prices less the discount, raised when the
	margin would fall under the minimum: price >= cost / (1 - minimum). When
	even the full price is under that, the full price and a note. A price list
	in another currency than the company's: the cost cannot be compared."""
	s = s or get_settings()
	pl = price_list()
	pl_currency = frappe.db.get_value("Price List", pl, "currency")
	company_currency = frappe.get_cached_value("Company", company, "default_currency")
	uoms = dict(frappe.get_all("Item", filters={"name": ("in", [a, b])}, fields=["name", "stock_uom"], as_list=True))
	pa, pb = selling_price(a, uoms.get(a), pl, today), selling_price(b, uoms.get(b), pl, today)
	out = {
		"price_list": pl,
		"currency": pl_currency or company_currency,
		"price_a": pa,
		"price_b": pb,
		"full_price": flt(pa + pb, 2),
		"bundle_price": None,
		"saving": None,
		"discount": None,
		"cost": None,
		"margin": None,
		"note": "",
	}
	if pa <= 0 or pb <= 0:
		out["note"] = NOTE_NO_PRICE
		return out
	full = pa + pb
	bundle = flt(full * (1 - s["bundle_discount"] / 100.0), 2)
	cost = None
	if not pl_currency or pl_currency == company_currency:
		ca, cb = unit_cost(company, a), unit_cost(company, b)
		cost = ca + cb if ca > 0 and cb > 0 else None
	if cost is None:
		out["note"] = NOTE_NO_COST
	else:
		floor = cost / (1 - s["bundle_min_margin"] / 100.0)
		if bundle < floor - 1e-9:
			if floor >= full:
				bundle, out["note"] = full, NOTE_NO_ROOM
			else:
				bundle, out["note"] = math.ceil(floor * 100 - 1e-6) / 100.0, NOTE_RAISED
		out["cost"] = flt(cost, 2)
		out["margin"] = flt((bundle - cost) / bundle * 100, 1)
	out["bundle_price"] = flt(bundle, 2)
	out["saving"] = flt(full - bundle, 2)
	out["discount"] = flt((full - bundle) / full * 100, 1)
	return out


def note_text(note, s=None):
	s = s or get_settings()
	if note == NOTE_NO_PRICE:
		return _("One of the two has no selling price in the price list. Set it first.")
	if note == NOTE_NO_ROOM:
		return _("The cost leaves no room for a discount. Sold at the full price.")
	if note == NOTE_RAISED:
		return _("The discount was made smaller to keep a profit of at least {0}%.").format(s["bundle_min_margin"])
	if note == NOTE_NO_COST:
		return _("The cost of one of the two is not known, so the profit is not checked.")
	return ""


# ---- the screen

def rows(company, status=None, lang=None):
	access.check_view("bundle_ideas")
	access.check_company(company)
	s = get_settings()
	filters = {"company": company}
	if status:
		filters["status"] = status
	arabic = (lang or frappe.local.lang or "en").startswith("ar")
	docs = frappe.get_all(
		SUGGESTION,
		filters=filters,
		fields=["name", "item_a", "item_b", "together", "bundle_name", "bundle_name_ar", "reason", "reason_ar", "status", "bundle_item", "found_on"],
		order_by="together desc, item_a asc, item_b asc",
	)
	names = dict(
		frappe.get_all("Item", filters={"name": ("in", list({d.item_a for d in docs} | {d.item_b for d in docs}) or [""])}, fields=["name", "item_name"], as_list=True)
	)
	order = {STATUS_NEW: 0, STATUS_CREATED: 1, STATUS_REJECTED: 2}
	out = []
	for d in docs:
		if d.status == STATUS_DISMISSED:
			continue
		row = {
			"name": d.name,
			"bundle_name": (d.bundle_name_ar or d.bundle_name) if arabic else d.bundle_name,
			"item_code": d.item_a,
			"item_name": names.get(d.item_a) or d.item_a,
			"partner": d.item_b,
			"partner_name": names.get(d.item_b) or d.item_b,
			"together": d.together,
			"reason": (d.reason_ar or d.reason) if arabic else d.reason,
			"status": _(d.status),
			"status_key": d.status,
			"bundle_item": d.bundle_item,
			"found_on": d.found_on,
		}
		if d.status == STATUS_NEW:
			p = price(company, d.item_a, d.item_b, s)
			row.update({k: p[k] for k in ("currency", "price_a", "price_b", "full_price", "bundle_price", "saving", "discount", "margin")})
			row["note"] = note_text(p["note"], s)
			row["can_create"] = 1 if p["bundle_price"] and bundles_sell() else 0
			if not bundles_sell():
				row["note"] = _("ERPNext 13's point of sale stops working while a Product Bundle exists, so bundles are not made here. You can sell the two together at a discount with a Pricing Rule.")
		out.append(row)
	out.sort(key=lambda r: order.get(r["status_key"], 3))
	return out


# ---- the buttons

def _open(name):
	doc = frappe.get_doc(SUGGESTION, name)
	access.check_view("bundle_ideas")
	access.check_company(doc.company)
	return doc


@frappe.whitelist(methods=["POST"])
def dismiss(name):
	"""Not interested: never suggested again. ERPNext's write permission on
	the suggestion applies (doc.save)."""
	doc = _open(name)
	_check_manager()
	doc.status = STATUS_DISMISSED
	doc.save()
	return {"name": doc.name, "status": doc.status}


def _code(name):
	"""A free item code from the bundle's name."""
	base = " ".join((name or "").split())[:120] or _("Bundle item")
	code, n = base, 2
	while frappe.db.exists("Item", code):
		code, n = "%s %d" % (base, n), n + 1
	return code


@frappe.whitelist(methods=["POST"])
def create(name):
	"""Make the idea a bundle the ERPNext way: an Item that is not a stock
	item, a Product Bundle of the two items (one each) and its selling price
	in the price list. ERPNext's own permission checks on each, no
	ignore_permissions. All three or none."""
	doc = _open(name)
	_check_manager()
	for doctype in ("Item", "Product Bundle", "Item Price"):
		if not frappe.has_permission(doctype, "create"):
			frappe.throw(_("You are not permitted to create a {0} in ERPNext.").format(_(doctype)), frappe.PermissionError)
	if not bundles_sell():
		frappe.throw(_("ERPNext 13's point of sale stops working while a Product Bundle exists, so bundles are not made here. You can sell the two together at a discount with a Pricing Rule."))
	if doc.status != STATUS_NEW:
		frappe.throw(_("This bundle idea is no longer open."))
	items = sellable([doc.item_a, doc.item_b])
	if doc.item_a not in items or doc.item_b not in items:
		frappe.throw(_("One of the two items is disabled or no longer a stock item."))
	if _pair(doc.item_a, doc.item_b) in bundled_pairs():
		frappe.throw(_("These two are already sold together in a Product Bundle."))
	p = price(doc.company, doc.item_a, doc.item_b)
	if not p["bundle_price"]:
		frappe.throw(note_text(p["note"]))
	arabic = (frappe.local.lang or "en").startswith("ar")
	title = ((doc.bundle_name_ar or doc.bundle_name) if arabic else doc.bundle_name) or doc.bundle_name
	a_name, b_name = items[doc.item_a][0], items[doc.item_b][0]
	uom = "Nos" if frappe.db.exists("UOM", "Nos") else items[doc.item_a][2]
	frappe.db.savepoint("lumen_shelf_bundle")
	try:
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": _code(title),
				"item_name": title[:140],
				"item_group": items[doc.item_a][1],
				"stock_uom": uom,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"is_purchase_item": 0,
				"include_item_in_manufacturing": 0,
				"description": "%s + %s" % (a_name, b_name),
			}
		).insert()
		frappe.get_doc(
			{
				"doctype": "Product Bundle",
				"new_item_code": item.name,
				"description": "%s + %s" % (a_name, b_name),
				"items": [
					{"item_code": doc.item_a, "qty": 1, "uom": items[doc.item_a][2], "description": a_name},
					{"item_code": doc.item_b, "qty": 1, "uom": items[doc.item_b][2], "description": b_name},
				],
			}
		).insert()
		frappe.get_doc(
			{"doctype": "Item Price", "price_list": p["price_list"], "item_code": item.name, "uom": uom, "price_list_rate": p["bundle_price"]}
		).insert()
		doc.status = STATUS_CREATED
		doc.bundle_item = item.name
		doc.save()
	except Exception:
		frappe.db.rollback(save_point="lumen_shelf_bundle")
		raise
	return {"item": item.name, "item_name": item.item_name, "price": p["bundle_price"], "currency": p["currency"]}
