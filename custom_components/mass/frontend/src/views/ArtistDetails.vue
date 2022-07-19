<template>
  <section>
    <InfoHeader :item="itemDetails" />
    <v-tabs v-model="activeTab" show-arrows grow hide-slider>
      <v-tab
        :class="activeTab == 'tracks' ? 'active-tab' : 'inactive-tab'"
        value="tracks"
      >
        {{ $t("tracks") }}</v-tab
      >
      <v-tab
        :class="activeTab == 'albums' ? 'active-tab' : 'inactive-tab'"
        value="albums"
      >
        {{ $t("albums") }}</v-tab
      >
    </v-tabs>
    <v-divider />
    <ItemsListing
      itemtype="artisttracks"
      :parent-item="itemDetails"
      :show-providers="true"
      :show-track-number="false"
      :show-library="false"
      :load-data="loadArtistTracks"
      :sort-keys="['timestamp DESC', 'sort_name', 'sort_album']"
      v-if="activeTab == 'tracks'"
    />
    <ItemsListing
      itemtype="artistalbums"
      :parent-item="itemDetails"
      :show-providers="true"
      :show-library="false"
      :load-data="loadArtistAlbums"
      :sort-keys="['timestamp DESC', 'sort_name', 'year']"
      v-if="activeTab == 'albums'"
    />
  </section>
</template>

<script setup lang="ts">
import ItemsListing from "../components/ItemsListing.vue";
import { filteredItems } from "../components/ItemsListing.vue";
import InfoHeader from "../components/InfoHeader.vue";
import { ref } from "@vue/reactivity";
import {
  MassEventType,
  type Artist,
  type ProviderType,
  type MassEvent,
  type MediaItemType,
} from "../plugins/api";
import { api } from "../plugins/api";
import { onBeforeUnmount, onMounted, watchEffect } from "vue";

export interface Props {
  item_id: string;
  provider: string;
}
const props = defineProps<Props>();
const activeTab = ref("");

const itemDetails = ref<Artist>();

const loadItemDetails = async function () {
  itemDetails.value = await api.getArtist(
    props.provider as ProviderType,
    props.item_id
  );
  activeTab.value = "tracks";
};

watchEffect(() => {
  // load info
  loadItemDetails();
});

onMounted(() => {
  //reload if/when item updates
  const unsub = api.subscribe_multi(
    [MassEventType.MEDIA_ITEM_ADDED, MassEventType.MEDIA_ITEM_UPDATED],
    (evt: MassEvent) => {
      // refresh info if we receive an update for this item
      const updatedItem = evt.data as MediaItemType;
      if (itemDetails.value?.uri == updatedItem.uri) {
        loadItemDetails();
      } else {
        for (const provId of updatedItem.provider_ids) {
          if (
            provId.prov_type == itemDetails.value?.provider &&
            provId.item_id == itemDetails.value?.item_id
          ) {
            loadItemDetails();
            break;
          }
        }
      }
    }
  );
  onBeforeUnmount(unsub);
});

const loadArtistAlbums = async function (
  offset: number,
  limit: number,
  sort: string,
  search?: string,
  inLibraryOnly = true
) {
  const artistAlbums = await api.getArtistAlbums(
    props.provider as ProviderType,
    props.item_id
  );
  return filteredItems(
    artistAlbums,
    offset,
    limit,
    sort,
    search,
    inLibraryOnly
  );
};
const loadArtistTracks = async function (
  offset: number,
  limit: number,
  sort: string,
  search?: string,
  inLibraryOnly = true
) {
  const artistTopTracks = await api.getArtistTracks(
    props.provider as ProviderType,
    props.item_id
  );
  return filteredItems(
    artistTopTracks,
    offset,
    limit,
    sort,
    search,
    inLibraryOnly
  );
};
</script>
