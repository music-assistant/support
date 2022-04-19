<template>
  <v-card>
    <v-container fluid>
      <v-row dense align-content="stretch" align="stretch">
        <v-col v-for="card in cards" :key="card.key" align-self="stretch">
          <v-card  @click="$router.push(card.path)">
            <v-btn variant="plain" :icon="card.icon" height="120px"> </v-btn>
            <v-divider />
            <v-card-title>{{ $t(card.key) }}</v-card-title>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </v-card>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { store } from "../plugins/store";

import { mdiAccountMusic, mdiAlbum, mdiFileMusic, mdiPlaylistMusic, mdiRadio } from "@mdi/js";

store.topBarTitle = store.defaultTopBarTitle;

const cards = ref([
  { key: "artists", icon: mdiAccountMusic, path: '/artists' },
  { key: "albums", icon: mdiAlbum, path: '/albums' },
  { key: "tracks", icon: mdiFileMusic, path: '/tracks' },
  { key: "playlists", icon: mdiPlaylistMusic, path: '/playlists' },
  { key: "radios", icon: mdiRadio, path: '/radios' }
  ]);
</script>
