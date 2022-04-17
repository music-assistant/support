<template>
  <section>
    <v-divider />
    <v-app-bar flat dense color="transparent">
      <v-label v-if="!selectedItems.length && items.length">{{
        $t("items_total", [items.length])
      }}</v-label>
      <a
        v-else-if="selectedItems.length"
        @click="
          contextMenuItems = selectedItems;
          showContextMenu = true;
        "
        >{{ $t("items_selected", [selectedItems.length]) }}</a
      >
      <v-spacer></v-spacer>
      <v-menu left :close-on-content-click="false">
        <template v-slot:activator="{ props }">
          <v-btn icon v-bind="props">
            <v-icon :icon="mdiSort"></v-icon>
          </v-btn>
        </template>
        <v-list>
          <v-list-item
            v-for="item of sortKeys"
            :key="item.text"
            @click="sortBy = item.value"
            v-text="item.text"
          >
          </v-list-item>
        </v-list>
      </v-menu>
      <v-btn icon @click="sortDesc = !sortDesc">
        <v-icon v-if="!sortDesc" :icon="mdiArrowUp"></v-icon>
        <v-icon v-if="sortDesc" :icon="mdiArrowDown"></v-icon>
      </v-btn>
      <v-menu left :close-on-content-click="false">
        <template v-slot:activator="{ props }">
          <v-btn icon v-bind="props">
            <v-icon :icon="mdiSearchWeb"></v-icon>
          </v-btn>
        </template>
        <v-card>
          <v-text-field
            v-model="search"
            clearable
            :prepend-inner-icon="mdiSearchWeb"
            label="Search"
            hide-details
            solo
            dense
          ></v-text-field>
        </v-card>
      </v-menu>
      <v-btn icon style="margin-right: -15px" @click="toggleViewMode()">
        <v-icon v-if="viewMode == 'panel'" :icon="mdiViewList"></v-icon>
        <v-icon v-if="viewMode == 'list'" :icon="mdiGrid"></v-icon>
      </v-btn>
    </v-app-bar>

    <v-container v-if="viewMode == 'panel'" fluid>
      <v-row dense align-content="stretch" align="stretch">
        <v-col v-for="item in items" :key="item.uri" align-self="stretch">
          <PanelviewItem
            :item="item"
            :thumb-width="thumbWidth"
            :thumb-height="thumbHeight"
            :is-selected="isSelected(item)"
            @select="onSelect"
            @menu="onMenu"
            @clicked="onClick"
          />
        </v-col>
      </v-row>
    </v-container>
    <!-- <v-list v-if="viewMode == 'list'" two-line> -->
      <RecycleScroller
        v-slot="{ item }"
        class="scroller"
        :items="items"
        :item-size="66"
        key-field="item_id"
        page-mode
      >
        <ListviewItem
          :item="item"
          :show-track-number="mediatype == 'albumtracks'"
          :show-duration="item.media_type != 'radio'"
          :show-providers="item.provider == 'database'"
          :is-selected="isSelected(item)"
          @select="onSelect"
          @menu="onMenu"
          @clicked="onClick"
        ></ListviewItem>
      </RecycleScroller>
    <!-- </v-list> -->

    <!-- <ContextMenu
      v-model="showContextMenu"
      :items="contextMenuItems"
      :parent-item="parentItem"
    /> -->
  </section>
</template>

<script setup lang="ts">
/* eslint-disable @typescript-eslint/no-unused-vars,vue/no-setup-props-destructure */
import {
  mdiArrowUp,
  mdiArrowDown,
  mdiSearchWeb,
  mdiSort,
  mdiGrid,
  mdiViewList,
} from "@mdi/js";

import {
  watchEffect,
  ref,
  computed,
  defineProps,
  onBeforeUnmount,
} from "vue";
import { useDisplay } from 'vuetify'
import type { MediaItemType, MediaType, MusicAssistantApi } from "../plugins/api";
import { RecycleScroller } from "vue-virtual-scroller";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";
import { store } from "../plugins/store";
import ListviewItem from "./ListviewItem.vue";
import PanelviewItem from "./PanelviewItem.vue";
// import ContextMenu from "./ContextMenu.vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import {api} from "../plugins/api";

// global refs
const router = useRouter();
const i18n = useI18n();
const display = useDisplay();

// properties
interface Props {
  mediatype: string;
  items: MediaItemType[];
  parentItem?: MediaItemType;
}
interface SortKey {
  text: string;
  value: string[];
}
const props = defineProps<Props>();

// local refs
const viewMode = ref("list");
const search = ref("");
const sortDesc = ref(false);
const sortBy = ref<string[]>(["name"]);
const sortKeys = ref<SortKey[]>([]);
const selectedItems = ref<MediaItemType[]>([]);
const contextMenuItems = ref<MediaItemType[]>([]);
const showContextMenu = ref(false);

