<template>
  <ItemsListing
    itemtype="tracks"
    :items="api.library.tracks"
    :show-library="false"
    :show-track-number="false"
    :show-providers="true"
    :show-search-by-default="true"
  />
</template>

<script setup lang="ts">
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api } from "../plugins/api";
import { store } from "../plugins/store";

const { t } = useI18n();

store.topBarTitle = t("tracks");
</script>
