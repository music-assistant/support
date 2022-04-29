<template>
  <div class="provider-icons" :style="`height: ${height};`">
    <img
      class="provider-icon"
      v-for="prov of uniqueProviders"
      :key="prov.provider"
      :height="height"
      :src="getProviderIcon(prov.provider)"
      @click="enableLink ? provClicked(prov) : ''"
      :style="enableLink ? 'cursor: pointer' : ''"
    />
  </div>
</template>

<script setup lang="ts">
import type { MediaItemProviderId } from "../plugins/api";
import { MediaQuality } from "../plugins/api";
import { computed } from "vue";

interface Props {
  providerIds: MediaItemProviderId[];
  height: number;
  enableLink?: boolean;
}
const props = defineProps<Props>();

const uniqueProviders = computed(() => {
  const output: MediaItemProviderId[] = [];
  const keys: string[] = [];
  if (!props.providerIds) return [];
  props.providerIds.forEach(function (prov: MediaItemProviderId) {
    const key = prov.provider;
    if (keys.indexOf(key) === -1) {
      keys.push(key);
      output.push(prov);
    }
  });
  return output.sort((a, b) => a.provider.localeCompare(b.provider));
});

const provClicked = function (prov: MediaItemProviderId) {
  if (prov.url) {
    window.open(prov.url, "_blank");
  }
};
</script>

<script lang="ts">
import { ContentType } from "../plugins/api";

export const iconSpotify = new URL("../assets/spotify.png", import.meta.url).href;
export const iconQobuz = new URL("../assets/qobuz.png", import.meta.url).href;
export const iconFilesystem = new URL("../assets/filesystem.png", import.meta.url).href;
export const iconTuneIn = new URL("../assets/tunein.png", import.meta.url).href;
export const iconFallback = new URL("../assets/fallback.png", import.meta.url).href;

export const iconAac = new URL("../assets/aac.png", import.meta.url).href;
export const iconFlac = new URL("../assets/flac.png", import.meta.url).href;
export const iconMp3 = new URL("../assets/mp3.png", import.meta.url).href;
export const iconOgg = new URL("../assets/ogg.png", import.meta.url).href;
export const iconVorbis = new URL("../assets/vorbis.png", import.meta.url).href;
export const iconHiRes = new URL("../assets/hires.png", import.meta.url).href;

export const getProviderIcon = function (provider: string) {
  if (provider == "spotify") return iconSpotify;
  if (provider == "qobuz") return iconQobuz;
  if (provider == "tunein") return iconTuneIn;
  return iconFilesystem;
};
export const getContentTypeIcon = function (contentType: ContentType) {
  if (contentType == ContentType.AAC) return iconAac;
  if (contentType == ContentType.FLAC) return iconFlac;
  if (contentType == ContentType.MP3) return iconMp3;
  if (contentType == ContentType.MPEG) return iconMp3;
  if (contentType == ContentType.OGG) return iconOgg;
  return iconFallback;
};
export const getQualityIcon = function (quality?: MediaQuality) {
  if (!quality) return iconFallback;
  if (quality == MediaQuality.LOSSY_AAC) return iconAac;
  if (quality == MediaQuality.LOSSY_MP3) return iconMp3;
  if (quality == MediaQuality.LOSSY_OGG) return iconOgg;
  if (quality >= MediaQuality.FLAC_LOSSLESS) return iconFlac;
  return iconFallback;
};
</script>

<style scoped>
.provider-icons {
  width: auto;
  vertical-align: middle;
  align-items: center;
  padding: 0px;
}
.provider-icon {
  float: inherit;
  padding-left: 5px;
  display: flex;
  margin: 5px;
}
</style>
