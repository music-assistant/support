<template>
  <section>
    <InfoHeader :item="track" />
    <v-tabs v-model="activeTab" show-arrows grow hide-slider>
      <v-tab
        :class="activeTab == 'versions' ? 'active-tab' : 'inactive-tab'"
        value="versions"
      >
        {{ $t("track_versions") }}</v-tab
      >
    </v-tabs>
    <v-divider />
    <ItemsListing
      :items="trackVersions"
      itemtype="tracks"
      :parent-item="track"
      v-if="activeTab == 'versions'"
    />
  </section>
</template>

<script setup lang="ts">
import ItemsListing from "../components/ItemsListing.vue";
import InfoHeader from "../components/InfoHeader.vue";
import { ref } from "@vue/reactivity";
import type { Track } from "../plugins/api";
import api from "../plugins/api";

interface Props {
  item_id: string;
  provider: string;
}
const props = defineProps<Props>();
const activeTab = ref(0);

const track = ref<Track>();
const trackVersions = ref<Track[]>([]);

api.getTrack(props.provider, props.item_id).then((x) => {
  track.value = x;
});
api.getTrackVersions(props.provider, props.item_id).then((x) => {
  trackVersions.value.push(...x);
});
</script>

