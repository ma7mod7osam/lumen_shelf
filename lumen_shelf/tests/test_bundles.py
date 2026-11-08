"""0.13.0 bundle ideas, the shop's side. Lumen's AI service is replaced by a
fake (nothing leaves the test site, nothing is paid). Every test works inside
a savepoint and rolls back. One test per rule, for dev/mutations.py."""

import copy
import json
import unittest
from unittest import mock

import frappe
from frappe.utils import add_days, flt

from lumen_shelf.restock import bundles as bd, compat, engine, home, trend_products as tp
from lumen_shelf.tests import fixtures
from lumen_shelf.tests.test_access import make_user
from lumen_shelf.tests.test_restock import set_settings

REAL_MAJOR = compat.erpnext_major()

SP = "rs_bundles"


def hub_on(company=None, main=None, **values):
	values.setdefault("bundle_ideas", 1)
	values.setdefault("trends_url", "https://hub.example.com/")
	values.setdefault("trends_api_key", "key1")
	values.setdefault("trends_api_secret", "secret1")
	set_settings(company, main, **values)


class FakeHub:
	"""Lumen's AI service: a ticket, then the answer for the pairs it was sent.
	Even places make a set, odd places do not."""

	def __init__(self, refuse=None, answers=None):
		self.sent = []
		self.calls = []
		self.refuse = refuse
		self.answers = answers

	def __call__(self, method, data=None, params=None):
		self.calls.append(method)
		credit = {"allowance": 3, "free_left": 2, "balance": 4, "available": 6, "topup_url": ""}
		if method == "lumen_trends.api.suggest":
			self.sent.append(json.loads(json.dumps(data)))
			if self.refuse:
				return {"status": "Failed", "code": self.refuse, "credit": credit}
			return {"ticket": "B1", "status": "Queued", "credit": credit}
		req = self.sent[-1]["request"]
		answers = self.answers
		if answers is None:
			answers = [
				{
					"index": i,
					"a": p["a"]["name"],
					"b": p["b"]["name"],
					"fits": i % 2 == 0,
					"name_en": "Set %d" % i if i % 2 == 0 else "",
					"name_ar": "مجموعة %d" % i if i % 2 == 0 else "",
					"reason_en": "Why %d" % i,
					"reason_ar": "لماذا %d" % i,
				}
				for i, p in enumerate(req["pairs"])
			]
		return {"ticket": "B1", "status": "Done", "kind": "bundles", "bundles": answers, "credit": credit}


def numbers_in(x):
	if isinstance(x, bool) or isinstance(x, (int, float)):
		return [x]
	if isinstance(x, dict):
		return [n for k, v in x.items() if k != "contract" for n in numbers_in(v)]
	if isinstance(x, list):
		return [n for v in x for n in numbers_in(v)]
	return []


