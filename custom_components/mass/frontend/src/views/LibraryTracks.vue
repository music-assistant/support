<template>
  <ItemsListing
    itemtype="tracks"
    :items="api.library.tracks.length > 0 ? api.library.tracks : []"
    :show-library="false"
    :show-track-number="false"
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

store.topBarTitle = t("tracks");
store.topBarContextMenuItems = [
  {
    title: t("sync"),
    link: () => {
      api.startSync(MediaType.TRACK);
    },
  },
];
onBeforeUnmount(() => {
  store.topBarContextMenuItems = [];
});

onMounted(() => {
  api.fetchLibraryTracks();
});
</script>
