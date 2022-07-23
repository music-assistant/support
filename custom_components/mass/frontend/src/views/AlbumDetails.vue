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
        :class="activeTab == 'versions' ? 'active-tab' : 'inactive-tab'"
        value="versions"
      >
        {{ $t("album_versions") }}</v-tab
      >
    </v-tabs>
    <v-divider />
    <ItemsListing
      itemtype="albumtracks"
      :parent-item="itemDetails"
      :show-providers="true"
      :show-library="true"
      :load-data="loadAlbumTracks"
      :sort-keys="['track_number', 'sort_name', 'duration']"
      v-if="activeTab == 'tracks'"
    />
    <ItemsListing
      itemtype="albumversions"
      :parent-item="itemDetails"
      :show-providers="true"
      :show-library="false"
      :load-data="loadAlbumVersions"
      :sort-keys="['provider', 'sort_name', 'year']"
      v-if="activeTab == 'versions'"
    />
  </section>
</template>

<script setup lang="ts">
import ItemsListing from "../components/ItemsListing.vue";
import { filteredItems } from "../components/ItemsListing.vue";
import InfoHeader from "../components/InfoHeader.vue";
import {
  MassEventType,
  type Album,
  type MassEvent,
  type MediaItemType,
} from "../plugins/api";
import { api, ProviderType } from "../plugins/api";
import { watchEffect, ref, onMounted, onBeforeUnmount } from "vue";
import { parseBool } from "@/utils";

export interface Props {
  item_id: string;
  provider: string;
  force_provider_version?: string;
}
const props = defineProps<Props>();
const activeTab = ref("");

const itemDetails = ref<Album>();

const loadItemDetails = async function () {
  itemDetails.value = await api.getAlbum(
    props.provider as ProviderType,
    props.item_id,
    true,
    false,
    parseBool(props.force_provider_version || "")
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

const loadAlbumTracks = async function (
  offset: number,
  limit: number,
  sort: string,
  search?: string,
  inLibraryOnly = true
) {
  const albumTracks = await api.getAlbumTracks(
    props.provider as ProviderType,
    props.item_id
  );
  return filteredItems(albumTracks, offset, limit, sort, search, inLibraryOnly);
};

const loadAlbumVersions = async function (
  offset: number,
  limit: number,
  sort: string,
  search?: string,
  inLibraryOnly = true
) {
  const albumVersions = await api.getAlbumVersions(
    props.provider as ProviderType,
    props.item_id
  );
  return filteredItems(
    albumVersions,
    offset,
    limit,
    sort,
    search,
    inLibraryOnly
  );
};
</script>
