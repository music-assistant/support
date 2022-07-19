<template>
  <section>
    <InfoHeader :item="itemDetails" />
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
      itemtype="trackversions"
      :parent-item="itemDetails"
      :show-providers="true"
      :show-library="false"
      :show-track-number="false"
      :load-data="loadTrackVersions"
      :sort-keys="['sort_name', 'duration']"
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
            <th class="text-left">preview</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) of itemDetails?.provider_ids" :key="item.item_id">
            <td class="details-column">
              <v-img
                width="25px"
                :src="getProviderIcon(item.prov_type)"
              ></v-img>
            </td>
            <td class="details-column">
              <a :href="item.url" target="_blank">{{ item.item_id }}</a>
            </td>
            <td class="details-column">{{ item.available }}</td>
            <td class="details-column">
              <v-img
                width="35px"
                :src="getQualityIcon(item.quality)"
                :style="
                  $vuetify.theme.current.dark
                    ? 'object-fit: contain;'
                    : 'object-fit: contain;filter: invert(100%);'
                "
              ></v-img>
            </td>
            <td class="details-column">{{ item.details }}</td>
            <td
              class="details-column"
              @mouseover="fetchPreviewUrl(item.prov_type, item.item_id, index)"
            >
              <audio
                style="width: 260px"
                controls
                :src="previewUrls[index]"
              ></audio>
            </td>
          </tr>
        </tbody>
      </v-table>
    </div>
  </section>
</template>

<script setup lang="ts">
import ItemsListing, { filteredItems } from "../components/ItemsListing.vue";
import InfoHeader from "../components/InfoHeader.vue";
import { ref, reactive } from "@vue/reactivity";
import type { ProviderType, Track } from "../plugins/api";
import { api } from "../plugins/api";
import {
  getProviderIcon,
  getQualityIcon,
} from "../components/ProviderIcons.vue";
import { watchEffect } from "vue";

export interface Props {
  item_id: string;
  provider: string;
}
const props = defineProps<Props>();
const activeTab = ref("");

const itemDetails = ref<Track>();
const previewUrls = reactive<Record<number, string>>({});

const loadItemDetails = async function () {
  itemDetails.value = await api.getTrack(
    props.provider as ProviderType,
    props.item_id
  );
  activeTab.value = "versions";
};

watchEffect(() => {
  // load info
  loadItemDetails();
});

const fetchPreviewUrl = async function (
  provider: ProviderType,
  item_id: string,
  index: number
) {
  if (index in previewUrls) return;
  const url = await api.getTrackPreviewUrl(provider, item_id);
  previewUrls[index] = url;
};

const loadTrackVersions = async function (
  offset: number,
  limit: number,
  sort: string,
  search?: string,
  inLibraryOnly = true
) {
  const trackVersions = await api.getTrackVersions(
    props.provider as ProviderType,
    props.item_id
  );
  return filteredItems(
    trackVersions,
    offset,
    limit,
    sort,
    search,
    inLibraryOnly
  );
};
</script>

<style>
.details-column {
  max-width: 200px;
  width: 30px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
