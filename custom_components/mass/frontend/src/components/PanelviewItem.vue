<template>
  <v-card
    @click="emit('click', item)"
    :min-height="[MediaType.ARTIST, MediaType.RADIO].includes(item.media_type) ? size * 1.7 : size * 2.2"
    :min-width="size"
    hover
    border
    @click.right.prevent="emit('select', item, !isSelected)"
  >
    <MediaItemThumb :item="item" :size="size" :border="false" />
    <div v-if="isSelected" style="position: absolute; top:0;background-color: #82b1ff94">
      <v-btn variant="plain" size="51" :icon="mdiCheckboxMarkedOutline" @click.stop="emit('select', item, !isSelected)"></v-btn>
    </div>
    <div
      v-if="isHiRes"
      class="hiresicon"
      :style="
        $vuetify.theme.current == 'dark'
          ? 'background-color: black'
          : 'background-color:white'
      "
    >
      <v-tooltip bottom>
        <template v-slot:activator="{ props }">
          <img
            :src="iconHiRes"
            height="35"
            v-bind="props"
            :style="
              $vuetify.theme.current == 'light'
                ? 'object-fit: contain;filter: invert(100%);'
                : 'object-fit: contain;'
            "
          />
        </template>
        <span>{{ isHiRes }}</span>
      </v-tooltip>
    </div>

    <v-card-title
      :class="$vuetify.display.mobile ? 'body-2' : 'text-subtitle-1'"
      style="padding: 8px; color: primary; margin-top: 8px"
      v-text="truncateString(item.name, 35)"
    />
    <v-card-subtitle
      v-if="'artist' in item && item.artist"
      style="
        padding: 8px;
        position: absolute;
        bottom: 0px;
        display: flex;
        align-items: flex-end;
      "
      @click.stop="artistClick(item.artist)"
      v-text="item.artist.name"
    />
    <v-card-subtitle
      v-if="'artists' in item && item.artists"
      style="
        padding: 8px;
        position: absolute;
        bottom: 0px;
        display: flex;
        align-items: flex-end;
      "
      @click.stop="artistClick(item.artists[0])"
      v-text="item.artists[0].name"
    />
    <v-card-subtitle
      v-if="'owner' in item && item.owner"
      style="
        padding: 8px;
        position: absolute;
        bottom: 0px;
        display: flex;
        align-items: flex-end;
      "
      v-text="item.owner"
    />
  </v-card>
</template>

<script setup lang="ts">
import {
  mdiCheckboxMarkedOutline,
} from "@mdi/js";
import { ref, computed } from "vue";
import { useRouter } from "vue-router";

import MediaItemThumb from "./MediaItemThumb.vue";
import ProviderIcons from "./ProviderIcons.vue";
import { iconHiRes } from "./ProviderIcons.vue";
import {
  Album,
  Artist,
  ItemMapping,
  MediaItem,
  MediaItemType,
  MediaQuality,
} from "../plugins/api";
import { MediaType } from "../plugins/api";
import { formatDuration, truncateString } from "../utils";
import { store } from "../plugins/store";

// global refs
const router = useRouter();
const actionInProgress = ref(false);

// properties
interface Props {
  item: MediaItemType;
  size?: number;
  isSelected: boolean;
}
const props = withDefaults(defineProps<Props>(), {
  size: 200,
});

// computed properties
const isHiRes = computed(() => {
  for (const prov of props.item.provider_ids) {
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
  (e: "menu", value: MediaItem): void;
  (e: "click", value: MediaItem): void;
  (e: "select", value: MediaItem, selected: boolean): void;
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
  if (actionInProgress.value) return;
  actionInProgress.value = true;
  router.push({
    name: "artist",
    params: {
      item_id: item.item_id,
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
