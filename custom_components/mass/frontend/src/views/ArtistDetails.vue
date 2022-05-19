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
      :items="artistTopTracks"
      :loading="loading"
      itemtype="tracks"
      :parent-item="artist"
      :show-providers="true"
      :show-track-number="false"
      v-if="activeTab == 'tracks'"
    />
    <ItemsListing
      :items="artistAlbums"
      :loading="loading"
      itemtype="albums"
      :parent-item="artist"
      :show-providers="true"
      v-if="activeTab == 'albums'"
    />
  </section>
</template>

<script setup lang="ts">
import ItemsListing from "../components/ItemsListing.vue";
import InfoHeader from "../components/InfoHeader.vue";
import { ref } from "@vue/reactivity";
import type { Album, Artist, MassEvent, ProviderType, Track } from "../plugins/api";
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

// listen for item updates to refresh interface when that happens
const unsub = api.subscribe(MassEventType.ARTIST_ADDED, (evt: MassEvent) => {
  const newItem = evt.data as Artist;
  if (
    (props.provider == "database" && newItem.item_id == props.item_id) ||
    newItem.provider_ids.filter(
      (x) => x.prov_type == props.provider && x.item_id == props.item_id
    ).length > 0
  ) {
    // got update for current item
    artist.value = newItem;
    getExtraInfo();
  }
});
onBeforeUnmount(unsub);
</script>
