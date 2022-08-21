<template>
  <v-card
    outlined
    @click="emit('click', item)"
    @click.right.prevent="emit('menu', item)"
  >
    <MediaItemThumb :item="item" :size="size" />
    <div
      v-if="showCheckboxes"
      style="
        position: absolute;
        top: 0;
        background-color: #82b1ff94;
        height: 50px;
      "
    >
      <v-checkbox
        :model-value="isSelected"
        @click.stop
        @update:model-value="
          (x) => {
            emit('select', item, x);
          }
        "
      />
    </div>
    <div
      v-if="isHiRes"
      class="hiresicon"
      :style="
        $vuetify.theme.current.dark
          ? 'background-color: black'
          : 'background-color:white'
      "
    >
      <v-tooltip bottom>
        <template #activator="{ props }">
          <img
            :src="iconHiRes"
            height="35"
            v-bind="props"
            :style="
              $vuetify.theme.current.dark
                ? 'object-fit: contain;'
                : 'object-fit: contain;filter: invert(100%);'
            "
          />
        </template>
        <span>{{ isHiRes }}</span>
      </v-tooltip>
    </div>

    <v-list-item two-line style="padding-left: 8px; padding-right: 8px">
      <v-list-item-content>
        <v-list-item-text>
          <p
            class="font-weight-bold line-clamp-1"
            style="color: primary; margin-top: 8px; margin-bottom: 8px"
          >
            {{ item.name }}
          </p>
        </v-list-item-text>
        <v-list-item-subtitle
          v-if="'artists' in item && item.artists"
          class="line-clamp-2"
          style="margin-bottom: 8px"
          v-text="getArtistsString(item.artists)"
        />
        <v-list-item-subtitle
          v-else-if="'owner' in item && item.owner"
          class="line-clamp-2"
          style="margin-bottom: 8px"
          v-text="item.owner"
        />
      </v-list-item-content>
    </v-list-item>
  </v-card>
</template>

<script setup lang="ts">
import { mdiCheckboxMarkedOutline, mdiDotsVertical } from '@mdi/js';
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useTheme } from 'vuetify';
import MediaItemThumb from './MediaItemThumb.vue';

import { iconHiRes } from './ProviderIcons.vue';

import type {
  Artist,
  ItemMapping,
  MediaItem,
  MediaItemType,
} from '../plugins/api';
import { MediaType, MediaQuality } from '../plugins/api';
import { getArtistsString } from '../utils';

// properties
export interface Props {
  item: MediaItemType;
  size?: number;
  isSelected: boolean;
  showCheckboxes: boolean;
}
const props = withDefaults(defineProps<Props>(), {
  size: 200,
  showCheckboxes: false,
});

// global refs
const router = useRouter();
const actionInProgress = ref(false);
const theme = useTheme();

// computed properties
const isHiRes = computed(() => {
  for (const prov of props.item.provider_ids) {
    if (prov.quality == undefined) continue;
    if (prov.quality >= MediaQuality.LOSSLESS_HI_RES_1) {
      if (prov.details) {
        return prov.details;
      } else if (prov.quality === MediaQuality.LOSSLESS_HI_RES_1) {
        return '44.1/48khz 24 bits';
      } else if (prov.quality === MediaQuality.LOSSLESS_HI_RES_2) {
        return '88.2/96khz 24 bits';
      } else if (prov.quality === MediaQuality.LOSSLESS_HI_RES_3) {
        return '176/192khz 24 bits';
      } else {
        return '+192kHz 24 bits';
      }
    }
  }
  return '';
});

// emits
const emit = defineEmits<{
  (e: 'menu', value: MediaItem): void;
  (e: 'click', value: MediaItem): void;
  (e: 'select', value: MediaItem, selected: boolean): void;
}>();

// methods

const artistClick = function (item: Artist | ItemMapping) {
  // album entry clicked
  if (actionInProgress.value) return;
  actionInProgress.value = true;
  router.push({
    name: 'artist',
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
