<template>
  <div>
    <v-list-item
      ripple
      @click.stop="itemClick"
      @contextmenu.prevent="menuClick"
      :key="item.uri"
      style="padding-right: 0px"
    >
      <template v-slot:prepend
        ><v-list-item-avatar class="listitem-thumb" @click.stop="onSelect">
          <MediaItemThumb :item="item" :size="50" />
          <div
            v-if="isSelected"
            style="position: absolute; margin-top: -50px; background-color: #82b1ff94"
          >
            <v-icon dark size="51" :icon="mdiCheckboxMarkedOutline"></v-icon>
          </div> </v-list-item-avatar
      ></template>

      <!-- title -->
      <template v-slot:title>
        {{ item.name }}
        <span v-if="'version' in item && item.version">({{ item.version }})</span>
        <b v-if="!itemIsAvailable(item)"> UNAVAILABLE</b>
      </template>

      <!-- subtitle -->
      <template v-slot:subtitle>
        <!-- track artists + album name -->
        <div v-if="'artists' in item && item.artists">
          <span v-for="(artist, artistindex) in item.artists" :key="artist.uri">
            <a color="primary" @click.stop="artistClick(artist)">{{ artist.name }}</a>
            <label v-if="artistindex + 1 < item.artists.length" :key="artistindex"
              >/</label
            >
          </span>
          <!-- album -->
          <a
            v-if="!!item.album && !showTrackNumber"
            style="color: grey"
            @click.stop.stop="albumClick(item.album)"
          >
            - {{ item.album.name }}</a
          >
          <!-- track + disc number -->
          <label v-if="showTrackNumber && item.track_number" style="color: grey"
            >- disc {{ item.disc_number }} track {{ item.track_number }}</label
          >
        </div>
        <!-- album artist -->
        <div v-if="'artist' in item && item.artist">
          <a @click.stop.stop="artistClick(item.artist)">{{ item.artist.name }}</a>
        </div>
        <!-- playlist owner -->
        <div v-if="'owner' in item && item.owner">{{ item.owner }}</div>
      </template>

      <!-- actions -->
      <template v-slot:append>
        <div class="listitem-actions">
          <!-- provider icons -->
          <ProviderIcons
            v-if="item.provider_ids && showProviders && !$vuetify.display.mobile"
            :provider-ids="item.provider_ids"
            :height="20"
            class="listitem-actions"
          />

          <!-- hi res icon -->
          <v-img
            class="listitem-action"
            v-if="highResDetails"
            :src="iconHiRes"
            width="35"
            :style="
              $vuetify.theme.current == 'light'
                ? 'margin-top:5px;filter: invert(100%);'
                : 'margin-top:5px;'
            "
          >
            <v-tooltip activator="parent" anchor="bottom">{{ highResDetails }}</v-tooltip>
          </v-img>

          <!-- in library (heart) icon -->
          <div
            class="listitem-action"
            v-if="'in_library' in item && showLibrary && !$vuetify.display.mobile"
          >
            <v-tooltip anchor="bottom">
              <template #activator="{ props }">
                <v-btn
                  variant="plain"
                  ripple
                  v-bind="props"
                  @click="api.toggleLibrary(item)"
                  @click.prevent
                  @click.stop
                  :icon="item.in_library ? mdiHeart : mdiHeartOutline"
                >
                </v-btn>
              </template>
              <span v-if="item.in_library">{{ $t("remove_library") }}</span>
              <span v-if="!item.in_library">{{ $t("add_library") }}</span>
            </v-tooltip>
          </div>

          <!-- track duration -->
          <div
            class="listitem-action"
            v-if="showDuration && 'duration' in item && !$vuetify.display.mobile"
          >
            <span>{{ formatDuration(item.duration) }}</span>
          </div>

          <!-- menu button/icon -->
          <v-btn
            class="listitem-action"
            v-if="showMenu"
            @click="menuClick"
            @click.stop
            :icon="mdiDotsVertical"
            variant="plain"
            style="margin-right: -10px; margin-left: -10px"
          ></v-btn>
        </div>
      </template>
    </v-list-item>
    <v-divider></v-divider>
  </div>
</template>

<script setup lang="ts">
import {
  mdiHeart,
  mdiHeartOutline,
  mdiDotsVertical,
  mdiCheckboxMarkedOutline,
} from "@mdi/js";
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import { VTooltip } from "vuetify/components";

import MediaItemThumb from "./MediaItemThumb.vue";
import ProviderIcons from "./ProviderIcons.vue";
import { iconHiRes } from "./ProviderIcons.vue";
import type {
  Album,
  Artist,
  ItemMapping,
  MediaItem,
  MediaItemType,
} from "../plugins/api";
import { api } from "../plugins/api";
import { formatDuration } from "../utils";
import { store } from "../plugins/store";

// global refs
const router = useRouter();
const actionInProgress = ref(false);

// properties
interface Props {
  item: MediaItemType;
  showTrackNumber?: boolean;
  showProviders?: boolean;
  showMenu?: boolean;
  showLibrary?: boolean;
  showDuration?: boolean;
  isSelected: boolean;
}
const props = withDefaults(defineProps<Props>(), {
  showTrackNumber: true,
  showProviders: true,
  showMenu: true,
  showLibrary: true,
  showDuration: true,
});

// computed properties
const highResDetails = computed(() => {
  if (!props.item.provider_ids) return "";
  for (const prov of props.item.provider_ids) {
    if (prov.quality !== 99 && prov.quality > 6) {
      if (prov.details) {
        return prov.details;
      } else if (prov.quality === 7) {
        return "44.1/48khz 24 bits";
      } else if (prov.quality === 8) {
        return "88.2/96khz 24 bits";
      } else if (prov.quality === 9) {
        return "176/192khz 24 bits";
      } else {
        return "+192kHz 24 bits";
      }
    }
  }
  return "";
});

// emits
const emit = defineEmits<{
  (e: "menu", value: MediaItem): void;
  (e: "clicked", value: MediaItem): void;
  (e: "select", value: MediaItem, selected: boolean): void;
}>();

// methods
const itemClick = function () {
  // contextmenu button clicked
  if (actionInProgress.value) return;
  actionInProgress.value = true;
  emit("clicked", props.item);

  setTimeout(() => {
    actionInProgress.value = false;
  }, 500);
};

const menuClick = function () {
  // contextmenu button clicked
  if (actionInProgress.value) return;
  emit("menu", props.item);
};

const onSelect = function (event: Event) {
  // contextmenu button clicked
  if (actionInProgress.value) return;
  actionInProgress.value = true;
  event.preventDefault();
  emit("select", props.item, !props.isSelected);
  setTimeout(() => {
    actionInProgress.value = false;
  }, 500);
};
const albumClick = function (item: Album | ItemMapping) {
  // album entry clicked
  if (actionInProgress.value) return;
  actionInProgress.value = true;
  router.push({
    name: "album",
    params: {
      id: item.item_id,
      provider: item.provider,
    },
  });
  setTimeout(() => {
    actionInProgress.value = false;
  }, 500);
};
const artistClick = function (item: Artist | ItemMapping) {
  // album entry clicked
  if (actionInProgress.value) return;
  actionInProgress.value = true;
  router.push({
    name: "artist",
    params: {
      id: item.item_id,
      provider: item.provider,
    },
  });
  setTimeout(() => {
    actionInProgress.value = false;
  }, 500);
};
const itemIsAvailable = function (item: MediaItem) {
  if (!props.item.provider_ids) return true;
  for (const x of item.provider_ids) {
    if (x.available) return true;
  }
  return false;
};
</script>