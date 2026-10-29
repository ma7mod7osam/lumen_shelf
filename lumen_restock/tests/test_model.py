"""The arithmetic on its own, with hand-worked numbers."""

import datetime
import unittest

from lumen_restock.restock import model

END = datetime.date(2026, 10, 28)


class TestModel(unittest.TestCase):
	def test_window_ends_yesterday_and_spans_whole_weeks(self):
		days = model.window_days(END, 8)
		self.assertEqual((len(days), days[0], days[-1]), (56, datetime.date(2026, 9, 3), END))

	def test_week_weights(self):
		self.assertEqual(model.week_weight(END, END, 8), 8)
		self.assertEqual(model.week_weight(END - datetime.timedelta(days=6), END, 8), 8)
		self.assertEqual(model.week_weight(END - datetime.timedelta(days=7), END, 8), 7)
		self.assertEqual(model.week_weight(END - datetime.timedelta(days=55), END, 8), 1)

	def test_in_stock_day_rules(self):
		days = model.window_days(END, 2)
		d0, d1, d2 = days[0], days[1], days[2]
		ledger = {d0: (0.0, 5.0), d2: (4.0, 4.0)}  # emptied on d0, nothing on d1, restocked d2
		stocked = model.in_stock_days(days, 0.0, ledger, {})
		self.assertIn(d0, stocked)  # had 5 for part of the day
		self.assertNotIn(d1, stocked)  # empty all day
		self.assertIn(d2, stocked)
		self.assertIn(days[3], stocked)  # 4 carried over
		self.assertIn(d1, model.in_stock_days(days, 0.0, ledger, {d1: 1.0}))  # a sale proves stock

	def test_speed_leaves_out_empty_days(self):
		days = model.window_days(END, 1)
		sold = {days[0]: 7.0}
		speed, sigma, n = model.speed_and_sigma(days, {days[0]}, sold, END, 1)
		self.assertEqual((speed, sigma, n), (7.0, 0.0, 1))

	def test_levels(self):
		self.assertAlmostEqual(model.safety_stock(1.65, 2.0, 4), 6.6)
		self.assertEqual(model.reorder_point(2.0, 4, 6.6), 14.6)
		self.assertAlmostEqual(model.order_up_to(14.6, 2.0, 14), 42.6)
		self.assertTrue(model.is_running_low(1.0, 7.0, 7.0))
		self.assertFalse(model.is_running_low(0.0, -5.0, 0.0))  # no sales, nothing to restock

	def test_rounding(self):
		self.assertEqual(model.round_need(16.2, True), 17)
		self.assertEqual(model.round_surplus(16.8, True), 16)
		self.assertEqual(model.round_need(2.25, False), 2.25)
		self.assertEqual(model.round_to_pack(17, 6, 0), 18)
		self.assertEqual(model.round_to_pack(17, 6, 24), 24)
		self.assertEqual(model.round_to_pack(17, 0, 0), 17)
		self.assertEqual(model.round_to_pack(0, 6, 24), 0)

	def test_median(self):
		self.assertEqual(model.median([10, 4, 6, 6]), 6.0)
		self.assertEqual(model.median([4, 10]), 7.0)
		self.assertIsNone(model.median([]))

	def test_abc(self):
		self.assertEqual(
			model.abc_classes({"a": 700, "b": 200, "c": 60, "d": 40, "e": 0}),
			{"a": "A", "b": "A", "c": "B", "d": "C", "e": "C"},
		)
		self.assertEqual(model.abc_classes({"only": 5}), {"only": "A"})
