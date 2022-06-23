/* eslint-disable @typescript-eslint/no-explicit-any */
"use strict";
import "vuetify/styles";
import { createApp } from "vue";
import vuetify from "./plugins/vuetify";
import router from "./plugins/router";
import { i18n } from "./plugins/i18n";
import App from "./App.vue";
import { loadFonts } from "./plugins/webfontloader";
import type { Connection } from "home-assistant-js-websocket";

const app = createApp(App);

app.use(vuetify);
app.use(i18n);
app.use(router);
loadFonts();

const vueContainer = document.createElement("div");
vueContainer.setAttribute("id", "app");
document.body.appendChild(vueContainer);
app.mount("#app");

// Vue app as Custom element is not yet very mature in Vue3
// instead we take a different road by passing the hass object from an intermediate custom element

export type HassData = {
  connection?: Connection;
  selectedTheme?: {
    primaryColor?: string;
    accentColor?: string;
  };
  themes?: {
    theme: string;
    darkMode: boolean;
    themes: Record<string, Record<string, string>>;
  };
  selectedLanguage: string;
  dockedSidebar: string;
};

export type HassPanelData = {
  config: {
    title: string;
  };
};

class HassPropsForwardElem extends HTMLElement {
  public set hass(val: HassData) {
    document.dispatchEvent(
      new CustomEvent("forward-hass-prop", {
        detail: val,
      })
    );
  }

  public set panel(val: HassPanelData) {
    document.dispatchEvent(
      new CustomEvent("forward-panel-prop", {
        detail: val,
      })
    );
  }
}
customElements.define("music-assistant", HassPropsForwardElem);
