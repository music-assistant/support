<template>
  <div
    style="
      padding-left: 15px;
      padding-right: 15px;
      padding-top: 20px;
      padding-bottom: 20px;
    "
  >
    <v-row dense>
      <v-col v-for="card in cards" :key="card.key">
        <v-card
          @click="$router.push(card.path)"
          hover
          border
          min-width="120"
          align="center"
          justify="center"
          :disabled="api.library[card.key].length == 0"
          :style="api.library[card.key].length == 0 ? 'opacity:0.5' : ''"
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
            <span class="text-caption" v-if="api.library[card.key].length > 0"
              >({{ api.library[card.key].length }})</span
            >
          </span>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { store } from "../plugins/store";

import {
  mdiAccountMusic,
  mdiAlbum,
  mdiFileMusic,
  mdiPlaylistMusic,
  mdiRadio,
} from "@mdi/js";
import api from "@/plugins/api";
import type { Library } from "@/plugins/api";

store.topBarTitle = store.defaultTopBarTitle;

const artistsKey: keyof Library = "artists";
const albumsKey: keyof Library = "albums";
const tracksKey: keyof Library = "tracks";
const radiosKey: keyof Library = "radios";
const playlistsKey: keyof Library = "playlists";

const cards = ref([
  {
    key: artistsKey,
    icon: mdiAccountMusic,
    path: "/artists",
  },
  {
    key: albumsKey,
    icon: mdiAlbum,
    path: "/albums",
  },
  {
    key: tracksKey,
    icon: mdiFileMusic,
    path: "/tracks",
  },
  {
    key: playlistsKey,
    icon: mdiPlaylistMusic,
    path: "/playlists",
  },
  {
    key: radiosKey,
    icon: mdiRadio,
    path: "/radios",
  },
]);
</script>
