<template>
  <v-card>
    <v-card-title>{{ $t("music_assistant") }}</v-card-title>
    <router-link to="/artists">{{ $t("artists") }}</router-link>
     <router-link to="/tracks">{{ $t("tracks") }}</router-link>
  </v-card>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { api } from "../plugins/api";



</script>

