<template>
  <v-app-bar dense app style="height: 55px" :color="store.topBarColor">
    <v-app-bar-nav-icon
      :icon="mdiArrowLeft"
      :color="store.topBarTextColor"
      @click="backButton"
      v-if="store.prevRoutes.length > 0"
      style="margin-left: -15px"
    />
    <v-toolbar-title
      :style="`color: ${store.topBarTextColor}`"
      v-html="store.topBarTitle"
    ></v-toolbar-title>
    <template v-slot:append>
      <div style="align-items: center">
        <v-dialog
          v-model="dialog"
          overlay-opacity="0.8"
          fullscreen
          :class="$vuetify.display.mobile ? '' : 'padded-overlay'"
        >
          <template v-slot:activator="{ props: menu }">
            <v-tooltip anchor="top end" origin="end center">
              <template v-slot:activator="{ props: tooltip }">
                <v-progress-circular
                  v-if="jobsInProgress.length > 0"
                  indeterminate
                  :color="store.topBarTextColor"
                  v-bind="mergeProps(menu, tooltip)"
                ></v-progress-circular>
              </template>
              <span>{{ $t("jobs_running", [jobsInProgress.length]) }}</span>
            </v-tooltip>
          </template>
          <v-card>
            <v-toolbar dark color="primary">
              <v-icon :icon="mdiReload"></v-icon>
              <v-toolbar-title style="padding-left: 10px"
                ><b>{{ $t("jobs") }}</b></v-toolbar-title>

              <v-btn :icon="mdiClose" dark text @click="dialog = !dialog">{{ $t("close") }}</v-btn>
            </v-toolbar>

            <v-list>
              <v-list-item v-for="(item, index) in api.jobs.value" :key="index">
                <v-list-item-avatar
                  :icon="getJobStatusIcon(item.status)"
                ></v-list-item-avatar>
                <v-list-item-title>{{ item.name }}</v-list-item-title>
              </v-list-item>
            </v-list>
          </v-card>
        </v-dialog>

        <v-btn
          :icon="mdiDotsVertical"
          v-if="store.contextMenuParentItem"
          :color="store.topBarTextColor"
          style="margin-right: -20px"
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
import {
  mdiArrowLeft,
  mdiDotsVertical,
  mdiProgressClock,
  mdiCancel,
  mdiCheckOutline,
  mdiAlertCircle,
  mdiReload,
  mdiClose
} from "@mdi/js";

import { computed, mergeProps, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../plugins/api";
import { JobStatus } from "../plugins/api";
import { store } from "../plugins/store";

const router = useRouter();
const dialog = ref(false);

const jobsInProgress = computed(() => {
  return api.jobs.value.filter((x) =>
    [JobStatus.PENDING, JobStatus.RUNNING].includes(x.status)
  );
});

const backButton = function () {
  const prevRoute = store.prevRoutes.pop();
  if (prevRoute) {
    prevRoute.params["backnav"] = "true";
    router.replace(prevRoute).then(() => {
      setTimeout(() => {
        window.scrollTo(0, prevRoute.meta.scrollPos || 0);
      }, 400);
    });
  }
};

const getJobStatusIcon = function (status: JobStatus) {
  if (status == JobStatus.PENDING) return mdiProgressClock;
  if (status == JobStatus.CANCELLED) return mdiCancel;
  if (status == JobStatus.FINISHED) return mdiCheckOutline;
  if (status == JobStatus.ERROR) return mdiAlertCircle;
  return mdiReload;
};
</script>

<style>
.padded-overlay .v-overlay__content {
  padding: 50px;
}
.v-overlay__scrim {
  opacity: 65%;
}
</style>
