<template>
  <section>
    <v-toolbar dense flat color="transparent" height="35">
      <span v-if="!selectedItems.length && items.length">{{
        $t("items_total", [items.length])
      }}</span>
      <a
        v-else-if="selectedItems.length"
        @click="
          store.contextMenuItems = selectedItems;
          store.showContextMenu = true;
        "
        >{{ $t("items_selected", [selectedItems.length]) }}</a
      >
      <v-spacer></v-spacer>
      <v-menu
        anchor="bottom end"
        :close-on-content-click="true"
        v-model="showSortMenu"
        v-if="sortKeys.length > 1"
      >
        <template v-slot:activator="{ props }">
          <v-btn icon v-bind="props">
            <v-icon :icon="mdiSort"></v-icon>
          </v-btn>
        </template>
        <v-card>
          <v-list>
            <div v-for="item of sortKeys" :key="item.text">
              <v-list-item @click="changeSort(item.value)">
                <v-list-item-title v-text="item.text"></v-list-item-title>
                <template v-slot:append>
                  <v-icon v-if="sortBy == item.value" :icon="mdiCheck"></v-icon>
                </template>
              </v-list-item>
              <v-divider />
            </div>
          </v-list>
        </v-card>
      </v-menu>
      <v-btn icon @click="changeSort(undefined, !sortDesc)">
        <v-icon v-if="!sortDesc" :icon="mdiArrowUp"></v-icon>
        <v-icon v-if="sortDesc" :icon="mdiArrowDown"></v-icon>
      </v-btn>
      <v-menu anchor="bottom end" :close-on-content-click="false">
        <template v-slot:activator="{ props }">
          <v-btn icon v-bind="props">
            <v-icon :icon="mdiSearchWeb"></v-icon>
          </v-btn>
        </template>
        <v-card min-width="350">
          <v-text-field
            v-model="search"
            clearable
            :prepend-inner-icon="mdiSearchWeb"
            :label="$t('search')"
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
    </v-toolbar>

    <div
      style="
        padding-left: 15px;
        padding-right: 15px;
        padding-top: 20px;
        padding-bottom: 20px;
      "
    >
      <v-progress-linear indeterminate v-if="loading"></v-progress-linear>
      <!-- panel view -->
      <v-row dense align-content="stretch" align="stretch" v-if="viewMode == 'panel'">
        <v-col v-for="item in filteredItems" :key="item.uri" align-self="stretch">
          <PanelviewItem
            :item="item"
            :size="thumbSize"
            :is-selected="isSelected(item)"
            @select="onSelect"
            @menu="onMenu"
            @click="onClick"
          />
        </v-col>
      </v-row>

      <!-- list view -->
      <div v-if="viewMode == 'list'">
        <RecycleScroller
          v-slot="{ item }"
          :items="sorting ? [] : filteredItems"
          :item-size="66"
          key-field="item_id"
          page-mode
        >
          <ListviewItem
            :item="item"
            :show-track-number="itemtype == 'albumtracks'"
            :show-duration="item.media_type != 'radio'"
            :is-selected="isSelected(item)"
            @select="onSelect"
            @menu="onMenu"
            @click="onClick"
          ></ListviewItem>
        </RecycleScroller>
      </div>

      <!-- show alert if no items found -->
      <v-alert type="info" v-if="!loading && items.length == 0">{{
        $t("no_content")
      }}</v-alert>
    </div>
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
  mdiCheck,
} from "@mdi/js";

import { watchEffect, ref, computed, onBeforeUnmount, onMounted, nextTick } from "vue";
import { useDisplay } from "vuetify";
import type {
  Album,
  MediaItemType,
  MediaType,
  MusicAssistantApi,
  Track,
} from "../plugins/api";
import { RecycleScroller } from "vue-virtual-scroller";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";
import { store } from "../plugins/store";
import ListviewItem from "./ListviewItem.vue";
import PanelviewItem from "./PanelviewItem.vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { api } from "../plugins/api";

// global refs
const router = useRouter();
const i18n = useI18n();
const display = useDisplay();

// properties
interface Props {
  itemtype: string;
  items: MediaItemType[];
  loading?: boolean;
}
interface SortKey {
  text: string;
  value: string;
}
const props = defineProps<Props>();

// local refs
const viewMode = ref("list");
const search = ref("");
const sortDesc = ref(false);
const sortBy = ref<string>("name");
const sortKeys = ref<SortKey[]>([]);
const selectedItems = ref<MediaItemType[]>([]);
const sorting = ref(false);
const showSortMenu = ref(false);

// computed properties
const thumbSize = computed(() => {
  return display.mobile ? 150 : 225;
});

