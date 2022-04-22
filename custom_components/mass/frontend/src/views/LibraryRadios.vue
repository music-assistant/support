<template>
  <ItemsListing itemtype="radios" :items="items" :loading="loading" />
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import ItemsListing from "../components/ItemsListing.vue";
import { api } from "../plugins/api";
import type { Radio } from "../plugins/api";
import { store } from "../plugins/store";

const {t } = useI18n();
const items = ref<Radio[]>([]);
const loading = ref(true);

api.getLibraryRadios().then((radios) => {
  items.value = radios;
  loading.value = false;
});

store.topBarTitle = t("radios");
</script>
