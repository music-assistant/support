<template>
  <section>
    <InfoHeader :item="itemDetails" />
    <v-tabs v-model="activeTab" show-arrows grow hide-slider>
      <v-tab
        :class="activeTab == 'versions' ? 'active-tab' : 'inactive-tab'"
        value="details"
      >
        {{ $t('track_versions') }}
      </v-tab>
    </v-tabs>
    <v-divider />
    <ItemsListing
      v-if="activeTab == 'versions'"
      itemtype="trackversions"
      :parent-item="itemDetails"
      :show-providers="true"
      :show-library="false"
      :show-track-number="false"
      :load-data="loadTrackVersions"
      :sort-keys="['provider', 'sort_name', 'duration']"
    />
  </section>
</template>

<script setup lang="ts">
import ItemsListing, { filteredItems } from '../components/ItemsListing.vue';
import InfoHeader from '../components/InfoHeader.vue';
import { ref, reactive } from 'vue';
import {
  MassEventType,
  type ProviderType,
  type Track,
  type MassEvent,
  type MediaItemType,
} from '../plugins/api';
import { api } from '../plugins/api';
import { onBeforeUnmount, onMounted, watchEffect } from 'vue';

export interface Props {
  item_id: string;
  provider: string;
}
const props = defineProps<Props>();
const activeTab = ref('');

const itemDetails = ref<Track>();

const loadItemDetails = async function () {
  itemDetails.value = await api.getTrack(
    props.provider as ProviderType,
    props.item_id
  );
  activeTab.value = 'versions';
};

watchEffect(() => {
  // load info
  loadItemDetails();
});

onMounted(() => {
  //reload if/when item updates
  const unsub = api.subscribe_multi(
    [MassEventType.MEDIA_ITEM_ADDED, MassEventType.MEDIA_ITEM_UPDATED],
    (evt: MassEvent) => {
      // refresh info if we receive an update for this item
      const updatedItem = evt.data as MediaItemType;
      if (itemDetails.value?.uri == updatedItem.uri) {
        loadItemDetails();
      } else {
        for (const provId of updatedItem.provider_ids) {
          if (
            provId.prov_type == itemDetails.value?.provider &&
            provId.item_id == itemDetails.value?.item_id
          ) {
            loadItemDetails();
            break;
          }
        }
      }
    }
  );
  onBeforeUnmount(unsub);
});

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
