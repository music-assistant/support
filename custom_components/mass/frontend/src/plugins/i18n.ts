/* eslint-disable @typescript-eslint/no-explicit-any */
import { createI18n } from "vue-i18n";

// supported languages need to be setup here manually
import en from "../../../translations/frontend/en.json";
import nl from "../../../translations/frontend/nl.json";
const messages = {
  en,
  nl,
};

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: "en",
  fallbackLocale: "en",
  messages,
});
