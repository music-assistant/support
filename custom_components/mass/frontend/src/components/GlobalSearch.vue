<template>
  <v-card>
    <v-text-field
      id="searchInput"
      v-model="search"
      clearable
      :prepend-inner-icon="mdiMagnify"
      :label="$t('type_to_search')"
      hide-details
      variant="filled"
      style="width: auto; margin: 10px"
      @focus="searchHasFocus = true"
      @blur="searchHasFocus = false"
    />

    <div v-if="search">
      <v-chip-group
        v-model="viewFilter"
        column
        style="margin-top: 15px; margin-left: 10px"
      >
        <v-chip v-for="item in viewFilters" :key="item" filter outlined>
          {{ $t(item) }}
        </v-chip>
      </v-chip-group>

      <MediaItemContextMenu
        v-model="showContextMenu"
        :items="selectedItems"
        @clear="
          () => {
            selectedItems = [];
          }
        "
      />

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
        <v-progress-linear v-if="loading" indeterminate />

        <!-- panel view -->
        <v-row
          v-if="viewMode == 'panel'"
          dense
          align-content="start"
          align="start"
        >
          <v-col
            v-for="item in filteredItems"
            :key="item.uri"
            align-self="start"
          >
            <PanelviewItem
              :item="item"
              :size="thumbSize"
              :is-selected="false"
              :show-checkboxes="false"
              @menu="onMenu"
              @click="onClick"
            />
          </v-col>
        </v-row>

        <!-- list view -->
        <div v-if="viewMode == 'list'">
          <RecycleScroller
            v-slot="{ item }"
            :items="filteredItems"
            :item-size="60"
            key-field="item_id"
            page-mode
          >
            <ListviewItem
              :item="item"
              :show-track-number="false"
              :show-duration="true"
              :show-library="false"
              :show-menu="true"
              :show-providers="true"
              :show-checkboxes="false"
              :is-selected="false"
              :show-details="true"
              @menu="onMenu"
              @click="onClick"
            />
          </RecycleScroller>
        </div>
      </div>
      <v-toolbar dense flat color="transparent" height="45">
        <span>{{ $t('items_total', [filteredItems.length]) }}</span>
        <v-spacer />

        <v-tooltip location="bottom">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              :icon="viewMode == 'panel' ? mdiViewList : mdiGrid"
              @click="toggleViewMode()"
            />
          </template>
          <span>{{ $t('tooltip.toggle_view_mode') }}</span>
        </v-tooltip>
      </v-toolbar>
    </div>
  </v-card>
</template>

<script setup lang="ts">
/* eslint-disable @typescript-eslint/no-unused-vars,vue/no-setup-props-destructure */
import { mdiMagnify, mdiGrid, mdiViewList } from '@mdi/js';

import {
  ref,
  computed,
  onBeforeUnmount,
  onMounted,
  watch,
  watchEffect,
} from 'vue';
import { useDisplay } from 'vuetify';
import { MediaType, type MediaItemType } from '../plugins/api';
import { RecycleScroller } from 'vue-virtual-scroller';
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import { store } from '../plugins/store';
import ListviewItem from './ListviewItem.vue';
import PanelviewItem from './PanelviewItem.vue';
import MediaItemContextMenu from './MediaItemContextMenu.vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { api } from '../plugins/api';

// global refs
const router = useRouter();
const i18n = useI18n();
const { mobile } = useDisplay();

// local refs
const viewMode = ref('list');
const viewFilter = ref(0);
const search = ref('');
const searchHasFocus = ref(false);
const items = ref<MediaItemType[]>([]);
const loading = ref(false);
const showContextMenu = ref(false);
const selectedItems = ref<MediaItemType[]>([]);
const throttleId = ref();

const viewFilters = ['topresult', 'artists', 'albums', 'tracks', 'playlists'];

// computed properties
const thumbSize = computed(() => {
  return mobile.value ? 140 : 150;
});

// methods

const toggleViewMode = function () {
  if (viewMode.value === 'panel') viewMode.value = 'list';
  else viewMode.value = 'panel';
  localStorage.setItem(
    `viewMode.search.${viewFilterStr.value}`,
    viewMode.value
  );
};

const onMenu = function (item: MediaItemType) {
  selectedItems.value = [item];
  showContextMenu.value = true;
};

const onClick = function (mediaItem: MediaItemType) {
  // mediaItem in the list is clicked

  if (
    ['artist', 'album', 'playlist'].includes(mediaItem.media_type) ||
    !store.selectedPlayer?.available
  ) {
    router.push({
      name: mediaItem.media_type,
      params: {
        item_id: mediaItem.item_id,
        provider: mediaItem.provider,
      },
    });
  } else if (store.selectedPlayer) {
    // assume track (or radio) item
    api.playMedia(mediaItem);
  }
};

// watchers
watch(
  () => search.value,
  (newVal) => {
    clearTimeout(throttleId.value);
    throttleId.value = setTimeout(() => {
      loadSearchResults();
    }, 200);
  }
);

const loadSearchResults = async function () {
  loading.value = true;
  localStorage.setItem('globalsearch', search.value);

  if (search.value) {
    items.value = await api.search(search.value);
  } else {
    items.value = [];
  }
  loading.value = false;
};

const viewFilterStr = computed(() => {
  return viewFilters[viewFilter.value];
});

const filteredItems = computed(() => {
  if (viewFilterStr.value == 'artists') {
    return items.value.filter((x) => x.media_type == MediaType.ARTIST);
  }
  if (viewFilterStr.value == 'albums') {
    return items.value.filter((x) => x.media_type == MediaType.ALBUM);
  }
  if (viewFilterStr.value == 'tracks') {
    return items.value.filter((x) => x.media_type == MediaType.TRACK);
  }
  if (viewFilterStr.value == 'playlists') {
    return items.value.filter((x) => x.media_type == MediaType.PLAYLIST);
  }
  if (viewFilterStr.value == 'radios') {
    return items.value.filter((x) => x.media_type == MediaType.RADIO);
  }

  return items.value;
});

// get/set default settings at load
watchEffect(() => {
  // get stored/default viewMode for this itemtype
  const savedViewMode = localStorage.getItem(
    `viewMode.search.${viewFilterStr.value}`
  );
  if (savedViewMode) {
    viewMode.value = savedViewMode;
  } else if (viewFilterStr.value == 'artists') {
    viewMode.value = 'panel';
  } else if (viewFilterStr.value == 'albums') {
    viewMode.value = 'panel';
  } else {
    viewMode.value = 'list';
  }
});

onMounted(() => {
  const savedSearch = localStorage.getItem('globalsearch');
  if (savedSearch) {
    search.value = savedSearch;
  }
});

// lifecycle hooks
const keyListener = function (e: KeyboardEvent) {
  if (showContextMenu.value) return;
  if (e.key === 'a' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    selectedItems.value = items.value;
  } else if (!searchHasFocus.value && e.key == 'Backspace') {
    search.value = search.value.slice(0, -1);
  } else if (!searchHasFocus.value && e.key.length == 1) {
    search.value += e.key;
  }
};

document.addEventListener('keydown', keyListener);

onBeforeUnmount(() => {
  document.removeEventListener('keydown', keyListener);
});
</script>
