<template>
  <section>
    <v-toolbar dense flat color="transparent" height="35">
      <v-tooltip location="bottom">
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            :icon="
              selectedItems.length > 0
                ? mdiCheckboxMultipleOutline
                : mdiCheckboxMultipleBlankOutline
            "
            @click="toggleCheckboxes"
          >
          </v-btn>
          <span v-if="!$vuetify.display.mobile">
            <span
              @click="toggleCheckboxes"
              style="cursor: pointer"
              v-if="!selectedItems.length && totalItems"
              >{{ $t("items_total", [totalItems]) }}</span
            >
            <span
              @click="toggleCheckboxes"
              style="cursor: pointer"
              v-else-if="selectedItems.length"
              >{{ $t("items_selected", [selectedItems.length]) }}</span
            >
          </span>
        </template>
        <span>{{ $t("tooltip.select_items") }}</span>
      </v-tooltip>

      <v-spacer></v-spacer>

      <v-tooltip location="bottom">
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            icon
            @click="toggleLibraryFilter"
            v-if="showLibrary !== false"
          >
            <v-icon :icon="inLibraryOnly ? mdiHeart : mdiHeartOutline"></v-icon>
          </v-btn>
        </template>
        <span>{{ $t("tooltip.filter_library") }}</span>
      </v-tooltip>

      <v-tooltip location="bottom" v-if="showAlbumArtistsOnlyFilter">
        <template #activator="{ props }">
          <v-btn v-bind="props" icon @click="toggleAlbumArtistsFilter">
            <v-icon
              :icon="
                albumArtistsOnlyFilter ? mdiAccountMusic : mdiAccountMusicOutline
              "
            ></v-icon>
          </v-btn>
        </template>
        <span>{{ $t("tooltip.album_artist_filter") }}</span>
      </v-tooltip>

      <v-tooltip location="bottom">
        <template #activator="{ props }">
          <v-btn v-bind="props" icon @click="loadData(true)">
            <v-badge color="error" dot v-model="newContentAvailable">
              <v-icon :icon="mdiRefresh"></v-icon>
            </v-badge>
          </v-btn>
        </template>
        <span v-if="newContentAvailable">{{
          $t("tooltip.refresh_new_content")
        }}</span>
        <span v-else>{{ $t("tooltip.refresh") }}</span>
      </v-tooltip>

      <v-menu
        location="bottom end"
        :close-on-content-click="true"
        v-model="showSortMenu"
        v-if="sortKeys.length > 1"
      >
        <template v-slot:activator="{ props: menu }">
          <v-tooltip location="bottom">
            <template v-slot:activator="{ props: tooltip }">
              <v-btn icon v-bind="props">
                <v-icon
                  v-bind="mergeProps(menu, tooltip)"
                  :icon="mdiSort"
                ></v-icon>
              </v-btn>
            </template>
            <span>{{ $t("tooltip.sort_options") }}</span>
          </v-tooltip>
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

      <v-tooltip location="bottom">
        <template #activator="{ props }">
          <v-btn v-bind="props" icon @click="toggleSearch()">
            <v-icon :icon="mdiMagnify"></v-icon>
          </v-btn>
        </template>
        <span>{{ $t("tooltip.search") }}</span>
      </v-tooltip>

      <v-tooltip location="bottom">
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            @click="toggleViewMode()"
            :icon="viewMode == 'panel' ? mdiViewList : mdiGrid"
          ></v-btn>
        </template>
        <span>{{ $t("tooltip.toggle_view_mode") }}</span>
      </v-tooltip>
    </v-toolbar>
    <MediaItemContextMenu
      :items="selectedItems"
      :parent-item="parentItem"
      @clear="onClearSelection"
      @delete="onDelete"
      v-model="showContextMenu"
    />
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
        margin-left: 15px;
        margin-right: 15px;
        margin-top: 20px;
        margin-bottom: 20px;
        padding: 0;
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
            :show-checkboxes="showCheckboxes"
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
          :item-size="60"
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
            :show-checkboxes="showCheckboxes"
            :is-selected="isSelected(item)"
            :show-details="itemtype.includes('versions')"
            :parent-item="parentItem"
            @select="onSelect"
            @menu="onMenu"
            @click="onClick"
          ></ListviewItem>
        </RecycleScroller>
      </div>

      <!-- inifinite scroll component -->
      <InfiniteLoading @infinite="loadNextPage" />

      <!-- show alert if no items found -->
      <div v-if="!loading && items.length == 0">
        <v-alert
          type="info"
          v-if="!loading && items.length == 0 && (search || inLibraryOnly)"
          >{{ $t("no_content_filter")
          }}<v-btn
            v-if="search"
            style="margin-top: 15px"
            @click="redirectSearch"
            >{{ $t("try_global_search") }}</v-btn
          ></v-alert
        >
        <v-alert type="info" v-else-if="!loading && items.length == 0">{{
          $t("no_content")
        }}</v-alert>
      </div>
      <v-snackbar :model-value="selectedItems.length > 1">
        <span>{{ $t("items_selected", [selectedItems.length]) }}</span>
        <template v-slot:actions>
          <v-btn color="primary" variant="text" @click="showContextMenu = true">
            {{ $t("actions") }}
          </v-btn>
        </template>
      </v-snackbar>
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
  mdiRefresh,
  mdiCheckboxMultipleOutline,
  mdiCheckboxMultipleBlankOutline,
  mdiAccountMusic,
  mdiAccountMusicOutline,
} from "@mdi/js";

