"""Phase 3, automatic mode: Lumen Shelf keeps ERPNext's Item Reorder levels up
to date and ERPNext's own nightly job (erpnext.stock.reorder_item) raises the
requests. Checked against ERPNext itself: its Item form accepts the rows, its
own job raises exactly what the levels and its projected qty say. One test per
rule, for dev/mutations.py.

Every test works inside a savepoint and rolls back."""

import math
from unittest import mock

import frappe
from frappe.utils import flt

from lumen_shelf.restock import engine, reorder
from lumen_shelf.restock import settings as st
from lumen_shelf.tests.test_access import make_user
from lumen_shelf.tests.test_restock import RestockCase, set_settings

SP = "rs_reorder"


def qualifies(p):
	return (
		p.get("rop", 0.0) > 1e-9
		and p.get("forecast", 0.0) > 1e-9
		and (p["eligible"] or p.get("base_basis") in ("similar brand", "similar group"))
	)


def expected_qty(p):
	gap = p["target"] - p["rop"]
	if p.get("plan") == "transfer":
		return float(math.ceil(gap - 1e-9)) if p["whole"] else round(gap, 3)
	gap = max(gap, p["min_order_qty"] or 0.0)
	if p["pack"]:
		return math.ceil(gap / p["pack"] - 1e-9) * p["pack"]
	return float(math.ceil(gap - 1e-9))


