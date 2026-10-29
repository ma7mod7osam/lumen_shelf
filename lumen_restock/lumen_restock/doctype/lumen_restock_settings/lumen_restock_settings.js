// The settings page: an introduction, and what the app found on its own (the
// main warehouse and the outlets), so the shop sees it works with nothing filled in.
frappe.ui.form.on("Lumen Restock Settings", {
	refresh(frm) {
		const esc = frappe.utils.escape_html;
		frm.get_field("intro").$wrapper.html(
			`<div class="text-muted" style="margin-bottom: 8px">${esc(
				__("Lumen Restock works from day one with the values below. Every field is optional and can be changed at any time.")
			)}</div>
			<div>
				<a href="/app/query-report/Restock Running Low">${esc(__("Running low"))}</a> &nbsp;|&nbsp;
				<a href="/app/query-report/Restock Transfers">${esc(__("Transfer suggestions"))}</a> &nbsp;|&nbsp;
				<a href="/app/query-report/Restock Stock Health">${esc(__("Stock health"))}</a>
			</div>`
		);
		frappe.call({ method: "lumen_restock.lumen_restock.doctype.lumen_restock_settings.lumen_restock_settings.detected_setup" }).then((r) => {
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
