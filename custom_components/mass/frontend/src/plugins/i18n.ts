/* eslint-disable @typescript-eslint/no-explicit-any */
import { createI18n } from "vue-i18n";

// supported languages need to be setup here manually
import de from "../../../translations/frontend/de.json";
import en from "../../../translations/frontend/en.json";
import nl from "../../../translations/frontend/nl.json";
import pl from "../../../translations/frontend/pl.json";
import fr from "../../../translations/frontend/fr.json";
import es from "../../../translations/frontend/es.json";
const messages = {
  de,
  en,
  nl,
  pl,
  fr,
  es
};

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: "en",
  fallbackLocale: "en",
  messages,
});
