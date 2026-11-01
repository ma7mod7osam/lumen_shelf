frappe.query_reports["Shelf Trending Products"] = {
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
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "region",
			label: __("Where"),
			fieldtype: "Select",
			options: [
				{ value: "", label: "" },
				{ value: "In the country", label: __("In the country") },
				{ value: "Worldwide", label: __("Worldwide") },
			],
		},
	],
	onload(report) {
		// Refresh now: for whoever may change the settings (checked again on the server).
		if (frappe.user.has_role("Shelf Manager") || frappe.user.has_role("System Manager")) {
			report.page.add_inner_button(__("Refresh now"), () => {
				frappe
					.call({
						method: "lumen_shelf.restock.trend_products.refresh_now",
						args: { company: report.get_filter_value("company") },
						freeze: true,
					})
					.then((r) => frappe.show_alert({ message: r.message, indicator: "blue" }, 8));
			});
		}
	},
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		// A manager can open the suggestion to dismiss it.
		if (column.fieldname === "product" && data.name && frappe.model.can_write("Shelf Trend Suggestion")) {
			value = `<a href="/app/shelf-trend-suggestion/${encodeURIComponent(data.name)}" style="font-weight: 600">${value}</a>`;
		}
		// blue, never green (Lumen rule), and not text-primary (black on v16)
		if (column.fieldname === "growth" && data.growth >= 100) {
			value = `<span style="color: var(--blue-500, #1463FF); font-weight: 600">${value}</span>`;
		}
		return value;
	},
};
