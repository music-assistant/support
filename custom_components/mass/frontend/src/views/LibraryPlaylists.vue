<template>
  <ItemsListing itemtype="playlists" :items="items" />
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api } from "../plugins/api";
import type { Playlist } from "../plugins/api";
import { store } from "../plugins/store";

const i18n = useI18n();
const items = ref<Playlist[]>([]);

api.getLibraryPlaylists().then((playlists) => {
  items.value.push(...playlists);
});

store.topBarTransparent = false;
store.topBarTitle = `${i18n.t("library")} | ${i18n.t("artists")}`;
</script>
