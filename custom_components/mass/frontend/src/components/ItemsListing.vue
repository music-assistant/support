<template>
  <section>
    <v-toolbar dense flat color="transparent" height="35">
      <span v-if="!store.contextMenuItems.length && totalItems">{{
        $t("items_total", [totalItems])
      }}</span>
      <a
        v-else-if="store.contextMenuItems.length"
        @click="store.showContextMenu = true"
        >{{ $t("items_selected", [store.contextMenuItems.length]) }}</a
      >
      <v-spacer></v-spacer>

      <v-btn icon @click="toggleLibraryFilter" v-if="showLibrary !== false">
        <v-icon :icon="inLibraryOnly ? mdiHeart : mdiHeartOutline"></v-icon>
      </v-btn>
      <v-menu
        location="bottom end"
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
            <div v-for="key of sortKeys" :key="key">
              <v-list-item @click="changeSort(key)">
                <v-list-item-title
                  v-text="$t('sort.' + key)"
                ></v-list-item-title>
                <template v-slot:append>
                  <v-icon v-if="sortBy == key" :icon="mdiCheck"></v-icon>
                </template>
              </v-list-item>
              <v-divider />
            </div>
          </v-list>
        </v-card>
      </v-menu>

      <v-btn icon @click="toggleSearch()">
        <v-icon :icon="mdiMagnify"></v-icon>
      </v-btn>

      <v-btn icon @click="toggleViewMode()">
        <v-icon v-if="viewMode == 'panel'" :icon="mdiViewList"></v-icon>
        <v-icon v-if="viewMode == 'list'" :icon="mdiGrid"></v-icon>
      </v-btn>
    </v-toolbar>
    <v-text-field
      v-model="search"
      id="searchInput"
      clearable
      :prepend-inner-icon="mdiMagnify"
      :label="$t('search')"
      hide-details
      variant="filled"
      style="
        width: auto;
        margin-left: 15px;
        margin-right: 15px;
        margin-top: 10px;
      "
      v-if="showSearch"
      @focus="searchHasFocus = true"
      @blur="searchHasFocus = false"
    ></v-text-field>

    <div
      style="
        padding-left: 15px;
        padding-right: 15px;
        padding-top: 20px;
        padding-bottom: 20px;
      "
    >
      <!-- loading animation -->
      <v-progress-linear indeterminate v-if="loading"></v-progress-linear>

      <!-- panel view -->
      <v-row
        dense
        align-content="start"
        align="start"
        v-if="viewMode == 'panel'"
      >
        <v-col v-for="item in items" :key="item.uri" align-self="start">
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
          :items="items"
          :item-size="66"
          key-field="item_id"
          page-mode
        >
          <ListviewItem
            :item="item"
            :show-track-number="showTrackNumber"
            :show-duration="showDuration"
            :show-library="showLibrary !== false && !inLibraryOnly"
            :show-menu="showMenu"
            :show-providers="showProviders"
            :is-selected="isSelected(item)"
            @select="onSelect"
            @menu="onMenu"
            @click="onClick"
          ></ListviewItem>
        </RecycleScroller>
      </div>

      <!-- inifinite scroll component -->
      <InfiniteLoading @infinite="loadNextPage" />

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
  mdiMagnify,
  mdiSort,
  mdiGrid,
  mdiViewList,
  mdiCheck,
  mdiHeart,
  mdiHeartOutline,
} from "@mdi/js";

import {
  watchEffect,
  ref,
  computed,
  onBeforeUnmount,
  nextTick,
  onMounted,
  watch,
} from "vue";
import { useDisplay } from "vuetify";
import type { Album, MediaItemType, Track } from "../plugins/api";
import { RecycleScroller } from "vue-virtual-scroller";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";
import { store } from "../plugins/store";
import ListviewItem from "./ListviewItem.vue";
import PanelviewItem from "./PanelviewItem.vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { api } from "../plugins/api";
import InfiniteLoading from "v3-infinite-loading";
import "v3-infinite-loading/lib/style.css";

