<template>
  <div>
    <v-list-item
      ripple
      @click.stop="emit('click', item)"
      @click.right.prevent="emit('menu', item)"
      style="padding-right: 0px"
    >
      <template v-slot:prepend
        ><v-list-item-avatar
          rounded="0"
          class="listitem-thumb"
          @click.stop="emit('select', item, !isSelected)"
        >
          <MediaItemThumb :item="item" :size="50" />
          <div v-if="isSelected" style="position: absolute; background-color: #82b1ff94">
            <v-icon dark size="51" :icon="mdiCheckboxMarkedOutline"></v-icon>
          </div> </v-list-item-avatar
      ></template>

      <!-- title -->
      <template v-slot:title>
        {{ item.name }}
        <span v-if="'version' in item && item.version">({{ item.version }})</span>
        <b v-if="!itemIsAvailable(item)"> UNAVAILABLE</b>
        <!-- explicit icon -->
        <v-tooltip anchor="bottom">
          <template #activator="{ props }">
            <v-icon
              v-bind="props"
              class="listitem-action"
              :icon="mdiAlphaEBox"
              width="35"
              v-if="parseBool(item.metadata['explicit'])"
            />
          </template>
          <span>{{ $t("explicit") }}</span>
        </v-tooltip>
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
          <a @click.stop="artistClick(item.artist)">{{ item.artist.name }}</a>
        </div>
        <!-- playlist owner -->
        <div v-if="'owner' in item && item.owner">{{ item.owner }}</div>
        <!-- radio description -->
        <div v-if="item.media_type == MediaType.RADIO && item.metadata.description">
          {{ item.metadata.description }}
        </div>
      </template>

      <!-- actions -->
      <template v-slot:append>
        <div class="listitem-actions">
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

          <!-- provider icons -->
          <ProviderIcons
            v-if="item.provider_ids && showProviders && !$vuetify.display.mobile"
            :provider-ids="item.provider_ids"
            :height="20"
            class="listitem-actions"
          />

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
            @click.stop="emit('menu', item)"
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
  mdiAlphaEBox,
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
import { api, MediaQuality, MediaType } from "../plugins/api";
import { formatDuration, parseBool } from "../utils";

// global refs
const router = useRouter();
const actionInProgress = ref(false);

// properties
export interface Props {
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
    if (!prov.quality) continue;
    if (prov.quality >= MediaQuality.FLAC_LOSSLESS_HI_RES_1) {
      if (prov.details) {
        return prov.details;
      } else if (prov.quality === MediaQuality.FLAC_LOSSLESS_HI_RES_1) {
        return "44.1/48khz 24 bits";
      } else if (prov.quality === MediaQuality.FLAC_LOSSLESS_HI_RES_2) {
        return "88.2/96khz 24 bits";
      } else if (prov.quality === MediaQuality.FLAC_LOSSLESS_HI_RES_3) {
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
  (e: "menu", value: MediaItemType): void;
  (e: "click", value: MediaItemType): void;
  (e: "select", value: MediaItemType, selected: boolean): void;
}>();

// methods

const albumClick = function (item: Album | ItemMapping) {
  // album entry clicked
  if (actionInProgress.value) return;
  actionInProgress.value = true;
  router.push({
    name: "album",
    params: {
      item_id: item.item_id,
      provider: item.provider,
    },
  });
  setTimeout(() => {
    actionInProgress.value = false;
  }, 500);
};
const artistClick = function (item: Artist | ItemMapping) {
  // album entry clicked
  router.push({
    name: "artist",
    params: {
      item_id: item.item_id,
      provider: item.provider,
    },
  });
};
const itemIsAvailable = function (item: MediaItem) {
  if (!props.item.provider_ids) return true;
  for (const x of item.provider_ids) {
    if (x.available && api.stats.providers.includes(x.provider)) return true;
  }
  return false;
};
</script>

<style scoped>
.listitem-actions {
  display: flex;
  justify-content: end;
  width: auto;
  height: 50px;
  vertical-align: middle;
  align-items: center;
  padding: 0px;
}
.listitem-action {
  padding-left: 5px;
}
.listitem-thumb {
  padding-left: 0px;
  margin-right: 10px;
  margin-left: -15px;
  width: 50px;
  height: 50px;
}
</style>
