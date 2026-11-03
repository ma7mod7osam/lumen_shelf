<script setup>
// Line icons drawn for the app (24 x 24, stroke follows the text colour).
defineProps({ name: { type: String, required: true }, size: { type: Number, default: 20 } });
const PATHS = {
	today: "M4 11.5 12 5l8 6.5M6 10v9h12v-9M10 19v-5h4v5",
	low: "M4 6h16M4 12h10M4 18h5M17 14v6M14.5 17.5 17 20l2.5-2.5",
	move: "M4 8h13M14 4.5 17.5 8 14 11.5M20 16H7M10 12.5 6.5 16 10 19.5",
	health: "M3 12h4l2.5-6 4 12 2.5-6H21",
	tag: "M3.5 12.5 12 4h7.5v7.5L11 20zM15.5 8.5h.01",
	spark: "M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18",
	gap: "M4 5h7v7H4zM13 12h7v7h-7zM13 5h7v4M4 15v4h4",
	link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
	ideas: "M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z",
	target: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 12h.01",
	settings:
		"M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
	refresh: "M20 11a8 8 0 0 0-14.6-4.5M4 5v4h4M4 13a8 8 0 0 0 14.6 4.5M20 19v-4h-4",
	search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
	download: "M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19h14",
	moon: "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z",
	sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
	close: "M6 6l12 12M18 6 6 18",
	desk: "M4 5h16v11H4zM9 20h6M12 16v4",
	cart: "M4 5h2l2 10h10l2-7H7.5M10 19.5h.01M17 19.5h.01",
	box: "M12 3 4 7.5v9L12 21l8-4.5v-9zM4 7.5 12 12l8-4.5M12 12v9",
	empty: "M4 7h16v12H4zM8 7V5h8v2M9 12h6",
	menu: "M4 7h16M4 12h16M4 17h16",
};
</script>

<template>
	<svg
		:width="size"
		:height="size"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width="1.8"
		stroke-linecap="round"
		stroke-linejoin="round"
		aria-hidden="true"
	>
		<path :d="PATHS[name] || ''" />
	</svg>
</template>
