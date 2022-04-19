<template>
  <section>
    <InfoHeader :item="artist" />
    <v-tabs v-model="activeTab" show-arrows grow hide-slider>
      <v-tab
        :class="activeTab == 'tracks' ? 'active-tab' : 'inactive-tab'"
        value="tracks"
      >
        {{ $t("artist_toptracks") }}</v-tab
      >
      <v-tab
        :class="activeTab == 'albums' ? 'active-tab' : 'inactive-tab'"
        value="albums"
      >
        {{ $t("artist_albums") }}</v-tab
      >
    </v-tabs>
    <v-divider />
    <ItemsListing
      :items="artistTopTracks"
      itemtype="tracks"
      :parent-item="artist"
      v-if="activeTab == 'tracks'"
    />
    <ItemsListing
      :items="artistAlbums"
      itemtype="albums"
      :parent-item="artist"
      v-if="activeTab == 'albums'"
    />
  </section>
</template>

<script setup lang="ts">
import ItemsListing from "../components/ItemsListing.vue";
import InfoHeader from "../components/InfoHeader.vue";
import { ref } from "@vue/reactivity";
import type { Album, Artist, Track } from "../plugins/api";
import api from "../plugins/api";

interface Props {
  item_id: string;
  provider: string;
}
const props = defineProps<Props>();
const activeTab = ref(0);

const artist = ref<Artist>();
const artistTopTracks = ref<Track[]>([]);
const artistAlbums = ref<Album[]>([]);

api.getArtist(props.provider, props.item_id).then((x) => {
  artist.value = x;
});
api.getArtistAlbums(props.provider, props.item_id).then((x) => {
  artistAlbums.value.push(...x);
});
api.getArtistTracks(props.provider, props.item_id).then((x) => {
  artistTopTracks.value.push(...x);
});
</script>