// computed properties
const thumbWidth = computed(() => {
  return display.mobile ? 120 : 175;
});
const thumbHeight = computed(() => {
  return (display.mobile ? 120 : 175) * 1.5;
});

// methods
const toggleViewMode = function () {
  if (viewMode.value === "panel") viewMode.value = "list";
  else viewMode.value = "panel";
  localStorage.setItem("viewMode" + props.mediatype, viewMode.value);
};
const filteredItems = function (mediaItems: MediaItemType[], search: string) {
  if (!search) return mediaItems;
  search = search.toLowerCase();
  const newLst = [];
  for (const item of mediaItems) {
    if (item.name.toLowerCase().includes(search)) {
      newLst.push(item);
    } else if ("artist" in item && item.artist.name.toLowerCase().includes(search)) {
      newLst.push(item);
    } else if ("album" in item && item.album.name.toLowerCase().includes(search)) {
      newLst.push(item);
    } else if ("artists" in item && item.artists[0].name.toLowerCase().includes(search)) {
      newLst.push(item);
    }
  }
  return newLst;
};
const isSelected = function (item: MediaItemType) {
  return selectedItems.value.includes(item);
};
const onSelect = function (item: MediaItemType, selected: boolean) {
  if (selected) {
    if (!selectedItems.value.includes(item)) selectedItems.value.push(item);
  } else {
    for (let i = 0; i < selectedItems.value.length; i++) {
      if (selectedItems.value[i] === item) {
        selectedItems.value.splice(i, 1);
      }
    }
  }
};
const onMenu = function (item: MediaItemType) {
  contextMenuItems.value = [item];
  showContextMenu.value = true;
};
const onClick = function (mediaItem: MediaItemType) {
  // mediaItem in the list is clicked
  if (mediaItem.media_type === "artist") {
    router.push({
      name: "artist",
      params: { id: mediaItem.item_id, provider: mediaItem.provider },
    });
  } else if (mediaItem.media_type === "album") {
    router.push({
      name: "album",
      params: { id: mediaItem.item_id, provider: mediaItem.provider },
    });
  } else if (mediaItem.media_type === "playlist") {
    router.push({
      name: "playlist",
      params: { id: mediaItem.item_id, provider: mediaItem.provider },
    });
  } else {
    // assume track (or radio) item
    onMenu(mediaItem);
  }
};

// watchers
watchEffect(async () => {
  sortKeys.value.push({
    text: i18n.t("sort_name").toString(),
    value: ["name"],
  });
  if (props.mediatype == "playlisttracks") {
    // playlist tracks
    sortKeys.value.push({
      text: i18n.t("sort_position").toString(),
      value: ["position"],
    });
    sortKeys.value.push({
      text: i18n.t("sort_artist").toString(),
      value: ["artists[0].name"],
    });
    sortKeys.value.push({
      text: i18n.t("sort_album").toString(),
      value: ["album.name"],
    });
    sortBy.value = ["position"];
    viewMode.value = "list";
  } else if (props.mediatype === "albumtracks") {
    // album tracks
    sortKeys.value.push({
      text: i18n.t("sort_track_number").toString(),
      value: ["disc_number", "track_number"],
    });
    sortBy.value = ["disc_number", "track_number"];
    viewMode.value = "list";
  } else if (props.mediatype === "tracks") {
    // tracks listing
    sortKeys.value.push({
      text: i18n.t("sort_artist").toString(),
      value: ["artists[0].name"],
    });
    sortKeys.value.push({
      text: i18n.t("sort_album").toString(),
      value: ["album.name"],
    });
    viewMode.value = "list";
  } else if (props.mediatype === "albums") {
    // albums listing
    sortKeys.value.push({
      text: i18n.t("sort_artist").toString(),
      value: ["artist.name"],
    });
    sortKeys.value.push({
      text: i18n.t("sort_date").toString(),
      value: ["year"],
    });
    viewMode.value = "panel";
  } else {
    viewMode.value = "list";
  }
  // get stored viewMode for this mediatype
  const savedViewMode = localStorage.getItem("viewMode" + props.mediatype);
  if (savedViewMode !== null) {
    viewMode.value = savedViewMode;
  }
});

// lifecycle hooks
const keyListener = function (e: KeyboardEvent) {
  if (e.key === "a" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    selectedItems.value = props.items;
  }
};
document.addEventListener("keydown", keyListener);

onBeforeUnmount(() => {
  if (keyListener !== undefined) document.removeEventListener("keydown", keyListener);
});
</script>

<style scoped>
.scroller {
  height: 100%;
}
</style>
