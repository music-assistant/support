<template>
  <div
    :max-height="maxHeight"
    :max-width="maxWidth"
    :min-height="minHeight"
    :min-width="minWidth"
    :height="height"
    :width="width"
  >
    <v-img
      :key="item?.uri"
      :cover="cover"
      :src="imgData"
      :style="border ? 'border: 1px solid rgba(0, 0, 0, 0.22)' : ''"
      :max-height="maxHeight"
      :max-width="maxWidth"
      :min-height="minHeight"
      :min-width="minWidth"
      :height="height"
      :width="width"
    >
      <template v-slot:placeholder>
        <div class="d-flex align-center justify-center fill-height">
          <v-progress-circular indeterminate color="grey-lighten-4"></v-progress-circular>
        </div>
      </template>
    </v-img>
  </div>
</template>

<script setup lang="ts">
import { watchEffect, ref, computed } from "vue";
import type { ItemMapping, MediaItemType, QueueItem } from "../plugins/api";
import { ImageType } from "../plugins/api";
import { store } from "../plugins/store";

export interface Props {
  item?: MediaItemType | ItemMapping | QueueItem;
  size?: number;
  width?: string | number;
  height?: string | number;
  minWidth?: string | number;
  minHeight?: string | number;
  maxWidth?: string | number;
  maxHeight?: string | number;
  border?: boolean;
  cover?: boolean;
  fallback?: string;
}

const props = withDefaults(defineProps<Props>(), {
  border: true,
  size: 200,
  width: "auto",
  height: "auto",
  cover: true,
});

const imgData = ref<string>();

const fallbackImage = computed(() => {
  if (props.fallback) return props.fallback;
  if (store.darkTheme)
    return `https://ui-avatars.com/api/?name=${props.item.name}&size=${props.size}&bold=true&background=1d1d1d&color=383838`;
  else
    return `https://ui-avatars.com/api/?name=${props.item.name}&size=${props.size}&bold=true&background=a0a0a0&color=cccccc`;
});

watchEffect(async () => {
  if (!props.item) return;
  imgData.value =
    (await getImageThumbForItem(props.item, ImageType.THUMB, props.size)) ||
    fallbackImage.value;
});
</script>

<script lang="ts">
//// utility functions for images

export const getImageUrl = function (
  mediaItem?: MediaItemType | ItemMapping | QueueItem,
  type: ImageType = ImageType.THUMB,
  includeFileBased = false
) {
  // get imageurl for mediaItem
  if (!mediaItem || !mediaItem.media_type) return "";
  if ("image" in mediaItem && mediaItem.image) return mediaItem.image; // queueItem
  if ("metadata" in mediaItem && mediaItem.metadata.images) {
    for (const img of mediaItem.metadata.images) {
      if (img.is_file && !includeFileBased) continue;
      if (img.type == type) return img.url;
    }
  }
  // retry with album of track
  if (
    "album" in mediaItem &&
    mediaItem.album &&
    "metadata" in mediaItem.album &&
    mediaItem.album.metadata &&
    mediaItem.album.metadata.images
  ) {
    for (const img of mediaItem.album.metadata.images) {
      if (img.is_file && !includeFileBased) continue;
      if (img.type == type) return img.url;
    }
  }
  // retry with album artist
  if (
    "artist" in mediaItem &&
    "metadata" in mediaItem.artist &&
    mediaItem.artist.metadata &&
    mediaItem.artist.metadata.images
  ) {
    for (const img of mediaItem.artist.metadata.images) {
      if (img.is_file && !includeFileBased) continue;
      if (img.type == type) return img.url;
    }
  }
  // retry with track artist
  if ("artists" in mediaItem && mediaItem.artists) {
    for (const artist of mediaItem.artists) {
      if ("metadata" in artist && artist.metadata.images) {
        for (const img of artist.metadata.images) {
          if (img.is_file && !includeFileBased) continue;
          if (img.type == type) return img.url;
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
  let url = getImageUrl(mediaItem, type, true);
  if (!url) return undefined;
  if (url.startsWith("http") && size) {
    // get url to resized image(thumb) from weserv service
    return `https://images.weserv.nl/?url=${url}&w=200`;
  } else if (url.startsWith("https://")) {
    return url;
  } else if (
    url.startsWith("http://") &&
    window.location.protocol == "https:"
  ) {
    // require https images if we're hosted as https...
    return url.replace("http://", "https://");
  } else {
    // use image proxy in HA integration to grab thumb
    const encUrl = encodeURIComponent(url);
    return `/api/mass/image_proxy?size=${size || 0}&url=${encUrl}`;
  }
};
</script>
