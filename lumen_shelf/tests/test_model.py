"""The arithmetic on its own, with hand-worked numbers."""

import datetime
import unittest

from lumen_shelf.restock import model

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


class TestModel020(unittest.TestCase):
	"""0.2.0 arithmetic, hand-worked."""

	def test_horizon_weeks(self):
		self.assertEqual(model.horizon_weeks(21), 3)
		self.assertEqual(model.horizon_weeks(2), 1)  # never under a week
		self.assertEqual(model.horizon_weeks(400), 13)  # never over a quarter

	def test_season_factor(self):
		self.assertAlmostEqual(model.season_factor(56, 8, 63, 3), 3.0)  # 7 a week, then 21
		self.assertEqual(model.season_factor(8, 8, 300, 1), 4.0)  # kept at 4 at most
		self.assertEqual(model.season_factor(80, 8, 0, 1), 0.25)  # and 0.25 at least
		self.assertIsNone(model.season_factor(0, 8, 10, 1))  # nothing to learn from

	def test_pick_calendar(self):
		self.assertEqual(model.pick_calendar({"Gregorian": 10.0, "Hijri": 4.0}, 12.0), "Hijri")
		self.assertIsNone(model.pick_calendar({"Gregorian": 13.0, "Hijri": None}, 12.0))  # worse than none
		self.assertIsNone(model.pick_calendar({"Gregorian": 12.0}, 12.0))  # a tie is no gain

	def test_trend(self):
		days = model.window_days(END, 4)  # 28 days, halves of 14
		stocked = set(days)
		sold = {d: (1.0 if i < 14 else 2.0) for i, d in enumerate(days)}
		self.assertAlmostEqual(model.trend(days, stocked, sold), 1.0)
		self.assertIsNone(model.trend(days, set(days[:9]) | set(days[14:]), sold))  # first half too thin
		self.assertIsNone(model.trend(days, stocked, {days[20]: 5.0}))  # nothing in the first half

	def test_out_of_stock_days(self):
		days = model.window_days(END, 2)
		stocked = set(days[3:6]) | set(days[8:])
		self.assertEqual(model.out_of_stock_days(days, stocked), 2)  # days 6 and 7, not 0 to 2
		self.assertEqual(model.out_of_stock_days(days, set()), 0)

	def test_accuracy(self):
		acc, bias = model.accuracy([(12.0, 10.0), (8.0, 10.0)])
		self.assertAlmostEqual(acc, 0.8)
		self.assertAlmostEqual(bias, 0.0)
		self.assertEqual(model.accuracy([(5.0, 0.0)]), (None, None))

	def test_fit_budget(self):
		lines = [{"cost": 60.0}, {"cost": 50.0}, {"cost": 30.0}]
		self.assertEqual(model.fit_budget(lines, 100.0), 90.0)
		self.assertEqual([l["in_budget"] for l in lines], [1, 0, 1])  # the second does not fit, the third does
		self.assertEqual([l["running_total"] for l in lines], [60.0, 60.0, 90.0])


class TestModel030(unittest.TestCase):
	"""0.3.0 arithmetic, hand-worked."""

	def test_demand_pattern(self):
		days = model.window_days(END, 2)
		stocked = set(days)
		smooth = {d: 2.0 for d in days}
		self.assertEqual(model.demand_pattern(days, stocked, smooth)[0], "Smooth")
		sparse = {d: 2.0 for d in days[::4]}  # every 4th day, same size
		pattern, adi, cv2 = model.demand_pattern(days, stocked, sparse)
		self.assertEqual((pattern, adi, cv2), ("Intermittent", 14 / 4.0, 0.0))
		lumpy = {d: (1.0 if i % 2 else 9.0) for i, d in enumerate(days[::3])}
		self.assertEqual(model.demand_pattern(days, stocked, lumpy)[0], "Lumpy")
		self.assertEqual(model.demand_pattern(days, stocked, {days[0]: 1.0}), (None, None, None))

	def test_sba(self):
		days = model.window_days(END, 2)
		sold = {days[1]: 4.0, days[5]: 4.0, days[9]: 4.0}
		# z stays 4. p: 2 at first, then 2 + 0.1 (4 - 2) = 2.2, then 2.2 + 0.1 (4 - 2.2) = 2.38
		self.assertAlmostEqual(model.sba(days, set(days), sold), 0.95 * 4 / 2.38)
		self.assertIsNone(model.sba(days, set(days), {days[3]: 1.0}))

	def test_shelf_life_cover(self):
		self.assertEqual(model.shelf_life_cover(14, 10, 7), 3.0)
		self.assertEqual(model.shelf_life_cover(14, 5, 7), 1.0)  # never under a day
		self.assertEqual(model.shelf_life_cover(14, 0, 7), 14)  # no shelf life: no cap

	def test_expiry_risk(self):
		today = END
		batches = [(today + datetime.timedelta(days=60), 30.0), (today + datetime.timedelta(days=5), 14.0)]
		self.assertAlmostEqual(model.expiry_risk(batches, 1.0, today), 9.0)  # 5 of 14 sell in time
		self.assertAlmostEqual(model.expiry_risk(batches, 0.0, today), 44.0)
		# what sold from the first batch is not sold again from the second
		close = [(today + datetime.timedelta(days=5), 3.0), (today + datetime.timedelta(days=6), 10.0)]
		self.assertAlmostEqual(model.expiry_risk(close, 1.0, today), 7.0)

	def test_dead_stock_action(self):
		self.assertEqual(model.dead_stock_action("O2", True, "X"), "Move")
		self.assertEqual(model.dead_stock_action(None, True, "X"), "Return to supplier")
		self.assertEqual(model.dead_stock_action(None, False, "X"), "Bundle")
		self.assertEqual(model.dead_stock_action(None, False, None), "Discount")

	def test_basket_pairs(self):
		baskets = [{"a", "b"}, {"a", "b"}, {"a", "b", "c"}, {"c"}]
		got = {(a, b): (n, c, l) for a, b, n, c, l in model.basket_pairs(baskets)}
		self.assertEqual(set(got), {("a", "b"), ("b", "a")})  # a and c only once together
		n, conf, lift = got[("a", "b")]
		self.assertEqual((n, conf), (3, 1.0))
		self.assertAlmostEqual(lift, 1.0 / (3 / 4.0))