// methods
const toggleViewMode = function () {
  if (viewMode.value === "panel") viewMode.value = "list";
  else viewMode.value = "panel";
  localStorage.setItem("viewMode" + props.itemtype, viewMode.value);
};
const filteredItems = computed(() => {
  let result = [];
  // search
  if (search.value) {
    const searchStr = search.value.toLowerCase();
    for (const item of props.items) {
      if (item.name.toLowerCase().includes(searchStr)) {
        result.push(item);
      } else if ("artist" in item && item.artist.name.toLowerCase().includes(searchStr)) {
        result.push(item);
      } else if ("album" in item && item.album?.name.toLowerCase().includes(searchStr)) {
        result.push(item);
      } else if (
        "artists" in item &&
        item.artists[0].name.toLowerCase().includes(searchStr)
      ) {
        result.push(item);
      }
    }
  } else {
    result = props.items;
  }
  // sort
  if (sortBy.value == "name") {
    result.sort((a, b) => (a.sort_name || a.name).localeCompare(b.sort_name || b.name));
  }
  if (sortBy.value == "album.name") {
    result.sort((a, b) =>
      (a as Track).album?.name.localeCompare((b as Track).album?.name)
    );
  }
  if (sortBy.value == "artist.name") {
    result.sort((a, b) =>
      (a as Album).artist.name.localeCompare((b as Album).artist.name)
    );
  }
  if (sortBy.value == "artists.name") {
    result.sort((a, b) =>
      (a as Track).artists[0].name.localeCompare((b as Track).artists[0].name)
    );
  }
  if (sortBy.value == "track_number") {
    result.sort(
      (a, b) => ((a as Track).disc_number || 0) - ((b as Track).disc_number || 0)
    );
    result.sort(
      (a, b) => ((a as Track).track_number || 0) - ((b as Track).track_number || 0)
    );
  }
  if (sortBy.value == "position") {
    result.sort((a, b) => ((a as Track).position || 0) - ((b as Track).position || 0));
  }
  if (sortBy.value == "year") {
    result.sort((a, b) => ((a as Album).year || 0) - ((b as Album).year || 0));
  }

  if (sortDesc.value) result.reverse();
  return result;
});
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
  store.contextMenuItems = [item];
  store.showContextMenu = true;
};
const onClick = function (mediaItem: MediaItemType) {
  // mediaItem in the list is clicked
  if (mediaItem.media_type === "artist") {
    router.push({
      name: "artist",
      params: { item_id: mediaItem.item_id, provider: mediaItem.provider },
    });
  } else if (mediaItem.media_type === "album") {
    router.push({
      name: "album",
      params: { item_id: mediaItem.item_id, provider: mediaItem.provider },
    });
  } else if (mediaItem.media_type === "playlist") {
    router.push({
      name: "playlist",
      params: { item_id: mediaItem.item_id, provider: mediaItem.provider },
    });
  } else {
    // assume track (or radio) item
    onMenu(mediaItem);
  }
};

const changeSort = function (sort_key?: string, sort_desc?: boolean) {
  sorting.value = true;
  if (sort_key !== undefined) {
    sortBy.value = sort_key;
  }
  if (sort_desc !== undefined) {
    sortDesc.value = sort_desc;
  }
  // ugly hack to force the recyclescroller to re-render all items
  setTimeout(() => {
    sorting.value = false;
    showSortMenu.value = false;
  }, 500);
};

// watchers
watchEffect(async () => {
  // get stored/default viewMode for this itemtype
  const storKey = "viewMode" + props.itemtype;
  const savedViewMode = localStorage.getItem(storKey);
  if (savedViewMode) {
    viewMode.value = savedViewMode;
  } else if (props.itemtype == "artists") {
    viewMode.value = "panel";
  } else if (props.itemtype == "albums") {
    viewMode.value = "panel";
  } else {
    viewMode.value = "list";
  }
  // determine sort keys
  const _sortKeys = [];
  _sortKeys.push({
    text: i18n.t("sort_name").toString(),
    value: "name",
  });
  if (props.itemtype == "playlisttracks") {
    // playlist tracks
    _sortKeys.push({
      text: i18n.t("sort_position").toString(),
      value: "position",
    });
    _sortKeys.push({
      text: i18n.t("sort_artist").toString(),
      value: "artists.name",
    });
    sortBy.value = "position";
  } else if (props.itemtype === "albumtracks") {
    // album tracks
    _sortKeys.push({
      text: i18n.t("sort_track_number").toString(),
      value: "track_number",
    });
    sortBy.value = "track_number";
  } else if (props.itemtype === "tracks") {
    // tracks listing
    _sortKeys.push({
      text: i18n.t("sort_artist").toString(),
      value: "artists.name",
    });
    if (props.items.length > 0 && "album" in props.items[0]) {
      _sortKeys.push({
        text: i18n.t("sort_album").toString(),
        value: "album.name",
      });
    }
  } else if (props.itemtype === "albums") {
    // albums listing
    _sortKeys.push({
      text: i18n.t("sort_artist").toString(),
      value: "artist.name",
    });
    _sortKeys.push({
      text: i18n.t("sort_date").toString(),
      value: "year",
    });
  }
  sortKeys.value = _sortKeys;
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
  document.removeEventListener("keydown", keyListener);
});
</script>

<style scoped>
.scroller {
  height: 100%;
}
</style>
