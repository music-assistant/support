<template>
  <v-app-bar dense app style="height: 55px" :color="topBarColor">
    <v-app-bar-nav-icon
      :icon="mdiArrowLeft"
      @click="$router.push('/')"
      v-if="$router.currentRoute.value.path != '/'"
    />
    <v-toolbar-title>{{ store.topBarTitle }}</v-toolbar-title>
    <template v-slot:append>
      <div style="align-items: center">
        <v-dialog>
          <template v-slot:activator="{ props: menu }">
            <v-tooltip anchor="top end" origin="end center">
              <template v-slot:activator="{ props: tooltip }">
                <v-progress-circular
                  v-if="api.jobs.value.length > 0"
                  indeterminate
                  v-bind="mergeProps(menu, tooltip)"
                ></v-progress-circular>
              </template>
              <span>{{ $t("jobs_running", [api.jobs.value.length]) }}</span>
            </v-tooltip>
          </template>
          <v-card>
            <v-card-title>{{ $t("jobs_running", [api.jobs.value.length]) }}</v-card-title>
            <v-list>
              <v-list-item v-for="(item, index) in api.jobs.value" :key="index">
                <v-list-item-title>{{ item }}</v-list-item-title>
              </v-list-item>
            </v-list>
          </v-card>
        </v-dialog>

        <v-btn
          :icon="mdiDotsVertical"
          v-if="store.contextMenuParentItem"
          @click="
            store.contextMenuItems = [store.contextMenuParentItem];
            store.showContextMenu = true;
          "
        ></v-btn>
      </div>
    </template>
  </v-app-bar>
</template>

<script setup lang="ts">
import { mdiArrowLeft, mdiDotsVertical } from "@mdi/js";

import { computed, mergeProps } from "vue";
import { api } from "../plugins/api";
import { store } from "../plugins/store";

const topBarColor = computed(() => {
  if (store.topBarTransparent) return "transparent";
  return store.topBarDefaultColor;
});
</script>
