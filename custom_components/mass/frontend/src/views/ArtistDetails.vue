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
      :loading="loading"
      itemtype="tracks"
      :parent-item="artist"
      v-if="activeTab == 'tracks'"
    />
    <ItemsListing
      :items="artistAlbums"
      :loading="loading"
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

const artist = ref<Artist>();
const artistTopTracks = ref<Track[]>([]);
const artistAlbums = ref<Album[]>([]);
const loading = ref(true);

watchEffect(async () => {
  const item = await api.getArtist(
    props.provider,
    props.item_id,
    parseBool(props.lazy),
    parseBool(props.refresh)
  );
  artist.value = item;
  // fetch additional info once main info retrieved
  artistAlbums.value = await api.getArtistAlbums(props.provider, props.item_id);
  artistTopTracks.value = await api.getArtistTracks(props.provider, props.item_id);
  loading.value = false;
});
</script>
