<template>
  <section>
    <InfoHeader :item="playlist" />
    
    <v-tabs v-model="activeTab" show-arrows grow hide-slider>
      <v-tab
        :class="activeTab == 'tracks' ? 'active-tab' : 'inactive-tab'"
        value="tracks"
      >
        {{ $t("playlist_tracks") }}</v-tab
      >
    </v-tabs>
    <v-divider />
    <v-progress-linear indeterminate v-if="loading"></v-progress-linear>
    <ItemsListing
      itemtype="playlisttracks"
      :parent-item="playlist"
      :show-providers="false"
      :show-library="false"
      :show-track-number="false"
      :load-data="loadPlaylistTracks"
      :count="playlistTracks.length"
      :sort-keys="['position', 'sort_name', 'sort_artist', 'sort_album']"
      v-if="activeTab == 'tracks' && playlistTracks.length > 0"
    />
  </section>
</template>

<script setup lang="ts">
import ItemsListing, { filteredItems } from "../components/ItemsListing.vue";
import InfoHeader from "../components/InfoHeader.vue";
import { ref } from "@vue/reactivity";
import type { Playlist, ProviderType, Track } from "../plugins/api";
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

const playlist = ref<Playlist>();
const playlistTracks = ref<Track[]>([]);
const loading = ref(true);

watchEffect(async () => {
  const item = await api.getPlaylist(
    props.provider as ProviderType,
    props.item_id,
    parseBool(props.lazy),
    parseBool(props.refresh)
  );
  playlist.value = item;
  // fetch additional info once main info retrieved
  playlistTracks.value = await api.getPlaylistTracks(
    props.provider as ProviderType,
    props.item_id
  );
  loading.value = false;
});

const loadPlaylistTracks = async function (
  offset: number,
  limit: number,
  sort: string,
  search?: string,
  inLibraryOnly = true
) {
  return filteredItems(playlistTracks.value, offset, limit, sort, search, inLibraryOnly);
};
</script>
