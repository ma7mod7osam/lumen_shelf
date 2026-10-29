frappe.query_reports["Restock Stock Health"] = {
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
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => ({
				filters: { company: frappe.query_report.get_filter_value("company"), is_group: 0 },
			}),
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: [
				{ value: "", label: "" },
				{ value: "No sales", label: __("No sales") },
				{ value: "Slow", label: __("Slow") },
				{ value: "Overstock", label: __("Overstock") },
				{ value: "Too new", label: __("Too new") },
				{ value: "OK", label: __("OK") },
			],
		},
		{
			fieldname: "abc",
			label: __("ABC"),
			fieldtype: "Select",
			options: ["", "A", "B", "C"],
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "status") {
			const cls = {
				"No sales": "text-danger",
				Slow: "text-warning",
				Overstock: "text-warning",
				OK: "text-muted",
			}[data.status_key];
			if (cls) value = `<span class="${cls}" style="font-weight: 600">${value}</span>`;
		}
		if (column.fieldname === "days_left" && data.days_left > 365) {
			// a year or more of stock: the exact figure is noise
			value = `<div style="text-align: right"><bdi dir="ltr">365+</bdi></div>`;
		}
		if (column.fieldname === "abc" && data.abc === "A") {
			value = `<span style="font-weight: 700">${value}</span>`;
		}
		return value;
	},
};
