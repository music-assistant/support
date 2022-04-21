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
      <v-tab
        :class="activeTab == 'details' ? 'active-tab' : 'inactive-tab'"
        value="details"
      >
        {{ $t("details") }}</v-tab
      >
    </v-tabs>
    <v-divider />
    <ItemsListing
      :items="trackVersions"
      itemtype="tracks"
      :loading="loading"
      :parent-item="track"
      v-if="activeTab == 'versions'"
    />
    <div v-if="activeTab == 'details'">
      <v-table style="width: 100%">
        <thead>
          <tr>
            <th class="text-left">Provider</th>
            <th class="text-left">ID</th>
            <th class="text-left">Available ?</th>
            <th class="text-left">Quality</th>
            <th class="text-left">details</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in track?.provider_ids" :key="item.item_id">
            <td class="details-column">
              <v-img width="25px" :src="getProviderIcon(item.provider)"></v-img>
            </td>
            <td class="details-column">{{ item.item_id }}</td>
            <td class="details-column">{{ item.available }}</td>
            <td class="details-column">
              <v-img
                width="35px"
                :src="getQualityIcon(item.quality)"
                :style="
                  $vuetify.theme.current == 'light'
                    ? 'object-fit: contain;filter: invert(100%);'
                    : 'object-fit: contain;'
                "
              ></v-img>
            </td>
            <td class="details-column">{{ item.details }}</td>
          </tr>
        </tbody>
      </v-table>
    </div>
  </section>
</template>

<script setup lang="ts">
import ItemsListing from "../components/ItemsListing.vue";
import InfoHeader from "../components/InfoHeader.vue";
import { ref } from "@vue/reactivity";
import type { Track } from "../plugins/api";
import api from "../plugins/api";
import { getProviderIcon, getQualityIcon } from "../components/ProviderIcons.vue";
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

const track = ref<Track>();
const trackVersions = ref<Track[]>([]);
const loading = ref(true);

watchEffect(async () => {
  const item = await api.getTrack(
    props.provider,
    props.item_id,
    parseBool(props.lazy),
    parseBool(props.refresh)
  );
  track.value = item;
  // fetch additional info once main info retrieved
  trackVersions.value = await api.getTrackVersions(props.provider, props.item_id);
  loading.value = false;
});

</script>

<style>
.details-column {
  max-width: 200px;
  width: 30px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