// properties
export interface Props {
  itemtype: string;
  sortKeys?: string[];
  showTrackNumber?: boolean;
  showProviders?: boolean;
  showMenu?: boolean;
  showLibrary?: boolean;
  showDuration?: boolean;
  count?: number;
  loadData: (
    offset: number,
    limit: number,
    sort: string,
    search: string,
    library?: boolean
  ) => Promise<MediaItemType[]>;
}
const props = withDefaults(defineProps<Props>(), {
  sortKeys: () => ["sort_name", "timestamp DESC"],
  showTrackNumber: true,
  showProviders: Object.keys(api.stats.providers).length > 1,
  showMenu: true,
  showLibrary: true,
  showDuration: true,
});

const defaultLimit = 50;

// global refs
const router = useRouter();
const i18n = useI18n();
const { mobile } = useDisplay();

// local refs
const viewMode = ref("list");
const search = ref("");
const sortBy = ref<string>("sort_name");
const showSortMenu = ref(false);
const showSearch = ref(false);
const searchHasFocus = ref(false);
const offset = ref(0);
const items = ref<MediaItemType[]>([]);
const totalItems = ref<number>();
const loading = ref(false);
const inLibraryOnly = ref(false);

// computed properties
const thumbSize = computed(() => {
  return mobile.value ? 140 : 150;
});

// methods
const toggleSearch = function () {
  if (showSearch.value) showSearch.value = false;
  else {
    showSearch.value = true;
    nextTick(() => {
      document.getElementById("searchInput")?.focus();
    });
  }
};

const toggleViewMode = function () {
  if (viewMode.value === "panel") viewMode.value = "list";
  else viewMode.value = "panel";
  localStorage.setItem(`viewMode.${props.itemtype}`, viewMode.value);
};

const toggleLibraryFilter = function () {
  inLibraryOnly.value = !inLibraryOnly.value;
  loadData(true);
};

const isSelected = function (item: MediaItemType) {
  return store.contextMenuItems.includes(item);
};

