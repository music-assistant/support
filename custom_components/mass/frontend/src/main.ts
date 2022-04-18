/* eslint-disable @typescript-eslint/no-explicit-any */
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
};

export type HassPanelData = {
  config: {
    title: string;
  };
};

export class HassPropsForwardElem extends HTMLElement {
  _hass?: HassData;
  _panel?: HassPanelData;

  public get hass() {
    return this._hass;
  }

  public set hass(val: HassData | undefined) {
    this._hass = val;
    document.dispatchEvent(
      new CustomEvent("hass-updated", {
        detail: this
      })
    );
  }

  public get panel() {
    return this._panel;
  }

  public set panel(val: HassPanelData | undefined) {
    this._panel = val;
  }

  connectedCallback() {
    const evt = new CustomEvent(`hass-props-forward`, {
      detail: this
    });
    document.dispatchEvent(evt);
  }
}
customElements.define("music-assistant", HassPropsForwardElem);
