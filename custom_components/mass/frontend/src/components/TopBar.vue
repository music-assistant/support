<template>
  <v-app-bar dense app style="height: 55px" :color="store.topBarColor">
    <v-app-bar-nav-icon
      :icon="mdiArrowLeft"
      :color="store.topBarTextColor"
      @click="backButton"
      v-if="store.prevRoutes.length > 0"
      style="margin-left:-15px"
    />
    <v-toolbar-title :style="`color: ${store.topBarTextColor}`" v-html="store.topBarTitle"></v-toolbar-title>
    <template v-slot:append>
      <div style="align-items: center">
        <v-dialog>
          <template v-slot:activator="{ props: menu }">
            <v-tooltip anchor="top end" origin="end center">
              <template v-slot:activator="{ props: tooltip }">
                <v-progress-circular
                  v-if="api.jobs.value.length > 0"
                  indeterminate
                  :color="store.topBarTextColor"
                  v-bind="mergeProps(menu, tooltip)"
                ></v-progress-circular>
              </template>
              <span>{{ $t("jobs_running", [api.jobs.value.length]) }}</span>
            </v-tooltip>
          </template>
          <v-card min-width="400">
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
          :color="store.topBarTextColor"
          style="margin-right:-20px;"
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

import { mergeProps } from "vue";
import { useRouter } from "vue-router";
import { api } from "../plugins/api";
import { store } from "../plugins/store";

const router = useRouter();

const backButton = function () {
  const prevRoute = store.prevRoutes.pop();
  if (prevRoute) {
    prevRoute.params['backnav'] = 'true';
    router.replace(prevRoute).then(() => {
      setTimeout(() => {
      window.scrollTo(0, prevRoute.meta.scrollPos || 0)
    },400)
    })
  }
}

</script>
