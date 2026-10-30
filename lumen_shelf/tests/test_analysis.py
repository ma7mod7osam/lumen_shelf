"""0.3.0: demand patterns, new items, shelf life and batches, dead stock
actions, bought together and assortment gaps. Each checked against ERPNext's
own documents (tests/oracle.py), one test per rule, so a deliberate break of
one rule (dev/mutations.py) fails its own test."""

import datetime
import math
import statistics

import frappe
from frappe.utils import flt, getdate

from lumen_shelf.restock import views
from lumen_shelf.tests import fixtures, oracle
from lumen_shelf.tests.test_restock import RestockCase, set_settings

COVER = 14


class TestAnalysis(RestockCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.today = fixtures.today()
		cls.days = [cls.start + datetime.timedelta(days=i) for i in range(56)]

	def run_with(self, **values):
		set_settings(self.company, self.wh["M"], **values)
		try:
			return self.compute()
		finally:
			set_settings(self.company, self.wh["M"])

	def series(self, name, wh="O1"):
		o = self.oracle_figures(name, wh)
		sold = {k: v[0] for k, v in self.sold.get((self.it[name], self.wh[wh]), {}).items()}
		return [sold.get(d, 0.0) for d in self.days if d in o.stocked], o

	# ---- demand patterns

	def test_demand_patterns(self):
		for name, expected in (("I1", "Intermittent"), ("LU1", "Lumpy"), ("A1", "Smooth")):
			series, _o = self.series(name)
			sizes = [q for q in series if q > 0]
			adi = len(series) / len(sizes)
			cv2 = (statistics.stdev(sizes) / statistics.mean(sizes)) ** 2
			# Syntetos and Boylan: interval 1.32, squared variation 0.49
			if adi < 1.32:
				pattern = "Smooth" if cv2 < 0.49 else "Erratic"
			else:
				pattern = "Intermittent" if cv2 < 0.49 else "Lumpy"
			self.assertEqual(pattern, expected, name)
			p = self.pair(name, "O1")
			self.assertEqual(p["pattern"], expected, name)
			self.assertAlmostEqual(p["adi"], adi, 9)
			self.assertAlmostEqual(p["cv2"], cv2, 9)

	def test_sporadic_items_forecast_by_size_and_gap(self):
		for name in ("I1", "LU1"):
			series, _o = self.series(name)
			p = self.pair(name, "O1")
			self.assertEqual(p["base_basis"], "pattern")
			self.assertAlmostEqual(p["base_speed"], oracle.croston_sba(series), 9)
		a1 = self.pair("A1", "O1")
		self.assertEqual((a1["base_basis"], a1["base_speed"]), ("history", a1["speed"]))

	def test_patterns_switch_off(self):
		p = self.pair("I1", "O1", self.run_with(demand_patterns=0))
		self.assertEqual((p["pattern"], p["base_basis"]), (None, "history"))
		self.assertEqual(p["base_speed"], p["speed"])

	# ---- new items

	def test_new_item_from_similar_brand(self):
		speeds = [self.oracle_figures(n, "O1").speed for n in ("NB1", "NB2", "NB3")]
		p = self.pair("N1", "O1")
		self.assertEqual(p["new_item"], 1)
		self.assertEqual(p["base_basis"], "similar brand")
		self.assertAlmostEqual(p["base_speed"], statistics.median(speeds), 9)

	def test_new_item_from_similar_group(self):
		peers = [self.oracle_figures(n, "O1") for n in ("NB1", "NB2", "NB3")]
		self.assertTrue(all(o.in_stock_days >= 28 for o in peers))
		p = self.pair("N2", "O1")  # no brand: its group
		self.assertEqual(p["base_basis"], "similar group")
		self.assertAlmostEqual(p["base_speed"], statistics.median(o.speed for o in peers), 9)
		self.assertEqual(self.pair("A1", "O1")["new_item"], 0)
		old1 = self.pair("OLD1", "O1")  # few days in stock, but long ago and empty now
		self.assertLess(old1["in_stock_days"], 14)
		self.assertEqual((old1["new_item"], old1["base_basis"]), (0, "history"))

	def test_new_items_switch_off(self):
		p = self.pair("N1", "O1", self.run_with(new_item_forecast=0))
		self.assertEqual(p["base_basis"], "history")

	# ---- expiry

	def test_shelf_life_caps_cover(self):
		p = self.pair("SL1", "O1")
		self.assertEqual(flt(frappe.db.get_value("Item", self.it["SL1"], "shelf_life_in_days")), 10)
		self.assertEqual(p["cover"], max(1.0, min(14.0, 10 - p["lead_time"])))
		self.assertAlmostEqual(p["target"], p["rop"] + p["forecast"] * p["cover"], 9)

	def test_expiry_risk(self):
		bal = oracle.batch_balance(self.company, self.it["EX1"], self.wh["O1"])
		b = self.ds["batches"]
		self.assertEqual((bal[b["A"]], bal[b["B"]]), (14.0, 30.0))
		p = self.pair("EX1", "O1")
		# the first to expire sells first, at the expected daily sales
		left = []
		for batch in sorted(bal, key=lambda x: frappe.db.get_value("Batch", x, "expiry_date")):
			days = (getdate(frappe.db.get_value("Batch", batch, "expiry_date")) - self.today).days
			left.append((days, bal[batch]))
		risk, sold = 0.0, 0.0
		for days, qty in left:
			sells = min(qty, max(p["forecast"] * days - sold, 0.0))
			risk += qty - sells
			sold += sells
		self.assertAlmostEqual(p["expiry_risk_qty"], risk, 9)
		self.assertGreater(risk, 0)
		valuation = flt(oracle.bin_row(self.it["EX1"], self.wh["O1"]).valuation_rate)
		self.assertAlmostEqual(p["expiry_risk_value"], risk * valuation, 6)

	def test_expiry_switch_off(self):
		r = self.run_with(expiry=0)
		self.assertEqual(self.pair("EX1", "O1", r)["expiry_risk_qty"], 0.0)
		self.assertEqual(self.pair("SL1", "O1", r)["cover"], 14.0)

	# ---- bought together

	def together(self):
		bks = list(oracle.baskets(self.company, self.start, self.end).values())
		item = self.it["DB1"]
		mine = [b for b in bks if item in b]
		out = {}
		for other in {x for b in mine for x in b if x != item}:
			n = sum(1 for b in mine if other in b)
			if n < 3:
				continue
			conf = n / len(mine)
			share = sum(1 for b in bks if other in b) / len(bks)
			out[other] = (n, conf, conf / share)
		return out

	def test_bought_together(self):
		expected = self.together()
		self.assertTrue(expected)
		got = {t["partner"]: (t["together"], t["confidence"], t["lift"]) for t in self.result["together"] if t["item"] == self.it["DB1"]}
		self.assertEqual(set(got), set(expected))
		for k, (n, conf, lift) in expected.items():
			self.assertEqual(got[k][0], n)
			self.assertAlmostEqual(got[k][1], conf, 9)
			self.assertAlmostEqual(got[k][2], lift, 9)

	# ---- dead stock

	def test_dead_stock_actions(self):
		ds1 = self.pair("DS1", "O1")
		self.assertEqual(ds1["status"], "No sales")
		self.assertEqual((ds1["action"], ds1["action_target"]), ("Return to supplier", self.ds.suppliers["S3"]))
		db1 = self.pair("DB1", "O1")
		self.assertEqual(db1["status"], "Slow")
		self.assertEqual(db1["action"], "Bundle")
		self.assertIn(db1["action_target"], self.together())
		partner = self.pair_code(db1["action_target"], "O1")
		self.assertGreater(partner["speed"], 0)
		self.assertNotIn(partner["status"], ("No sales", "Slow", "Overstock"))
		self.assertEqual(self.pair("DP1", "O1")["status"], "Slow")  # its strongest partner, but dead too
		self.assertNotEqual(db1["action_target"], self.it["DP1"])
		h2 = self.pair("H2", "HL")
		self.assertEqual((h2["status"], h2["action"]), ("No sales", "Discount"))
		moved = 0
		for l in self.result["lines"]:
			if l["reason"] == "sells_faster":
				p = [q for q in self.result["pairs"] if q["item_code"] == l["item_code"] and q["warehouse"] == l["from_warehouse"]][0]
				if p["status"] in ("No sales", "Slow", "Overstock"):
					self.assertEqual((p["action"], p["action_target"]), ("Move", l["to_warehouse"]))
					moved += 1
		self.assertGreater(moved, 0)

	def pair_code(self, code, wh):
		return [p for p in self.result["pairs"] if p["item_code"] == code and p["warehouse"] == self.wh[wh]][0]

	def test_dead_stock_switch_off(self):
		self.assertIsNone(self.pair("DS1", "O1", self.run_with(dead_stock_actions=0))["action"])

	# ---- assortment gaps

	def test_assortment_gaps(self):
		rows = views.assortment_gaps(self.result, None)
		ag1 = [r for r in rows if r["item_code"] == self.it["AG1"]]
		outlets = {w for k, w in self.wh.items() if k not in ("M", "O2")}
		self.assertEqual({r["warehouse"] for r in ag1}, outlets)
		o = self.oracle_figures("AG1", "O2")
		lead = self.pair("AG1", "O2")["lead_buy"]
		self.assertEqual(ag1[0]["start_qty"], math.ceil(o.speed * (lead + COVER) - 1e-9))
		# never an outlet that had the item
		for r in rows:
			b = oracle.bin_row(r["item_code"], r["warehouse"])
			self.assertLessEqual(flt(b.actual_qty), 0, r)
			self.assertFalse(self.sold.get((r["item_code"], r["warehouse"])), r)
		self.assertTrue(self.sold.get((self.it["MS1"], self.wh["M"])))  # the main warehouse sells
		self.assertNotIn(self.wh["M"], {r["warehouse"] for r in rows})
