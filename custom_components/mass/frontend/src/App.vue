<template>
  <v-app :theme="theme">
    <!-- override background color set in iframe by HASS -->
    <div
      style="
        position: fixed;
        height: 100%;
        width: 100%;
        background: rgb(var(--v-theme-background));
      "
    ></div>
    <ContextMenu
      v-model="store.showContextMenu"
      :items="store.contextMenuItems"
      :parent-item="store.contextMenuParentItem"
    />
    <player-select />
    <v-app-bar dense app style="height: 55px" :color="topBarColor">
      <v-app-bar-nav-icon
        :icon="mdiArrowLeft"
        @click="$router.push('/')"
        v-if="$router.currentRoute.value.path != '/'"
      />
      <v-toolbar-title>{{ store.topBarTitle }}</v-toolbar-title>
    </v-app-bar>
    <v-main>
      <v-container fluid style="padding: 0">
        <router-view></router-view>
      </v-container>
    </v-main>
    <player-o-s-d />
  </v-app>
</template>

<script setup lang="ts">
/* eslint-disable @typescript-eslint/no-unused-vars,vue/no-setup-props-destructure */
import { mdiArrowLeft } from "@mdi/js";

import { ref, computed, watchEffect, inject, reactive } from "vue";
import { api } from "./plugins/api";
import { store } from "./plugins/store";
import { isColorDark, mergeDeep } from "./utils";
import PlayerOSD from "./components/PlayerOSD.vue";
import PlayerSelect from "./components/PlayerSelect.vue";
import ContextMenu from "./components/ContextMenu.vue";
import type { HomeAssistant, HassPanel, HassRoute } from "./plugins/api";
import "vuetify/styles";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";
import { Connection } from "home-assistant-js-websocket";
import type { HassPanelData, HassData } from "./main";
import { useI18n } from "vue-i18n";

const { t, locale } = useI18n({ useScope: "global" });

interface HassPropEvent extends Event {
  detail: HassData;
}
interface HassPanelPropEvent extends Event {
  detail: HassPanelData;
}
const initialized = ref(false);

const topBarColor = computed(() => {
  if (store.topBarTransparent) return "transparent";
  return store.topBarDefaultColor;
});

document.addEventListener("forward-hass-prop", function (e) {
  console.log("hass prop updated");
  if (!initialized.value) {
    api.initialize((e as HassPropEvent).detail.connection);
    locale.value = (e as HassPropEvent).detail.selectedLanguage;
  }
  setTheme((e as HassPropEvent).detail);
});

document.addEventListener("forward-panel-prop", function (e) {
  console.log("panel prop updated");
  store.defaultTopBarTitle = (e as HassPanelPropEvent).detail.config.title;
});

// set darkmode based on HA darkmode
// TODO: we can set the entire vuetify theme based on HA theme
const theme = ref("light");
let lastTheme = "";
const setTheme = async function (hassData: HassData) {
  // determine if dark theme active
  const curTheme = hassData.themes?.theme || "default";
  const darkMode = hassData?.themes?.darkMode || false;
  const checkKey = `${curTheme}.${darkMode}`;
  if (lastTheme == checkKey) return;
  lastTheme = checkKey;

  // try to figure out topbar color
  if (curTheme == "default") {
    // default theme
    const defaultPrimaryColor = hassData.selectedTheme?.primaryColor || "#03A9F4";
    store.topBarDefaultColor = "#101e24";
    store.darkTheme = darkMode;
    store.topBarDefaultColor = darkMode ? "#101e24" : defaultPrimaryColor;
  } else {
    // custom theme
    const theme = hassData.themes?.themes[hassData.themes.theme];
    if (theme && "app-header-background-color" in theme)
      store.topBarDefaultColor = theme["app-header-background-color"];
    if (darkMode) store.darkTheme = true;
    else if (theme) {
      const bgColor = theme["primary-background-color"] || store.topBarDefaultColor;
      console.log("bgcolor", bgColor);
      store.darkTheme = isColorDark(bgColor);
    }
  }
  theme.value = store.darkTheme ? "dark" : "light";
};
</script>

<style lang="scss">
.vertical-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.right {
  float: right;
}

.left {
  float: left;
}

div.v-navigation-drawer__scrim {
  opacity: 0.8;
  background: grey;
}
.vertical-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.volumerow {
  height: 60px;
  padding-top: 5px;
  padding-bottom: 0px;
}

.volumerow .v-slider .v-slider__container {
  margin-left: 57px;
  margin-right: 15px;
  margin-top: -10px;
}

.slider .div.v-input__append {
  padding-top: 0px;
  margin-top: -10px;
}

.active-tab {
  background: rgba(var(--v-theme-on-surface), 0.6);
  color: rgb(var(--v-theme-surface));
}
.inactive-tab {
  background: rgba(var(--v-theme-on-surface), 0.3);
  color: rgba(var(--v-theme-surface), 0.6);
}

.hiresicon {
  position: absolute;
  margin-left: 5px;
  margin-top: -20px;
  height: 30px;
  border-radius: 5px;
}
</style>
