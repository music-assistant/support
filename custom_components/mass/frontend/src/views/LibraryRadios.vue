<template>
  <ItemsListing
    itemtype="radios"
    :items="api.library.radios.length > 0 ? api.library.radios : []"
    :show-library="false"
    :show-providers="true"
    :show-duration="false"
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

store.topBarTitle = t("radios");
store.topBarContextMenuItems = [
  {
    title: t("sync"),
    link: () => {
      api.startSync(MediaType.RADIO);
    },
  },
];
onBeforeUnmount(() => {
  store.topBarContextMenuItems = [];
});

onMounted(() => {
  api.fetchLibraryRadios();
});
</script>
