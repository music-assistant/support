<template>
  <v-app>
    <v-app-bar color="white" dense app style="height: 55px;padding:0;vertical-content-align:center">
      <v-app-bar-nav-icon :icon="mdiHome" />
      <v-toolbar-title>{{ topbarTitle }}</v-toolbar-title>
    </v-app-bar>
    <v-main>
      <HomeView v-if="route.path == '/' || route.path == ''" />
    </v-main>
  </v-app>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import { mdiHome } from "@mdi/js";
import HomeView from "./views/Home.vue";

export default defineComponent({
  name: "App",
  components: { HomeView },
  props: {
    hass: { type: Object, default: new Object({ states: [] }) },
    narrow: { type: Boolean, default: false },
    panel: {
      type: Object,
      default: new Object({
        config: {
          title: 'Music Assistant'
        }
      }),
    },
    route: { type: Object, default: new Object({ path: "" }) },
  },

  computed: {
    color() {
      if (this.topBarTransparent) {
        return "transparent";
      } else if (this.$vuetify.theme.current.value == "dark") {
        // is dark
        return "";
      } else return "";
    },
  },
  mounted() {
    console.log(this.panel)
    // this.hass.callService("homeassistant", "toggle", {
    //     entity_id: 'media_player.mass_soundbar_woonkamer'
    //   });
  },
  data() {
    return {
      topBarTransparent: false,
      topbarTitle: this.panel.config.title,
      mdiHome,
    };
  },
});
</script>

<style lang="scss">
@use "vuetify/styles";
</style>
