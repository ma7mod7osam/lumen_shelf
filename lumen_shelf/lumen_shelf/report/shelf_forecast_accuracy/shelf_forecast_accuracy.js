frappe.query_reports["Shelf Forecast Accuracy"] = {
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
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if ((column.fieldname === "error_pct" || column.fieldname === "difference") && data[column.fieldname] !== null) {
			// keep the sign on the left in Arabic too, red when far off
			const v = data[column.fieldname];
			const text = (v > 0 ? "+" : "") + v.toFixed(1) + (column.fieldname === "error_pct" ? "%" : "");
			const far = column.fieldname === "error_pct" && Math.abs(v) >= 50;
			value = `<div style="text-align: right"${far ? ' class="text-danger"' : ""}><bdi dir="ltr">${text}</bdi></div>`;
		}
		if (column.fieldname === "actual_qty" && data.actual_qty < 0) {
			// a return: keep the minus on the left in Arabic too
			value = `<div style="text-align: right"><bdi dir="ltr">${data.actual_qty.toFixed(3)}</bdi></div>`;
		}
		return value;
	},
};
