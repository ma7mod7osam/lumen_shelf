// The settings page: an introduction, and what the app found on its own (the
// main warehouse and the outlets), so the shop sees it works with nothing filled in.
frappe.ui.form.on("Lumen Shelf Settings", {
	refresh(frm) {
		const esc = frappe.utils.escape_html;
		frm.get_field("intro").$wrapper.html(
			`<div class="text-muted" style="margin-bottom: 8px">${esc(
				__("Lumen Shelf works from day one with the values below. Every field is optional and can be changed at any time.")
			)}</div>
			<div>
				<a href="/app/query-report/Shelf Running Low">${esc(__("Running low"))}</a> &nbsp;|&nbsp;
				<a href="/app/query-report/Shelf Transfers">${esc(__("Transfer suggestions"))}</a> &nbsp;|&nbsp;
				<a href="/app/query-report/Shelf Stock Health">${esc(__("Stock health"))}</a>
			</div>`
		);
		frappe.call({ method: "lumen_shelf.lumen_shelf.doctype.lumen_shelf_settings.lumen_shelf_settings.detected_setup" }).then((r) => {
			const rows = (r && r.message) || [];
			const html = rows
				.map((c) => {
					const main = c.main_warehouse
						? `${esc(c.main_warehouse)} <span class="text-muted">(${esc(
								c.basis === "set" ? __("named below") : __("found from the transfers it sends")
						  )})</span>`
						: `<span class="text-muted">${esc(__("None found. Outlets restock by buying, and from each other's surplus."))}</span>`;
					const outlets = c.outlets.length ? c.outlets.map(esc).join(", ") : "-";
					return `<div style="margin-bottom: 10px">
						<div><b>${esc(c.company)}</b></div>
						<div>${esc(__("Main warehouse"))}: ${main}</div>
						<div>${esc(__("Outlets"))}: ${outlets}</div>
					</div>`;
				})
				.join("");
			frm.get_field("detected").$wrapper.html(html);
		});
	},
});

// Automatic mode: update the reorder levels now, without waiting for the night.
frappe.ui.form.on("Lumen Shelf Settings", {
	update_levels_now(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save the settings first."));
			return;
		}
		frappe
			.call({ method: "lumen_shelf.restock.reorder.update_now", freeze: true })
			.then((r) => {
				frappe.msgprint({ title: __("Reorder levels"), message: frappe.utils.escape_html(r.message || ""), indicator: "blue" });
				frm.reload_doc();
			});
	},
});

// Trending products: ask Lumen's trends service now, without waiting for the week.
frappe.ui.form.on("Lumen Shelf Settings", {
	refresh_trends_now(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save the settings first."));
			return;
		}
		frappe
			.call({ method: "lumen_shelf.restock.trend_products.refresh_now", freeze: true })
			.then((r) => frappe.msgprint({ title: __("Trending products"), message: frappe.utils.escape_html(r.message || ""), indicator: "blue" }));
	},
});

// Bundle ideas: ask Lumen's AI service now, without waiting for the week.
frappe.ui.form.on("Lumen Shelf Settings", {
	refresh_bundles_now(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save the settings first."));
			return;
		}
		frappe
			.call({ method: "lumen_shelf.restock.bundles.refresh_now", freeze: true })
			.then((r) => frappe.msgprint({ title: __("Bundle ideas"), message: frappe.utils.escape_html(r.message || ""), indicator: "blue" }));
	},
});

// Credit on Lumen's trends service: ask what is left (free), or go and top up.
frappe.ui.form.on("Lumen Shelf Settings", {
	check_credit(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save the settings first."));
			return;
		}
		frappe.call({ method: "lumen_shelf.restock.trend_products.check_credit", freeze: true }).then(() => frm.reload_doc());
	},
	top_up_credit(frm) {
		const url = frm.doc.trends_topup_url;
		if (url && /^https?:\/\//.test(url)) {
			window.open(url, "_blank", "noopener");
		} else {
			frappe.msgprint(__("Ask Lumen to top up your credit on the trends service."));
		}
	},
});