const onSelect = function (item: MediaItemType, selected: boolean) {
  if (selected) {
    if (!store.contextMenuItems.includes(item))
      store.contextMenuItems.push(item);
  } else {
    for (let i = 0; i < store.contextMenuItems.length; i++) {
      if (store.contextMenuItems[i] === item) {
        store.contextMenuItems.splice(i, 1);
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
  } else if (store.selectedPlayer) {
    // assume track (or radio) item
    api.playMedia(store.selectedPlayer?.active_queue, mediaItem);
  }
};

const changeSort = function (sort_key?: string, sort_desc?: boolean) {
  if (sort_key !== undefined) {
    sortBy.value = sort_key;
  }
  localStorage.setItem(`sortBy.${props.itemtype}`, sortBy.value);
  loadData(true);
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const loadNextPage = function ($state: any) {
  if (items.value.length == 0) {
    $state.loaded();
    return;
  }
  if (totalItems.value !== undefined && offset.value >= totalItems.value) {
    $state.loaded();
    return;
  }
  offset.value += defaultLimit;
  loadData().then(() => {
    $state.loaded();
  });
};

// watchers
onMounted(() => {
  // get stored/default viewMode for this itemtype
  const savedViewMode = localStorage.getItem(`viewMode.${props.itemtype}`);
  if (savedViewMode) {
    viewMode.value = savedViewMode;
  } else if (props.itemtype == "artists") {
    viewMode.value = "panel";
  } else if (props.itemtype == "albums") {
    viewMode.value = "panel";
  } else {
    viewMode.value = "list";
  }

  const savedSortBy = localStorage.getItem(`sortBy.${props.itemtype}`);
  if (savedSortBy) {
    sortBy.value = savedSortBy;
  } else {
    sortBy.value = props.sortKeys[0];
  }

  if (
    ["artists", "albums", "tracks", "playlists", "radios"].includes(
      props.itemtype
    )
  ) {
    inLibraryOnly.value = true;
  }

  loadData(true);
});

watch(
  () => search.value,
  (newVal) => {
    loadData(true);
  }
);

const loadData = async function (clear = false) {
  if (clear) {
    totalItems.value = props.count;
    offset.value = 0;
  }
  loading.value = true;

  if (!totalItems.value) {
    if (props.itemtype == "artists" && inLibraryOnly.value)
      totalItems.value = api.stats.library_count.artists;
    else if (props.itemtype == "artists")
      totalItems.value = api.stats.db_count.artists;
    else if (props.itemtype == "albums" && inLibraryOnly.value)
      totalItems.value = api.stats.library_count.albums;
    else if (props.itemtype == "albums")
      totalItems.value = api.stats.db_count.albums;
    else if (props.itemtype == "tracks" && inLibraryOnly.value)
      totalItems.value = api.stats.library_count.tracks;
    else if (props.itemtype == "tracks")
      totalItems.value = api.stats.db_count.tracks;
    else if (props.itemtype == "playlists" && inLibraryOnly.value)
      totalItems.value = api.stats.library_count.playlists;
    else if (props.itemtype == "playlists")
      totalItems.value = api.stats.db_count.playlists;
    else if (props.itemtype == "radios" && inLibraryOnly.value)
      totalItems.value = api.stats.library_count.radios;
    else if (props.itemtype == "radios")
      totalItems.value = api.stats.db_count.radios;
  }
  const nextItems = await props.loadData(
    offset.value,
    defaultLimit,
    sortBy.value,
    search.value,
    inLibraryOnly.value
  );
  if (offset.value) {
    items.value.push(...nextItems);
  } else {
    items.value = nextItems;
  }
  if (nextItems.length < defaultLimit) {
    totalItems.value = items.value.length;
  }
  loading.value = false;
};

// lifecycle hooks
const keyListener = function (e: KeyboardEvent) {
  if (e.key === "a" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    store.contextMenuItems = items.value;
  } else if (!searchHasFocus.value && e.key == "Backspace") {
    search.value = search.value.slice(0, -1);
  } else if (!searchHasFocus.value && e.key.length == 1) {
    search.value += e.key;
    showSearch.value = true;
  }
};
document.addEventListener("keydown", keyListener);

onBeforeUnmount(() => {
  document.removeEventListener("keydown", keyListener);
});
</script>

<script lang="ts">
export const filteredItems = function (
  // In-memory paging for (smaller) item sets that do not have server side paging
  items: MediaItemType[],
  offset: number,
  limit: number,
  sortBy: string,
  search?: string,
  inLibraryOnly = true
) {
  let result = [];

  // console.log(
  //   `filteredItems items: ${items.length} - offset: ${offset} - limit: ${limit} - sortBy: ${sortBy} - search: ${search} - inLibraryOnly: ${inLibraryOnly}`
  // );

  // search
  if (search) {
    const searchStr = search.toLowerCase();
    for (const item of items) {
      if (item.name.toLowerCase().includes(searchStr)) {
        result.push(item);
      } else if (
        "artist" in item &&
        item.artist?.name.toLowerCase().includes(searchStr)
      ) {
        result.push(item);
      } else if (
        "album" in item &&
        item.album?.name.toLowerCase().includes(searchStr)
      ) {
        result.push(item);
      } else if (
        "artists" in item &&
        item.artists &&
        item.artists[0].name.toLowerCase().includes(searchStr)
      ) {
        result.push(item);
      }
    }
  } else {
    result = items;
  }
  // sort
  if (sortBy == "sort_name") {
    result.sort((a, b) =>
      (a.sort_name || a.name).localeCompare(b.sort_name || b.name)
    );
  }
  if (sortBy == "sort_album") {
    result.sort((a, b) =>
      (a as Track).album?.name.localeCompare((b as Track).album?.name)
    );
  }
  if (sortBy == "sort_artist") {
    result.sort((a, b) =>
      (a as Track).artists[0].name.localeCompare((b as Track).artists[0].name)
    );
  }
  if (sortBy == "track_number") {
    result.sort(
      (a, b) =>
        ((a as Track).track_number || 0) - ((b as Track).track_number || 0)
    );
    result.sort(
      (a, b) =>
        ((a as Track).disc_number || 0) - ((b as Track).disc_number || 0)
    );
  }
  if (sortBy == "position") {
    result.sort(
      (a, b) => ((a as Track).position || 0) - ((b as Track).position || 0)
    );
  }
  if (sortBy == "year") {
    result.sort((a, b) => ((a as Album).year || 0) - ((b as Album).year || 0));
  }
  if (sortBy == "timestamp DESC") {
    result.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
  }

  if (sortBy == "duration") {
    result.sort(
      (a, b) => ((a as Track).duration || 0) - ((b as Track).duration || 0)
    );
  }

  if (inLibraryOnly) {
    result = result.filter((x) => x.in_library);
  }

  return result.slice(offset, offset + limit);
};
</script>

<style scoped>
.scroller {
  height: 100%;
}
</style>