import {
  ref,
  computed,
  onBeforeUnmount,
  nextTick,
  onMounted,
  watch,
  mergeProps,
  watchEffect,
} from "vue";
import { useDisplay } from "vuetify";
import {
  MassEventType,
  type Album,
  type MassEvent,
  type MediaItemType,
  type PagedItems,
  type Track,
} from "../plugins/api";
import { RecycleScroller } from "vue-virtual-scroller";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";
import { store } from "../plugins/store";
import ListviewItem from "./ListviewItem.vue";
import PanelviewItem from "./PanelviewItem.vue";
import MediaItemContextMenu from "./MediaItemContextMenu.vue";
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
  parentItem?: MediaItemType;
  showAlbumArtistsOnlyFilter?: boolean;
  loadData: (
    offset: number,
    limit: number,
    sort: string,
    search: string,
    library?: boolean
  ) => Promise<PagedItems>;
}
const props = withDefaults(defineProps<Props>(), {
  sortKeys: () => ["sort_name", "timestamp DESC"],
  showTrackNumber: true,
  showProviders: Object.keys(api.providers).length > 1,
  showMenu: true,
  showLibrary: true,
  showDuration: true,
});

const defaultLimit = 100;

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
const selectedItems = ref<MediaItemType[]>([]);
const showContextMenu = ref(false);
const newContentAvailable = ref(false);
const showCheckboxes = ref(false);
const albumArtistsOnlyFilter = ref(false);

// computed properties
const thumbSize = computed(() => {
  return mobile.value ? 140 : 150;
});

const emit = defineEmits<{
  (e: "toggleAlbumArtistsOnly", value: boolean): void;
}>();

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
  const inLibraryOnlyStr = inLibraryOnly.value ? "true" : "false";
  localStorage.setItem(`libraryFilter.${props.itemtype}`, inLibraryOnlyStr);
  loadData(true);
};

const toggleAlbumArtistsFilter = function () {
  albumArtistsOnlyFilter.value = !albumArtistsOnlyFilter.value;
  const albumArtistsOnlyStr = albumArtistsOnlyFilter.value ? "true" : "false";
  localStorage.setItem(
    `albumArtistsFilter.${props.itemtype}`,
    albumArtistsOnlyStr
  );
  emit("toggleAlbumArtistsOnly", albumArtistsOnlyFilter.value);
  loadData(true);
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
  store.blockGlobalPlayMenu = selectedItems.value.length > 0;
};

const onClearSelection = function () {
  selectedItems.value = [];
  showCheckboxes.value = false;
  store.blockGlobalPlayMenu = false;
};

const toggleCheckboxes = function () {
  if (selectedItems.value.length > 0) {
    showContextMenu.value = true;
  } else {
    showCheckboxes.value = !showCheckboxes.value;
  }
};

const onDelete = function (item: MediaItemType) {
  loadData(true);
};

const onMenu = function (item: MediaItemType) {
  selectedItems.value = [item];
  showContextMenu.value = true;
};

