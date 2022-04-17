<template>
<ItemsListing mediatype="artists" :items="items" />
</template>

<script setup lang="ts">

import { ref } from "vue";
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api, MediaType } from "../plugins/api";
import type { Artist } from "../plugins/api";
import {store} from "../plugins/store";

const i18n = useI18n();
const items = ref<Artist[]>([]);

api.getLibraryArtists().then((artists) => {
  console.log('artists', artists)
  items.value.push(...artists)
})

store.topBarTransparent = false;
store.topBarTitle = i18n.t("library") || i18n.t("library")

</script>
