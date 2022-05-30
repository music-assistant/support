<template>
  <ItemsListing
    itemtype="artists"
    :items="api.library.artists"
    :show-library="false"
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

store.topBarTitle = t("artists");
</script>
