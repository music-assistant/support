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
      :loading="loading"
      itemtype="albumtracks"
      :parent-item="album"
      v-if="activeTab == 'tracks'"
    />
    <ItemsListing
      :items="albumVersions"
      :loading="loading"
      itemtype="albums"
      :parent-item="album"
      v-if="activeTab == 'versions'"
    />
  </section>
</template>

<script setup lang="ts">
import ItemsListing from "../components/ItemsListing.vue";
import InfoHeader from "../components/InfoHeader.vue";
import type { Album, MassEvent, Track } from "../plugins/api";
import { api, MassEventType } from "../plugins/api";
import { onBeforeUnmount, watchEffect, ref } from "vue";
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
const activeTab = ref("tracks");

const album = ref<Album>();
const albumTracks = ref<Track[]>([]);
const albumVersions = ref<Album[]>([]);
const loading = ref(true);

watchEffect(async () => {
  const item = await api.getAlbum(
    props.provider,
    props.item_id,
    parseBool(props.lazy),
    parseBool(props.refresh)
  );
  album.value = item;
  // fetch additional info once main info retrieved
  albumVersions.value = await api.getAlbumVersions(props.provider, props.item_id);
  albumTracks.value = await api.getAlbumTracks(props.provider, props.item_id);
  loading.value = false;
});

// listen for item updates to refresh interface when that happens
const unsub = api.subscribe(MassEventType.ALBUM_ADDED, (evt: MassEvent) => {
  const newItem = evt.data as Album;
  if (
    (props.provider == "database" && newItem.item_id == props.item_id) ||
    newItem.provider_ids.filter(
      (x) => x.provider == props.provider && x.item_id == props.item_id
    ).length > 0
  ) {
    // got update for current item
    album.value = newItem;
  }
});
onBeforeUnmount(unsub);
</script>
