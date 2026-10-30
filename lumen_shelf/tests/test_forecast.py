"""0.2.0: seasons, trend, lost sales, the budget and forecast accuracy, each
checked against ERPNext's own documents (tests/oracle.py), one test per rule
so a deliberate break of one rule (dev/mutations.py) fails its own test."""

import datetime

import frappe
from frappe.utils import flt

from lumen_shelf.restock import settings as st
from lumen_shelf.restock import views
from lumen_shelf.tests import fixtures, oracle
from lumen_shelf.tests.test_restock import Z95, RestockCase, set_settings

COVER = 14


def ahead_weeks(lead):
	"""The weeks a suggestion covers, lead time + cover, in whole weeks (1 to 13)."""
	return max(1, min(13, int(round((lead + COVER) / 7.0))))


class TestForecast(RestockCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.today = fixtures.today()
		cls.all_sold = oracle.invoices(cls.company, fixtures.d(440), fixtures.d(1))
		cls.whs = sorted(cls.wh.values())

	def run_with(self, **values):
		set_settings(self.company, self.wh["M"], **values)
		try:
			return self.compute()
		finally:
			set_settings(self.company, self.wh["M"])

	def keys(self, *names):
		return [(self.it[n], w) for n in names for w in self.whs]

	def check_levels(self, p, f):
		"""Expected daily sales = history x season, and the levels follow it."""
		self.assertAlmostEqual(p["forecast"], p["speed"] * f, 9)
		lv = oracle.levels(p["speed"] * f, p["sigma"] * f, p["lead_time"], Z95, COVER)
		self.assertAlmostEqual(p["rop"], lv.rop, 6)
		self.assertAlmostEqual(p["target"], lv.target, 6)

	# ---- seasons

	def test_season_gregorian(self):
		r = self.run_with(season_calendar=st.CAL_GREGORIAN)
		self.assertEqual((r["season"]["calendar"], r["season"]["basis"]), (st.CAL_GREGORIAN, "set"))
		p = self.pair("S1", "O1", r)
		ref = self.today - datetime.timedelta(days=364)
		f, base = oracle.season_ratio(self.all_sold, self.keys("S1"), ref, 8, ahead_weeks(p["lead_time"]))
		self.assertGreaterEqual(base, 20)
		self.assertAlmostEqual(f, 3.0, 6)  # 1 a day, then 3 a day
		self.assertAlmostEqual(p["season_factor"], f, 9)
		self.assertEqual(p["season_basis"], "item")
		self.assertGreater(p["sigma"], 0)  # its sales swing, so the safety stock shows the season too
		self.check_levels(p, f)

	def test_season_hijri(self):
		r = self.run_with(season_calendar=st.CAL_HIJRI)
		p = self.pair("S2", "O1", r)
		ref = self.today - datetime.timedelta(days=354)
		f, _base = oracle.season_ratio(self.all_sold, self.keys("S2"), ref, 8, ahead_weeks(p["lead_time"]))
		self.assertAlmostEqual(f, 3.0, 6)
		self.assertAlmostEqual(p["season_factor"], f, 9)
		self.assertEqual(p["season_basis"], "item")
		self.check_levels(p, f)

	def test_season_falls_back_to_group(self):
		r = self.run_with(season_calendar=st.CAL_GREGORIAN)
		p = self.pair("S3", "O1", r)
		ref = self.today - datetime.timedelta(days=364)
		hw = ahead_weeks(p["lead_time"])
		own, own_base = oracle.season_ratio(self.all_sold, self.keys("S3"), ref, 8, hw)
		self.assertLess(own_base, 20)  # S3 has no history of its own
		f, base = oracle.season_ratio(self.all_sold, self.keys("S1", "S2", "S3"), ref, 8, hw)
		self.assertGreaterEqual(base, 50)
		self.assertAlmostEqual(p["season_factor"], f, 9)
		self.assertEqual(p["season_basis"], "group")
		self.check_levels(p, f)
		# an item of another group with no history keeps a factor of 1
		a1 = self.pair("A1", "O1", r)
		self.assertEqual((a1["season_factor"], a1["season_basis"]), (1.0, None))

	def test_season_switch_off(self):
		r = self.run_with(seasonality=0, season_calendar=st.CAL_GREGORIAN)
		self.assertEqual(r["season"]["basis"], "off")
		p = self.pair("S1", "O1", r)
		self.assertEqual((p["season_factor"], p["season_basis"]), (1.0, None))
		self.check_levels(p, 1.0)

	def test_season_automatic_choice(self):
		"""Each calendar forecasts the company's last 8 weeks, 2 weeks at a
		time, from the 8 weeks before each. The best one is used, if it beats
		no seasons at all."""
		errors = {st.CAL_GREGORIAN: 0.0, st.CAL_HIJRI: 0.0}
		shifts = {st.CAL_GREGORIAN: 364, st.CAL_HIJRI: 354}
		none_err = 0.0
		for t in range(4):
			test, base = (2 * t, 2 * t + 1), range(2 * t + 2, 2 * t + 10)
			actual = sum(oracle.company_week(self.all_sold, self.today, k) for k in test)
			rate = sum(oracle.company_week(self.all_sold, self.today, k) for k in base) / 8.0
			none_err += abs(rate * 2 - actual)
			for cal, shift in shifts.items():
				if errors[cal] is None:
					continue
				ref = self.today - datetime.timedelta(days=shift)
				ly_base = sum(oracle.company_week(self.all_sold, ref, k) for k in base)
				ly_test = sum(oracle.company_week(self.all_sold, ref, k) for k in test)
				if ly_base <= 0:
					errors[cal] = None
					continue
				f = min(max((ly_test / 2.0) / (ly_base / 8.0), 0.25), 4.0)
				errors[cal] += abs(rate * 2 * f - actual)
		got = self.result["season"]
		self.assertAlmostEqual(got["errors"]["none"], none_err, 6)
		for cal in shifts:
			if errors[cal] is None:
				self.assertIsNone(got["errors"][cal])
			else:
				self.assertAlmostEqual(got["errors"][cal], errors[cal], 6)
		best = min((e, c) for c, e in errors.items() if e is not None)
		expected = best[1] if best[0] < none_err - 1e-9 else None
		self.assertEqual(got["calendar"], expected)

	# ---- trend

	def halves(self, name, wh):
		o = self.oracle_figures(name, wh)
		days = sorted(o.stocked)
		start = self.start + datetime.timedelta(days=28)
		sold = {k: v[0] for k, v in self.sold.get((self.it[name], self.wh[wh]), {}).items()}
		first = [d for d in days if d < start]
		second = [d for d in days if d >= start]
		return (sum(sold.get(d, 0) for d in first), len(first)), (sum(sold.get(d, 0) for d in second), len(second))

	def test_trend_rising_and_falling(self):
		for name, expected, status in (("T1", 1.0, "Rising"), ("T2", -0.5, "Falling")):
			(q0, n0), (q1, n1) = self.halves(name, "O1")
			change = (q1 / n1) / (q0 / n0) - 1
			self.assertAlmostEqual(change, expected, 6)
			p = self.pair(name, "O1")
			self.assertAlmostEqual(p["trend"], change, 9)
			self.assertEqual(p["trend_status"], status)
		self.assertEqual(self.pair("A1", "O1")["trend_status"], "")  # 2 a day all along

	def test_trend_threshold(self):
		r = self.run_with(trend_threshold=150)
		self.assertEqual(self.pair("T1", "O1", r)["trend_status"], "")  # +100% is under 150%
		self.assertEqual(self.pair("T2", "O1", r)["trend_status"], "")

	def test_trend_switch_off(self):
		r = self.run_with(trends=0)
		p = self.pair("T1", "O1", r)
		self.assertIsNone(p["trend"])
		self.assertEqual(p["trend_status"], "")

	# ---- lost sales

	def test_lost_sales(self):
		o = self.oracle_figures("A2", "O1")
		window = [self.start + datetime.timedelta(days=i) for i in range(56)]
		first = min(o.stocked)
		out_days = sum(1 for d in window if d >= first and d not in o.stocked)
		self.assertEqual(out_days, 17)
		p = self.pair("A2", "O1")
		self.assertAlmostEqual(p["lost_qty"], o.speed * out_days, 6)
		self.assertAlmostEqual(p["lost_value"], o.speed * out_days * o.sales_value / o.sold_qty, 6)
		self.assertEqual(self.pair("A2", "M")["lost_qty"], 0.0)  # outlets only

	def test_lost_sales_switch_off(self):
		r = self.run_with(lost_sales=0)
		p = self.pair("A2", "O1", r)
		self.assertEqual((p["lost_qty"], p["lost_value"]), (0.0, 0.0))

	# ---- budget

	def unit_cost(self, item, wh):
		rate = flt(frappe.db.get_value("Item", item, "last_purchase_rate"))
		return rate or flt(oracle.bin_row(item, wh).valuation_rate)

	def test_purchase_cost(self):
		rows = views.running_low(self.result, None)
		buying = [r for r in rows if r["buy_qty"]]
		self.assertTrue(buying)
		for r in buying:
			self.assertAlmostEqual(r["buy_cost"], round(r["buy_qty"] * self.unit_cost(r["item_code"], r["warehouse"]), 2), 2)
		self.assertTrue(any(flt(frappe.db.get_value("Item", r["item_code"], "last_purchase_rate")) for r in buying))

	def test_budget_plan(self):
		rows = views.running_low(self.result, None)
		total = sum(r["buy_cost"] or 0 for r in rows)
		budget = total / 2.0
		rows = views.running_low(self.result, None, budget=budget)
		spent = 0.0
		last_urgent = 0
		for r in rows:
			urgent = 0 if (r["days_left"] or 0) <= (r["lead_time"] or 0) + 1e-9 else 1
			self.assertGreaterEqual(urgent, last_urgent)  # what runs out first comes first
			last_urgent = urgent
			if not r["buy_qty"]:
				self.assertIsNone(r["in_budget"])
				continue
			if r["in_budget"]:
				spent += r["buy_cost"]
			else:
				self.assertGreater(spent + r["buy_cost"], budget)  # skipped only if it does not fit
			self.assertAlmostEqual(r["running_total"], round(spent, 2), 2)
		self.assertLessEqual(spent, budget + 1e-6)
		self.assertTrue(0 < sum(1 for r in rows if r["in_budget"]) < sum(1 for r in rows if r["buy_qty"]))

	def test_budget_switch_off(self):
		r = self.run_with(budget_plan=0)
		rows = views.running_low(r, None, budget=10 ** 9)
		self.assertTrue(all(row["in_budget"] is None for row in rows))

	# ---- accuracy

	def test_forecast_accuracy(self):
		rows, stats = views.accuracy(self.result, None)
		then = self.today - datetime.timedelta(days=14)
		row = [r for r in rows if r["item_code"] == self.it["A1"] and r["warehouse"] == self.wh["O1"]][0]
		actual = oracle.qty_between(self.all_sold, [(self.it["A1"], self.wh["O1"])], then, self.today - datetime.timedelta(days=1))
		self.assertEqual(actual, 28)
		self.assertAlmostEqual(row["actual_qty"], actual, 6)
		old = oracle.figures(self.it["A1"], self.wh["O1"], then, 8, self.all_sold)
		self.assertAlmostEqual(row["forecast_qty"], round(old.speed * 14, 2), 2)
		self.assertAlmostEqual(row["plain_qty"], round(old.sold_qty_window * 14 / 56.0, 2), 2)
		err = sum(abs(r["forecast_qty"] - r["actual_qty"]) for r in rows)
		total = sum(r["actual_qty"] for r in rows)
		self.assertAlmostEqual(stats["accuracy"], max(0.0, 1 - err / total), 2)
		self.assertAlmostEqual(stats["bias"], sum(r["forecast_qty"] - r["actual_qty"] for r in rows) / total, 2)

	def test_accuracy_leaves_out_empty_shelves(self):
		rows, _stats = views.accuracy(self.result, None)
		shown = {(r["item_code"], r["warehouse"]) for r in rows}
		last14 = [self.today - datetime.timedelta(days=i) for i in range(14, 0, -1)]
		checked = 0
		for name in ("A2", "A3", "A4", "A5", "A6", "L1", "L2", "L3", "X1", "X2", "X6", "SO1"):
			for wh in ("O1", "O2", "O3"):
				key = (self.it[name], self.wh[wh])
				days = oracle.stocked_days(key[0], key[1], last14, self.all_sold)
				if len(days) < 14:
					self.assertNotIn(key, shown)
					checked += 1
		self.assertGreater(checked, 0)
		# E1 sold before and after its empty days: left out all the same
		e1 = (self.it["E1"], self.wh["O1"])
		self.assertEqual(len(oracle.stocked_days(e1[0], e1[1], last14, self.all_sold)), 9)
		self.assertNotIn(e1, shown)
