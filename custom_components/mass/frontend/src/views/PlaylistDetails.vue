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
    <ItemsListing
      :items="playlistTracks"
      :loading="loading"
      itemtype="playlisttracks"
      :parent-item="playlist"
      v-if="activeTab == 'tracks'"
    />
  </section>
</template>

<script setup lang="ts">
import ItemsListing from "../components/ItemsListing.vue";
import InfoHeader from "../components/InfoHeader.vue";
import { ref } from "@vue/reactivity";
import type { Playlist, Track } from "../plugins/api";
import api from "../plugins/api";
import { watchEffect } from "vue";
import { parseBool } from "../utils";

interface Props {
  item_id: string;
  provider: string;
  lazy?: boolean | string;
  refresh?: boolean | string;
}
const props = withDefaults(defineProps<Props>(), {
  lazy: true,
  refresh: false,
});
const activeTab = ref(0);

const playlist = ref<Playlist>();
const playlistTracks = ref<Track[]>([]);
const loading = ref(true);

watchEffect(async () => {
  const item = await api.getPlaylist(
    props.provider,
    props.item_id,
    parseBool(props.lazy),
    parseBool(props.refresh)
  );
  playlist.value = item;
  // fetch additional info once main info retrieved
  playlistTracks.value = await api.getPlaylistTracks(props.provider, props.item_id);
  loading.value = false;
});
</script>
