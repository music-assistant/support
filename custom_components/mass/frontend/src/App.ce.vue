<template>
  <v-app>
    <PlayerSelect />
    <v-app-bar dense app style="height: 55px">
      <v-app-bar-nav-icon :icon="mdiHome" />
      <v-toolbar-title>{{ topbarTitle }}</v-toolbar-title>
    </v-app-bar>
    <v-main>
      <v-container fluid>
        <router-view></router-view>
      </v-container>
    </v-main>
    <PlayerOSD />
  </v-app>
</template>

<script setup lang="ts">
/* eslint-disable @typescript-eslint/no-unused-vars,vue/no-setup-props-destructure */
import { mdiHome } from "@mdi/js";

import { ref, computed } from "vue";
import vuetify from "./plugins/vuetify";
import { setupRouter } from "./plugins/router";
import { api } from "./plugins/api";
import { i18n } from "./plugins/i18n";
import { store } from "./plugins/store";
import { loadFonts } from "./plugins/webfontloader";
import { createApp, getCurrentInstance, onMounted } from "vue";
import { adoptStyles } from "./utils";
import PlayerOSD from "./components/PlayerOSD.vue";
import PlayerSelect from "./components/PlayerSelect.vue";
import type { HomeAssistant, HassPanel, HassRoute } from "./plugins/api";

interface Props {
  hass?: HomeAssistant;
  narrow?: boolean;
  panel?: HassPanel;
  route?: HassRoute;
}
const props = defineProps<Props>();

/////// workaround: allow plugins to be loaded on customelement wrapped app //////////

const app = createApp();
[vuetify, setupRouter(props.panel?.url_path || "/"), i18n].forEach(app.use);
loadFonts();
const inst = getCurrentInstance();
Object.assign(inst.appContext, app._context);
Object.assign(inst.provides, app._context.provides);

// move vuetify theme css from head (oustide shadowroot) into shadowroot css
onMounted(() => {
  console.log(`the component is now mounted.`);
  const themestyles = document.querySelector("#vuetify-theme-stylesheet")?.innerHTML;
  // document.querySelector("#vuetify-theme-stylesheet")?.remove();
  console.log("move theme css to shadowroot");
  const shadowRoot = getCurrentInstance()?.vnode?.el?.getRootNode();
  if (shadowRoot && themestyles) {
    adoptStyles(shadowRoot, themestyles, "#vuetify-theme-stylesheet");
  }
});
/////// end of workaround ///////////////////////////

const topbarTitle = ref("");
const topBarTransparent = ref(false);

if (props && props.hass) api?.initialize(props.hass);

console.log("cur theme", props.hass.themes);

const color = computed(() => {
  if (topBarTransparent.value) {
    return "transparent";
  } else if (props.hass?.themes.darkMode) {
    return "";
  } else return "";
});

// set default topbarTitle to panel title
if (props.panel) {
  topbarTitle.value = props.panel.config.title;
}
</script>

<style lang="scss">
@use "vuetify/styles";
@use "vue-virtual-scroller/dist/vue-virtual-scroller.css";
.body {
  overscroll-behavior-x: none;
}

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
  padding-right: 10px;
  margin-left: -15px;
}
.provider-icons {
  display: inline-grid;
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
