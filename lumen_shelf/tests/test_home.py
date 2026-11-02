"""The one page (Lumen Shelf > Today): its numbers are the detail screens'
numbers, its buttons make the same requests, and it follows the same
switches and permissions. One test per rule, so a deliberate break of one
rule (dev/mutations.py) fails its own test.

Tests that save anything work inside a savepoint and roll back."""

import json

import frappe

from lumen_shelf.restock import engine, home, requests, views
from lumen_shelf.tests.test_access import limit, make_user
from lumen_shelf.tests.test_restock import RestockCase, set_settings

SP = "rs_home"


class TestHome(RestockCase):
	def setUp(self):
		frappe.set_user("Administrator")
		set_settings(self.company, self.wh["M"])

	def tearDown(self):
		frappe.set_user("Administrator")
		set_settings(self.company, self.wh["M"])

	def page(self, **kw):
		kw.setdefault("company", self.company)
		return home.overview(**kw)

	def full(self):
		return engine.compute(self.company)

	def card(self, d, key):
		return next((c for c in d["cards"] if c["key"] == key), None)

	def kinds(self, d):
		return [t["kind"] for t in d["tasks"]]

	# ---- the numbers are the screens' numbers

	def test_cards_match_the_screens(self):
		d, r = self.page(), self.full()
		low = views.running_low(r, None)
		moves = views.transfers(r, None)
		health = views.stock_health(r, None)
		self.assertTrue(low and moves)
		self.assertEqual(self.card(d, "low")["count"], len(low))
		self.assertEqual(self.card(d, "move")["count"], len(moves))
		stuck = [h for h in health if h["status_key"] in home.STUCK]
		self.assertTrue(stuck)
		self.assertEqual(self.card(d, "stuck")["count"], len(stuck))
		self.assertAlmostEqual(self.card(d, "stuck")["value"], sum(h["excess_value"] or 0 for h in stuck), 2)
		expiring = [h for h in health if h["expiry_risk_qty"]]
		self.assertEqual(self.card(d, "expiry")["count"], len(expiring))
		out = sum(1 for x in low if (x["on_shelf"] or 0) <= 0)
		self.assertEqual(self.card(d, "low")["note"], "{0} out of stock".format(out))

	def test_tasks_in_order(self):
		d = self.page()
		order = {home.KIND_LOW: 0, home.KIND_MOVE: 1, home.KIND_EXPIRY: 2, home.KIND_STUCK: 3}
		ranks = [order[k] for k in self.kinds(d)]
		self.assertEqual(ranks, sorted(ranks))
		low = [t for t in d["tasks"] if t["kind"] == home.KIND_LOW]
		rows = views.running_low(self.full(), None)
		self.assertEqual([(t["item_code"], t["warehouse"]) for t in low], [(x["item_code"], x["warehouse"]) for x in rows][: len(low)])
		moves = [t for t in d["tasks"] if t["kind"] == home.KIND_MOVE]
		faster = [x for x in views.transfers(self.full(), None) if x["reason_key"] == engine.REASON_FASTER]
		self.assertEqual(len(moves), len(faster))  # shortage transfers are inside the restock tasks

	def test_task_limit(self):
		d = self.page()
		with_all = len(d["tasks"]) + d["more_tasks"]
		old = home.TASK_LIMIT
		try:
			home.TASK_LIMIT = 3
			d = self.page()
		finally:
			home.TASK_LIMIT = old
		self.assertEqual(len(d["tasks"]), 3)
		self.assertEqual(d["more_tasks"], with_all - 3)

	def test_restock_words(self):
		rows = {(x["item_code"], x["warehouse"]): x for x in views.running_low(self.full(), None)}
		seen = set()
		for t in self.page()["tasks"]:
			if t["kind"] != home.KIND_LOW:
				continue
			x = rows[(t["item_code"], t["warehouse"])]
			src = x["source_key"]
			seen.add(src)
			if src == views.SOURCE_TRANSFER:
				self.assertEqual(t["todo"], "Transfer {0} from {1}".format(home._num(x["transfer_qty"]), x["transfer_from"]))
			elif src == views.SOURCE_WAIT:
				self.assertEqual(t["todo"], "Wait for main warehouse")
				self.assertNotIn("request", t)
			elif src == views.SOURCE_BUY:
				self.assertTrue(t["todo"].startswith("Buy "), t["todo"])
			if (x["on_shelf"] or 0) <= 0:
				self.assertEqual(t["when"], "Already out of stock")
			else:
				self.assertEqual(t["when"], "Runs out in {0} days".format(home._num(max(x["days_left"], 0))))
			self.assertEqual(t["tone"], "danger" if (x["days_left"] or 0) <= (x["lead_time"] or 0) else "warning")
		self.assertIn(views.SOURCE_BUY, seen)
		self.assertIn(views.SOURCE_TRANSFER, seen)

	def test_numbers_written_plainly(self):
		self.assertEqual(home._num(12.0), "12")
		self.assertEqual(home._num(2.5), "2.5")
		self.assertEqual(home._num(1.23456), "1.235")

	# ---- the buttons

	def test_task_button_requests_that_item_only(self):
		r = self.full()
		task = next(t for t in self.page()["tasks"] if t.get("request") and t["kind"] == home.KIND_LOW)
		f = dict(task["request"]["filters"], company=self.company)
		lines = requests.chosen_lines(r, None, task["request"]["scope"], f)
		self.assertTrue(lines)
		self.assertEqual({(l["item_code"], l["to_warehouse"]) for l in lines}, {(task["item_code"], task["warehouse"])})
		every = requests.chosen_lines(r, None, "running_low", {"company": self.company, "warehouse": task["warehouse"]})
		self.assertEqual(lines, [l for l in every if l["item_code"] == task["item_code"]])

	def test_move_button_requests_that_move(self):
		r = self.full()
		task = next(t for t in self.page()["tasks"] if t["kind"] == home.KIND_MOVE and t.get("request"))
		f = dict(task["request"]["filters"], company=self.company)
		lines = requests.chosen_lines(r, None, "transfers", f)
		self.assertTrue(lines)
		for l in lines:
			self.assertEqual((l["item_code"], l["to_warehouse"], l["reason"]), (task["item_code"], task["warehouse"], engine.REASON_FASTER))

	def test_button_round_trip(self):
		frappe.db.savepoint(SP)
		try:
			task = next(t for t in self.page()["tasks"] if t.get("request") and t["kind"] == home.KIND_LOW)
			filters = json.dumps(dict(task["request"]["filters"], company=self.company))
			made = requests.create("running_low", filters)
			self.assertTrue(made["count"])
			for name in made["names"]:
				codes = {i.item_code for i in frappe.get_doc("Material Request", name).items}
				self.assertEqual(codes, {task["item_code"]})
			# asked once: the same task asks for nothing more
			self.assertEqual(requests.preview("running_low", filters)["count"], 0)
		finally:
			frappe.db.rollback(save_point=SP)
			engine.forget(self.company)

	def test_buttons_only_for_who_may_request(self):
		viewer = make_user("rs-home-viewer-%s@example.com" % self.ds.suffix, ["Stock User", "Shelf User"])
		frappe.set_user(viewer)
		d = self.page()
		self.assertEqual(d["can_request"], 0)
		self.assertEqual(d["can_settings"], 0)
		self.assertFalse([t for t in d["tasks"] if t.get("request")])
		frappe.set_user("Administrator")
		d = self.page()
		self.assertEqual((d["can_request"], d["can_settings"]), (1, 1))
		self.assertTrue([t for t in d["tasks"] if t.get("request")])
		set_settings(self.company, self.wh["M"], material_requests=0)
		self.assertFalse([t for t in self.page()["tasks"] if t.get("request")])

	# ---- switches and permissions

	def test_switches(self):
		set_settings(self.company, self.wh["M"], outlet_transfers=0)
		d = self.page()
		self.assertIsNone(self.card(d, "move"))
		self.assertNotIn(home.KIND_MOVE, self.kinds(d))
		set_settings(self.company, self.wh["M"], expiry=0)
		d = self.page()
		self.assertIsNone(self.card(d, "expiry"))
		self.assertNotIn(home.KIND_EXPIRY, self.kinds(d))
		self.assertIsNotNone(self.card(d, "stuck"))
		set_settings(self.company, self.wh["M"], stock_health=0)
		d = self.page()
		self.assertIsNone(self.card(d, "stuck"))
		self.assertFalse({home.KIND_STUCK, home.KIND_EXPIRY} & set(self.kinds(d)))
		set_settings(self.company, self.wh["M"], enabled=0)
		with self.assertRaises(frappe.ValidationError):
			self.page()

	def test_ideas_follow_their_switches(self):
		keys = lambda: {b["key"] for b in self.page()["ideas"]}
		self.assertEqual(keys(), {"gaps", "together"})  # trending: off until Lumen gives a key
		set_settings(self.company, self.wh["M"], assortment_gaps=0)
		self.assertEqual(keys(), {"together"})
		set_settings(self.company, self.wh["M"], assortment_gaps=0, bought_together=0)
		self.assertEqual(keys(), set())

	def test_ideas_are_the_screens_rows(self):
		r = self.full()
		ideas = {b["key"]: b for b in self.page()["ideas"]}
		together = views.bought_together(r, None)
		self.assertTrue(together)
		self.assertEqual(ideas["together"]["count"], len(together))
		self.assertEqual(ideas["together"]["items"][0]["note"], "On {0} invoices together".format(together[0]["together"]))
		gaps = views.assortment_gaps(r, None)
		self.assertEqual(ideas["gaps"]["count"], len(gaps))
		self.assertLessEqual(len(ideas["gaps"]["items"]), home.IDEA_LIMIT)

	def test_needs_a_viewer_role(self):
		nobody = make_user("rs-home-nobody-%s@example.com" % self.ds.suffix, ["Stock User"])
		frappe.set_user(nobody)
		with self.assertRaises(frappe.PermissionError):
			self.page()

	def test_warehouse_filter(self):
		o1 = self.wh["O1"]
		d = self.page(warehouse=o1)
		self.assertTrue(d["tasks"])
		for t in d["tasks"]:
			if t["kind"] == home.KIND_MOVE:
				continue
			self.assertEqual(t["warehouse"], o1)
		self.assertEqual(self.card(d, "low")["count"], len(views.running_low(self.full(), None, warehouse=o1)))

	def test_limited_person_sees_own_outlet(self):
		user = make_user("rs-home-o2-%s@example.com" % self.ds.suffix, ["Stock User", "Shelf User"])
		limit(user, "Warehouse", self.wh["O2"])
		frappe.set_user(user)
		d = self.page()
		self.assertTrue(d["tasks"])
		for t in d["tasks"]:
			if t["kind"] != home.KIND_MOVE:
				self.assertEqual(t["warehouse"], self.wh["O2"])
		with self.assertRaises(frappe.PermissionError):
			self.page(warehouse=self.wh["O1"])

	def test_default_company(self):
		# stored the way ERPNext's desk stores it: key "company" (Frappe reads
		# get_user_default("Company") from the scrubbed key)
		frappe.defaults.set_user_default("company", self.company)
		try:
			self.assertEqual(home.default_company(), self.company)
			self.assertEqual(home.overview()["company"], self.company)
		finally:
			frappe.defaults.clear_user_default("company")

	def test_page_is_the_way_in(self):
		self.assertTrue(frappe.db.exists("Page", "shelf-today"))
		hooks = frappe.get_hooks("add_to_apps_screen", app_name="lumen_shelf") or []
		self.assertIn("/app/shelf-today", [h.get("route") for h in hooks])
		ws = frappe.get_doc("Workspace", "Lumen Shelf")
		self.assertEqual((ws.shortcuts[0].type, ws.shortcuts[0].link_to), ("Page", "shelf-today"))
