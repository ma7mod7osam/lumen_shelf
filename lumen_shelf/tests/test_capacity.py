"""0.8.0 shelf capacity: ERPNext's Putaway Rule (how much of an item a
warehouse can hold) caps what a suggestion fills the warehouse up to. Checked
against the Putaway Rules themselves, one test per rule, for dev/mutations.py."""

import math

import frappe
from frappe.utils import flt

from lumen_shelf.restock import views
from lumen_shelf.tests import oracle
from lumen_shelf.tests.test_restock import Z95, RestockCase, set_settings


class TestCapacity(RestockCase):
	def capacity(self, name):
		return flt(frappe.db.get_value("Putaway Rule", self.ds["putaway_rules"][name], "stock_capacity"))

	def raw_target(self, p):
		return oracle.levels(p["forecast"], p["base_sigma"] * p["season_factor"], p["lead_time"], Z95, p["cover"]).target

	def run_with(self, **values):
		set_settings(self.company, self.wh["M"], **values)
		try:
			return self.compute()
		finally:
			set_settings(self.company, self.wh["M"])

	def test_capacity_caps_the_target(self):
		cap = self.capacity("CP1")
		self.assertEqual(cap, 15)
		p = self.pair("CP1", "O1")
		self.assertEqual(p["capacity"], cap)
		self.assertGreater(self.raw_target(p), cap)
		self.assertEqual((p["target"], p["capped"]), (cap, 1))
		buy = self.lines("CP1", kind="buy")
		self.assertEqual(len(buy), 1)
		self.assertEqual(buy[0]["qty"], math.ceil(cap - p["position"]))
		self.assertLessEqual(p["position"] + buy[0]["qty"], cap)

	def test_pack_rounds_down_to_fit(self):
		cap = self.capacity("CP2")
		p = self.pair("CP2", "O1")
		room = cap - p["position"]
		buy = self.lines("CP2", kind="buy")[0]
		# up to whole boxes of 6 would overflow: as many whole boxes as fit
		self.assertGreater(math.ceil(room / 6.0) * 6, room)
		self.assertEqual(buy["qty"], math.floor(room / 6.0) * 6)
		self.assertEqual((buy["purchase_qty"], buy["purchase_uom"]), (buy["qty"] / 6, "Box"))
		self.assertLessEqual(p["position"] + buy["qty"], cap)

	def test_full_shelf_is_not_running_low(self):
		cap = self.capacity("CP3")
		p = self.pair("CP3", "O1")
		self.assertEqual(p["position"], cap)
		self.assertLessEqual(p["position"], p["rop"])  # below the reorder point, but the shelf is full
		self.assertEqual((p["low"], p["need"]), (0, 0.0))
		self.assertFalse(self.lines("CP3"))

	def test_disabled_rule_is_left_out(self):
		p = self.pair("CP4", "O1")
		self.assertTrue(frappe.db.get_value("Putaway Rule", self.ds["putaway_rules"]["CP4"], "disable"))
		self.assertIsNone(p["capacity"])
		self.assertAlmostEqual(p["target"], self.raw_target(p), 9)

	def test_running_low_shows_it(self):
		rows = {(r["item_code"], r["warehouse"]): r for r in views.running_low(self.result, None)}
		self.assertEqual(rows[(self.it["CP1"], self.wh["O1"])]["capacity"], 15)
		self.assertIsNone(rows[(self.it["CP4"], self.wh["O1"])]["capacity"])

	def test_switch_off(self):
		r = self.run_with(shelf_capacity=0)
		p = self.pair("CP1", "O1", r)
		self.assertIsNone(p["capacity"])
		self.assertAlmostEqual(p["target"], self.raw_target(p), 9)
		self.assertTrue(self.pair("CP3", "O1", r)["low"])
