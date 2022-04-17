// Vuetify
import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";
import { aliases, mdi } from "vuetify/lib/iconsets/mdi-svg";

import colors from "vuetify/lib/util/colors";
import "vuetify/styles";

export default createVuetify(
  // https://vuetifyjs.com/en/introduction/why-vuetify/#feature-guides
  {
    components,
    directives,
    icons: {
      defaultSet: "mdi",
      aliases,
      sets: {
        mdi
      }
    },
    display: {
      mobileBreakpoint: "md",
      thresholds: {
        xs: 0,
        sm: 340,
        md: 540,
        lg: 800,
        xl: 1280
      }
    },
    theme: {
      defaultTheme: "light",
      themes: {
        light: {
          dark: false,
          colors: {
            primary: colors.blue.darken4,
            accent: colors.blue.lighten2
          }
        },
        dark: {
          dark: true,
          colors: {
            primary: colors.blue.base,
            accent: colors.blue.darken2
          }
        }
      }
    }
  }
);
