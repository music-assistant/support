/* eslint-disable @typescript-eslint/no-explicit-any */
import { createI18n } from "vue-i18n";
import en from "../../locales/en.json";
import nl from "../../locales/nl.json";

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: "en",
  fallbackLocale: "en",
  messages: {
    en,
    nl
  }
});