class TestReorder(RestockCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(SP)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=SP)
		engine.forget(self.company)

	def rows(self):
		"""The Item Reorder table as ERPNext keeps it, for the day's items."""
		got = frappe.db.sql(
			"""select name, parent, warehouse, warehouse_group, warehouse_reorder_level, warehouse_reorder_qty,
				material_request_type, ifnull(lumen_shelf_managed, 0) as managed
			from `tabItem Reorder` where parenttype = 'Item' and parent in %s""",
			(tuple(self.items),),
			as_dict=True,
		)
		return {(r.parent, r.warehouse): r for r in got}

	def raw_row(self, name, wh, level, qty, managed, rtype="Purchase"):
		idx = (frappe.db.sql("select max(idx) from `tabItem Reorder` where parent=%s", self.it[name])[0][0] or 0) + 1
		frappe.get_doc(
			{
				"doctype": "Item Reorder",
				"parent": self.it[name],
				"parenttype": "Item",
				"parentfield": "reorder_levels",
				"idx": idx,
				"warehouse": self.wh[wh],
				"warehouse_group": self.wh[wh],
				"warehouse_reorder_level": level,
				"warehouse_reorder_qty": qty,
				"material_request_type": rtype,
				"lumen_shelf_managed": managed,
			}
		).db_insert()

	# ---- the levels

	def test_field_installed(self):
		self.assertTrue(frappe.db.has_column("Item Reorder", "lumen_shelf_managed"))
		self.assertTrue(frappe.get_meta("Item Reorder").get_field("lumen_shelf_managed").read_only)

	def test_levels_follow_the_forecast(self):
		stats = reorder.apply(self.result)
		got = self.rows()
		want = [p for p in self.result["pairs"] if qualifies(p) and expected_qty(p) > 1e-9]
		self.assertTrue(want)
		self.assertEqual({k for k, r in got.items() if r.managed}, {(p["item_code"], p["warehouse"]) for p in want})
		self.assertEqual(stats["set"], len(want))
		for p in want:
			r = got[(p["item_code"], p["warehouse"])]
			key = (p["item_code"], p["warehouse"])
			self.assertAlmostEqual(flt(r.warehouse_reorder_level), round(p["rop"], 3), 6, key)
			self.assertAlmostEqual(flt(r.warehouse_reorder_qty), expected_qty(p), 6, key)
			self.assertEqual(r.material_request_type, "Transfer" if p["plan"] == "transfer" else "Purchase", key)
			self.assertEqual(r.warehouse_group, p["warehouse"])
		self.assertEqual(stats["running_low"], sum(1 for p in want if p["low"]))

	def test_no_level_without_reorder_point(self):
		base = {"item_code": "x", "warehouse": "w", "eligible": 1, "plan": "buy", "pack": 0.0, "min_order_qty": 0.0, "whole": 1}
		ok = dict(base, rop=4.0, target=10.0, forecast=1.0)
		no_rop = dict(base, rop=0.0, target=5.0, forecast=1.0)
		self.assertEqual(reorder.wanted({"pairs": [ok]}), {("x", "w"): (4.0, 6.0, "Purchase")})
		self.assertEqual(reorder.wanted({"pairs": [no_rop]}), {})

	def test_pack_and_min_order(self):
		reorder.apply(self.result)
		got = self.rows()
		a3 = [r for k, r in got.items() if k[0] == self.it["A3"]]
		a5 = [r for k, r in got.items() if k[0] == self.it["A5"]]
		self.assertTrue(a3 and a5)
		for r in a3 + a5:
			self.assertEqual(flt(r.warehouse_reorder_qty) % 6, 0)
		for r in a5:
			self.assertGreaterEqual(flt(r.warehouse_reorder_qty), 24)

	def test_transfer_or_purchase(self):
		reorder.apply(self.result)
		got = self.rows()
		self.assertEqual(self.pair("X1", "O2")["plan"], "transfer")
		self.assertEqual(got[(self.it["X1"], self.wh["O2"])].material_request_type, "Transfer")
		self.assertEqual(got[(self.it["L1"], self.wh["O1"])].material_request_type, "Purchase")
		main = [r for k, r in got.items() if k[1] == self.wh["M"]]
		self.assertTrue(main)
		self.assertTrue(all(r.material_request_type == "Purchase" for r in main))

	def test_erpnext_item_form_accepts_them(self):
		reorder.apply(self.result)
		item = frappe.get_doc("Item", self.it["A3"])
		self.assertTrue([d for d in item.reorder_levels if d.lumen_shelf_managed])
		item.save()  # ERPNext's own checks on the reorder table
		self.assertTrue([d for d in frappe.get_doc("Item", self.it["A3"]).reorder_levels if d.lumen_shelf_managed])

	def test_a_level_set_by_the_shop_is_kept(self):
		key = (self.it["L1"], self.wh["O1"])
		self.raw_row("L1", "O1", 1, 2, 0)
		stats = reorder.apply(self.result)
		r = self.rows()[key]
		self.assertEqual((r.managed, flt(r.warehouse_reorder_level), flt(r.warehouse_reorder_qty)), (0, 1, 2))
		self.assertGreaterEqual(stats["kept"], 1)
		# and one of ours already there beside it goes
		key2 = (self.it["A3"], self.wh["O1"])
		self.assertTrue(self.rows()[key2].managed)
		self.raw_row("A3", "O1", 1, 6, 0, rtype="Material Issue")
		reorder.apply(self.result)
		left = frappe.db.sql(
			"select ifnull(lumen_shelf_managed, 0) from `tabItem Reorder` where parent=%s and warehouse=%s", key2
		)
		self.assertEqual([x[0] for x in left], [0])

	def test_second_run_and_repair(self):
		first = reorder.apply(self.result)
		again = reorder.apply(self.result)
		self.assertEqual((again["set"], again["removed"], again["unchanged"]), (0, 0, first["set"]))
		key = (self.it["L1"], self.wh["O1"])
		frappe.db.set_value("Item Reorder", self.rows()[key].name, "warehouse_reorder_level", 999)
		self.assertEqual(reorder.apply(self.result)["set"], 1)
		self.assertAlmostEqual(flt(self.rows()[key].warehouse_reorder_level), round(self.pair("L1", "O1")["rop"], 3), 6)
		# a level of ours that is no longer wanted is removed
		self.assertFalse(qualifies(self.pair("H2", "HL")))
		self.raw_row("H2", "HL", 5, 5, 1)
		self.assertEqual(reorder.apply(self.result)["removed"], 1)
		self.assertNotIn((self.it["H2"], self.wh["HL"]), self.rows())

	def test_left_out_warehouse(self):
		reorder.apply(self.result)
		self.assertTrue([k for k in self.rows() if k[1] == self.wh["O3"]])
		doc = frappe.get_doc(st.DOCTYPE)
		doc.append("warehouses", {"company": self.company, "warehouse": self.wh["O3"], "warehouse_role": st.ROLE_LEAVE_OUT})
		doc.save(ignore_permissions=True)
		reorder.apply(self.compute())
		self.assertFalse([k for k in self.rows() if k[1] == self.wh["O3"]])

	# ---- what ERPNext does with them

	def test_erpnext_raises_the_requests(self):
		from erpnext.stock.reorder_item import reorder_item

		reorder.apply(self.result)
		ours = {k: r for k, r in self.rows().items() if r.managed}
		# ERPNext's projected qty as its job will read it, before the job raises anything
		projected_of = {
			k: flt(frappe.db.get_value("Bin", {"item_code": k[0], "warehouse": k[1]}, "projected_qty")) for k in ours
		}
		frappe.db.set_value("Stock Settings", "Stock Settings", {"auto_indent": 1, "reorder_email_notify": 0})
		before = set(frappe.get_all("Material Request", pluck="name"))
		reorder_item()
		new = [n for n in frappe.get_all("Material Request", filters={"company": self.company}, pluck="name") if n not in before]
		raised = {}
		for n in new:
			mr = frappe.get_doc("Material Request", n)
			for i in mr.items:
				raised[(i.item_code, i.warehouse)] = (flt(i.stock_qty), mr.material_request_type)
		pairs = {(p["item_code"], p["warehouse"]): p for p in self.result["pairs"]}
		checked = agree = 0
		for key, r in ours.items():
			projected = projected_of[key]
			level, qty = flt(r.warehouse_reorder_level), flt(r.warehouse_reorder_qty)
			if abs(projected - level) <= 1e-6:
				continue  # v13 raises below the level, v14+ at it too
			if projected > level:
				self.assertNotIn(key, raised, key)
				continue
			self.assertIn(key, raised, key)
			want = max(qty, level - projected)
			p = pairs[key]
			factor = p["pack"] if (r.material_request_type == "Purchase" and p["pack"]) else 1.0
			uom = p["purchase_uom"] if factor != 1.0 else p["stock_uom"]
			if frappe.db.get_value("UOM", uom, "must_be_whole_number"):
				want = math.ceil(want / factor) * factor
			self.assertAlmostEqual(raised[key][0], want, 6, key)
			self.assertEqual(raised[key][1], "Material Transfer" if r.material_request_type == "Transfer" else "Purchase")
			checked += 1
		self.assertGreater(checked, 0)
		# where ERPNext's projected qty is Lumen Shelf's position, both agree on what is running low
		for key, r in ours.items():
			p = pairs[key]
			projected = projected_of[key]
			if abs(projected - p["position"]) > 1e-6 or abs(projected - flt(r.warehouse_reorder_level)) <= 1e-6:
				continue
			self.assertEqual(key in raised, bool(p["low"]), key)
			agree += 1
		self.assertGreater(agree, 0)

	# ---- switching on and off

	def test_switching_on_and_off(self):
		frappe.db.set_value("Stock Settings", "Stock Settings", "auto_indent", 0)
		set_settings(self.company, self.wh["M"], auto_reorder=1)
		self.assertEqual(frappe.db.get_single_value("Stock Settings", "auto_indent"), 1)
		reorder.apply(self.result)
		self.raw_row("L1", "O1", 1, 2, 0)
		self.assertTrue([r for r in self.rows().values() if r.managed])
		set_settings(self.company, self.wh["M"], auto_reorder=0)
		self.assertFalse([r for r in self.rows().values() if r.managed])
		self.assertIn((self.it["L1"], self.wh["O1"]), self.rows())  # the shop's own level stays
		# the app switched off removes them too
		set_settings(self.company, self.wh["M"], auto_reorder=1)
		reorder.apply(self.result)
		set_settings(self.company, self.wh["M"], auto_reorder=1, enabled=0)
		self.assertFalse([r for r in self.rows().values() if r.managed])

	def test_run_records_and_alerts(self):
		manager = make_user("rs-shelf-mgr-%s@example.com" % self.ds.suffix, ["Stock User", "Shelf Manager"])
		set_settings(self.company, self.wh["M"], auto_reorder=1)
		self.assertIn(manager, reorder.alert_users())
		before = frappe.db.count("Notification Log", {"for_user": manager})
		totals = reorder.run(companies=[self.company])
		self.assertGreater(totals["set"], 0)
		self.assertEqual(frappe.db.get_single_value(st.DOCTYPE, "last_reorder_result"), reorder.summary(totals))
		self.assertTrue(frappe.db.get_single_value(st.DOCTYPE, "last_reorder_run"))
		self.assertEqual(frappe.db.count("Notification Log", {"for_user": manager}), before + 1)
		set_settings(self.company, self.wh["M"], auto_reorder=1, reorder_alerts=0)
		reorder.run(companies=[self.company])
		self.assertEqual(frappe.db.count("Notification Log", {"for_user": manager}), before + 1)

	def test_nightly(self):
		self.assertIn("lumen_shelf.restock.reorder.nightly", frappe.get_hooks("scheduler_events")["cron"]["15 0 * * *"])
		reorder.apply(self.result)
		with mock.patch.object(reorder.frappe, "enqueue") as enq:
			reorder.nightly()  # automatic mode off: clears, starts nothing
			self.assertFalse(enq.called)
			self.assertFalse([r for r in self.rows().values() if r.managed])
			set_settings(self.company, self.wh["M"], auto_reorder=1)
			reorder.nightly()
			enq.assert_called_once()
			self.assertEqual(enq.call_args[0][0], "lumen_shelf.restock.reorder.run")

	def test_update_now_who_may(self):
		sfx = self.ds.suffix
		viewer = make_user("rs-viewer-%s@example.com" % sfx, ["Stock User", "Shelf User"])
		bare = make_user("rs-bare-mgr-%s@example.com" % sfx, ["Shelf Manager"])
		items = make_user("rs-item-mgr-%s@example.com" % sfx, ["Stock User", "Shelf User", "Item Manager"])
		with self.assertRaises(frappe.ValidationError):
			reorder.update_now()  # automatic mode off
		set_settings(self.company, self.wh["M"], auto_reorder=1)
		frappe.set_user(viewer)
		with self.assertRaises(frappe.PermissionError):
			reorder.update_now()
		# may change items in ERPNext, but has no role for Lumen Shelf's settings
		self.assertTrue(frappe.has_permission("Item", "write", user=items))
		frappe.set_user(items)
		with self.assertRaises(frappe.PermissionError):
			reorder.update_now()
		frappe.set_user(bare)  # may change the settings, but not ERPNext's items
		with self.assertRaises(frappe.PermissionError):
			reorder.update_now()
		frappe.set_user("Administrator")
		with mock.patch.object(reorder, "run", return_value={"set": 1, "unchanged": 2, "removed": 3, "kept": 4, "running_low": 5}):
			self.assertEqual(reorder.update_now(), reorder.summary({"set": 1, "unchanged": 2, "removed": 3, "kept": 4, "running_low": 5}))
