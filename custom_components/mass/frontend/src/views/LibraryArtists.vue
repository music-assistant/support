<template>
  <ItemsListing
    itemtype="artists"
    :items="items"
    :show-providers="true"
    :load-data="loadItems"
    :show-album-artists-only-filter="true"
    @toggle-album-artists-only="
      (e) => {
        albumArtistsOnly = e;
      }
    "
  />
</template>

<script setup lang="ts">
import { mdiFileSync } from '@mdi/js';
import { onBeforeUnmount, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import ItemsListing from '../components/ItemsListing.vue';
import { api, MediaType, type Artist } from '../plugins/api';
import { store } from '../plugins/store';

const { t } = useI18n();
const items = ref<Artist[]>([]);
const albumArtistsOnly = ref(false);

const loadItems = async function (
  offset: number,
  limit: number,
  sort: string,
  search?: string,
  inLibraryOnly = true
) {
  const library = inLibraryOnly || undefined;
  return await api.getArtists(
    offset,
    limit,
    sort,
    library,
    search,
    albumArtistsOnly.value
  );
};

store.topBarTitle = t('artists');
store.topBarContextMenuItems = [
  {
    label: 'sync',
    labelArgs: [],
    action: () => {
      api.startSync(MediaType.ARTIST);
    },
    icon: mdiFileSync,
  },
];
onBeforeUnmount(() => {
  store.topBarContextMenuItems = [];
});
</script>
