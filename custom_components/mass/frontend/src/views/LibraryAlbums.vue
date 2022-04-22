<template>
  <ItemsListing itemtype="albums" :items="items" :loading="loading" />
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api } from "../plugins/api";
import type { Album } from "../plugins/api";
import { store } from "../plugins/store";

const { t } = useI18n();
const items = ref<Album[]>([]);
const loading = ref(true);

api.getLibraryAlbums().then((albums) => {
  items.value = albums;
  loading.value = false;
});

store.topBarTitle = t("albums");
</script>
