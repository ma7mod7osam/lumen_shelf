<script setup>
// Product ideas in one place: trending in the market, missing in a branch,
// often bought together. Each tab is that screen's own rows.
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { screens } from "../screens.js";
import { state } from "../store.js";
import ScreenView from "./ScreenView.vue";

const route = useRoute();
const router = useRouter();
const tabs = computed(() => screens(state.boot).filter((s) => s.idea));
const tab = computed(() => {
	const t = route.params.tab;
	return tabs.value.some((s) => s.name === t) ? t : tabs.value.length ? tabs.value[0].name : "";
});
</script>

<template>
	<section class="screen">
		<header class="screen-head">
			<h1>{{ __("Product ideas") }}</h1>
		</header>
		<div v-if="tabs.length" class="tabs" role="tablist">
			<button
				v-for="s in tabs"
				:key="s.name"
				type="button"
				role="tab"
				class="tab"
				:class="{ active: s.name === tab }"
				@click="router.replace('/ideas/' + s.name)"
			>
				{{ s.title }}
			</button>
		</div>
		<ScreenView v-if="tab" :key="tab" :name="tab" embedded />
		<div v-else class="notice">{{ __("No product ideas are switched on in the settings.") }}</div>
	</section>
</template>
