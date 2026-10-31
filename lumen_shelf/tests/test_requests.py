"""Phase 2: the suggestions become ERPNext Material Requests. Checked against
what ERPNext itself does with them: the Bin's on-order figure, its own
Create > Purchase Order and Create > Transfer Material. One test per rule, so a
deliberate break of one rule (dev/mutations.py) fails its own test.

Every test works inside a savepoint and rolls back, so the day's dataset stays
as it was for the other test modules."""

import json
import math
from unittest import mock

import frappe
from frappe.utils import add_days, flt, getdate, nowdate

from lumen_shelf.restock import access, engine, requests, views
from lumen_shelf.tests import oracle
from lumen_shelf.tests.test_access import limit, make_user
from lumen_shelf.tests.test_restock import RestockCase, set_settings

SP = "rs_requests"


class TestRequests(RestockCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(SP)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=SP)
		engine.forget(self.company)

	def lines_of(self, result, scope="running_low", **filters):
		filters.setdefault("company", self.company)
		return requests.chosen_lines(result, None, scope, filters)

	def planned(self, result=None, scope="running_low", **filters):
		result = result or self.result
		return requests.plan(result, self.lines_of(result, scope, **filters))

	def items_of(self, groups, rtype=None):
		return [i for g in groups if rtype in (None, g["type"]) for i in g["items"]]

	# ---- grouping

	def test_purchases_one_request_per_supplier(self):
		buys = [l for l in self.result["lines"] if l["kind"] == engine.KIND_BUY]
		self.assertTrue(buys)
		groups = [g for g in self.planned() if g["type"] == requests.TYPE_PURCHASE]
		self.assertEqual(sorted(g["supplier"] or "" for g in groups), sorted({l["supplier"] or "" for l in buys}))
		for g in groups:
			mine = sorted((l["item_code"], l["to_warehouse"], l["qty"]) for l in buys if (l["supplier"] or None) == g["supplier"])
			self.assertEqual(sorted((i["item_code"], i["warehouse"], i["stock_qty"]) for i in g["items"]), mine)
			if g["supplier"]:
				name = frappe.db.get_value("Supplier", g["supplier"], "supplier_name")
				self.assertEqual(g["title"], "Restock from {0}".format(name))
			else:
				self.assertEqual(g["title"], "Restock, supplier to choose")
		# suppliers first, the one still to choose last
		self.assertEqual([g["supplier"] or "" for g in groups][-1], "")

	def test_transfers_one_request_per_sending_warehouse(self):
		moves = [l for l in self.result["lines"] if l["kind"] == engine.KIND_TRANSFER and l["reason"] == engine.REASON_LOW]
		self.assertTrue(moves)
		groups = [g for g in self.planned() if g["type"] == requests.TYPE_TRANSFER]
		self.assertEqual(sorted(g["from_warehouse"] for g in groups), sorted({l["from_warehouse"] for l in moves}))
		for g in groups:
			mine = sorted((l["item_code"], l["to_warehouse"], l["qty"]) for l in moves if l["from_warehouse"] == g["from_warehouse"])
			self.assertEqual(sorted((i["item_code"], i["warehouse"], i["stock_qty"]) for i in g["items"]), mine)
			self.assertTrue(all(i["from_warehouse"] == g["from_warehouse"] for i in g["items"]))
			self.assertEqual(g["title"], "Restock from {0}".format(g["from_warehouse"]))

	def test_purchase_unit_and_dates(self):
		a3 = [i for i in self.items_of(self.planned(), requests.TYPE_PURCHASE) if i["item_code"] == self.it["A3"]][0]
		self.assertEqual((a3["qty"], a3["uom"], a3["conversion_factor"], a3["stock_qty"]), (3, "Box", 6, 18))
		l1 = [i for i in self.items_of(self.planned(), requests.TYPE_PURCHASE) if i["item_code"] == self.it["L1"]][0]
		self.assertEqual((l1["uom"], l1["conversion_factor"]), (self.pair("L1", "O1")["stock_uom"], 1.0))
		pairs = {(p["item_code"], p["warehouse"]): p for p in self.result["pairs"]}
		transfer_days = self.result["settings"]["transfer_lead_time"]
		for g in self.planned():
			for i in g["items"]:
				p = pairs[(i["item_code"], i["warehouse"])]
				days = p["lead_buy"] if g["type"] == requests.TYPE_PURCHASE else transfer_days
				self.assertEqual(getdate(i["schedule_date"]), getdate(add_days(nowdate(), math.ceil(days))), i)

	# ---- filters: the button asks for what the screen shows

	def test_source_and_warehouse_filters(self):
		self.assertFalse(self.items_of(self.planned(source=views.SOURCE_TRANSFER), requests.TYPE_PURCHASE))
		self.assertTrue(self.items_of(self.planned(source=views.SOURCE_TRANSFER), requests.TYPE_TRANSFER))
		self.assertFalse(self.items_of(self.planned(source=views.SOURCE_BUY), requests.TYPE_TRANSFER))
		self.assertTrue(self.items_of(self.planned(source=views.SOURCE_BUY), requests.TYPE_PURCHASE))
		o1 = self.items_of(self.planned(warehouse=self.wh["O1"]))
		self.assertTrue(o1)
		self.assertEqual({i["warehouse"] for i in o1}, {self.wh["O1"]})

	def test_budget_buys_only_what_fits(self):
		costs = sorted(r["buy_cost"] for r in views.running_low(self.result, None) if r["buy_cost"])
		budget = sum(costs[: len(costs) // 2]) + 0.01
		rows = views.running_low(self.result, None, budget=budget)
		fit = {(r["item_code"], r["warehouse"]) for r in rows if r["buy_qty"] and r["in_budget"]}
		left = {(r["item_code"], r["warehouse"]) for r in rows if r["buy_qty"] and not r["in_budget"]}
		self.assertTrue(fit and left)
		got = {(i["item_code"], i["warehouse"]) for i in self.items_of(self.planned(budget=budget), requests.TYPE_PURCHASE)}
		self.assertEqual(got, fit)
		# transfers do not spend the budget
		self.assertEqual(
			len(self.items_of(self.planned(budget=budget), requests.TYPE_TRANSFER)),
			len(self.items_of(self.planned(), requests.TYPE_TRANSFER)),
		)

	def test_transfer_screen_and_reason(self):
		moves = [l for l in self.result["lines"] if l["kind"] == engine.KIND_TRANSFER]
		every = self.items_of(self.planned(scope="transfers"))
		self.assertEqual(len(every), len(moves))
		faster = self.items_of(self.planned(scope="transfers", reason="Sells faster there"))
		n_faster = sum(1 for l in moves if l["reason"] == engine.REASON_FASTER)
		self.assertTrue(n_faster)
		self.assertEqual(len(faster), n_faster)
		self.assertFalse(self.items_of(self.planned(scope="transfers"), requests.TYPE_PURCHASE))

	# ---- what ERPNext does with them

	def test_erpnext_takes_them_on_order(self):
		groups = self.planned()
		before = {}
		for i in self.items_of(groups):
			b = oracle.bin_row(i["item_code"], i["warehouse"])
			before[(i["item_code"], i["warehouse"])] = flt(b.indented_qty) if b else 0.0
		made = requests.make(groups, self.company, submit=True)
		self.assertEqual(len(made), len(groups))
		want = {}
		for i in self.items_of(groups):
			want[(i["item_code"], i["warehouse"])] = want.get((i["item_code"], i["warehouse"]), 0.0) + i["stock_qty"]
		for (item, wh), qty in want.items():
			b = oracle.bin_row(item, wh)
			self.assertAlmostEqual(flt(b.indented_qty) - before[(item, wh)], qty, 6, (item, wh))
		for m, g in zip(made, groups):
			doc = frappe.get_doc("Material Request", m["name"])
			self.assertEqual((doc.docstatus, doc.material_request_type, doc.title), (1, g["type"], g["title"]))
			self.assertEqual(
				sorted((r.item_code, r.warehouse, r.from_warehouse or None, flt(r.stock_qty), r.uom) for r in doc.items),
				sorted((i["item_code"], i["warehouse"], i["from_warehouse"], i["stock_qty"], i["uom"]) for i in g["items"]),
			)
		# asked once: worked out again, nothing is left to request
		again = self.compute()
		self.assertEqual(self.planned(again), [])

	def test_purchase_order_from_the_request(self):
		from erpnext.stock.doctype.material_request.material_request import make_purchase_order

		groups = [g for g in self.planned() if g["type"] == requests.TYPE_PURCHASE and g["supplier"]]
		made = requests.make(groups[:1], self.company, submit=True)
		po = make_purchase_order(made[0]["name"])
		self.assertEqual(
			sorted((r.item_code, r.warehouse, flt(r.qty), r.uom, flt(r.conversion_factor)) for r in po.items),
			sorted((i["item_code"], i["warehouse"], i["qty"], i["uom"], i["conversion_factor"]) for i in groups[0]["items"]),
		)

	def test_transfer_requested_is_not_spare(self):
		from erpnext.stock.doctype.material_request.material_request import make_stock_entry

		groups = [g for g in self.planned() if g["type"] == requests.TYPE_TRANSFER]
		made = requests.make(groups, self.company, submit=True)
		asked = {}
		for g in groups:
			for i in g["items"]:
				asked[(i["item_code"], i["from_warehouse"])] = asked.get((i["item_code"], i["from_warehouse"]), 0.0) + i["stock_qty"]
		after = self.compute()
		for (item, wh), qty in asked.items():
			p = [q for q in after["pairs"] if q["item_code"] == item and q["warehouse"] == wh][0]
			self.assertAlmostEqual(p["requested_out"], qty, 6, (item, wh))
			self.assertAlmostEqual(p["position"], p["on_shelf"] + p["on_order"] - p["so_reserved"] - qty, 6)
		# ERPNext moves the stock: the request is filled and nothing is held back
		# ERPNext moves part of the stock: what is still to move stays held back
		se = make_stock_entry(made[0]["name"])
		sent = {}
		for r in se.items:
			self.assertEqual(r.s_warehouse, groups[0]["from_warehouse"])
			r.cost_center = r.cost_center or frappe.get_cached_value("Company", self.company, "cost_center")
			if flt(r.qty) >= 2:
				r.qty = math.floor(flt(r.qty) / 2)
				r.transfer_qty = flt(r.qty) * flt(r.conversion_factor or 1)
			sent[r.item_code] = sent.get(r.item_code, 0.0) + flt(r.transfer_qty or r.qty)
		self.assertTrue(any(asked[(i, groups[0]["from_warehouse"])] > q for i, q in sent.items()))
		se.insert()
		se.submit()
		moved = self.compute()
		for item, q in sent.items():
			wh = groups[0]["from_warehouse"]
			p = [x for x in moved["pairs"] if x["item_code"] == item and x["warehouse"] == wh][0]
			self.assertAlmostEqual(p["requested_out"], asked[(item, wh)] - q, 6, item)

	def ask_transfer(self, name, src, dst, qty):
		requests.make(
			[
				{
					"type": requests.TYPE_TRANSFER,
					"supplier": None,
					"from_warehouse": self.wh[src],
					"title": "test",
					"items": [
						{
							"item_code": self.it[name],
							"warehouse": self.wh[dst],
							"from_warehouse": self.wh[src],
							"qty": qty,
							"uom": self.pair(name, src)["stock_uom"],
							"conversion_factor": 1.0,
							"stock_qty": qty,
							"stock_uom": self.pair(name, src)["stock_uom"],
							"schedule_date": nowdate(),
						}
					],
				}
			],
			self.company,
			submit=True,
		)

	def test_requested_stock_is_promised(self):
		# an outlet's surplus already asked for elsewhere covers no other shortage
		o3 = self.pair("X2", "O3")
		self.assertTrue(self.lines("X2", from_warehouse="O3", to_warehouse="O2"))
		self.ask_transfer("X2", "O3", "O1", math.floor(o3["on_shelf"] - o3["so_reserved"] - o3["target"]))
		after = self.compute()
		self.assertFalse(self.lines("X2", after, from_warehouse="O3"))
		self.assertEqual(sum(l["qty"] for l in self.lines("X2", after, kind="buy", to_warehouse="O2")), self.pair("X2", "O2", after)["need"])
		# nor the main warehouse's stock
		self.assertTrue(self.lines("X1", from_warehouse="M", to_warehouse="O2"))
		m = self.pair("X1", "M")
		self.ask_transfer("X1", "M", "O3", m["on_shelf"] - m["so_reserved"])
		self.assertFalse(self.lines("X1", self.compute(), from_warehouse="M", to_warehouse="O2"))

	def test_drafts_are_not_asked_twice(self):
		groups = self.planned()
		made = requests.make(groups, self.company, submit=False)
		self.assertTrue(all(m["docstatus"] == 0 for m in made))
		self.assertEqual(self.planned(self.compute()), [])

	def test_a_draft_covers_part(self):
		a3 = [i for i in self.items_of(self.planned(), requests.TYPE_PURCHASE) if i["item_code"] == self.it["A3"]][0]
		doc = frappe.new_doc("Material Request")
		doc.material_request_type = requests.TYPE_PURCHASE
		doc.company = self.company
		doc.transaction_date = nowdate()
		doc.schedule_date = nowdate()
		doc.append(
			"items",
			{
				"item_code": self.it["A3"],
				"qty": 1,
				"uom": "Box",
				"conversion_factor": 6,
				"warehouse": a3["warehouse"],
				"schedule_date": nowdate(),
				"cost_center": frappe.get_cached_value("Company", self.company, "cost_center"),
			},
		)
		doc.insert()
		got = [i for i in self.items_of(self.planned(), requests.TYPE_PURCHASE) if i["item_code"] == self.it["A3"]][0]
		self.assertEqual((got["stock_qty"], got["qty"]), (a3["stock_qty"] - 6, a3["qty"] - 1))

	def test_screen_cache_and_forget(self):
		def a3_buy(result):
			return sum(l["qty"] for l in result["lines"] if l["item_code"] == self.it["A3"] and l["kind"] == engine.KIND_BUY)

		engine.forget(self.company)
		first = engine.compute(self.company, items=self.items)
		self.assertGreater(a3_buy(first), 0)
		# ordered in ERPNext behind Lumen Shelf's back: the screen keeps its figures
		po = frappe.new_doc("Material Request")
		po.material_request_type = requests.TYPE_PURCHASE
		po.company = self.company
		po.transaction_date = po.schedule_date = nowdate()
		wh = [l["to_warehouse"] for l in first["lines"] if l["item_code"] == self.it["A3"] and l["kind"] == engine.KIND_BUY][0]
		po.append("items", {"item_code": self.it["A3"], "qty": a3_buy(first), "uom": self.pair("A3", "O1")["stock_uom"], "conversion_factor": 1, "warehouse": wh, "schedule_date": nowdate(), "cost_center": frappe.get_cached_value("Company", self.company, "cost_center")})
		po.insert()
		po.submit()
		self.assertEqual(a3_buy(engine.compute(self.company, items=self.items)), a3_buy(first))
		# until Lumen Shelf forgets them, as it does after it makes requests
		engine.forget(self.company)
		self.assertEqual(a3_buy(engine.compute(self.company, items=self.items)), 0)

	# ---- the buttons, through their whitelisted calls

	def test_button_round_trip(self):
		filters = json.dumps({"company": self.company})
		first = requests.preview("running_low", filters)
		self.assertGreater(first["count"], 0)
		frappe.clear_messages()
		made = requests.create("running_low", filters)
		self.assertEqual(made["count"], first["count"])
		self.assertFalse(frappe.local.message_log)  # ERPNext's per-request notes left out
		for name in made["names"]:
			self.assertEqual(frappe.db.get_value("Material Request", name, ["company", "docstatus"]), (self.company, 1))
			self.assertIn("/app/material-request/" + name, made["message"])
		# the cached screen is forgotten: the next look sees them on order
		self.assertEqual(requests.preview("running_low", filters)["count"], 0)

	# ---- who may

	def test_switch_and_roles(self):
		sfx = self.ds.suffix
		viewer = make_user("rs-viewer-%s@example.com" % sfx, ["Stock User", "Shelf User"])
		bare = make_user("rs-bare-mgr-%s@example.com" % sfx, ["Shelf Manager"])
		# ERPNext would let this person make a request: only our role check stops them
		self.assertTrue(frappe.has_permission("Material Request", "submit", user=viewer))
		frappe.set_user(viewer)
		self.assertTrue(access.can_view())
		with self.assertRaises(frappe.PermissionError):
			access.check_requests("running_low")
		self.assertEqual(requests.can_create("running_low")["ok"], 0)
		with self.assertRaises(frappe.PermissionError):
			requests.create("running_low", json.dumps({"company": self.company}))
		frappe.set_user(bare)  # a role that may act, but no ERPNext right to a Material Request
		with self.assertRaises(frappe.PermissionError):
			access.check_requests("running_low")
		frappe.set_user("Administrator")
		self.assertEqual(requests.can_create("transfers")["ok"], 1)
		set_settings(self.company, self.wh["M"], material_requests=0)
		with self.assertRaises(frappe.ValidationError):
			access.check_requests("running_low")
		self.assertEqual(requests.can_create("running_low")["ok"], 0)

	def test_limited_to_own_warehouses(self):
		sfx = self.ds.suffix
		user = make_user("rs-o2-mgr-%s@example.com" % sfx, ["Stock User", "Stock Manager"])
		mine_whs = {self.wh["O2"], self.wh["M"]}
		for w in mine_whs:
			limit(user, "Warehouse", w)
		frappe.set_user(user)
		result, allowed = views.load("transfers", self.company, items=self.items, use_cache=False)
		self.assertEqual(allowed, mine_whs)
		seen = [r for r in views.transfers(result, allowed)]
		mine = requests.chosen_lines(result, allowed, "transfers", {"company": self.company})
		self.assertTrue(mine)
		for l in mine:
			self.assertTrue({l["from_warehouse"], l["to_warehouse"]} <= mine_whs, l)
		# the screen shows a move from or to a warehouse it may not see, the button leaves it out
		self.assertLess(len(mine), len(seen))

	# ---- contract 2: the till's button (lumen_shelf.api)

	def test_api_state(self):
		from lumen_shelf import api

		got = api.state()
		self.assertEqual((got["contract"], got["can_request"], got["submit_requests"]), (2, 1, 1))
		viewer = make_user("rs-viewer-%s@example.com" % self.ds.suffix, ["Stock User", "Shelf User"])
		frappe.set_user(viewer)
		got = api.state()
		self.assertEqual((got["can_view"], got["can_request"]), (1, 0))

	def test_api_preview_and_create_for_one_outlet(self):
		from lumen_shelf import api

		o1 = self.wh["O1"]
		first = api.preview_requests(self.company, o1)
		self.assertEqual(first["status"], "ok")
		self.assertTrue(first["requests"])
		lines = [l for r in first["requests"] for l in r["lines"]]
		self.assertEqual({l["warehouse"] for l in lines}, {o1})
		expected = {(l["item_code"], l["to_warehouse"], l["qty"]) for l in self.lines_of(self.result, warehouse=o1)}
		self.assertEqual({(l["item_code"], l["warehouse"], l["stock_qty"]) for l in lines}, expected)
		for r in first["requests"]:
			self.assertEqual(r["type_label"], "Purchase request" if r["type"] == requests.TYPE_PURCHASE else "Transfer request")
		made = api.create_requests(self.company, o1)
		self.assertEqual(made["status"], "ok")
		self.assertEqual(len(made["created"]), len(first["requests"]))
		for m in made["created"]:
			self.assertEqual(frappe.db.get_value("Material Request", m["name"], "docstatus"), 1)
		self.assertEqual(api.preview_requests(self.company, o1)["requests"], [])

	def test_api_transfers_from_or_to_the_outlet(self):
		from lumen_shelf import api

		moves = [l for l in self.result["lines"] if l["kind"] == engine.KIND_TRANSFER]
		# an outlet that some moves touch and some do not, so the cut shows
		outlet = None
		for wh in sorted(self.wh.values()):
			touching = [l for l in moves if wh in (l["from_warehouse"], l["to_warehouse"])]
			if 0 < len(touching) < len(moves):
				outlet = wh
				break
		self.assertTrue(outlet)
		got = api.preview_requests(self.company, outlet, scope="transfers")
		lines = [l for r in got["requests"] for l in r["lines"]]
		self.assertTrue(lines)
		for l in lines:
			self.assertIn(outlet, (l["warehouse"], l["from_warehouse"]))
		self.assertEqual(len(lines), len(touching))

	def test_api_refusals(self):
		from lumen_shelf import api

		self.assertEqual(api.preview_requests(self.company, scope="nope")["status"], "error")
		viewer = make_user("rs-viewer-%s@example.com" % self.ds.suffix, ["Stock User", "Shelf User"])
		frappe.set_user(viewer)
		self.assertEqual(api.preview_requests(self.company)["status"], "forbidden")
		self.assertEqual(api.create_requests(self.company)["status"], "forbidden")
		# a manager limited to one outlet asks for another one
		limited = make_user("rs-o2-only-%s@example.com" % self.ds.suffix, ["Stock User", "Stock Manager"])
		limit(limited, "Warehouse", self.wh["O2"])
		frappe.set_user(limited)
		self.assertEqual(api.preview_requests(self.company, self.wh["O2"])["status"], "ok")
		self.assertEqual(api.preview_requests(self.company, self.wh["O1"])["status"], "forbidden")
		frappe.set_user("Administrator")
		set_settings(self.company, self.wh["M"], material_requests=0)
		self.assertEqual(api.preview_requests(self.company)["status"], "disabled")
		set_settings(self.company, self.wh["M"], enabled=0)
		self.assertEqual(api.create_requests(self.company)["status"], "disabled")

	def test_api_create_is_all_or_nothing(self):
		from lumen_shelf import api

		real = requests.make
		before = frappe.db.count("Material Request", {"company": self.company})

		def first_then_fail(groups, company, submit, today=None):
			real(groups[:1], company, submit)
			frappe.throw("RS test failure")

		with mock.patch.object(requests, "make", side_effect=first_then_fail):
			got = api.create_requests(self.company)
		self.assertEqual(got["status"], "error")
		self.assertIn("RS test failure", got["message"])
		self.assertEqual(frappe.db.count("Material Request", {"company": self.company}), before)

	def test_request_roles_from_other_apps(self):
		user = make_user("rs-till-%s@example.com" % self.ds.suffix, ["Stock User", "Shelf User", "RS Till Manager"])
		frappe.set_user(user)
		self.assertFalse(access.can_request())
		real = frappe.get_hooks

		def fake(name=None, *args, **kwargs):
			if name == "lumen_shelf_request_roles":
				return ["RS Till Manager", "Guest"]
			return real(name, *args, **kwargs)

		with mock.patch.object(access.frappe, "get_hooks", side_effect=fake):
			self.assertTrue(access.can_request())
			self.assertNotIn("Guest", access.request_roles())
