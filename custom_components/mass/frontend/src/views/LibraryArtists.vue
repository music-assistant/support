<template>
  <ItemsListing
    itemtype="artists"
    :items="api.library.artists.length > 0 ? api.library.artists : []"
    :show-library="false"
    :show-providers="true"
    :show-search-by-default="!display.mobile"
  />
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api, MediaType } from "../plugins/api";
import { store } from "../plugins/store";

const { t } = useI18n();
const display = useDisplay();

store.topBarTitle = t("artists");
store.topBarContextMenuItems = [
  {
    title: t("sync"),
    link: () => {
      api.startSync(MediaType.ARTIST);
    },
  },
];
onBeforeUnmount(() => {
  store.topBarContextMenuItems = [];
});

onMounted(() => {
  api.fetchLibraryArtists();
});
</script>
