<template>
  <v-img
    :key="item.uri"
    cover
    :src="imgData"
    :height="height"
    :width="width"
    :style="border ? 'border: 1px solid rgba(0, 0, 0, 0.22)' : ''"
    :max-height="maxHeight || size * 1.4"
    :max-width="maxWidth"
    :min-height="minHeight || size"
    :min-width="minWidth || size"
  >
    <template v-slot:placeholder>
      <div class="d-flex align-center justify-center fill-height">
        <v-progress-circular indeterminate color="grey-lighten-4"></v-progress-circular>
      </div>
    </template>
  </v-img>
</template>

<script setup lang="ts">
import { store } from "@/plugins/store";
import { watchEffect, ref } from "vue";
import { MediaType, type ItemMapping, type MediaItemType } from "../plugins/api";
import { api } from "../plugins/api";

interface Props {
  item?: MediaItemType | ItemMapping;
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
});

const imgData = ref<string>();

const getImageThumb = (url: string, size = 200) => {
  // get url to resized image(thumb) from weserv service
  // we request a static size of 200 pixels
  return `https://images.weserv.nl/?url=${url}&w=${size}`;
};

watchEffect(async () => {
  if (!props.item) return;
  let url: string | undefined = '';
  // const url = await api?.getImageUrlForMediaItem(props.item);
  url = api?.getImageUrl(props.item);
  if (!url && store.contextMenuParentItem) {
    url = api?.getImageUrl(store.contextMenuParentItem);
  }

  if (typeof url == "string" && (!props.size || props.size > 200)) {
    // simply use the fullsize url
    imgData.value = url;
  } else if (typeof url == "string") {
    // resized image by url
    imgData.value = getImageThumb(url);
  }
});
</script>
