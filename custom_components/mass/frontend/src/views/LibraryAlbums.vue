<template>
  <ItemsListing
    itemtype="albums"
    :items="items"
    :show-providers="true"
    :load-data="loadItems"
    :sort-keys="['sort_name', 'timestamp DESC', 'sort_artist', 'year']"
  />
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api, MediaType, type Album } from "../plugins/api";
import { store } from "../plugins/store";

const { t } = useI18n();
const items = ref<Album[]>([]);

store.topBarTitle = t("albums");
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
  return await api.getAlbums(offset, limit, sort, library, search);
};
</script>
