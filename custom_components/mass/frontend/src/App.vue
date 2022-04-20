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
    <TopBar />
    <v-main>
      <v-container fluid style="padding: 0">
        <router-view></router-view>
        <!-- white space to reserve space for footer -->
        <div style="height: 150px"></div>
      </v-container>
    </v-main>
    <player-o-s-d />
  </v-app>
</template>

<script setup lang="ts">
/* eslint-disable @typescript-eslint/no-unused-vars,vue/no-setup-props-destructure */
import { ref } from "vue";
import { api } from "./plugins/api";
import { store } from "./plugins/store";
import { useRouter } from "vue-router";
import { isColorDark } from "./utils";
import TopBar from "./components/TopBar.vue";
import PlayerOSD from "./components/PlayerOSD.vue";
import PlayerSelect from "./components/PlayerSelect.vue";
import ContextMenu from "./components/ContextMenu.vue";
import type { HomeAssistant, HassPanel, HassRoute } from "./plugins/api";
import "vuetify/styles";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";
import { Connection } from "home-assistant-js-websocket";
import type { HassPanelData, HassData } from "./main";
import { useI18n } from "vue-i18n";

const { locale } = useI18n({ useScope: "global" });
const router = useRouter();

interface HassPropEvent extends Event {
  detail: HassData;
}
interface HassPanelPropEvent extends Event {
  detail: HassPanelData;
}

document.addEventListener("forward-hass-prop", function (e) {
  const hass = (e as HassPropEvent).detail;
  if (!hass) return;
  if (!api.initialized) {
    api.initialize(hass.connection);
    locale.value = hass.selectedLanguage;
  }
  setTheme(hass);
});

document.addEventListener("forward-panel-prop", function (e) {
  store.defaultTopBarTitle = (e as HassPanelPropEvent).detail.config.title;
});

// set theme colors based on HA theme
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

setTimeout(() => {
  if (!api.initialized) {
    console.log("stand-alone mode activating...")
    api.initialize();
  }
}, 500);
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
