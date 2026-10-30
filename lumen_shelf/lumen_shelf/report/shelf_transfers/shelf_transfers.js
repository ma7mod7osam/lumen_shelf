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
