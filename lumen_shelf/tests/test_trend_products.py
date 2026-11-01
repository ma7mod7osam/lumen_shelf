"""0.9.0 trending products, the shop's side. Lumen's trends service is replaced
by a fake (nothing leaves the test site, nothing is paid). What is sent is
checked against the invoices themselves (oracle.invoices). Every test works
inside a savepoint and rolls back. One test per rule, for dev/mutations.py."""

import json
import unittest
from unittest import mock

import frappe
from frappe.utils import flt

from lumen_shelf.restock import trend_products as tp
from lumen_shelf.tests import fixtures, oracle
from lumen_shelf.tests.test_access import make_user
from lumen_shelf.tests.test_restock import set_settings

SP = "rs_trends"
REAL_PAYLOAD = tp.payload  # the tests patch tp.payload to fix the day


def hub_on(company=None, main=None, **values):
	values.setdefault("trend_products", 1)
	values.setdefault("trends_url", "https://hub.example.com/")
	values.setdefault("trends_api_key", "key1")
	values.setdefault("trends_api_secret", "secret1")
	set_settings(company, main, **values)


class FakeHub:
	"""Lumen's trends service: a ticket at once, then Queued, then the answer."""

	def __init__(self, suggestions=None, fail=None, queued=1, refuse=None, credit=None):
		self.sent = []
		self.calls = []
		self.suggestions = suggestions or []
		self.fail = fail
		self.queued = queued
		self.refuse = refuse
		self.credit = credit or {"allowance": 3, "free_left": 2, "balance": 4, "available": 6, "topup_url": "https://wa.me/1"}

	def __call__(self, method, data=None, params=None):
		self.calls.append(method)
		if method == "lumen_trends.api.balance":
			return dict(self.credit)
		out = self.answer(method, data)
		if isinstance(out, dict):
			out["credit"] = dict(self.credit)
			if method == "lumen_trends.api.suggest":  # before the work: one more
				out["credit"]["balance"] += 1
				out["credit"]["available"] += 1
		return out

	def answer(self, method, data):
		if method == "lumen_trends.api.balance":
			return {}
		if method == "lumen_trends.api.suggest":
			self.sent.append(json.loads(json.dumps(data)))
			if self.refuse:
				return {"status": "Failed", "code": self.refuse, "error": "hub words"}
			return {"ticket": "T1", "status": "Queued"}
		if self.queued:
			self.queued -= 1
			return {"ticket": "T1", "status": "Running"}
		if self.fail:
			return {"ticket": "T1", "status": "Failed", "code": self.fail, "error": "hub words"}
		return {"ticket": "T1", "status": "Done", "suggestions": self.suggestions}


def suggestion(group, en, ar, region="local", **kw):
	row = {"group": group, "product_en": en, "product_ar": ar, "region": region, "search_term": en.lower(), "growth": 250, "reason_en": "Why " + en, "reason_ar": "لماذا " + ar}
	row.update(kw)
	return row


