<template>
  <div
    :max-height="maxSize"
    :max-width="maxSize"
    :min-height="minSize || size"
    :min-width="minSize || size"
    :height="'auto'"
    :width="'100%'"
  >
    <v-avatar
      :size="size"
      :min-height="minSize"
      :min-width="minSize"
      :rounded="tile ? 0 : undefined"
    >
      <v-img
        :key="item?.uri"
        :min-height="minSize"
        :min-width="minSize"
        :cover="cover"
        :src="imgData"
      >
        <template #placeholder>
          <div class="d-flex align-center justify-center fill-height">
            <v-progress-circular indeterminate color="grey-lighten-4" />
          </div>
        </template>
      </v-img>
    </v-avatar>
  </div>
</template>

<script setup lang="ts">
import { watchEffect, ref, computed } from 'vue';
import type {
  ItemMapping,
  MediaItemImage,
  MediaItemType,
  QueueItem,
} from '../plugins/api';
import { ImageType } from '../plugins/api';
import { store } from '../plugins/store';

export interface Props {
  item?: MediaItemType | ItemMapping | QueueItem;
  size?: number;
  minSize?: number;
  maxSize?: number;
  tile?: boolean;
  cover?: boolean;
  fallback?: string;
}

const props = withDefaults(defineProps<Props>(), {
  maxSize: 256,
  tile: true,
  cover: true,
});

const imgData = ref<string>();

const fallbackImage = computed(() => {
  if (props.fallback) return props.fallback;
  if (store.darkTheme)
    return `https://ui-avatars.com/api/?name=${props.item.name}&size=${props.maxSize}&bold=true&background=1d1d1d&color=383838`;
  else
    return `https://ui-avatars.com/api/?name=${props.item.name}&size=${props.maxSize}&bold=true&background=a0a0a0&color=cccccc`;
});

watchEffect(async () => {
  if (!props.item) return;
  imgData.value =
    (await getImageThumbForItem(props.item, ImageType.THUMB, props.maxSize)) ||
    fallbackImage.value;
});
</script>

<script lang="ts">
//// utility functions for images

export const getMediaItemImage = function (
  mediaItem?: MediaItemType | ItemMapping | QueueItem,
  type: ImageType = ImageType.THUMB,
  includeFileBased = false
): MediaItemImage | undefined {
  // get imageurl for mediaItem
  if (!mediaItem) return undefined;
  if ('image' in mediaItem && mediaItem.image) return mediaItem.image; // queueItem
  if ('metadata' in mediaItem && mediaItem.metadata.images) {
    for (const img of mediaItem.metadata.images) {
      if (img.is_file && !includeFileBased) continue;
      if (img.type == type) return img;
    }
  }
  // retry with album of track
  if (
    'album' in mediaItem &&
    mediaItem.album &&
    'metadata' in mediaItem.album &&
    mediaItem.album.metadata &&
    mediaItem.album.metadata.images
  ) {
    for (const img of mediaItem.album.metadata.images) {
      if (img.is_file && !includeFileBased) continue;
      if (img.type == type) return img;
    }
  }
  // retry with album artist
  if (
    'artist' in mediaItem &&
    'metadata' in mediaItem.artist &&
    mediaItem.artist.metadata &&
    mediaItem.artist.metadata.images
  ) {
    for (const img of mediaItem.artist.metadata.images) {
      if (img.is_file && !includeFileBased) continue;
      if (img.type == type) return img;
    }
  }
  // retry with track artist
  if ('artists' in mediaItem && mediaItem.artists) {
    for (const artist of mediaItem.artists) {
      if ('metadata' in artist && artist.metadata.images) {
        for (const img of artist.metadata.images) {
          if (img.is_file && !includeFileBased) continue;
          if (img.type == type) return img;
        }
      }
    }
  }
};

export const getImageThumbForItem = async function (
  mediaItem?: MediaItemType | ItemMapping | QueueItem,
  type: ImageType = ImageType.THUMB,
  size?: number
): Promise<string | undefined> {
  if (!mediaItem) return;
  const img = getMediaItemImage(mediaItem, type, true);
  if (!img) return undefined;
  if (!img.is_file && size) {
    // get url to resized image(thumb) from weserv service
    return `https://images.weserv.nl/?url=${img.url}&w=${size}&h=${size}&fit=cover&a=attention`;
  } else if (img.url.startsWith('https://')) {
    return img.url;
  } else if (
    img.url.startsWith('http://') &&
    window.location.protocol == 'https:'
  ) {
    // require https images if we're hosted as https...
    return img.url.replace('http://', 'https://');
  } else {
    // use image proxy in HA integration to grab thumb
    const encUrl = encodeURIComponent(img.url);
    return `${store.apiBaseUrl}/mass/image_proxy?size=${
      size || 0
    }&url=${encUrl}`;
  }
};
</script>

<style>
.v-avatar.v-avatar--density-default {
  height: 100% !important;
  width: 100% !important;
}
</style>