const onClick = function (mediaItem: MediaItemType) {
  // mediaItem in the list is clicked
  const force_provider_version = props.itemtype.includes("versions").toString();

  if (
    ["artist", "album", "playlist"].includes(mediaItem.media_type) ||
    force_provider_version == "true" ||
    !store.selectedPlayer?.available
  ) {
    router.push({
      name: mediaItem.media_type,
      params: {
        item_id: mediaItem.item_id,
        provider: mediaItem.provider,
        force_provider_version,
      },
    });
  } else if (store.selectedPlayer) {
    // assume track (or radio) item
    api.playMedia(mediaItem);
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

const redirectSearch = function () {
  localStorage.setItem("globalsearch", search.value);
  router.push({ name: "home" });
};

// watchers
watch(
  () => search.value,
  (newVal) => {
    if (newVal) showSearch.value = true;
    loadData(true);
  }
);

const loadData = async function (clear = false, limit = defaultLimit) {
  if (clear) {
    offset.value = 0;
    newContentAvailable.value = false;
  }
  loading.value = true;

  const nextItems = await props.loadData(
    offset.value,
    limit,
    sortBy.value,
    search.value,
    inLibraryOnly.value
  );
  if (offset.value) {
    items.value.push(...nextItems.items);
  } else {
    items.value = nextItems.items;
  }
  totalItems.value = nextItems.total;
  loading.value = false;
  let storKey = `search.${props.itemtype}`;
  if (props.parentItem) storKey += props.parentItem.item_id;
  localStorage.setItem(storKey, search.value);
};

// get/set default settings at load
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
  // get stored/default sortBy for this itemtype
  const savedSortBy = localStorage.getItem(`sortBy.${props.itemtype}`);
  if (savedSortBy) {
    sortBy.value = savedSortBy;
  } else {
    sortBy.value = props.sortKeys[0];
  }

  // get stored/default libraryOnlyFilter for this itemtype
  if (props.showLibrary !== false) {
    const savedInLibraryOnlyStr = localStorage.getItem(
      `libraryFilter.${props.itemtype}`
    );
    if (savedInLibraryOnlyStr && savedInLibraryOnlyStr == "true") {
      inLibraryOnly.value = true;
    }
  }

  // get stored/default albumArtistsOnlyFilter for this itemtype
  if (props.showAlbumArtistsOnlyFilter !== false) {
    const albumArtistsOnlyStr = localStorage.getItem(
      `albumArtistsFilter.${props.itemtype}`
    );
    if (albumArtistsOnlyStr && albumArtistsOnlyStr == "true") {
      albumArtistsOnlyFilter.value = true;
      emit("toggleAlbumArtistsOnly", albumArtistsOnlyFilter.value);
    }
  }
  // get stored searchquery
  let storKey = `search.${props.itemtype}`;
  if (props.parentItem) storKey += props.parentItem.item_id;
  const savedSearch = localStorage.getItem(storKey);
  if (savedSearch) {
    search.value = savedSearch;
  }
  loadData(true);
});

onMounted(() => {
  //reload if/when parent item updates
  const unsub = api.subscribe_multi(
    [
      MassEventType.MEDIA_ITEM_ADDED,
      MassEventType.MEDIA_ITEM_UPDATED,
      MassEventType.MEDIA_ITEM_DELETED,
    ],
    (evt: MassEvent) => {
      if (evt.type == MassEventType.MEDIA_ITEM_ADDED) {
        if (props.itemtype.includes((evt.data as MediaItemType).media_type)) {
          // signal that there is new content
          newContentAvailable.value = true;
        }
      } else if (evt.type == MassEventType.MEDIA_ITEM_DELETED) {
        items.value = items.value.filter((x) => x.uri != evt.object_id);
      } else if (evt.type == MassEventType.MEDIA_ITEM_UPDATED) {
        // update listing if relevant item changes
        const updatedItem = evt.data as MediaItemType;
        items.value = items.value.map((x) =>
          x.uri == updatedItem.uri ? updatedItem : x
        );
      }
    }
  );
  onBeforeUnmount(unsub);
});

// lifecycle hooks
const keyListener = function (e: KeyboardEvent) {
  if (showContextMenu.value) return;
  if (e.key === "a" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    selectedItems.value = items.value;
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

  if (sortBy == "provider") {
    result.sort((a, b) => a.provider.localeCompare(b.provider));
  }

  if (inLibraryOnly) {
    result = result.filter((x) => x.in_library);
  }

  const totalItems = result.length;
  const pagedItems = result.slice(offset, offset + limit);
  return {
    items: pagedItems,
    count: pagedItems.length,
    limit: limit,
    offset: offset,
    total: totalItems,
  };
};
</script>

<style scoped>
.scroller {
  height: 100%;
}
</style>
