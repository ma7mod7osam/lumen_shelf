// Lists every __("...") text in src/ into lumen_shelf/restock/app_strings.json.
// The server translates exactly these for the app (restock/app.py boot), and
// the translation test checks each one has Arabic and that this list is
// up to date with src/.
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const RE = /__\(\s*"((?:[^"\\]|\\.)+)"\s*[,)]/g;
const found = new Set();
function walk(dir) {
	for (const f of readdirSync(dir)) {
		const p = join(dir, f);
		if (statSync(p).isDirectory()) walk(p);
		else if (/\.(vue|js)$/.test(f)) for (const m of readFileSync(p, "utf8").matchAll(RE)) found.add(m[1].replace(/\\"/g, '"'));
	}
}
walk(fileURLToPath(new URL("./src", import.meta.url)));
const out = [...found].sort();
writeFileSync(new URL("../lumen_shelf/restock/app_strings.json", import.meta.url), JSON.stringify(out, null, "\t") + "\n");
console.log(out.length + " strings");
