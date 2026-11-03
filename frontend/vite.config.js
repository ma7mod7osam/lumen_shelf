// Lumen Shelf app. Built straight into the Frappe app's public folder with
// fixed names, so lumen_shelf/www/shelf.html can load
// /assets/lumen_shelf/shelf/shelf.js and shelf.css (the version on the URL
// makes browsers fetch a new build after an update).
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
	plugins: [vue()],
	base: "/assets/lumen_shelf/shelf/",
	build: {
		outDir: "../lumen_shelf/public/shelf",
		emptyOutDir: true,
		cssCodeSplit: false,
		rollupOptions: {
			input: "src/main.js",
			output: {
				entryFileNames: "shelf.js",
				chunkFileNames: "shelf-[name]-[hash].js",
				assetFileNames: (a) => (a.name && a.name.endsWith(".css") ? "shelf.css" : "shelf-[name][extname]"),
			},
		},
	},
});
