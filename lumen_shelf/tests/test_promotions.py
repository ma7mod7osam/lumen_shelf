"""0.7.0 promotions: days sold mostly at a discount are left out of the
normal sales, the lift is measured, and a planned promotion raises the
suggestion before it starts. Checked against the invoice lines and the
Pricing Rules themselves (tests/oracle.py), one test per rule, for
dev/mutations.py."""

import datetime
import math
import statistics

import frappe
from frappe.utils import add_days, getdate

from lumen_shelf.restock import engine, views
from lumen_shelf.tests import fixtures, oracle
from lumen_shelf.tests.test_restock import RestockCase, set_settings


class TestPromotions(RestockCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.today = fixtures.today()
		cls.off = oracle.discounted(cls.company, cls.start, cls.end)

	def run_with(self, **values):
		set_settings(self.company, self.wh["M"], **values)
		try:
			return self.compute()
		finally:
			set_settings(self.company, self.wh["M"])

	def promo_days(self, name, wh="O1"):
		"""Days at least half of what sold was discounted, from the invoices."""
		key = (self.it[name], self.wh[wh])
		sold = self.sold.get(key, {})
		off = self.off.get(key, {})
		stocked = self.oracle_figures(name, wh).stocked
		return {d for d in stocked if sold.get(d, [0])[0] > 0 and off.get(d, 0.0) >= 0.5 * sold[d][0]}

	def test_promotion_days_from_the_invoices(self):
		days = self.promo_days("PR1")
		self.assertEqual(days, {getdate(add_days(self.today, -k)) for k in fixtures.PROMO_DAYS})
		self.assertEqual(self.pair("PR1", "O1")["promo_days"], len(days))
		self.assertEqual(self.pair("A1", "O1")["promo_days"], 0)  # sold at full price

	def test_lift(self):
		key = (self.it["PR1"], self.wh["O1"])
		stocked = self.oracle_figures("PR1", "O1").stocked
		promo = self.promo_days("PR1")
		sold = {d: v[0] for d, v in self.sold[key].items()}
		on = statistics.mean(sold.get(d, 0.0) for d in promo)
		off = statistics.mean(sold.get(d, 0.0) for d in stocked - promo)
		p = self.pair("PR1", "O1")
		self.assertAlmostEqual(p["promo_speed"], on, 9)
		self.assertAlmostEqual(p["normal_speed"], off, 9)
		self.assertAlmostEqual(p["lift"], on / off, 9)
		self.assertAlmostEqual(p["lift"], 3.0, 9)

	def test_base_leaves_promotions_out(self):
		key = (self.it["PR1"], self.wh["O1"])
		normal = self.oracle_figures("PR1", "O1").stocked - self.promo_days("PR1")
		sold = {d: v[0] for d, v in self.sold[key].items()}
		p = self.pair("PR1", "O1")
		self.assertEqual(p["base_basis"], engine.BASIS_NO_PROMO)
		self.assertAlmostEqual(p["base_speed"], oracle.weighted_mean(normal, sold, self.end, 8), 9)
		self.assertAlmostEqual(p["base_sigma"], statistics.stdev(sold.get(d, 0.0) for d in normal), 9)
		self.assertGreater(p["sigma"], p["base_sigma"])  # the history swings with the spikes
		self.assertGreater(p["speed"], p["base_speed"])  # the history alone would buy for the spikes

	def expected_factor(self, p, start, end):
		horizon = int(math.ceil(p["lead_time"] + p["cover"] - 1e-9))
		days = [o for o in range(horizon) if start <= self.today + datetime.timedelta(days=o) <= end]
		return 1 + (min(max(p["lift"], 1), 5) - 1) * len(days) / float(horizon), len(days)

	def test_planned_promotion_raises_the_forecast(self):
		rule = frappe.get_doc("Pricing Rule", self.ds["pricing_rules"]["PR2"])
		p = self.pair("PR2", "O1")
		f, n = self.expected_factor(p, getdate(rule.valid_from), getdate(rule.valid_upto))
		self.assertEqual(n, 5)
		self.assertEqual(p["promo_days_ahead"], n)
		self.assertAlmostEqual(p["promo_factor"], f, 9)
		self.assertAlmostEqual(p["forecast"], p["base_speed"] * p["season_factor"] * f, 9)
		self.assertEqual(p["promo_next"]["name"], rule.name)

	def test_rule_on_a_parent_group(self):
		rule = frappe.get_doc("Pricing Rule", self.ds["pricing_rules"]["PR3"])
		self.assertEqual(rule.item_groups[0].item_group, self.ds["promo_parent"])
		self.assertNotEqual(frappe.db.get_value("Item", self.it["PR3"], "item_group"), self.ds["promo_parent"])
		p = self.pair("PR3", "O1")
		f, n = self.expected_factor(p, getdate(rule.valid_from), getdate(rule.valid_upto))
		self.assertEqual((p["promo_days_ahead"], p["promo_next"]["name"]), (n, rule.name))
		self.assertAlmostEqual(p["promo_factor"], f, 9)

	def test_rules_that_do_not_count(self):
		# expired, no end date, another warehouse, disabled: none touch PR1 in O1
		p = self.pair("PR1", "O1")
		self.assertIsNone(p["promo_next"])
		self.assertEqual((p["promo_days_ahead"], p["promo_factor"]), (0, 1.0))
		self.assertAlmostEqual(p["forecast"], p["base_speed"] * p["season_factor"], 9)

	def test_report(self):
		rows = {(r["item_code"], r["warehouse"]): r for r in views.promotions(self.result, None)}
		r = rows[(self.it["PR2"], self.wh["O1"])]
		p = self.pair("PR2", "O1")
		self.assertEqual(r["lift"], 3.0)
		self.assertEqual(r["promo_days"], 5)
		plain = p["forecast"] / p["promo_factor"]
		self.assertAlmostEqual(r["extra_qty"], round((p["forecast"] - plain) * (p["lead_time"] + p["cover"]), 3), 6)
		self.assertEqual(r["next_source"], "ERPNext pricing rule")
		self.assertNotIn((self.it["A1"], self.wh["O1"]), rows)
		self.assertIsNone(rows[(self.it["PR1"], self.wh["O1"])]["extra_qty"])

	def test_switch_off(self):
		r = self.run_with(promotions=0)
		p1, p2 = self.pair("PR1", "O1", r), self.pair("PR2", "O1", r)
		self.assertEqual((p1["base_basis"], p1["promo_days"]), ("history", 0))
		self.assertEqual(p1["base_speed"], p1["speed"])
		self.assertEqual((p2["promo_factor"], p2["promo_next"]), (1.0, None))
