<template>
  <v-app :theme="theme">
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
      <v-container fluid>
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
import type { HomeAssistant, HassPanel, HassRoute } from "./plugins/api";
import "vuetify/styles";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";
import { Connection } from "home-assistant-js-websocket";
import type { HassPropsForwardElem, HassData } from "./main";
import { useI18n } from "vue-i18n";

const { t, locale } = useI18n({ useScope: 'global' })

interface HassDataPropsEvent extends Event {
  detail: HassPropsForwardElem;
}

const topBarColor = computed(() => {
  if (store.topBarTransparent) return "transparent";
  return store.topBarDefaultColor;
});

document.addEventListener("hass-props-forward", function (e) {
  // we're only interested in a few properties of the hass object
  const hassElem = (e as HassDataPropsEvent).detail;
  api.initialize(hassElem.hass?.connection);
  if (hassElem.panel) store.defaultTopBarTitle = hassElem.panel.config.title;
  if (hassElem.hass) setTheme(hassElem.hass);
  if (hassElem.hass) locale.value = hassElem.hass?.selectedLanguage;
});

document.addEventListener("hass-updated", function (e) {
  console.log("hass props updated");
  const hassElem = (e as HassDataPropsEvent).detail;
  if (hassElem.hass) setTheme(hassElem.hass);
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
    else {
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

.bg-image {
  /* Add the blur effect */
  filter: blur(20px);
  -webkit-filter: blur(20px);
  /* Center and scale the image nicely */
  background-position: center;
  background-size: cover;
}

.mediadetails {
  display: inline-block;
  width: 100%;
  height: 55px;
  margin-top: 0px;
  margin-left: 0px;
  margin-bottom: 6px;
  padding-top: 5px;
}

.mediadetails-thumb {
  width: auto;
  float: left;
  height: 50px;
}
.mediadetails-title {
  width: auto;
  padding-left: 10px;
  padding-top: 0px;
  float: left;
}

.mediadetails-time {
  float: right;
  width: auto;
  margin-top: 30px;

  position: absolute;
  right: 15px;
}
.mediadetails-streamdetails {
  float: right;
  width: 40px;
  right: 10px;
  margin-top: -10px;
  position: absolute;
}

.mediadetails-streamdetails .icon {
  opacity: 100;
}

.mediacontrols {
  display: inline-block;
  width: 100%;
  height: 55px;
  margin-top: 5px;
  margin-left: 0px;
  padding-bottom: 5px;
}
.mediacontrols-left {
  width: auto;
  margin-left: -15px;
  padding-top: 0px;
  float: left;
}
.mediacontrols-right {
  float: right;
  padding-left: 10px;
  padding-right: 0px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.mediacontrols-right span {
  width: 80px;
  font-size: xx-small;
  padding-top: 5px;
  text-overflow: ellipsis;

  /* Required for text-overflow to do anything */
  white-space: nowrap;
  overflow: hidden;
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
.playerrow {
  height: 60px;
}

div.v-expansion-panel-text__wrapper {
  padding-left: 0px;
  padding-right: 0px;
  padding-top: 0px;
  padding-bottom: 0px;
}

div.v-expansion-panel--active:not(:first-child),
.v-expansion-panel--active + .v-expansion-panel {
  margin-top: 0px;
}
div.v-expansion-panel__shadow {
  box-shadow: none;
}
.hiresicon {
  position: absolute;
  margin-left: 5px;
  margin-top: -20px;
  height: 30px;
  border-radius: 5px;
}
.listitem-actions {
  display: flex;
  justify-content: end;
  width: auto;
  height: 50px;
  vertical-align: middle;
  align-items: center;
  padding: 0px;
}
.listitem-action {
  padding-left: 5px;
}
.listitem-thumb {
  padding-left: 0px;
  margin-right: 10px;
  margin-left: -15px;
  width: 50px;
  height: 50px;
}
.provider-icons {
  width: auto;
  vertical-align: middle;
  align-items: center;
  padding: 0px;
}
.provider-icon {
  float: inherit;
  padding-left: 5px;
  display: flex;
}
</style>
