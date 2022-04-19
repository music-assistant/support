<template>
  <ItemsListing itemtype="radios" :items="items" />
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api } from "../plugins/api";
import type { Radio } from "../plugins/api";
import { store } from "../plugins/store";

const i18n = useI18n();
const items = ref<Radio[]>([]);

api.getLibraryRadios().then((radios) => {
  items.value.push(...radios);
});

store.topBarTransparent = false;
store.topBarTitle = `${i18n.t("library")} | ${i18n.t("artists")}`;
</script>
