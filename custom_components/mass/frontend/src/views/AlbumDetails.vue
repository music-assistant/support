<template>
  <section>
    <InfoHeader :item="album" />
    <v-tabs v-model="activeTab" show-arrows grow hide-slider>
      <v-tab
        :class="activeTab == 'tracks' ? 'active-tab' : 'inactive-tab'"
        value="tracks"
      >
        {{ $t("album_tracks") }}</v-tab
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
      :items="albumTracks"
      itemtype="albumtracks"
      :parent-item="album"
      v-if="activeTab == 'tracks'"
    />
    <ItemsListing
      :items="albumVersions"
      itemtype="albums"
      :parent-item="album"
      v-if="activeTab == 'versions'"
    />
  </section>
</template>

<script setup lang="ts">
import ItemsListing from "../components/ItemsListing.vue";
import InfoHeader from "../components/InfoHeader.vue";
import { ref } from "@vue/reactivity";
import type { Album, Track } from "../plugins/api";
import api from "../plugins/api";

interface Props {
  item_id: string;
  provider: string;
}
const props = defineProps<Props>();
const activeTab = ref(0);

const album = ref<Album>();
const albumTracks = ref<Track[]>([]);
const albumVersions = ref<Album[]>([]);

api.getAlbum(props.provider, props.item_id).then((x) => {
  album.value = x;
});
api.getAlbumVersions(props.provider, props.item_id).then((x) => {
  albumVersions.value.push(...x);
});
api.getAlbumTracks(props.provider, props.item_id).then((x) => {
  albumTracks.value.push(...x);
});
</script>

