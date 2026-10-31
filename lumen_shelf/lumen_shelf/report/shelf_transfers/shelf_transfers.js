frappe.query_reports["Shelf Transfers"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "from_warehouse",
			label: __("From warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => ({
				filters: { company: frappe.query_report.get_filter_value("company"), is_group: 0 },
			}),
		},
		{
			fieldname: "to_warehouse",
			label: __("To warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => ({
				filters: { company: frappe.query_report.get_filter_value("company"), is_group: 0 },
			}),
		},
		{
			fieldname: "reason",
			label: __("Reason"),
			fieldtype: "Select",
			options: [
				{ value: "", label: "" },
				{ value: "Running low there", label: __("Running low there") },
				{ value: "Sells faster there", label: __("Sells faster there") },
			],
		},
	],
	onload(report) {
		// Phase 2: one button turns what the screen shows into ERPNext Material
		// Requests. Shown only to people the server lets create them.
		const scope = "transfers";
		const call = (method, args) =>
			frappe.call({ method: "lumen_shelf.restock.requests." + method, args, freeze: true });
		frappe
			.call({ method: "lumen_shelf.restock.requests.can_create", args: { scope } })
			.then((r) => {
				if (!r.message || !r.message.ok) return;
				report.page.add_inner_button(__("Create material requests"), () => {
					const filters = report.get_filter_values();
					call("preview", { scope, filters }).then((p) => {
						if (!p.message.count) return frappe.msgprint(p.message.message);
						frappe.confirm(p.message.message, () => {
							call("create", { scope, filters }).then((c) => {
								frappe.msgprint({
									title: __("Material requests"),
									message: c.message.message,
									indicator: c.message.count ? "blue" : "orange",
								});
								report.refresh();
							});
						});
					});
				});
			});
	},
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "qty") {
			value = `<span style="font-weight: 600">${value}</span>`;
		}
		if (column.fieldname === "reason") {
			// Not "text-primary": on Frappe v16 that is the body text colour, so it
			// reads black, and in dark mode black on black. Blue from the theme,
			// Lumen blue when the theme has none.
			value =
				data.reason_key === "running_low"
					? `<span class="text-danger">${value}</span>`
					: `<span style="color: var(--blue-500, #1463FF)">${value}</span>`;
		}
		return value;
	},
};
