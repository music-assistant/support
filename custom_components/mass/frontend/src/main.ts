// import { defineCustomElement } from "./defineCustomElementWithStyles";
import { defineCustomElement } from "vue";
import App from "./App.ce.vue";
// import vuetify from "./plugins/vuetify";
// import { router } from "./plugins/router";
// import api from "./plugins/api";
// import { i18n } from "./plugins/i18n";

customElements.define("music-assistant", defineCustomElement(App));
