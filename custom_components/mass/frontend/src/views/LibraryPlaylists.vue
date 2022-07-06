<template>
  <ItemsListing
    itemtype="playlists"
    :items="items"
    :show-duration="false"
    :show-providers="true"
    :load-data="loadItems"
    :show-library="false"
    :sort-keys="['sort_name', 'timestamp DESC']"
  />
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api, MediaType, type Playlist } from "../plugins/api";
import { store } from "../plugins/store";

const { t } = useI18n();
const items = ref<Playlist[]>([]);

store.topBarTitle = t("playlists");
store.topBarContextMenuItems = [
  {
    title: t("sync"),
    link: () => {
      api.startSync(MediaType.ALBUM);
    },
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
  return await api.getPlaylists(offset, limit, sort, library, search);
};
</script>
