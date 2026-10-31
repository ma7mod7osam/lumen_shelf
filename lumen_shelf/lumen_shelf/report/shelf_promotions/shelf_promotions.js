frappe.query_reports["Shelf Promotions"] = {
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
			fieldname: "warehouse",
			label: __("Outlet"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => ({
				filters: { company: frappe.query_report.get_filter_value("company"), is_group: 0 },
			}),
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		// blue, never green (Lumen rule), and not text-primary (black on v16)
		const blue = "color: var(--blue-500, #1463FF); font-weight: 600";
		if (column.fieldname === "lift" && data.lift) {
			value = `<span style="${data.lift > 1 ? blue : "font-weight: 600"}">${value}</span>`;
		}
		if (column.fieldname === "promo_factor" && data.promo_factor) {
			value = `<span style="${blue}">${value}</span>`;
		}
		if (column.fieldname === "extra_qty" && data.extra_qty) {
			value = `<span style="font-weight: 600">${value}</span>`;
		}
		return value;
	},
};
