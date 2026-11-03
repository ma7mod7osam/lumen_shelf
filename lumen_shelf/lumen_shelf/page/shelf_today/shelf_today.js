// The desk's way in (workspace shortcut, v16 sidebar): the Lumen Shelf app
// lives at /shelf, outside the desk, like LumenPOS at /pos.
frappe.pages["shelf-today"].on_page_load = function () {
	window.location.href = "/shelf";
};

frappe.pages["shelf-today"].on_page_show = function () {
	window.location.href = "/shelf";
};
