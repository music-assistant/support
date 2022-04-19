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

interface Props {
  item_id: string;
  provider: string;
}
const props = defineProps<Props>();
const activeTab = ref(0);

const playlist = ref<Playlist>();
const playlistTracks = ref<Track[]>([]);

api.getPlaylist(props.provider, props.item_id).then((x) => {
  playlist.value = x;
});
api.getPlaylistTracks(props.provider, props.item_id).then((x) => {
  playlistTracks.value.push(...x);
});
</script>

