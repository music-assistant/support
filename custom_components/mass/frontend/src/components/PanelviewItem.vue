<template>
  <v-card
    @click="itemClick"
    :min-height="thumbHeight"
    :min-width="thumbWidth"
    :max-width="thumbWidth * 1.4"
    hover
    outlined
    @contextmenu.prevent="menuClick"
  >
    <MediaItemThumb :item="item" :size="thumbWidth" />
    <div v-if="isSelected" style="position: absolute; background-color: #82b1ff94">
      <v-icon dark size="51"> mdi-checkbox-marked-outline </v-icon>
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
    <v-divider />
    <v-card-title
      :class="$vuetify.display.mobile ? 'body-2' : 'title'"
      style="padding: 8px; color: primary; margin-top: 8px"
      v-text="item.name"
    />
    <v-card-subtitle
      v-if="'artist' in item && item.artist"
      :class="$vuetify.display.mobile ? 'caption' : 'body-1'"
      style="padding: 8px"
      @click.stop="artistClick(item.artist)"
      v-text="item.artist.name"
    />
    <v-card-subtitle
      v-if="'artists' in item && item.artists"
      :class="$vuetify.display.mobile ? 'caption' : 'body-1'"
      style="padding: 8px"
      @click.stop="artistClick(item.artists[0])"
      v-text="item.artists[0].name"
    />
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useRouter } from "vue-router";

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
import { formatDuration } from "../utils";
import { store } from "../plugins/store";

// global refs
const router = useRouter();
const actionInProgress = ref(false);

// properties
interface Props {
  item: MediaItemType;
  thumbHeight?: number;
  thumbWidth?: number;
  isSelected: boolean;
}
const props = withDefaults(defineProps<Props>(), {
  thumbHeight: 400,
  thumbWidth: 400,
});

// computed properties
const isHiRes = computed(() => {
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
