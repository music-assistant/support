<template>
  <ItemsListing
    itemtype="radios"
    :items="api.library.radios"
    :show-library="false"
    :show-providers="true"
    :show-duration="false"
    :show-search-by-default="true"
    :refresh-button="
      () => {
        api.startSync(MediaType.ALBUM);
      }
    "
  />
</template>

<script setup lang="ts">
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api, MediaType } from "../plugins/api";
import { store } from "../plugins/store";

const { t } = useI18n();

store.topBarTitle = t("radios");
</script>