class TestPromotionModel(unittest.TestCase):
	def promo(self, **kw):
		p = {
			"warehouses": set(), "all_items": 0, "items": set(), "groups": set(), "brands": set(),
			"exclude_items": set(), "exclude_groups": set(), "exclude_brands": set(), "weekdays": set(),
			"start": datetime.date(2026, 11, 2), "end": datetime.date(2026, 11, 8),
		}
		p.update(kw)
		return p

	def test_promotion_days_need_half_discounted(self):
		days = [datetime.date(2026, 10, d) for d in (1, 2, 3, 4)]
		by_day = {days[0]: (4, 40, 2), days[1]: (4, 40, 1.9), days[2]: (0, 0, 0), days[3]: (4, 40, 4)}
		self.assertEqual(model.promotion_days(days, set(days[:3]), by_day), {days[0]})

	def test_lift_needs_enough_days(self):
		days = [datetime.date(2026, 9, 1) + datetime.timedelta(days=i) for i in range(20)]
		sold = {d: 2.0 for d in days}
		promo = set(days[:3])
		for d in promo:
			sold[d] = 8.0
		self.assertEqual(model.lift(set(days), promo, sold), (4.0, 8.0, 2.0))
		self.assertIsNone(model.lift(set(days), set(days[:2]), sold))  # 2 promotion days
		self.assertIsNone(model.lift(set(days[:16]), promo, sold))  # 13 normal days

	def test_promotion_factor(self):
		self.assertEqual(model.promotion_factor(3.0, {0, 1, 5, 30}, 10), (1 + 2 * 3 / 10.0, 3))
		self.assertEqual(model.promotion_factor(9.0, {0}, 10), (1 + 4 / 10.0, 1))  # lift used up to 5
		self.assertEqual(model.promotion_factor(0.5, {0}, 10), (1.0, 1))  # a promotion never lowers it
		self.assertEqual(model.promotion_factor(None, {0, 1}, 10), (1.0, 2))

	def test_promotion_applies(self):
		groups = {"Drinks", "All Item Groups"}
		self.assertTrue(model.promotion_applies(self.promo(items={"A"}), "A", groups, None, "W1"))
		self.assertFalse(model.promotion_applies(self.promo(items={"A"}), "B", groups, None, "W1"))
		self.assertTrue(model.promotion_applies(self.promo(groups={"Drinks"}), "B", groups, None, "W1"))
		self.assertTrue(model.promotion_applies(self.promo(brands={"X"}), "B", groups, "X", "W1"))
		self.assertFalse(model.promotion_applies(self.promo(items={"A"}, warehouses={"W2"}), "A", groups, None, "W1"))
		self.assertTrue(model.promotion_applies(self.promo(all_items=1), "B", groups, None, "W1"))
		self.assertFalse(model.promotion_applies(self.promo(all_items=1, exclude_items={"B"}), "B", groups, None, "W1"))
		self.assertFalse(model.promotion_applies(self.promo(all_items=1, exclude_groups={"Drinks"}), "B", groups, None, "W1"))
		self.assertFalse(model.promotion_applies(self.promo(all_items=1, exclude_brands={"X"}), "B", groups, "X", "W1"))

	def test_promotion_offsets_and_weekdays(self):
		as_of = datetime.date(2026, 11, 1)  # a Sunday
		self.assertEqual(model.promotion_offsets([self.promo()], as_of, 30), {1, 2, 3, 4, 5, 6, 7})
		fridays = self.promo(weekdays={4})
		self.assertEqual(model.promotion_offsets([fridays], as_of, 30), {5})
		self.assertEqual(model.promotion_offsets([self.promo()], as_of, 3), {1, 2})
