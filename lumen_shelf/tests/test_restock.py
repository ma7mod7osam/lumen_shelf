"""Every figure, checked against what ERPNext itself says (tests/oracle.py) on
data built through ERPNext's own documents (tests/fixtures.py).

Each rule has its own test, named after the rule, so a deliberate break of
one rule (dev/mutations.py) fails that test."""

import math
import unittest

import frappe
from frappe.utils import flt

from lumen_shelf.restock import engine
from lumen_shelf.restock import settings as st
from lumen_shelf.tests import fixtures, oracle

Z95 = st.SERVICE_LEVELS["95%"]


def set_settings(company=None, main=None, **values):
	"""Write Lumen Shelf Settings the way a person would, through the doc."""
	doc = frappe.get_doc(st.DOCTYPE)
	for k, v in st.DEFAULTS.items():
		doc.set(k, v)
	doc.set("warehouses", [])
	if company and main:
		doc.append("warehouses", {"company": company, "warehouse": main, "warehouse_role": st.ROLE_MAIN})
	for k, v in values.items():
		doc.set(k, v)
	doc.save(ignore_permissions=True)


def reset_settings():
	set_settings()


class RestockCase(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")
		cls.ds = fixtures.dataset()
		cls.company = cls.ds.company
		cls.wh = cls.ds.warehouses
		cls.it = cls.ds["items"]
		cls.items = sorted(cls.it.values())
		set_settings(cls.company, cls.wh["M"])
		cls.result = cls.compute()
		cls.start, cls.end = oracle.window(fixtures.today(), 8)
		cls.sold = oracle.invoices(cls.company, cls.start, cls.end)

	@classmethod
	def tearDownClass(cls):
		reset_settings()

	@classmethod
	def compute(cls):
		return engine.compute(cls.company, items=cls.items, use_cache=False)

	def pair(self, name, wh, result=None):
		for p in (result or self.result)["pairs"]:
			if p["item_code"] == self.it[name] and p["warehouse"] == self.wh[wh]:
				return p
		self.fail("no row for %s in %s" % (name, wh))

	def lines(self, name, result=None, **match):
		out = []
		for l in (result or self.result)["lines"]:
			if l["item_code"] != self.it[name]:
				continue
			if all(l.get(k) == (self.wh.get(v, v) if k.endswith("warehouse") else v) for k, v in match.items()):
				out.append(l)
		return out

	def oracle_figures(self, name, wh, extra=None):
		return oracle.figures(self.it[name], self.wh[wh], fixtures.today(), 8, self.sold, extra)


class TestFigures(RestockCase):
	"""What is on the shelf, what is on order, what sold and how fast."""

	def test_on_shelf_matches_erpnext(self):
		for p in self.result["pairs"]:
			self.assertAlmostEqual(
				p["on_shelf"], oracle.on_shelf(p["item_code"], p["warehouse"]), 6, (p["item_code"], p["warehouse"])
			)

	def test_unconsolidated_pos_is_off_the_shelf(self):
		p = self.pair("P1", "O1")
		b = oracle.bin_row(self.it["P1"], self.wh["O1"])
		self.assertEqual(flt(b.actual_qty), 46)  # 50 received, 2 + 2 consolidated
		self.assertEqual(p["on_shelf"], 43)  # 3 more sold at the till, not yet consolidated

	def test_on_order_counts_open_orders_and_requests(self):
		p = self.pair("ON1", "O1")
		b = oracle.bin_row(self.it["ON1"], self.wh["O1"])
		self.assertEqual(p["on_order"], flt(b.ordered_qty) + flt(b.indented_qty))
		self.assertEqual(p["on_order"], 15)  # PO 10 + Material Request 5
		self.assertEqual(p["on_shelf"], 6)
		self.assertFalse(p["low"])  # 6 + 15 is above the reorder point of 7

	def test_sales_order_reserved(self):
		p = self.pair("SO1", "O1")
		b = oracle.bin_row(self.it["SO1"], self.wh["O1"])
		self.assertEqual(p["so_reserved"], flt(b.reserved_qty))
		self.assertEqual(p["so_reserved"], 10)
		self.assertTrue(p["low"])  # 14 on the shelf, 10 promised: 4 left against a reorder point of 7

	def test_sold_qty_matches_invoices(self):
		for p in self.result["pairs"]:
			expected = sum(v[0] for v in self.sold.get((p["item_code"], p["warehouse"]), {}).values())
			self.assertAlmostEqual(p["sold_qty"], expected, 6, (p["item_code"], p["warehouse"]))

	def test_pos_counted_once(self):
		# 2 + 2 consolidated by ERPNext into a Sales Invoice, + 3 not yet consolidated
		self.assertEqual(self.pair("P1", "O1")["sold_qty"], 7)
		consolidated = frappe.db.get_value("POS Invoice", self.ds.pos_invoices["10"], "consolidated_invoice")
		self.assertTrue(consolidated)
		self.assertEqual(frappe.db.get_value("Sales Invoice", consolidated, "is_consolidated"), 1)

	def test_bundle_parts_count(self):
		self.assertEqual(self.pair("K1", "O1")["sold_qty"], 28)  # 14 bundles of 2

	def test_returns_net(self):
		self.assertEqual(self.pair("R1", "O1")["sold_qty"], 3)  # 5 sold, 2 returned

	def test_today_not_counted(self):
		p = self.pair("A1", "O1")
		self.assertEqual(p["sold_qty"], 112)  # 2 a day for 56 days, not today's 10
		self.assertAlmostEqual(p["speed"], 2.0, 9)
		self.assertEqual(p["on_shelf"], 78)  # but today's sale is off the shelf

	def test_stockout_days_left_out(self):
		p = self.pair("A2", "O1")
		o = self.oracle_figures("A2", "O1")
		self.assertEqual(p["in_stock_days"], o.in_stock_days)
		self.assertEqual(p["in_stock_days"], 39)  # 17 empty days left out
		self.assertAlmostEqual(p["speed"], 225.0 / 199.0, 9)
		self.assertAlmostEqual(p["speed"], o.speed, 9)

	def test_stock_before_window_and_restock_day(self):
		# sold out 70 days ago, so the window opens empty; restocked 31 days ago
		# with no sale that day, then 1 a day for 30 days
		p = self.pair("Z1", "O1")
		o = self.oracle_figures("Z1", "O1")
		self.assertEqual(p["in_stock_days"], 31)
		self.assertEqual(p["in_stock_days"], o.in_stock_days)
		self.assertAlmostEqual(p["speed"], o.speed, 9)

	def test_weighted_speed_recent_weighs_more(self):
		p = self.pair("A4", "O1")
		self.assertAlmostEqual(p["speed"], 616.0 / 252.0, 9)  # unweighted it would be 2.0
		self.assertAlmostEqual(p["sigma"], math.sqrt(56.0 / 55.0), 9)

	def test_speed_and_sigma_match_erpnext_ledger(self):
		for p in self.result["pairs"]:
			if p["is_main"]:
				continue
			o = oracle.figures(p["item_code"], p["warehouse"], fixtures.today(), 8, self.sold)
			key = (p["item_code"], p["warehouse"])
			self.assertEqual(p["in_stock_days"], o.in_stock_days, key)
			self.assertAlmostEqual(p["speed"], o.speed, 9, key)
			self.assertAlmostEqual(p["sigma"], o.sigma, 9, key)

	def test_main_demand_includes_transfers_out(self):
		sent = oracle.transfers_sent(self.company, self.wh["M"], self.start, self.end)
		p = self.pair("X7", "M")
		o = self.oracle_figures("X7", "M", sent.get(self.it["X7"]))
		self.assertGreater(p["speed"], 0)
		self.assertAlmostEqual(p["speed"], o.speed, 9)
		self.assertEqual(p["sold_qty"], 0)  # it sold nothing: its demand is what it sent


class TestLevels(RestockCase):
	"""Lead times, safety, reorder point and the suggested quantity."""

	def test_lead_time_learned_from_receipts(self):
		samples = oracle.lead_days_by_supplier(self.company)[self.ds.suppliers["S1"]]
		self.assertEqual(sorted(samples), [4, 6, 6, 10])
		p = self.pair("L1", "O1")
		self.assertEqual(p["supplier"], self.ds.suppliers["S1"])
		self.assertEqual(p["lead_basis"], "learned")
		self.assertEqual(p["lead_buy"], 6.0)  # the median, not the mean (6.5)

	def test_lead_time_from_item(self):
		p = self.pair("L2", "O1")
		self.assertEqual(p["supplier"], self.ds.suppliers["S2"])
		self.assertEqual(p["lead_basis"], "item")
		self.assertEqual(p["lead_buy"], 12.0)

	def test_supplier_from_last_purchase_order(self):
		p = self.pair("L3", "O1")
		self.assertEqual(p["supplier"], self.ds.suppliers["S1"])
		self.assertEqual(p["lead_buy"], 6.0)

	def test_lead_time_default(self):
		p = self.pair("A3", "O1")
		self.assertEqual((p["lead_basis"], p["lead_buy"]), ("default", 7.0))
		set_settings(self.company, self.wh["M"], default_lead_time=9)
		try:
			self.assertEqual(self.pair("A3", "O1", self.compute())["lead_buy"], 9.0)
		finally:
			set_settings(self.company, self.wh["M"])

	def test_levels_match_the_rule(self):
		for p in self.result["pairs"]:
			# the season effect itself is checked in test_forecast
			# the season effect, the pattern base and the shelf-life cover are checked
			# in test_forecast and test_analysis
			f = p["season_factor"]
			lv = oracle.levels(p["base_speed"] * f, p["sigma"] * f, p["lead_time"], Z95, p["cover"])
			key = (p["item_code"], p["warehouse"])
			self.assertAlmostEqual(p["rop"], lv.rop, 9, key)
			self.assertAlmostEqual(p["target"], lv.target, 9, key)

	def test_safety_grows_with_swing(self):
		p = self.pair("A6", "O1")
		self.assertGreater(p["sigma"], 1.5)
		self.assertAlmostEqual(p["safety"], Z95 * p["sigma"] * math.sqrt(7), 9)
		self.assertGreater(p["position"], p["speed"] * 7)  # without safety it would not be low
		self.assertTrue(p["low"])

	def test_suggested_qty_covers_n_days(self):
		p = self.pair("L1", "O1")
		self.assertTrue(p["low"])
		buy = self.lines("L1", kind="buy")
		self.assertEqual(len(buy), 1)
		self.assertEqual(buy[0]["qty"], math.ceil(1.0 * 6 + 1.0 * 14 - p["position"]))  # 15
		self.assertEqual(buy[0]["supplier"], self.ds.suppliers["S1"])

	def test_buy_rounded_to_pack(self):
		buy = self.lines("A3", kind="buy")
		self.assertEqual(buy[0]["qty"], 18)  # 17 short, packs of 6
		self.assertEqual(buy[0]["purchase_qty"], 3)
		self.assertEqual(buy[0]["purchase_uom"], "Box")

	def test_buy_respects_min_order(self):
		self.assertEqual(self.lines("A5", kind="buy")[0]["qty"], 24)

	def test_not_low_when_enough(self):
		self.assertFalse(self.pair("A1", "O1")["low"])
		self.assertFalse(self.lines("A1"))

	def test_days_left(self):
		p = self.pair("A1", "O1")
		self.assertAlmostEqual(p["days_left"], 78 / 2.0, 9)


class TestTransfers(RestockCase):
	def test_main_warehouse_first(self):
		into = self.lines("X1", to_warehouse="O2")
		self.assertEqual([l["from_warehouse"] for l in into], [self.wh["M"]])
		p = self.pair("X1", "O2")
		self.assertEqual(p["lead_time"], 2.0)  # restocked by transfer
		self.assertEqual(into[0]["qty"], p["need"])
		self.assertFalse(self.lines("X1", from_warehouse="O3"))

	def test_outlet_surplus_before_buying(self):
		o3 = self.pair("X2", "O3")
		o2 = self.pair("X2", "O2")
		spare = math.floor(o3["on_shelf"] - o3["target"])
		moved = self.lines("X2", from_warehouse="O3", to_warehouse="O2", reason="running_low")
		self.assertEqual(len(moved), 1)
		self.assertEqual(moved[0]["qty"], spare)
		bought = self.lines("X2", kind="buy", to_warehouse="O2")
		self.assertEqual(bought[0]["qty"], o2["need"] - spare)

	def test_only_surplus_moves(self):
		o3 = self.pair("X2", "O3")
		moved = sum(l["qty"] for l in self.lines("X2", from_warehouse="O3"))
		self.assertGreaterEqual(o3["on_shelf"] - moved, o3["target"])

	def test_sells_faster_moves_slow_stock(self):
		moved = self.lines("X3", from_warehouse="O2", to_warehouse="O3")
		self.assertEqual(len(moved), 1)
		self.assertEqual(moved[0]["reason"], "sells_faster")
		o3 = self.pair("X3", "O3")
		self.assertEqual(moved[0]["qty"], math.floor(o3["target"] - o3["position"]))  # 11, what O3 can sell
		self.assertFalse(o3["low"])

	def test_no_transfer_without_history(self):
		self.assertLess(self.pair("X4", "O2")["in_stock_days"], 28)
		self.assertFalse(self.lines("X4", from_warehouse="O2"))
		# nor to cover a shortage: O3 is short of X6, O2 has it but too new
		self.assertTrue(self.pair("X6", "O3")["low"])
		self.assertFalse(self.lines("X6", from_warehouse="O2"))
		self.assertTrue(self.lines("X6", kind="buy", to_warehouse="O3"))

	def test_sells_faster_needs_twice_the_speed(self):
		o2, o3 = self.pair("X5", "O2"), self.pair("X5", "O3")
		self.assertGreater(o3["speed"], o2["speed"])
		self.assertLess(o3["speed"], 2 * o2["speed"])
		self.assertGreater(o3["target"] - o3["position"], 1)  # O3 would have room
		self.assertFalse(self.lines("X5", from_warehouse="O2"))

	def test_main_detected_from_transfers(self):
		set_settings()  # no main named
		try:
			r = self.compute()
			self.assertEqual((r["main_warehouse"], r["main_basis"]), (self.wh["M"], "detected"))
		finally:
			set_settings(self.company, self.wh["M"])

	def test_transfer_only_mode(self):
		set_settings(self.company, self.wh["M"], restock_source=st.SOURCE_TRANSFER)
		try:
			r = self.compute()
			o2 = self.pair("X2", "O2", r)
			self.assertEqual(o2["lead_time"], 2.0)
			from_o3 = sum(l["qty"] for l in self.lines("X2", r, from_warehouse="O3"))
			wait = self.lines("X2", r, from_warehouse="M", to_warehouse="O2")
			self.assertEqual(len(wait), 1)
			self.assertEqual(wait[0]["main_short"], 1)
			self.assertEqual(wait[0]["qty"] + from_o3, o2["need"])
			self.assertFalse(self.lines("X2", r, kind="buy", to_warehouse="O2"))
			main_buy = self.lines("X2", r, kind="buy", to_warehouse="M")
			self.assertEqual(len(main_buy), 1)
			self.assertGreaterEqual(main_buy[0]["qty"], wait[0]["qty"])
		finally:
			set_settings(self.company, self.wh["M"])

	def test_buy_only_mode(self):
		set_settings(self.company, self.wh["M"], restock_source=st.SOURCE_BUY)
		try:
			r = self.compute()
			self.assertFalse(self.lines("X1", r, from_warehouse="M"))
			self.assertEqual(self.pair("X1", "O2", r)["lead_time"], 7.0)
			self.assertTrue(self.lines("X1", r, kind="buy", to_warehouse="O2"))
		finally:
			set_settings(self.company, self.wh["M"])

	def test_outlet_transfers_switch(self):
		set_settings(self.company, self.wh["M"], outlet_transfers=0)
		try:
			r = self.compute()
			between = [l for l in r["lines"] if l["kind"] == "transfer" and l["from_warehouse"] != self.wh["M"]]
			self.assertEqual(between, [])
			self.assertTrue(self.lines("X1", r, from_warehouse="M"))  # the main warehouse still feeds outlets
		finally:
			set_settings(self.company, self.wh["M"])


class TestHealth(RestockCase):
	def test_abc_ranking(self):
		for name in ("B1", "B2", "B3", "B4"):
			expected = sum(v[1] for v in self.sold[(self.it[name], self.wh["AB"])].values())
			self.assertAlmostEqual(self.pair(name, "AB")["sales_value"], expected, 6)
		got = {n: self.pair(n, "AB")["abc"] for n in ("B1", "B2", "B3", "B4")}
		self.assertEqual(got, {"B1": "A", "B2": "A", "B3": "B", "B4": "C"})

	def test_health_statuses(self):
		got = {n: self.pair(n, "HL")["status"] for n in ("H1", "H2", "H3", "H4")}
		self.assertEqual(got, {"H1": "Slow", "H2": "No sales", "H3": "Overstock", "H4": "Too new"})
		self.assertEqual(self.pair("A1", "O1")["status"], "OK")

	def test_overstock_value(self):
		p = self.pair("H3", "HL")
		self.assertAlmostEqual(p["excess_qty"], 80 - 21, 6)
		b = oracle.bin_row(self.it["H3"], self.wh["HL"])
		self.assertAlmostEqual(p["excess_value"], (80 - 21) * flt(b.valuation_rate), 6)
