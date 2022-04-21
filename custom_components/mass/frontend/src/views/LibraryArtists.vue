<template>
  <ItemsListing itemtype="artists" :items="items" :loading="loading" />
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api } from "../plugins/api";
import type { Artist } from "../plugins/api";
import { store } from "../plugins/store";

const i18n = useI18n();
const items = ref<Artist[]>([]);
const loading = ref(true);

api.getLibraryArtists().then((artists) => {
  items.value = artists;
  loading.value = false;
});

store.topBarTitle = `${i18n.t("library")} | ${i18n.t("artists")}`;
</script>
