<template>
  <v-card
    @click="emit('click', item)"
    :min-height="
      [MediaType.ARTIST, MediaType.RADIO].includes(item.media_type)
        ? size * 1.9
        : size * 2.2
    "
    :min-width="size"
    :max-width="size * 1.5"
    hover
    border
    @click.right.prevent="emit('select', item, !isSelected)"
  >
    <MediaItemThumb
      :item="item"
      :size="size"
      :min-height="size"
      :max-height="size * 1.2"
      :max-width="size * 1.5"
      :min-width="size"
      width="100%"
      :border="false"
      :cover="true"
    />
    <div
      v-if="isSelected"
      style="position: absolute; top: 0; background-color: #82b1ff94"
    >
      <v-btn
        variant="plain"
        size="51"
        :icon="mdiCheckboxMarkedOutline"
        @click.stop="emit('select', item, !isSelected)"
      ></v-btn>
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
import { mdiCheckboxMarkedOutline } from "@mdi/js";
import { ref, computed } from "vue";
import { useRouter } from "vue-router";

import MediaItemThumb from "./MediaItemThumb.vue";

import { iconHiRes } from "./ProviderIcons.vue";
import type {
  Artist,
  ItemMapping,
  MediaItem,
  MediaItemType,
} from "../plugins/api";
import { MediaType, MediaQuality } from "../plugins/api";
import { truncateString } from "../utils";

// global refs
const router = useRouter();
const actionInProgress = ref(false);

// properties
export interface Props {
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
    if (prov.quality == undefined) continue;
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
</script>
