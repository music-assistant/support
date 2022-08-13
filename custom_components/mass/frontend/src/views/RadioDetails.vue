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
      itemtype="radioversions"
      :parent-item="itemDetails"
      :show-providers="true"
      :show-library="false"
      :show-radio-number="false"
      :show-duration="false"
      :load-data="loadRadioVersions"
      :sort-keys="['provider', 'sort_name']"
    />
  </section>
</template>

<script setup lang="ts">
import ItemsListing, { filteredItems } from '../components/ItemsListing.vue';
import InfoHeader from '../components/InfoHeader.vue';
import { ref } from 'vue';
import type { ProviderType, Radio } from '../plugins/api';
import { api } from '../plugins/api';
import { watchEffect } from 'vue';

export interface Props {
  item_id: string;
  provider: string;
}
const props = defineProps<Props>();
const activeTab = ref('');

const itemDetails = ref<Radio>();

const loadItemDetails = async function () {
  itemDetails.value = await api.getRadio(
    props.provider as ProviderType,
    props.item_id
  );
  activeTab.value = 'versions';
};

watchEffect(() => {
  // load info
  loadItemDetails();
});

const loadRadioVersions = async function (
  offset: number,
  limit: number,
  sort: string,
  search?: string,
  inLibraryOnly = true
) {
  const radioVersions = await api.getRadioVersions(
    props.provider as ProviderType,
    props.item_id
  );
  return filteredItems(
    radioVersions,
    offset,
    limit,
    sort,
    search,
    inLibraryOnly
  );
};
</script>
