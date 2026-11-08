frappe.query_reports["Shelf Bundle Ideas"] = {
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
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: [
				{ value: "", label: "" },
				{ value: "New", label: __("New") },
				{ value: "Created", label: __("Created") },
				{ value: "Not a match", label: __("Not a match") },
			],
		},
	],
	onload(report) {
		// Ask for new ideas: for whoever may change the settings (checked again on the server).
		if (frappe.user.has_role("Shelf Manager") || frappe.user.has_role("System Manager")) {
			report.page.add_inner_button(__("Ask for new ideas"), () => {
				frappe
					.call({
						method: "lumen_shelf.restock.bundles.refresh_now",
						args: { company: report.get_filter_value("company") },
						freeze: true,
					})
					.then((r) => frappe.show_alert({ message: r.message, indicator: "blue" }, 8));
			});
		}
	},
};