class TestTrendProducts(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")
		cls.ds = fixtures.dataset()
		cls.company = cls.ds.company
		cls.wh = cls.ds.warehouses
		cls.it = cls.ds["items"]
		cls.start, cls.end = oracle.window(fixtures.today(), 8)
		sold = oracle.invoices(cls.company, cls.start, cls.end)
		value = {}
		for (item, _wh), days in sold.items():
			g = frappe.db.get_value("Item", item, "item_group")
			value[g] = value.get(g, 0.0) + sum(c[1] for c in days.values())
		cls.group_value = {g: v for g, v in value.items() if v > 0}
		cls.group = max(cls.group_value, key=lambda g: (cls.group_value[g], g))
		cls.sold_items = {item for (item, _wh) in sold}

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(SP)
		hub_on(self.company, self.wh["M"])
		self.s = tp.get_settings()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=SP)

	def payload(self, company=None, s=None):
		return REAL_PAYLOAD(company or self.company, s or self.s, today=fixtures.today())

	def refresh(self, hub, wait=True):
		with mock.patch.object(tp, "call_hub", side_effect=hub), mock.patch.object(tp, "POLL_EVERY", 0), mock.patch.object(
			tp, "POLL_FOR", 3
		), mock.patch.object(tp, "payload", side_effect=self.payload):
			return tp.refresh(self.company, wait=wait)

	def new_rows(self):
		return frappe.get_all(tp.SUGGESTION, filters={"company": self.company, "status": tp.STATUS_NEW}, fields=["*"])

	# ---- what is sent

	def test_only_names_are_sent(self):
		p = self.payload()
		self.assertEqual(set(p), {"contract", "country", "groups"})
		self.assertEqual(p["contract"], tp.CONTRACT)
		self.assertEqual(p["country"], frappe.db.get_value("Company", self.company, "country"))
		for g in p["groups"]:
			self.assertEqual(set(g), {"name", "items"})
			self.assertIsInstance(g["name"], str)
			for i in g["items"]:
				self.assertIsInstance(i, str)

	def test_groups_are_the_selling_ones(self):
		p = self.payload()
		self.assertEqual({g["name"] for g in p["groups"]}, set(self.group_value))

	def test_group_sales_match_the_invoices(self):
		got = tp.group_sales(self.company, self.start, self.end)
		self.assertEqual(set(got), set(self.group_value) | {g for g, v in got.items() if abs(v) < 1e-9})
		for g, v in self.group_value.items():
			self.assertAlmostEqual(got[g], v, 4, g)

	def test_groups_capped_by_sales(self):
		ranked = sorted(self.group_value, key=lambda g: (-round(self.group_value[g], 6), g))
		self.assertGreater(len(ranked), 1)
		for k in range(1, len(ranked) + 1):
			got = tp.selling_groups(self.company, self.start, self.end, limit=k)
			self.assertEqual(got, sorted(ranked[:k]), k)

	def test_groups_in_name_order(self):
		names = [g["name"] for g in self.payload()["groups"]]
		self.assertEqual(names, sorted(names))

	def test_items_leave_out_disabled_and_non_sales(self):
		off = fixtures.make_item("RS TP OFF " + self.ds.suffix, self.company, group=self.group)
		frappe.db.set_value("Item", off, "disabled", 1)
		nosale = fixtures.make_item("RS TP NOSALE " + self.ds.suffix, self.company, group=self.group)
		frappe.db.set_value("Item", nosale, "is_sales_item", 0)
		on = fixtures.make_item("RS TP ON " + self.ds.suffix, self.company, group=self.group)
		with mock.patch.object(tp, "MAX_ITEMS", 100000):  # the test group holds every day's items
			items = tp.group_items(self.company, self.group, self.start, self.end)
		self.assertIn(on, items)
		self.assertNotIn(off, items)
		self.assertNotIn(nosale, items)

	def test_items_sold_first(self):
		unsold = fixtures.make_item("0 RS TP FIRST " + self.ds.suffix, self.company, group=self.group)
		with mock.patch.object(tp, "MAX_ITEMS", 1):
			items = tp.group_items(self.company, self.group, self.start, self.end)
		self.assertEqual(len(items), 1)
		self.assertNotEqual(items[0], unsold)  # first by name, but never sold
		sold_names = {frappe.db.get_value("Item", i, "item_name") for i in self.sold_items}
		self.assertIn(items[0], sold_names)

	def test_no_country_stops(self):
		frappe.db.set_value("Company", self.company, "country", "")
		self.assertRaises(tp.HubError, self.payload)

	# ---- keeping the answer

	def test_store_rules(self):
		item_name = frappe.db.get_value("Item", self.it[sorted(self.it)[0]], "item_name")
		frappe.get_doc(
			{"doctype": tp.SUGGESTION, "company": self.company, "item_group": self.group, "product": "Old dismissed", "product_ar": "قديم", "region": tp.REGION_LOCAL, "status": tp.STATUS_DISMISSED}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{"doctype": tp.SUGGESTION, "company": self.company, "item_group": self.group, "product": "Old open", "product_ar": "قديم", "region": tp.REGION_LOCAL, "status": tp.STATUS_NEW}
		).insert(ignore_permissions=True)
		kept = tp.store(
			self.company,
			[
				suggestion(self.group, "Matcha powder", "بودرة ماتشا"),
				suggestion(self.group, "matcha  POWDER", "ماتشا"),  # the same again
				suggestion(self.group, item_name.upper(), "x"),  # an item the shop has
				suggestion(self.group, "Other", item_name),  # the same, by its Arabic
				suggestion(self.group, "old DISMISSED", "قديم"),  # dismissed before
				suggestion("No such group " + self.ds.suffix, "Ghost", "شبح"),
				suggestion(self.group, "Pistachio spread", "كريمة الفستق", region="global"),
				suggestion(self.group, "Bad region", "منطقة", region="moon"),
			],
			today=fixtures.today(),
		)
		self.assertEqual(kept, 2)
		rows = {r.product: r for r in self.new_rows()}
		self.assertEqual(set(rows), {"Matcha powder", "Pistachio spread"})
		self.assertEqual(rows["Pistachio spread"].region, tp.REGION_GLOBAL)
		self.assertEqual(rows["Matcha powder"].product_ar, "بودرة ماتشا")
		self.assertTrue(frappe.db.exists(tp.SUGGESTION, {"company": self.company, "product": "Old dismissed", "status": tp.STATUS_DISMISSED}))

	# ---- the round trip

	def test_refresh_stores_the_answer(self):
		hub = FakeHub([suggestion(self.group, "Matcha powder", "بودرة ماتشا")], queued=2)
		line = self.refresh(hub)
		self.assertIn("1", line)
		self.assertEqual([r.product for r in self.new_rows()], ["Matcha powder"])
		self.assertEqual(hub.sent, [{"request": self.payload()}])
		self.assertEqual(hub.calls.count("lumen_trends.api.result"), 3)

	def test_failed_answer_keeps_the_old_ones(self):
		tp.store(self.company, [suggestion(self.group, "Matcha powder", "بودرة ماتشا")])
		line = self.refresh(FakeHub(fail="budget"))
		self.assertIn(tp.refused("budget"), line)
		self.assertNotIn("hub words", line)
		self.assertEqual([r.product for r in self.new_rows()], ["Matcha powder"])

	def test_refused_at_once(self):
		hub = FakeHub([suggestion(self.group, "Matcha powder", "بودرة ماتشا")], refuse="shop_limit")
		line = self.refresh(hub)
		self.assertIn(tp.refused("shop_limit"), line)
		self.assertNotIn("lumen_trends.api.result", hub.calls)
		self.assertEqual(self.new_rows(), [])

	def test_refusal_words(self):
		self.assertNotEqual(tp.refused("budget"), tp.refused("shop_limit"))
		self.assertEqual(tp.refused("failed"), tp.refused("anything else"))
		self.assertNotEqual(tp.refused("failed"), tp.refused("budget"))
		self.assertNotEqual(tp.refused("failed"), tp.refused("shop_limit"))

	# ---- credit

	def test_credit_is_kept(self):
		self.refresh(FakeHub([suggestion(self.group, "Matcha powder", "بودرة ماتشا")], credit={"allowance": 3, "free_left": 1.5, "balance": 7.25, "available": 8.75, "topup_url": "https://wa.me/9"}))
		got = frappe.db.get_value(tp.DOCTYPE, None, ["trends_credit", "trends_free_left", "trends_available", "trends_topup_url"], as_dict=True)
		self.assertEqual((flt(got.trends_credit), flt(got.trends_free_left), flt(got.trends_available), got.trends_topup_url), (7.25, 1.5, 8.75, "https://wa.me/9"))

	def test_credit_kept_when_refused(self):
		self.refresh(FakeHub(refuse="shop_limit", credit={"allowance": 3, "free_left": 0, "balance": 0, "available": 0, "topup_url": ""}))
		self.assertEqual(flt(frappe.db.get_single_value(tp.DOCTYPE, "trends_available")), 1)  # as the refusal said

	def test_low_credit_is_said(self):
		low = {"allowance": 3, "free_left": 0.2, "balance": 0.3, "available": 0.5, "topup_url": ""}
		line = self.refresh(FakeHub([suggestion(self.group, "Matcha powder", "بودرة ماتشا")], credit=low))
		self.assertIn(tp.credit_note(), line)
		self.assertTrue(tp.credit_note())
		line = self.refresh(FakeHub([suggestion(self.group, "Matcha powder", "بودرة ماتشا")]))
		self.assertEqual(tp.credit_note(), "")
		self.assertNotIn("Top up", line)

	def test_report_shows_the_credit(self):
		from lumen_shelf.lumen_shelf.report.shelf_trending_products import shelf_trending_products as rep

		low = {"allowance": 3, "free_left": 0, "balance": 0.4, "available": 0.4, "topup_url": ""}
		self.refresh(FakeHub([suggestion(self.group, "Matcha powder", "بودرة ماتشا")], credit=low))
		_cols, rows, message, _chart, summary = rep.execute({"company": self.company})
		self.assertEqual([r["product"] for r in rows], ["Matcha powder"])
		card = next(c for c in summary if c["label"] == frappe._("Available to spend (USD)"))
		self.assertEqual(flt(card["value"]), 0.4)
		self.assertIn(tp.credit_note(), message)

	def test_check_credit_is_for_managers(self):
		viewer = make_user("rs-tp-user-%s@example.com" % self.ds.suffix, ["Shelf User", "Stock User"])
		manager = make_user("rs-tp-mgr-%s@example.com" % self.ds.suffix, ["Shelf Manager", "Stock User"])
		hub = FakeHub(credit={"allowance": 3, "free_left": 3, "balance": 2, "available": 5, "topup_url": ""})
		with mock.patch.object(tp, "call_hub", side_effect=hub):
			frappe.set_user(viewer)
			self.assertRaises(frappe.PermissionError, tp.check_credit)
			frappe.set_user(manager)
			tp.check_credit()
		self.assertEqual(hub.calls, ["lumen_trends.api.balance"])
		self.assertEqual(flt(frappe.db.get_single_value(tp.DOCTYPE, "trends_credit")), 2)

	def test_not_waiting_forever(self):
		line = self.refresh(FakeHub(queued=5), wait=False)
		self.assertIn(frappe._("Lumen's trends service took too long. It will be asked again next week."), line)

	def test_switch_off(self):
		hub_on(self.company, self.wh["M"], trend_products=0)
		hub = FakeHub([suggestion(self.group, "Matcha powder", "بودرة ماتشا")])
		line = self.refresh(hub)
		self.assertEqual(hub.calls, [])
		self.assertIn("off", line)
		with mock.patch.object(frappe, "enqueue") as enq:
			tp.weekly()
		enq.assert_not_called()

	def test_weekly_needs_the_hub_set_up(self):
		with mock.patch.object(frappe, "enqueue") as enq:
			tp.weekly()
		self.assertEqual(enq.call_count, 1)
		self.assertIn(self.company, enq.call_args[1]["companies"])
		hub_on(self.company, self.wh["M"], trends_api_key="")
		with mock.patch.object(frappe, "enqueue") as enq:
			tp.weekly()
		enq.assert_not_called()

	def test_run_records_the_result(self):
		hub = FakeHub([suggestion(self.group, "Matcha powder", "بودرة ماتشا")], queued=0)
		with mock.patch.object(tp, "call_hub", side_effect=hub), mock.patch.object(tp, "payload", side_effect=self.payload):
			tp.run([self.company])
		text = frappe.db.get_single_value(tp.DOCTYPE, "last_trends_result")
		self.assertIn(self.company, text)
		self.assertTrue(frappe.db.get_single_value(tp.DOCTYPE, "last_trends_run"))

	# ---- who may

	def test_refresh_now_is_for_managers(self):
		viewer = make_user("rs-tp-user-%s@example.com" % self.ds.suffix, ["Shelf User", "Stock User"])
		manager = make_user("rs-tp-mgr-%s@example.com" % self.ds.suffix, ["Shelf Manager", "Stock User"])
		frappe.set_user(viewer)
		with mock.patch.object(frappe, "enqueue") as enq:
			self.assertRaises(frappe.PermissionError, tp.refresh_now, self.company)
		enq.assert_not_called()
		frappe.set_user(manager)
		with mock.patch.object(frappe, "enqueue") as enq:
			tp.refresh_now(self.company)
		self.assertEqual(enq.call_args[1]["companies"], [self.company])

	def test_refresh_now_checks_the_company(self):
		with mock.patch.object(frappe, "enqueue") as enq:
			self.assertRaises(frappe.ValidationError, tp.refresh_now, "No such company " + self.ds.suffix)
		enq.assert_not_called()

	def test_off_by_default_and_weekly(self):
		self.assertEqual(tp.get_settings.__globals__["DEFAULTS"]["trend_products"], 0)
		from lumen_shelf import hooks  # the file itself: Frappe caches hooks in Redis

		self.assertIn("lumen_shelf.restock.trend_products.weekly", hooks.scheduler_events.get("weekly", []))

	def test_refresh_now_needs_the_hub_set_up(self):
		hub_on(self.company, self.wh["M"], trends_url="")
		with mock.patch.object(frappe, "enqueue") as enq:
			self.assertRaises(frappe.ValidationError, tp.refresh_now, self.company)
		enq.assert_not_called()

	def test_screen_needs_a_viewer_role(self):
		nobody = make_user("rs-tp-nobody-%s@example.com" % self.ds.suffix, ["Stock User"])
		frappe.set_user(nobody)
		self.assertRaises(frappe.PermissionError, tp.rows, self.company)

	def test_screen_switch(self):
		hub_on(self.company, self.wh["M"], trend_products=0)
		self.assertRaises(frappe.ValidationError, tp.rows, self.company)

	def test_screen_language_and_dismissed(self):
		tp.store(self.company, [suggestion(self.group, "Matcha powder", "بودرة ماتشا"), suggestion(self.group, "Date syrup", "دبس التمر")])
		name = frappe.db.get_value(tp.SUGGESTION, {"company": self.company, "product": "Date syrup"})
		frappe.db.set_value(tp.SUGGESTION, name, "status", tp.STATUS_DISMISSED)
		en = tp.rows(self.company, lang="en")
		ar = tp.rows(self.company, lang="ar")
		self.assertEqual([r["product"] for r in en], ["Matcha powder"])
		self.assertEqual([r["product"] for r in ar], ["بودرة ماتشا"])
		self.assertEqual(ar[0]["reason"], "لماذا بودرة ماتشا")

	# ---- the hub's replies

	def test_call_hub_errors(self):
		class R:
			def __init__(self, code, js=None):
				self.status_code = code
				self.js = js

			def json(self):
				if self.js is None:
					raise ValueError
				return self.js

		with mock.patch.object(tp.requests, "post", return_value=R(403, {})):
			with self.assertRaises(tp.HubError) as e:
				tp.call_hub("x", data={})
			self.assertIn("API Key", str(e.exception))
		msg = json.dumps([json.dumps({"message": "The hub's monthly budget is used up."})])
		with mock.patch.object(tp.requests, "post", return_value=R(417, {"_server_messages": msg})):
			with self.assertRaises(tp.HubError) as e:
				tp.call_hub("x", data={})
			self.assertIn("budget", str(e.exception))
		with mock.patch.object(tp.requests, "get", side_effect=tp.requests.ConnectionError()):
			self.assertRaises(tp.HubError, tp.call_hub, "x", params={})
		with mock.patch.object(tp.requests, "post", return_value=R(200, {"message": {"ticket": "T"}})) as post:
			self.assertEqual(tp.call_hub("lumen_trends.api.suggest", data={"a": 1}), {"ticket": "T"})
		self.assertEqual(post.call_args[0][0], "https://hub.example.com/api/method/lumen_trends.api.suggest")
		self.assertEqual(post.call_args[1]["headers"]["Authorization"], "token key1:secret1")
