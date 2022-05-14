<template>
  <div
    :height="size"
    :width="width"
    :max-height="maxHeight || size * 1.4"
    :max-width="maxWidth || size * 1.4"
    :min-height="minHeight || size"
    :min-width="minWidth || size"
  >
    <v-avatar rounded="0" color="grey" :style="`height:${size}px;width:100%`">
      <v-img
        :key="item?.uri"
        cover
        :src="imgData"
        :style="border ? 'border: 1px solid rgba(0, 0, 0, 0.22)' : ''"
      >
        <template v-slot:placeholder>
          <div class="d-flex align-center justify-center fill-height">
            <v-progress-circular
              indeterminate
              color="grey-lighten-4"
            ></v-progress-circular>
          </div>
        </template>
      </v-img>
    </v-avatar>
  </div>
</template>

<script setup lang="ts">
import { store } from "@/plugins/store";
import { watchEffect, ref } from "vue";
import type { ItemMapping, MediaItemType, QueueItem } from "../plugins/api";
import { api, ImageType } from "../plugins/api";

export interface Props {
  item?: MediaItemType | ItemMapping | QueueItem;
  size?: number;
  width?: string;
  height?: string;
  minWidth?: string;
  minHeight?: string;
  maxWidth?: string;
  maxHeight?: string;
  border?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  border: true,
  size: 200,
});

const imgData = ref<string>();

watchEffect(async () => {
  if (!props.item) return;
  imgData.value = await getImageThumbForItem(props.item, ImageType.THUMB, props.size) || `https://ui-avatars.com/api/?name=${props.item.name}&size=${props.size}}`;
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
  if (!mediaItem) return;
  if ("image" in mediaItem) return mediaItem.image; // queueItem
  if (!mediaItem || !mediaItem.media_type) return "";
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
      if (img.type == type) return img.url;
    }
  }
  // retry with track artist
  if ("artists" in mediaItem && mediaItem.artists) {
    for (const artist of mediaItem.artists) {
      if ("metadata" in artist && artist.metadata.images) {
        for (const img of artist.metadata.images) {
          if (img.type == type) return img.url;
        }
      }
    }
  }
};

export const getFanartUrl = function (mediaItem?: MediaItemType, fallbackToImage = true) {
  const fanartImage = getImageUrl(mediaItem, ImageType.FANART);
  if (fanartImage) return fanartImage;
  if (fallbackToImage) return getImageUrl(mediaItem);
};

export const getImageThumbForItem = async function (
  mediaItem?: MediaItemType | ItemMapping | QueueItem,
  type: ImageType = ImageType.THUMB,
  size?: number
): Promise<string | undefined> {
  if (!mediaItem) return;
  let imgPath = getImageUrl(mediaItem, type, false);
  if (imgPath && size) {
    // get url to resized image(thumb) from weserv service
    return `https://images.weserv.nl/?url=${imgPath}&w=200`;
  } else if (imgPath) {
    return imgPath;
  }
  imgPath = getImageUrl(mediaItem, type, true);
  if (imgPath) {
    return await api.getLocalThumb(imgPath, size);
  }
  return undefined;
};
</script>
