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
      :show-track-number="false"
      v-if="activeTab == 'tracks'"
    />
  </section>
</template>

<script setup lang="ts">
import ItemsListing from "../components/ItemsListing.vue";
import InfoHeader from "../components/InfoHeader.vue";
import { ref } from "@vue/reactivity";
import type { MassEvent, Playlist, ProviderType, Track } from "../plugins/api";
import { api, MassEventType } from "../plugins/api";
import { onBeforeUnmount, watchEffect } from "vue";
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

// listen for item updates to refresh interface when that happens
const unsub = api.subscribe(
  MassEventType.MEDIA_ITEM_UPDATED,
  async (evt: MassEvent) => {
    const updItem = evt.data as Playlist;
    if (updItem.item_id == props.item_id) {
      // got update for current item
      // fetch playlist tracks as they might have changed
      playlistTracks.value = await api.getPlaylistTracks(
        props.provider as ProviderType,
        props.item_id
      );
    }
  }
);
onBeforeUnmount(unsub);
</script>
