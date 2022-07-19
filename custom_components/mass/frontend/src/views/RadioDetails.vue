<template>
  <section>
    <InfoHeader :item="itemDetails" />
    <v-tabs v-model="activeTab" show-arrows grow hide-slider>
      <v-tab
        :class="activeTab == 'details' ? 'active-tab' : 'inactive-tab'"
        value="details"
      >
        {{ $t("details") }}</v-tab
      >
    </v-tabs>
    <v-divider />
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
          <tr v-for="item of itemDetails?.provider_ids" :key="item.item_id">
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
          </tr>
        </tbody>
      </v-table>
    </div>
  </section>
</template>

<script setup lang="ts">
import InfoHeader from "../components/InfoHeader.vue";
import { ref } from "@vue/reactivity";
import {
  MassEventType,
  type ProviderType,
  type Radio,
  type MassEvent,
  type MediaItemType,
} from "../plugins/api";
import { api } from "../plugins/api";
import {
  getProviderIcon,
  getQualityIcon,
} from "../components/ProviderIcons.vue";
import { onBeforeUnmount, onMounted, watchEffect } from "vue";

export interface Props {
  item_id: string;
  provider: string;
}
const props = defineProps<Props>();
const activeTab = ref("");

const itemDetails = ref<Radio>();

const loadItemDetails = async function () {
  itemDetails.value = await api.getRadio(
    props.provider as ProviderType,
    props.item_id
  );
  activeTab.value = "details";
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
</script>

<style>
.details-column {
  max-width: 200px;
  width: 30px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
