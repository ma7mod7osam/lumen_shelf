"""The app at /shelf (restock/app.py): every screen is the report's own rows,
it opens only for who may see the reports, the settings screen is the
doctype's own (and never sends a password), and the search boxes follow
ERPNext's permissions. One test per rule, so a deliberate break of one rule
(dev/mutations.py) fails its own test.

Tests that save anything work inside a savepoint and roll back."""

import json
import os

import frappe

from lumen_shelf import i18n_strings
from lumen_shelf.restock import access, app, home
from lumen_shelf.restock import settings as st
from lumen_shelf.tests.test_access import limit, make_user
from lumen_shelf.tests.test_restock import RestockCase, set_settings

SP = "rs_app"


def report_rows(report, filters):
	module = "lumen_shelf.lumen_shelf.report.{0}.{0}".format(frappe.scrub(report))
	return frappe.get_attr(module + ".execute")(filters)


class TestApp(RestockCase):
	def setUp(self):
		frappe.set_user("Administrator")
		set_settings(self.company, self.wh["M"])

	def tearDown(self):
		frappe.set_user("Administrator")
		set_settings(self.company, self.wh["M"])

	def user(self, name, roles):
		return make_user("rs-app-%s-%s@example.com" % (name, self.ds.suffix), roles)

	# ---- the screens are the reports

	def test_every_screen_is_its_report(self):
		set_settings(self.company, self.wh["M"], bundle_ideas=1)  # off by default
		for name, report in app.SCREENS.items():
			if name == "trending_products":
				continue  # needs the hub: test_trend_products
			f = {"company": self.company}
			got = app.screen(name, json.dumps(f))
			cols, rows, message, chart, summary = report_rows(report, dict(f))
			self.assertEqual([c["fieldname"] for c in got["columns"]], [c["fieldname"] for c in cols], name)
			self.assertEqual(got["rows"], rows, name)
			self.assertEqual(got["message"], message, name)
			self.assertEqual(got["summary"], summary or [], name)

	def test_screen_follows_its_filters(self):
		o1 = self.wh["O1"]
		got = app.screen("running_low", {"company": self.company, "warehouse": o1, "item_group": ""})
		self.assertTrue(got["rows"])
		self.assertEqual({r["warehouse"] for r in got["rows"]}, {o1})

	def test_unknown_screen(self):
		# a real report that is not one of ours is refused too, by name
		for name in ("tabUser", "Stock Balance"):
			frappe.clear_messages()
			with self.assertRaises(frappe.ValidationError) as cm:
				app.screen(name, {"company": self.company})
			self.assertEqual(str(cm.exception), "Unknown screen.")

	def test_screen_needs_the_report_permission(self):
		# Shelf User with no ERPNext stock role: our gate lets them in, the
		# report's ref doctype (Bin) does not, as in the desk
		u = self.user("nobin", ["Shelf User"])
		frappe.set_user(u)
		self.assertFalse(app._report_allowed("Shelf Running Low"))
		with self.assertRaises(frappe.PermissionError):
			app.screen("running_low", {"company": self.company})
		frappe.set_user(self.user("bin", ["Shelf User", "Stock User"]))
		self.assertTrue(app.screen("running_low", {"company": self.company})["rows"])

	def test_screen_follows_the_switches(self):
		set_settings(self.company, self.wh["M"], stock_health=0)
		with self.assertRaises(frappe.ValidationError):
			app.screen("stock_health", {"company": self.company})

	# ---- boot: who may open it and what they see

	def test_boot_screens_follow_switches(self):
		b = app.boot()
		self.assertTrue(b["screens"]["running_low"])
		self.assertTrue(b["screens"]["stock_health"])
		self.assertFalse(b["screens"]["trending_products"])  # off until Lumen gives a key
		set_settings(self.company, self.wh["M"], stock_health=0, outlet_transfers=0)
		b = app.boot()
		self.assertFalse(b["screens"]["stock_health"])
		self.assertFalse(b["screens"]["transfers"])
		self.assertTrue(b["screens"]["running_low"])

	def test_boot_who_may_do_what(self):
		b = app.boot()
		self.assertEqual((b["can_view"], b["can_settings"], b["can_request"]), (1, 1, 1))
		frappe.set_user(self.user("viewer", ["Shelf User", "Stock User"]))
		b = app.boot()
		self.assertEqual((b["can_view"], b["can_settings"], b["can_request"]), (1, 0, 0))
		frappe.set_user(self.user("nobody", ["Stock User"]))
		with self.assertRaises(frappe.PermissionError):
			app.boot()

	def test_boot_when_switched_off(self):
		# the app off: a Shelf Manager still gets in, to switch it back on
		set_settings(self.company, self.wh["M"], enabled=0)
		frappe.set_user(self.user("mgr", ["Shelf Manager", "Stock User"]))
		b = app.boot()
		self.assertEqual((b["enabled"], b["can_view"], b["can_settings"]), (0, 0, 1))
		self.assertEqual(b["screens"], {})
		frappe.set_user(self.user("viewer", ["Shelf User", "Stock User"]))
		with self.assertRaises(frappe.PermissionError):
			app.boot()

	def test_boot_translates_the_app(self):
		def lang(code):
			frappe.local.lang = code
			# Frappe v13 keeps the first language's dictionary for the request
			if getattr(frappe.local, "lang_full_dict", None) is not None:
				frappe.local.lang_full_dict = None

		lang("ar")
		try:
			b = app.boot()
		finally:
			lang("en")
		self.assertEqual(b["messages"]["Today's tasks"], "مهام اليوم")
		self.assertEqual(sorted(b["messages"]), app.app_strings())
		self.assertTrue(b["rtl"])

	def test_boot_companies_are_the_allowed_ones(self):
		self.assertIn(self.company, app.boot()["companies"])
		u = self.user("co", ["Shelf User", "Stock User"])
		other = frappe.get_all("Company", filters={"name": ["!=", self.company]}, pluck="name", limit=1)
		limit(u, "Company", self.company)
		frappe.set_user(u)
		got = app.boot()["companies"]
		self.assertIn(self.company, got)
		for c in other:
			self.assertNotIn(c, got)
		self.assertEqual(set(app.boot()["abbrs"]), set(got))

	def test_boot_short_company_names(self):
		self.assertEqual(app.boot()["abbrs"][self.company], frappe.db.get_value("Company", self.company, "abbr"))

	def test_today_is_the_overview(self):
		self.assertEqual(app.overview(company=self.company), home.overview(company=self.company))
		o1 = self.wh["O1"]
		self.assertEqual(app.overview(company=self.company, warehouse=o1), home.overview(company=self.company, warehouse=o1))

	# ---- search boxes

	def test_lookup_warehouses_of_the_company(self):
		got = [r["name"] for r in app.lookup("Warehouse", "", self.company)]
		self.assertTrue(got)
		for w in got:
			self.assertEqual(frappe.db.get_value("Warehouse", w, "company"), self.company)
			self.assertEqual(frappe.db.get_value("Warehouse", w, "is_group"), 0)

	def test_lookup_follows_user_permissions(self):
		u = self.user("o2", ["Shelf User", "Stock User"])
		limit(u, "Warehouse", self.wh["O2"])
		frappe.set_user(u)
		self.assertEqual([r["name"] for r in app.lookup("Warehouse", "", self.company)], [self.wh["O2"]])

	def test_lookup_only_its_lists(self):
		with self.assertRaises(frappe.ValidationError):
			app.lookup("User", "")
		frappe.set_user(self.user("nobody", ["Stock User"]))
		with self.assertRaises(frappe.PermissionError):
			app.lookup("Warehouse", "")

	# ---- settings

	def test_settings_are_the_doctype(self):
		got = app.settings()
		meta = frappe.get_meta(st.DOCTYPE)
		self.assertEqual([f["fieldname"] for f in got["fields"]], [d.fieldname for d in meta.fields if d.fieldtype != "HTML"])
		self.assertEqual(got["values"]["cover_days"], frappe.get_single(st.DOCTYPE).cover_days)
		self.assertEqual(got["warehouses"][0]["warehouse"], self.wh["M"])

	def test_settings_never_send_a_password(self):
		frappe.db.savepoint(SP)
		try:
			set_settings(self.company, self.wh["M"], trends_api_secret="s3cret-value")
			got = app.settings()
			self.assertEqual(got["values"]["trends_api_secret"], "")
			self.assertEqual(got["values"]["trends_api_secret_set"], 1)
			self.assertNotIn("s3cret-value", json.dumps(got, default=str))
		finally:
			frappe.db.rollback(save_point=SP)

	def test_save_keeps_the_password_when_left_empty(self):
		frappe.db.savepoint(SP)
		try:
			set_settings(self.company, self.wh["M"], trends_api_secret="s3cret-value")
			values = app.settings()["values"]
			values["cover_days"] = 21
			app.save_settings(json.dumps(values, default=str), None)
			doc = frappe.get_single(st.DOCTYPE)
			self.assertEqual(doc.cover_days, 21)
			self.assertEqual(doc.get_password("trends_api_secret"), "s3cret-value")
			self.assertEqual(doc.warehouses[0].warehouse, self.wh["M"])  # rows untouched when not sent
		finally:
			frappe.db.rollback(save_point=SP)

	def test_save_runs_the_doctype_checks(self):
		frappe.db.savepoint(SP)
		try:
			values = app.settings()["values"]
			values["cover_days"] = 21
			rows = [{"company": self.company, "warehouse": self.wh["O1"], "warehouse_role": st.ROLE_MAIN}]
			app.save_settings(values, rows)
			doc = frappe.get_single(st.DOCTYPE)
			self.assertEqual([(r.warehouse, r.warehouse_role) for r in doc.warehouses], [(self.wh["O1"], st.ROLE_MAIN)])
			# read-only fields are not taken from the screen
			values["last_reorder_result"] = "typed by someone"
			app.save_settings(values, None)
			self.assertNotEqual(frappe.get_single(st.DOCTYPE).last_reorder_result, "typed by someone")
		finally:
			frappe.db.rollback(save_point=SP)

	def test_settings_only_for_a_shelf_manager(self):
		frappe.set_user(self.user("viewer", ["Shelf User", "Stock User", "Stock Manager"]))
		with self.assertRaises(frappe.PermissionError):
			app.settings()
		with self.assertRaises(frappe.PermissionError):
			app.save_settings({"cover_days": 3}, None)
		frappe.set_user("Administrator")
		self.assertEqual(frappe.get_single(st.DOCTYPE).cover_days, st.DEFAULTS["cover_days"])

	# ---- the page and the ways in

	def test_page_needs_a_login(self):
		from lumen_shelf.www import shelf

		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.Redirect):
				shelf.get_context(frappe._dict())
			self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=/shelf")
		finally:
			frappe.set_user("Administrator")
		# a test has no browser session (Frappe v13 cannot make a token then)
		if not frappe.local.session.data.get("csrf_token"):
			frappe.local.session.data.csrf_token = "test-token"
		ctx = shelf.get_context(frappe._dict())
		from lumen_shelf import __version__

		self.assertEqual(ctx.shelf_version, __version__)

	def test_ways_in_open_the_app(self):
		hooks = frappe.get_hooks("add_to_apps_screen", app_name="lumen_shelf") or []
		self.assertEqual([h.get("route") for h in hooks], ["/shelf"])
		rules = frappe.get_hooks("website_route_rules", app_name="lumen_shelf") or []
		self.assertIn({"from_route": "/shelf/<path:app_path>", "to_route": "shelf"}, rules)
		js = open(frappe.get_app_path("lumen_shelf", "lumen_shelf", "page", "shelf_today", "shelf_today.js"), encoding="utf-8").read()
		self.assertEqual(js.count('window.location.href = "/shelf"'), 2)  # opened and shown again
		self.assertTrue(os.path.exists(frappe.get_app_path("lumen_shelf", "public", "shelf", "shelf.js")))

	def test_app_strings_are_up_to_date(self):
		"""app_strings.json is what frontend/src uses (rebuilt by npm run build)."""
		src = os.path.join(os.path.dirname(frappe.get_app_path("lumen_shelf")), "frontend", "src")
		if not os.path.isdir(src):
			self.skipTest("no frontend source on this bench")
		found = set()
		for base, _dirs, files in os.walk(src):
			for f in files:
				if f.endswith((".vue", ".js")):
					with open(os.path.join(base, f), encoding="utf-8") as fh:
						found.update(i18n_strings.JS.findall(fh.read()))
		self.assertEqual(sorted(s.replace('\\"', '"') for s in found), app.app_strings())

	# ---- trending products

	def test_dismiss_a_trend(self):
		from lumen_shelf.restock import trend_products as tp

		frappe.db.savepoint(SP)
		try:
			set_settings(self.company, self.wh["M"], trend_products=1)
			group = frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name", limit=1)[0]
			tp.store(self.company, [{"group": group, "product_en": "Matcha powder", "product_ar": "بودرة ماتشا", "region": "local", "growth": 200}])
			name = frappe.db.get_value(tp.SUGGESTION, {"company": self.company, "product": "Matcha powder"})
			self.assertTrue(name)
			frappe.set_user(self.user("viewer", ["Shelf User", "Stock User"]))
			with self.assertRaises(frappe.PermissionError):
				app.dismiss_trend(name)
			frappe.set_user("Administrator")
			self.assertEqual(app.dismiss_trend(name)["status"], tp.STATUS_DISMISSED)
			self.assertEqual(frappe.db.get_value(tp.SUGGESTION, name, "status"), tp.STATUS_DISMISSED)
		finally:
			frappe.set_user("Administrator")
			frappe.db.rollback(save_point=SP)
