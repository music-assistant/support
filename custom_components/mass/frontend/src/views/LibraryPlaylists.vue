<template>
  <ItemsListing itemtype="playlists" :items="items" :loading="loading" />
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api } from "../plugins/api";
import type { Playlist } from "../plugins/api";
import { store } from "../plugins/store";

const { t } = useI18n();
const items = ref<Playlist[]>([]);
const loading = ref(true);

api.getLibraryPlaylists().then((playlists) => {
  items.value = playlists;
  loading.value = false;
});

store.topBarTitle = t("playlists");
</script>
