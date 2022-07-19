<template>
  <ItemsListing
    itemtype="tracks"
    :items="items"
    :show-providers="true"
    :show-track-number="false"
    :load-data="loadItems"
    :sort-keys="[
      'sort_name',
      'timestamp DESC',
      'sort_artist',
      'sort_album',
      'duration',
    ]"
  />
</template>

<script setup lang="ts">
import { mdiFileSync } from "@mdi/js";
import { onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api, MediaType, type Track } from "../plugins/api";
import { store } from "../plugins/store";

const { t } = useI18n();
const items = ref<Track[]>([]);

store.topBarTitle = t("tracks");
store.topBarContextMenuItems = [
  {
    label: "sync",
    labelArgs: [],
    action: () => {
      api.startSync(MediaType.TRACK);
    },
    icon: mdiFileSync
  },
];
onBeforeUnmount(() => {
  store.topBarContextMenuItems = [];
});

const loadItems = async function (
  offset: number,
  limit: number,
  sort: string,
  search?: string,
  inLibraryOnly = true
) {
  const library = inLibraryOnly || undefined;
  return await api.getTracks(offset, limit, sort, library, search);
};
</script>
