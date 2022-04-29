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
        >
          <v-icon
            variant="plain"
            :icon="card.icon"
            size="70"
            style="align: center;padding: 10px"
          >
          </v-icon>
          <v-divider />
          <div class="text-center text-subtitle-1" style="padding: 10px">
            {{ $t(card.key) }}
          </div>
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

store.topBarTitle = store.defaultTopBarTitle;

const cards = ref([
  { key: "artists", icon: mdiAccountMusic, path: "/artists" },
  { key: "albums", icon: mdiAlbum, path: "/albums" },
  { key: "tracks", icon: mdiFileMusic, path: "/tracks" },
  { key: "playlists", icon: mdiPlaylistMusic, path: "/playlists" },
  { key: "radios", icon: mdiRadio, path: "/radios" },
]);
</script>
