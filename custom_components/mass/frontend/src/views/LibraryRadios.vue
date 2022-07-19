<template>
  <ItemsListing
    itemtype="radios"
    :items="items"
    :show-duration="false"
    :show-providers="true"
    :show-library="true"
    :load-data="loadItems"
    :sort-keys="['sort_name', 'timestamp DESC']"
  />
</template>

<script setup lang="ts">
import { mdiFileSync } from "@mdi/js";
import { onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api, MediaType, type Radio } from "../plugins/api";
import { store } from "../plugins/store";

const { t } = useI18n();
const items = ref<Radio[]>([]);

store.topBarTitle = t("radios");
store.topBarContextMenuItems = [
  {
    label: "sync",
    labelArgs: [],
    action: () => {
      api.startSync(MediaType.RADIO);
    },
    icon: mdiFileSync
  },
];
onBeforeUnmount(() => {
  store.topBarContextMenuItems = [];
});

const loadItems = async function (
  offset: number,
  limit: number,
  sort: string,
  search?: string,
  inLibraryOnly = true
) {
  const library = inLibraryOnly || undefined;
  return await api.getRadios(offset, limit, sort, library, search);
};
</script>
