<template>
  <section>
    <InfoHeader :item="artist" />
    <v-tabs v-model="activeTab" show-arrows grow hide-slider>
      <v-tab
        :class="activeTab == 'tracks' ? 'active-tab' : 'inactive-tab'"
        value="tracks"
      >
        {{ $t("tracks") }} ({{ artistTopTracks.length }})</v-tab
      >
      <v-tab
        :class="activeTab == 'albums' ? 'active-tab' : 'inactive-tab'"
        value="albums"
      >
        {{ $t("albums") }} ({{ artistAlbums.length }})</v-tab
      >
    </v-tabs>
    <v-divider />
    <ItemsListing
      itemtype="artisttracks"
      :parent-item="artist"
      :show-providers="true"
      :show-track-number="false"
      :show-library="false"
      :load-data="loadArtistTracks"
      :count="artistTopTracks.length"
      :sort-keys="['timestamp DESC', 'sort_name', 'sort_album']"
      v-if="activeTab == 'tracks' && artistTopTracks.length > 0"
    />
    <ItemsListing
      itemtype="artistalbums"
      :parent-item="artist"
      :show-providers="true"
      :show-library="false"
      :load-data="loadArtistAlbums"
      :count="artistAlbums.length"
      :sort-keys="['timestamp DESC', 'sort_name', 'year']"
      v-if="activeTab == 'albums' && artistAlbums.length > 0"
    />
  </section>
</template>

<script setup lang="ts">
import ItemsListing from "../components/ItemsListing.vue";
import { filteredItems } from "../components/ItemsListing.vue";
import InfoHeader from "../components/InfoHeader.vue";
import { ref } from "@vue/reactivity";
import type { Album, Artist, ProviderType, Track } from "../plugins/api";
import { api } from "../plugins/api";
import { watchEffect } from "vue";
import { parseBool } from "../utils";

export interface Props {
  item_id: string;
  provider: string;
  lazy?: boolean | string;
  refresh?: boolean | string;
}
const props = withDefaults(defineProps<Props>(), {
  lazy: true,
  refresh: false,
});
const activeTab = ref("tracks");

const artist = ref<Artist>();
const artistTopTracks = ref<Track[]>([]);
const artistAlbums = ref<Album[]>([]);
const loading = ref(true);

watchEffect(async () => {
  api
    .getArtist(
      props.provider as ProviderType,
      props.item_id,
      parseBool(props.lazy),
      parseBool(props.refresh)
    )
    .then(async (item) => {
      artist.value = item;
      // fetch additional info once main info retrieved
      await getExtraInfo();
      loading.value = false;
    });
});

const getExtraInfo = async function () {
  artistAlbums.value = await api.getArtistAlbums(
    props.provider as ProviderType,
    props.item_id
  );
  artistTopTracks.value = await api.getArtistTracks(
    props.provider as ProviderType,
    props.item_id
  );
};

const loadArtistAlbums = async function (
  offset: number,
  limit: number,
  sort: string,
  search?: string,
  inLibraryOnly = true
) {
  return filteredItems(
    artistAlbums.value,
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
  return filteredItems(
    artistTopTracks.value,
    offset,
    limit,
    sort,
    search,
    inLibraryOnly
  );
};
</script>
