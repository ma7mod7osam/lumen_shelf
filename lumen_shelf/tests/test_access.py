"""Who may see what: switches, roles, the hook for other apps, Company and
Warehouse User Permissions, the reports through Frappe's own report runner,
and the API contract LumenPOS will call."""

import unittest
from unittest import mock

import frappe

from lumen_shelf import api
from lumen_shelf.restock import access, views
from lumen_shelf.tests import fixtures
from lumen_shelf.tests.test_restock import set_settings


def make_user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0, "user_type": "System User"}
		).insert(ignore_permissions=True)
	user = frappe.get_doc("User", email)
	user.set("roles", [])
	for r in roles:
		user.append("roles", {"role": r})
	user.save(ignore_permissions=True)
	return email


def limit(user, doctype, name):
	if not frappe.db.exists("User Permission", {"user": user, "allow": doctype, "for_value": name}):
		frappe.get_doc(
			{"doctype": "User Permission", "user": user, "allow": doctype, "for_value": name, "apply_to_all_doctypes": 1}
		).insert(ignore_permissions=True)


class TestAccess(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")
		cls.ds = fixtures.dataset()
		cls.company = cls.ds.company
		cls.wh = cls.ds.warehouses
		set_settings(cls.company, cls.wh["M"])
		sfx = cls.ds.suffix
		cls.nobody = make_user("rs-nobody-%s@example.com" % sfx, ["Stock User"])
		cls.viewer = make_user("rs-viewer-%s@example.com" % sfx, ["Stock User", "Shelf User"])
		cls.outlet = make_user("rs-outlet-%s@example.com" % sfx, ["Stock User", "Shelf User"])
		limit(cls.outlet, "Warehouse", cls.wh["O2"])
		if not frappe.db.exists("Role", "RS Till Manager"):
			frappe.get_doc({"doctype": "Role", "role_name": "RS Till Manager", "desk_access": 1}).insert(ignore_permissions=True)
		cls.hooked = make_user("rs-hooked-%s@example.com" % sfx, ["Stock User", "RS Till Manager"])
		other, _abbr = fixtures.make_company("other " + sfx, abbr="O" + sfx[:5].upper())
		cls.other_company = other
		cls.elsewhere = make_user("rs-elsewhere-%s@example.com" % sfx, ["Stock User", "Shelf User"])
		limit(cls.elsewhere, "Company", other)
		frappe.db.commit()

	def tearDown(self):
		frappe.set_user("Administrator")
		set_settings(self.company, self.wh["M"])

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		set_settings()

	def items(self):
		return sorted(self.ds["items"].values())

	def test_role_required(self):
		frappe.set_user(self.nobody)
		with self.assertRaises(frappe.PermissionError):
			views.load("running_low", self.company, items=self.items(), use_cache=False)
		self.assertEqual(api.running_low(self.company)["status"], "forbidden")
		self.assertEqual(api.state()["can_view"], 0)

	def test_viewer_role_sees(self):
		frappe.set_user(self.viewer)
		result, allowed = views.load("running_low", self.company, items=self.items(), use_cache=False)
		self.assertIsNone(allowed)
		rows = views.running_low(result, allowed)
		self.assertTrue(rows)
		self.assertEqual(api.state()["can_view"], 1)

	def test_warehouse_permission(self):
		frappe.set_user(self.outlet)
		result, allowed = views.load("running_low", self.company, items=self.items(), use_cache=False)
		self.assertEqual(allowed, {self.wh["O2"]})
		low = views.running_low(result, allowed)
		self.assertTrue(low)
		self.assertEqual({r["warehouse"] for r in low}, {self.wh["O2"]})
		moves = views.transfers(result, allowed)
		self.assertTrue(moves)
		for r in moves:
			self.assertIn(self.wh["O2"], (r["from_warehouse"], r["to_warehouse"]))
		health = views.stock_health(result, allowed)
		self.assertEqual({r["warehouse"] for r in health}, {self.wh["O2"]})
		self.assertEqual(api.running_low(self.company, warehouse=self.wh["O1"])["status"], "forbidden")

	def test_company_permission(self):
		frappe.set_user(self.elsewhere)
		with self.assertRaises(frappe.PermissionError):
			access.check_company(self.company)
		access.check_company(self.other_company)

	def test_switch_off(self):
		set_settings(self.company, self.wh["M"], enabled=0)
		frappe.set_user(self.viewer)
		with self.assertRaises(frappe.ValidationError):
			views.load("running_low", self.company, use_cache=False)
		self.assertEqual(api.running_low(self.company)["status"], "disabled")
		self.assertEqual(api.state()["enabled"], 0)
		self.assertFalse(access.can_view())

	def test_feature_switches(self):
		set_settings(
			self.company,
			self.wh["M"],
			outlet_transfers=0,
			stock_health=0,
			forecast_accuracy=0,
			bought_together=0,
			assortment_gaps=0,
			promotions=0,
		)
		frappe.set_user(self.viewer)
		with self.assertRaises(frappe.ValidationError):
			views.load("transfers", self.company, use_cache=False)
		with self.assertRaises(frappe.ValidationError):
			views.load("stock_health", self.company, use_cache=False)
		for feature in ("forecast_accuracy", "bought_together", "assortment_gaps", "promotions"):
			with self.assertRaises(frappe.ValidationError):
				views.load(feature, self.company, use_cache=False)
		views.load("running_low", self.company, items=self.items(), use_cache=False)

	def test_hook_roles_from_other_apps(self):
		frappe.set_user(self.hooked)
		self.assertFalse(access.has_view_role())
		real = frappe.get_hooks

		def fake(name=None, *args, **kwargs):
			if name == "lumen_shelf_viewer_roles":
				return ["RS Till Manager", "Guest"]
			return real(name, *args, **kwargs)

		with mock.patch.object(access.frappe, "get_hooks", side_effect=fake):
			self.assertTrue(access.has_view_role())
			self.assertNotIn("Guest", access.viewer_roles())

	def test_reports_through_frappe(self):
		from frappe.desk.query_report import run

		frappe.set_user(self.viewer)
		for name in ("Shelf Running Low", "Shelf Transfers", "Shelf Stock Health", "Shelf Forecast Accuracy", "Shelf Bought Together", "Shelf Assortment Gaps", "Shelf Promotions"):
			out = run(name, filters={"company": self.company})
			self.assertTrue(out["columns"], name)
			self.assertIsInstance(out["result"], list, name)
		out = run("Shelf Running Low", filters={"company": self.company, "budget": 1000})
		self.assertIn("in_budget", [c["fieldname"] for c in out["columns"]])
		frappe.set_user(self.nobody)
		with self.assertRaises(frappe.PermissionError):
			run("Shelf Running Low", filters={"company": self.company})

	def test_api_contract(self):
		self.assertEqual(api.CONTRACT_VERSION, 2)
		s = api.state()
		self.assertEqual(set(s), {"app", "version", "contract", "enabled", "can_view", "can_request", "submit_requests"})
		out = api.running_low(self.company)
		self.assertEqual(out["status"], "ok")
		self.assertEqual(out["contract"], 2)
		row_keys = {
			"item_code", "item_name", "warehouse", "on_shelf", "daily_sales", "days_left", "on_order",
			"reorder_point", "suggested_qty", "stock_uom", "source_key", "source", "transfer_qty",
			"transfer_from", "buy_qty", "supplier", "purchase_qty", "purchase_uom", "lead_time", "history_days",
		}
		self.assertTrue(out["rows"])
		self.assertTrue(row_keys <= set(out["rows"][0]))
		t = api.transfers(warehouse=self.wh["O2"])
		self.assertEqual(t["status"], "ok")
		self.assertEqual(t["company"], self.company)
		for r in t["rows"]:
			self.assertIn(self.wh["O2"], (r["from_warehouse"], r["to_warehouse"]))
