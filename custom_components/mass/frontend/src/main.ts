import { defineCustomElement } from "./defineCustomElementWithStyles";
import App from "./App.vue";
import vuetify from "./plugins/vuetify";

customElements.define(
  "music-assistant",
  defineCustomElement(App, {
    plugins: [vuetify]
  })
);
