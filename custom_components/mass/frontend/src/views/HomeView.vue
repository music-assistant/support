<template>
  <div
    style="
      padding-left: 15px;
      padding-right: 15px;
      padding-top: 20px;
      padding-bottom: 20px;
    "
  >
    <!-- <v-text-field
      v-model="search"
      id="searchInput"
      clearable
      :prepend-inner-icon="mdiMagnify"
      label="Global search..."
      hide-details
      variant="outlined"
      @focus="searchHasFocus = true"
      @blur="searchHasFocus = false"
    ></v-text-field> -->

    <v-progress-linear indeterminate v-if="loading"></v-progress-linear>
    <!-- panel view -->
    <!-- <v-row dense align-content="start" align="start">
      <v-col v-for="item in browseItems" :key="item.uri" align-self="start">
        <PanelviewItem :item="item" :size="thumbSize" :is-selected="false" />
      </v-col>
    </v-row> -->

    <div style="margin-top: 20px">
      <v-row dense align-content="start" align="start">
        <v-col v-for="card in cards" :key="card.label" align-self="start">
          <v-card
            @click="$router.push(card.path)"
            hover
            border
            width="auto"
            min-height="90"
            min-width="90"
            align="center"
            justify="center"
          >
            <v-btn variant="plain" icon height="80">
              <v-icon :icon="card.icon" size="80" style="align: center; padding: 10px">
              </v-icon>
            </v-btn>
            <v-divider />
            <span class="text-center text-subtitle-1" style="padding: 10px">
              {{ $t(card.label) }}
            </span>
          </v-card>
        </v-col>
      </v-row>

      <!-- <v-slide-group class="pa-4" :show-arrows="false">
      <v-slide-group-item v-for="card in cards" :key="card.key">
        <v-card
          @click="$router.push(card.path)"
          hover
          border
          min-width="120"
          align="center"
          justify="center"
          :disabled="api.stats.count[card.key] == 0"
          :style="api.stats.count[card.key] == 0 ? 'opacity:0.5' : ''"
        >
          <v-icon
            variant="plain"
            :icon="card.icon"
            size="70"
            style="align: center; padding: 10px"
          >
          </v-icon>
          <v-divider />
          <span class="text-center text-subtitle-1" style="padding: 10px">
            {{ $t(card.key) }}
            <span class="text-caption" v-if="api.stats.count[card.key] > 0"
              >({{ api.stats.count[card.key] }})</span
            >
          </span>
        </v-card>
      </v-slide-group-item>
    </v-slide-group> -->
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { store } from "../plugins/store";
import PanelviewItem from "../components/PanelviewItem.vue";

import {
  mdiAccountMusic,
  mdiAlbum,
  mdiFileMusic,
  mdiMagnify,
  mdiPlaylistMusic,
  mdiRadio,
  mdiFolder
} from "@mdi/js";
import api, { type MediaItemType } from "@/plugins/api";
import { useDisplay } from "vuetify";

const { mobile } = useDisplay();

store.topBarTitle = store.defaultTopBarTitle;

const searchHasFocus = ref(false);
const loading = ref(false);
const search = ref("");


const thumbSize = computed(() => {
  return mobile.value ? 150 : 225;
});

const cards = ref([
  {
    label: "artists",
    icon: mdiAccountMusic,
    path: "/artists",
  },
  {
    label: "albums",
    icon: mdiAlbum,
    path: "/albums",
  },
  {
    label: "tracks",
    icon: mdiFileMusic,
    path: "/tracks",
  },
  {
    label: "radios",
    icon: mdiRadio,
    path: "/radios",
  },
  {
    label: "playlists",
    icon: mdiPlaylistMusic,
    path: "/playlists",
  },
  {
    label: "browse",
    icon: mdiFolder,
    path: "/browse",
  },
]);
</script>
