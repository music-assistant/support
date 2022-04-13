<template>
  <v-app>
    <v-app-bar
      :color="color"
      dark
      dense
      app
      style="height: 55px; padding: 0; vertical-content-align: center"
    >
      <v-app-bar-nav-icon :icon="mdiHome" />
      <v-toolbar-title>{{ topbarTitle }}</v-toolbar-title>
    </v-app-bar>
    <v-main>
      <div>{{ Object.keys(api.players).length }}</div>
      <HomeView v-if="route?.path == '/' || route?.path == ''" />
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
/* eslint-disable @typescript-eslint/no-unused-vars,vue/no-setup-props-destructure */
import { mdiHome } from "@mdi/js";
import HomeView from "./views/Home.vue";
import { provide, ref, computed } from "vue";
import type { HomeAssistant, HassPanel, HassRoute } from "./plugins/api";
import { MusicAssistantApi } from "./plugins/api";
import { store } from "./plugins/store";
interface Props {
  hass?: HomeAssistant;
  narrow?: boolean;
  panel?: HassPanel;
  route?: HassRoute;
}

const props = defineProps<Props>();
const topbarTitle = ref("Home Assistant");
const topBarTransparent = ref(false);

const api = new MusicAssistantApi(props.hass);
provide("api", api);

const color = computed(() => {
  if (topBarTransparent.value) {
    return "transparent";
  } else if (props.hass?.themes.darkMode) {
    return "";
  } else return "";
});
</script>

<style lang="scss">
@use "vuetify/styles";
</style>