class TestBundles(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")
		cls.ds = fixtures.dataset()
		cls.company = cls.ds.company
		cls.wh = cls.ds.warehouses
		cls.currency = frappe.get_cached_value("Company", cls.company, "default_currency")

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(SP)
		# the create paths run on every version: ERPNext 13 only refuses
		v = mock.patch.object(compat, "erpnext_major", return_value=max(REAL_MAJOR, 14))
		v.start()
		self.addCleanup(v.stop)
		hub_on(self.company, self.wh["M"])
		self.result = engine.compute(self.company)
		self.pairs = bd.candidates(self.company, self.result)
		self.assertGreaterEqual(len(self.pairs), 3, "the test data has strong pairs")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=SP)

	def refresh(self, hub):
		with mock.patch.object(tp, "call_hub", side_effect=hub), mock.patch.object(tp, "POLL_EVERY", 0):
			return bd.refresh(self.company)

	def strength(self):
		out = {}
		for t in self.result["together"]:
			out[bd._pair(t["item"], t["partner"])] = (t["together"], t["lift"])
		return out

	def suggestion(self, pair=None, status=bd.STATUS_NEW, name="Tea time set", name_ar="مجموعة وقت الشاي", together=None):
		p = pair or self.pairs[0]
		return frappe.get_doc(
			{
				"doctype": bd.SUGGESTION,
				"company": self.company,
				"item_a": p["a"],
				"item_b": p["b"],
				"together": together if together is not None else p.get("together", 3),
				"bundle_name": name,
				"bundle_name_ar": name_ar,
				"reason": "They go together",
				"reason_ar": "يناسب بعضهما",
				"status": status,
			}
		).insert(ignore_permissions=True)

	def price_list(self, prices, costs=None):
		"""A selling price list of the company's currency with these prices,
		made the one Selling Settings uses. costs: last purchase rates."""
		name = "RS Bundle PL " + self.ds.suffix
		if not frappe.db.exists("Price List", name):
			frappe.get_doc({"doctype": "Price List", "price_list_name": name, "currency": self.currency, "selling": 1, "enabled": 1}).insert(ignore_permissions=True)
		frappe.db.set_single_value("Selling Settings", "selling_price_list", name)
		for item, rate in prices.items():
			frappe.get_doc({"doctype": "Item Price", "price_list": name, "item_code": item, "price_list_rate": rate}).insert(ignore_permissions=True)
		for item, rate in (costs or {}).items():
			frappe.db.set_value("Item", item, "last_purchase_rate", rate)
		return name

	# ---- which pairs

	def test_candidates_are_strong_pairs(self):
		strength = self.strength()
		for p in self.pairs:
			together, lift = strength[(p["a"], p["b"])]
			self.assertGreaterEqual(together, bd.TOGETHER_MIN)
			self.assertGreaterEqual(lift, bd.LIFT_MIN)
			self.assertEqual(p["together"], together)
		weak = [k for k, (n, lift) in strength.items() if n >= bd.TOGETHER_MIN and lift < bd.LIFT_MIN]
		few = [k for k, (n, lift) in strength.items() if n < bd.TOGETHER_MIN and lift >= bd.LIFT_MIN]
		got = {(p["a"], p["b"]) for p in self.pairs}
		self.assertTrue(weak)
		self.assertFalse(got & set(weak))
		self.assertFalse(got & set(few))

	def test_candidates_few_invoices_left_out(self):
		r = copy.deepcopy(self.result)
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		for t in r["together"]:
			if bd._pair(t["item"], t["partner"]) == (a, b):
				t["together"] = bd.TOGETHER_MIN - 1
		self.assertNotIn((a, b), {(p["a"], p["b"]) for p in bd.candidates(self.company, r)})

	def test_pair_once_in_order(self):
		keys = [(p["a"], p["b"]) for p in self.pairs]
		self.assertEqual(len(keys), len(set(keys)))
		for a, b in keys:
			self.assertLess(a, b)

	def test_both_in_stock(self):
		r = copy.deepcopy(self.result)
		a = self.pairs[0]["a"]
		for p in r["pairs"]:
			if p["item_code"] == a:
				p["on_shelf"] = 0
		got = bd.candidates(self.company, r)
		self.assertFalse([p for p in got if a in (p["a"], p["b"])])
		r = copy.deepcopy(self.result)
		b = self.pairs[0]["b"]
		for p in r["pairs"]:
			if p["item_code"] == b:
				p["on_shelf"] = 0
		self.assertFalse([p for p in bd.candidates(self.company, r) if b in (p["a"], p["b"])])

	def test_only_sellable_stock_items(self):
		a = self.pairs[0]["a"]
		frappe.db.set_value("Item", a, "disabled", 1)
		self.assertFalse([p for p in bd.candidates(self.company, self.result) if a in (p["a"], p["b"])])
		frappe.db.set_value("Item", a, "disabled", 0)
		frappe.db.set_value("Item", a, "is_sales_item", 0)
		self.assertFalse([p for p in bd.candidates(self.company, self.result) if a in (p["a"], p["b"])])
		frappe.db.set_value("Item", a, "is_sales_item", 1)
		frappe.db.set_value("Item", a, "is_stock_item", 0)
		self.assertFalse([p for p in bd.candidates(self.company, self.result) if a in (p["a"], p["b"])])

	def test_existing_bundle_left_out(self):
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		parent = "RS Bundle " + self.ds.suffix
		frappe.get_doc({"doctype": "Item", "item_code": parent, "item_name": parent, "item_group": frappe.db.get_value("Item", a, "item_group"), "stock_uom": "Nos", "is_stock_item": 0}).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "Product Bundle", "new_item_code": parent, "items": [{"item_code": b, "qty": 1}, {"item_code": a, "qty": 2}]}).insert(ignore_permissions=True)
		self.assertIn((a, b), bd.bundled_pairs())
		self.assertNotIn((a, b), {(p["a"], p["b"]) for p in bd.candidates(self.company, self.result)})

	def test_made_and_dismissed_left_out(self):
		got = lambda: {(p["a"], p["b"]) for p in bd.candidates(self.company, self.result)}
		self.suggestion(self.pairs[0], status=bd.STATUS_CREATED)
		self.suggestion(self.pairs[1], status=bd.STATUS_DISMISSED)
		self.assertFalse(got() & {(self.pairs[0]["a"], self.pairs[0]["b"]), (self.pairs[1]["a"], self.pairs[1]["b"])})

	def test_not_selling_first_then_most_invoices(self):
		r = copy.deepcopy(self.result)
		# a pair with few invoices, sharing no item with the pair that has the most
		top = max(self.pairs, key=lambda p: (p["together"], p["a"], p["b"]))
		last = min((p for p in self.pairs if not {p["a"], p["b"]} & {top["a"], top["b"]}), key=lambda p: (p["together"], p["a"], p["b"]))
		self.assertLess(last["together"], top["together"])
		for p in r["pairs"]:
			p["status"] = engine.STATUS_OK if p["item_code"] != last["b"] else engine.STATUS_SLOW
		got = bd.candidates(self.company, r)
		first = got[0]
		self.assertIn(last["b"], (first["a"], first["b"]))
		self.assertTrue(first["stuck"])
		rest = [p for p in got if not p["stuck"]]
		self.assertEqual([p["together"] for p in rest], sorted((p["together"] for p in rest), reverse=True))

	def test_capped(self):
		with mock.patch.object(bd, "MAX_PAIRS", 1):
			self.assertEqual(len(bd.candidates(self.company, self.result)), 1)

	# ---- what is sent

	def test_only_names_are_sent(self):
		p = bd.payload(self.company, self.pairs)
		self.assertEqual(set(p), {"contract", "kind", "country", "pairs"})
		self.assertEqual((p["contract"], p["kind"]), (tp.CONTRACT, "bundles"))
		self.assertEqual(p["country"], frappe.db.get_value("Company", self.company, "country"))
		self.assertEqual(len(p["pairs"]), len(self.pairs))
		for sent, pair in zip(p["pairs"], self.pairs):
			self.assertEqual(set(sent), {"a", "b"})
			for side in ("a", "b"):
				self.assertEqual(set(sent[side]), {"name", "group"})
				item = frappe.db.get_value("Item", pair[side], ["item_name", "item_group"])
				self.assertEqual((sent[side]["name"], sent[side]["group"]), tuple(item))
		self.assertEqual(numbers_in(p), [])

	def test_no_country_stops(self):
		frappe.db.set_value("Company", self.company, "country", None)
		self.assertRaises(tp.HubError, bd.payload, self.company, self.pairs)

	# ---- keeping the answers

	def test_store_rules(self):
		names = {c: frappe.db.get_value("Item", c, "item_name") for p in self.pairs for c in (p["a"], p["b"])}
		pa, pb = self.pairs[0], self.pairs[1]
		old = self.suggestion(pa, status=bd.STATUS_NEW, name="Old idea")
		old_no = self.suggestion(self.pairs[2], status=bd.STATUS_REJECTED, name="")
		kept = self.suggestion(pb, status=bd.STATUS_CREATED, name="Made one")
		ans = lambda i, **kw: dict({"index": i, "a": names[self.pairs[i]["a"]], "b": names[self.pairs[i]["b"]], "fits": True, "name_en": "Set %d" % i, "name_ar": "مجموعة", "reason_en": "r", "reason_ar": "س"}, **kw)
		answers = [
			ans(0),
			ans(1, a="Someone else", name_en="Wrong"),  # names that were not sent there
			dict(ans(1), index=True, name_en="Bool"),  # True is not a place
			ans(1, fits=False, name_en="", name_ar=""),
			ans(0, name_en="Twice"),  # the same place again: the first stays
			dict(ans(0), index=99),
			"not an answer",
			ans(2, name_en="  "),  # a set needs a name
		]
		n = bd.store(self.company, self.pairs, answers)
		self.assertEqual(n, 1)
		rows = frappe.get_all(bd.SUGGESTION, filters={"company": self.company}, fields=["name", "item_a", "item_b", "status", "bundle_name"])
		self.assertFalse(frappe.db.exists(bd.SUGGESTION, old.name))
		self.assertFalse(frappe.db.exists(bd.SUGGESTION, old_no.name))
		self.assertTrue(frappe.db.exists(bd.SUGGESTION, kept.name))
		by = {(r.item_a, r.item_b, r.status): r for r in rows}
		self.assertEqual(by[(pa["a"], pa["b"], bd.STATUS_NEW)].bundle_name, "Set 0")
		self.assertIn((pb["a"], pb["b"], bd.STATUS_REJECTED), by)
		self.assertEqual(sum(1 for r in rows if r.status == bd.STATUS_NEW), 1)
		self.assertEqual(len(rows), 4)  # 0 New, 1 and 2 Not a match, the Created one
		self.assertIn((self.pairs[2]["a"], self.pairs[2]["b"], bd.STATUS_REJECTED), by)

	def test_refresh_stores_the_answer(self):
		hub = FakeHub()
		line = self.refresh(hub)
		self.assertEqual(hub.calls[0], "lumen_trends.api.suggest")
		self.assertEqual(hub.sent[0]["request"]["kind"], "bundles")
		new = frappe.get_all(bd.SUGGESTION, filters={"company": self.company, "status": bd.STATUS_NEW}, pluck="bundle_name")
		self.assertEqual(sorted(new), sorted("Set %d" % i for i in range(0, len(self.pairs), 2)))
		self.assertIn(str(len(new)), line)
		self.assertIn(str(len(self.pairs)), line)

	def test_refused(self):
		self.suggestion(self.pairs[0], name="Old idea")
		line = self.refresh(FakeHub(refuse="shop_limit"))
		self.assertIn(tp.refused("shop_limit"), line)
		self.assertTrue(frappe.db.exists(bd.SUGGESTION, {"company": self.company, "bundle_name": "Old idea"}))

	def test_no_pairs_no_call(self):
		hub = FakeHub()
		with mock.patch.object(bd, "candidates", return_value=[]):
			line = self.refresh(hub)
		self.assertEqual(hub.calls, [])
		self.assertIn(self.company, line)

	def test_switch_off(self):
		hub_on(self.company, self.wh["M"], bundle_ideas=0)
		hub = FakeHub()
		line = self.refresh(hub)
		self.assertEqual(hub.calls, [])
		self.assertIn("off", line)
		with mock.patch.object(frappe, "enqueue") as enq:
			bd.weekly()
		enq.assert_not_called()
		self.assertRaises(frappe.ValidationError, bd.rows, self.company)

	def test_weekly_needs_the_hub_set_up(self):
		with mock.patch.object(frappe, "enqueue") as enq:
			bd.weekly()
		self.assertEqual(enq.call_args[0][0], "lumen_shelf.restock.bundles.run")
		self.assertIn(self.company, enq.call_args[1]["companies"])
		hub_on(self.company, self.wh["M"], trends_api_key="")
		with mock.patch.object(frappe, "enqueue") as enq:
			bd.weekly()
		enq.assert_not_called()

	def test_off_by_default_and_weekly(self):
		from lumen_shelf import hooks
		from lumen_shelf.restock import settings as st

		self.assertEqual(st.DEFAULTS["bundle_ideas"], 0)
		self.assertEqual((st.DEFAULTS["bundle_discount"], st.DEFAULTS["bundle_min_margin"]), (10, 15))
		self.assertIn("lumen_shelf.restock.bundles.weekly", hooks.scheduler_events.get("weekly", []))

	def test_run_records_the_result(self):
		with mock.patch.object(tp, "call_hub", side_effect=FakeHub()), mock.patch.object(tp, "POLL_EVERY", 0):
			bd.run([self.company])
		self.assertIn(self.company, frappe.db.get_single_value(bd.DOCTYPE, "last_bundles_result"))
		self.assertTrue(frappe.db.get_single_value(bd.DOCTYPE, "last_bundles_run"))

	def test_limits(self):
		self.assertRaises(frappe.ValidationError, hub_on, self.company, self.wh["M"], bundle_discount=60)
		self.assertRaises(frappe.ValidationError, hub_on, self.company, self.wh["M"], bundle_min_margin=95)

	# ---- the price

	def test_price_rules(self):
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		self.price_list({a: 10, b: 20}, {a: 5, b: 5})
		p = bd.price(self.company, a, b)
		self.assertEqual((p["full_price"], p["bundle_price"], p["saving"], p["discount"], p["note"]), (30, 27, 3, 10, ""))
		self.assertEqual(p["margin"], flt((27 - 10) / 27 * 100, 1))
		self.assertEqual(p["currency"], self.currency)
		# the margin would fall under 15%: the price is raised to cost / 0.85
		frappe.db.set_value("Item", a, "last_purchase_rate", 12)
		frappe.db.set_value("Item", b, "last_purchase_rate", 12)
		p = bd.price(self.company, a, b)
		self.assertEqual((p["bundle_price"], p["note"]), (28.24, bd.NOTE_RAISED))
		self.assertGreaterEqual(p["margin"], 15)
		self.assertEqual(p["discount"], flt((30 - 28.24) / 30 * 100, 1))
		# no room at all: the full price
		frappe.db.set_value("Item", a, "last_purchase_rate", 15)
		frappe.db.set_value("Item", b, "last_purchase_rate", 15)
		p = bd.price(self.company, a, b)
		self.assertEqual((p["bundle_price"], p["discount"], p["note"]), (30, 0, bd.NOTE_NO_ROOM))

	def test_price_follows_the_settings(self):
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		self.price_list({a: 10, b: 20}, {a: 5, b: 5})
		hub_on(self.company, self.wh["M"], bundle_discount=20, bundle_min_margin=60)
		p = bd.price(self.company, a, b)
		self.assertEqual(p["bundle_price"], 25)  # 30 x 0.8 = 24 is under 10 / 0.4 = 25
		self.assertEqual(p["note"], bd.NOTE_RAISED)

	def test_price_without_a_price_or_a_cost(self):
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		self.price_list({a: 10})
		p = bd.price(self.company, a, b)
		self.assertEqual((p["bundle_price"], p["note"]), (None, bd.NOTE_NO_PRICE))
		frappe.get_doc({"doctype": "Item Price", "price_list": bd.price_list(), "item_code": b, "price_list_rate": 20}).insert(ignore_permissions=True)
		with mock.patch.object(bd, "unit_cost", return_value=0):
			p = bd.price(self.company, a, b)
		self.assertEqual((p["bundle_price"], p["margin"], p["note"]), (27, None, bd.NOTE_NO_COST))

	def test_price_list_in_another_currency(self):
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		name = self.price_list({a: 10, b: 20}, {a: 14, b: 14})
		other = "EUR" if self.currency != "EUR" else "USD"
		frappe.db.set_value("Price List", name, "currency", other)
		p = bd.price(self.company, a, b)
		self.assertEqual((p["bundle_price"], p["note"], p["currency"]), (27, bd.NOTE_NO_COST, other))

	def test_selling_price_rules(self):
		a = self.pairs[0]["a"]
		pl = self.price_list({})
		uom = frappe.db.get_value("Item", a, "stock_uom")
		today = fixtures.today()
		# uom given: ERPNext 13 and 14 leave it empty (= any unit), 15+ fill it
		add = lambda rate, **kw: frappe.get_doc(dict({"doctype": "Item Price", "price_list": pl, "item_code": a, "price_list_rate": rate, "uom": uom}, **kw)).insert(ignore_permissions=True)
		customer = frappe.get_all("Customer", pluck="name", limit=1)
		if customer:
			add(1, customer=customer[0])
		add(2, valid_from=add_days(today, -30), valid_upto=add_days(today, -1))
		add(3, valid_from=add_days(today, 1))
		self.assertEqual(bd.selling_price(a, uom, pl, today), 0)
		add(7, valid_from=add_days(today, -20))
		add(8, valid_from=add_days(today, -5))
		self.assertEqual(bd.selling_price(a, uom, pl, today), 8)
		self.assertEqual(bd.selling_price(a, "No such unit", pl, today), 0)

	def test_unit_cost(self):
		a = self.pairs[0]["a"]
		frappe.db.set_value("Item", a, "last_purchase_rate", 4.5)
		self.assertEqual(bd.unit_cost(self.company, a), 4.5)
		frappe.db.set_value("Item", a, "last_purchase_rate", 0)
		bins = frappe.db.sql("select max(b.valuation_rate) from tabBin b join tabWarehouse w on w.name=b.warehouse where b.item_code=%s and w.company=%s", (a, self.company))[0][0]
		self.assertEqual(bd.unit_cost(self.company, a), flt(bins))

	def test_note_words(self):
		s = bd.get_settings()
		self.assertIn("15", bd.note_text(bd.NOTE_RAISED, s))
		for n in (bd.NOTE_NO_PRICE, bd.NOTE_NO_ROOM, bd.NOTE_NO_COST):
			self.assertTrue(bd.note_text(n, s))
		self.assertEqual(bd.note_text("", s), "")

	# ---- the screen

	def test_rows(self):
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		self.price_list({a: 10, b: 20}, {a: 5, b: 5})
		self.suggestion(self.pairs[1], status=bd.STATUS_REJECTED, name="", together=99)
		self.suggestion(self.pairs[0], together=1)
		self.suggestion(self.pairs[2], status=bd.STATUS_DISMISSED, name="Gone")
		en = bd.rows(self.company, lang="en")
		self.assertEqual([r["status_key"] for r in en], [bd.STATUS_NEW, bd.STATUS_REJECTED])
		self.assertEqual((en[0]["bundle_name"], en[0]["bundle_price"], en[0]["full_price"]), ("Tea time set", 27, 30))
		self.assertEqual(en[0]["item_name"], frappe.db.get_value("Item", a, "item_name"))
		self.assertNotIn("bundle_price", en[1])
		ar = bd.rows(self.company, lang="ar")
		self.assertEqual((ar[0]["bundle_name"], ar[0]["reason"]), ("مجموعة وقت الشاي", "يناسب بعضهما"))
		self.assertEqual([r["status_key"] for r in bd.rows(self.company, status=bd.STATUS_REJECTED)], [bd.STATUS_REJECTED])

	def test_screen_needs_a_viewer_role(self):
		nobody = make_user("rs-bd-nobody-%s@example.com" % self.ds.suffix, ["Stock User"])
		frappe.set_user(nobody)
		self.assertRaises(frappe.PermissionError, bd.rows, self.company)

	def test_today_box(self):
		self.suggestion(self.pairs[0])
		self.suggestion(self.pairs[1], status=bd.STATUS_REJECTED, name="")
		keys = lambda: [b["key"] for b in home.overview(self.company)["ideas"]]
		self.assertIn("bundles", keys())
		box = next(b for b in home.overview(self.company)["ideas"] if b["key"] == "bundles")
		self.assertEqual((box["count"], box["items"][0]["text"], box["report"]), (1, "Tea time set", "Shelf Bundle Ideas"))
		hub_on(self.company, self.wh["M"], trends_url="")
		self.assertNotIn("bundles", keys())
		hub_on(self.company, self.wh["M"], bundle_ideas=0)
		self.assertNotIn("bundles", keys())

	def test_report_and_app_screen(self):
		from lumen_shelf.restock import app

		self.suggestion(self.pairs[0])
		got = app.screen("bundle_ideas", {"company": self.company})
		self.assertEqual([r["bundle_name"] for r in got["rows"]], ["Tea time set"])
		self.assertTrue(app.boot()["screens"]["bundle_ideas"])
		hub_on(self.company, self.wh["M"], bundle_ideas=0)
		self.assertFalse(app.boot()["screens"]["bundle_ideas"])

	# ---- the buttons

	def manager(self, extra=("Item Manager", "Sales User", "Sales Master Manager", "Stock User")):
		return make_user("rs-bd-mgr-%s@example.com" % self.ds.suffix, ["Shelf Manager"] + list(extra))

	def test_create_bundle(self):
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		self.price_list({a: 10, b: 20}, {a: 5, b: 5})
		doc = self.suggestion(name="Tea time set %s" % self.ds.suffix)
		frappe.set_user(self.manager())
		out = bd.create(doc.name)
		frappe.set_user("Administrator")
		item = frappe.get_doc("Item", out["item"])
		self.assertEqual((item.is_stock_item, item.is_sales_item, item.item_name), (0, 1, "Tea time set %s" % self.ds.suffix))
		self.assertEqual(item.item_group, frappe.db.get_value("Item", a, "item_group"))
		bundle = frappe.get_doc("Product Bundle", {"new_item_code": item.name})
		self.assertEqual(sorted((r.item_code, flt(r.qty)) for r in bundle.items), sorted([(a, 1.0), (b, 1.0)]))
		rate = frappe.db.get_value("Item Price", {"item_code": item.name, "price_list": bd.price_list()}, "price_list_rate")
		self.assertEqual((flt(rate), out["price"]), (27, 27))
		doc.reload()
		self.assertEqual((doc.status, doc.bundle_item), (bd.STATUS_CREATED, item.name))
		self.assertNotIn((a, b), {(p["a"], p["b"]) for p in bd.candidates(self.company, self.result)})
		self.assertRaises(frappe.ValidationError, bd.create, doc.name)  # not twice

	def test_bundles_not_made_on_erpnext_13(self):
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		self.price_list({a: 10, b: 20}, {a: 5, b: 5})
		doc = self.suggestion()
		row = [r for r in bd.rows(self.company) if r["name"] == doc.name][0]
		self.assertEqual((row["can_create"], row["bundle_price"]), (1, 27))
		self.assertTrue(bd.bundles_sell())
		with mock.patch.object(compat, "erpnext_major", return_value=13):
			self.assertFalse(bd.bundles_sell())
			row = [r for r in bd.rows(self.company) if r["name"] == doc.name][0]
			self.assertEqual(row["can_create"], 0)
			self.assertIn("ERPNext 13", row["note"])
			self.assertRaises(frappe.ValidationError, bd.create, doc.name)
		self.assertEqual(frappe.db.get_value("Shelf Bundle Suggestion", doc.name, "status"), bd.STATUS_NEW)

	def test_create_in_arabic_and_a_free_code(self):
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		self.price_list({a: 10, b: 20}, {a: 5, b: 5})
		title = "مجموعة %s" % self.ds.suffix
		frappe.get_doc({"doctype": "Item", "item_code": title, "item_name": title, "item_group": frappe.db.get_value("Item", a, "item_group"), "stock_uom": "Nos", "is_stock_item": 0}).insert(ignore_permissions=True)
		doc = self.suggestion(name_ar=title)
		with mock.patch.object(frappe.local, "lang", "ar"):
			out = bd.create(doc.name)
		self.assertEqual(out["item"], title + " 2")
		self.assertEqual(out["item_name"], title)

	def test_create_is_all_or_none(self):
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		self.price_list({a: 10, b: 20}, {a: 5, b: 5})
		title = "All or none %s" % self.ds.suffix
		doc = self.suggestion(name=title)
		real = bd.price

		def broken(*args, **kw):
			p = real(*args, **kw)
			p["price_list"] = "No such price list " + self.ds.suffix
			return p

		with mock.patch.object(bd, "price", side_effect=broken):
			self.assertRaises(frappe.ValidationError, bd.create, doc.name)
		self.assertFalse(frappe.db.exists("Item", title))
		self.assertFalse(frappe.db.exists("Product Bundle", title))
		self.assertEqual(frappe.db.get_value(bd.SUGGESTION, doc.name, "status"), bd.STATUS_NEW)

	def test_create_needs_a_price(self):
		a = self.pairs[0]["a"]
		self.price_list({a: 10})
		doc = self.suggestion()
		with self.assertRaises(frappe.ValidationError) as e:
			bd.create(doc.name)
		self.assertIn(bd.note_text(bd.NOTE_NO_PRICE), str(e.exception))
		self.assertEqual(frappe.db.get_value(bd.SUGGESTION, doc.name, "status"), bd.STATUS_NEW)

	def test_create_only_an_open_idea(self):
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		self.price_list({a: 10, b: 20}, {a: 5, b: 5})
		title = "Gone idea %s" % self.ds.suffix
		for status in (bd.STATUS_DISMISSED, bd.STATUS_REJECTED):
			doc = self.suggestion(status=status, name=title)
			self.assertRaises(frappe.ValidationError, bd.create, doc.name)
			self.assertFalse(frappe.db.exists("Item", title))

	def test_settings_warn_without_the_service(self):
		frappe.clear_messages()
		hub_on(self.company, self.wh["M"], trends_url="")
		said = " ".join(str(m) for m in frappe.message_log)
		self.assertIn("trends service URL", said)

	def test_create_refuses_a_disabled_item_or_a_bundle_that_exists(self):
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		self.price_list({a: 10, b: 20}, {a: 5, b: 5})
		doc = self.suggestion()
		frappe.db.set_value("Item", b, "disabled", 1)
		self.assertRaises(frappe.ValidationError, bd.create, doc.name)
		frappe.db.set_value("Item", b, "disabled", 0)
		with mock.patch.object(bd, "bundled_pairs", return_value={(a, b)}):
			self.assertRaises(frappe.ValidationError, bd.create, doc.name)

	def test_create_is_for_managers_with_erpnext_rights(self):
		a, b = self.pairs[0]["a"], self.pairs[0]["b"]
		self.price_list({a: 10, b: 20}, {a: 5, b: 5})
		doc = self.suggestion()
		viewer = make_user("rs-bd-user-%s@example.com" % self.ds.suffix, ["Shelf User", "Item Manager", "Sales User", "Sales Master Manager", "Stock User"])
		frappe.set_user(viewer)
		self.assertRaises(frappe.PermissionError, bd.create, doc.name)
		frappe.set_user(self.manager(extra=("Stock User",)))  # may not create Items in ERPNext
		with self.assertRaises(frappe.PermissionError) as e:
			bd.create(doc.name)
		self.assertIn("ERPNext", str(e.exception))  # said before anything is tried
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value(bd.SUGGESTION, doc.name, "status"), bd.STATUS_NEW)

	def test_create_checks_the_switch_and_company(self):
		doc = self.suggestion()
		hub_on(self.company, self.wh["M"], bundle_ideas=0)
		self.assertRaises(frappe.ValidationError, bd.create, doc.name)
		self.assertRaises(frappe.ValidationError, bd.dismiss, doc.name)

	def test_dismiss(self):
		doc = self.suggestion()
		viewer = make_user("rs-bd-user-%s@example.com" % self.ds.suffix, ["Shelf User", "Stock User"])
		frappe.set_user(viewer)
		self.assertRaises(frappe.PermissionError, bd.dismiss, doc.name)
		frappe.set_user(self.manager())
		bd.dismiss(doc.name)
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value(bd.SUGGESTION, doc.name, "status"), bd.STATUS_DISMISSED)
		self.assertEqual(bd.rows(self.company), [])

	def test_refresh_now_is_for_managers(self):
		viewer = make_user("rs-bd-user-%s@example.com" % self.ds.suffix, ["Shelf User", "Stock User"])
		frappe.set_user(viewer)
		with mock.patch.object(frappe, "enqueue") as enq:
			self.assertRaises(frappe.PermissionError, bd.refresh_now, self.company)
		enq.assert_not_called()
		frappe.set_user(self.manager())
		with mock.patch.object(frappe, "enqueue") as enq:
			bd.refresh_now(self.company)
		self.assertEqual(enq.call_args[1]["companies"], [self.company])
		frappe.set_user("Administrator")
		hub_on(self.company, self.wh["M"], trends_url="")
		with mock.patch.object(frappe, "enqueue") as enq:
			self.assertRaises(frappe.ValidationError, bd.refresh_now, self.company)
		enq.assert_not_called()
		hub_on(self.company, self.wh["M"])
		with mock.patch.object(frappe, "enqueue") as enq:
			self.assertRaises(frappe.ValidationError, bd.refresh_now, "No such company " + self.ds.suffix)
		enq.assert_not_called()
