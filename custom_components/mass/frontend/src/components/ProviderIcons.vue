<template>
  <div class="provider-icons" :style="`height: ${height};`">
    <v-tooltip
      v-for="prov of uniqueProviders"
      :key="prov.prov_id"
      location="bottom"
    >
      <template #activator="{ props }">
        <img
          v-bind="props"
          :key="prov.prov_type"
          class="provider-icon"
          :height="height"
          :src="getProviderIcon(prov.prov_type)"
          :style="enableLink ? 'cursor: pointer' : ''"
          @click="enableLink ? provClicked(prov) : ''"
        />
      </template>
      <span>{{ $t('providers.' + prov.prov_type.toString()) }}</span>
    </v-tooltip>
  </div>
</template>

<script setup lang="ts">
import type { MediaItemProviderId } from '../plugins/api';
import { MediaQuality } from '../plugins/api';
import { computed } from 'vue';

export interface Props {
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
    const key = prov.prov_type;
    if (keys.indexOf(key) === -1) {
      keys.push(key);
      output.push(prov);
    }
  });
  return output.sort((a, b) => a.prov_type.localeCompare(b.prov_type));
});

const provClicked = function (prov: MediaItemProviderId) {
  window.open(prov.url, '_blank');
};
</script>

<script lang="ts">
import { ContentType, ProviderType } from '../plugins/api';

export const iconSpotify = new URL('../assets/spotify.png', import.meta.url)
  .href;
export const iconQobuz = new URL('../assets/qobuz.png', import.meta.url).href;
export const iconFilesystem = new URL(
  '../assets/filesystem.png',
  import.meta.url
).href;
export const iconTuneIn = new URL('../assets/tunein.png', import.meta.url).href;
export const iconYTMusic = new URL('../assets/ytmusic.png', import.meta.url)
  .href;
export const iconFallback = new URL('../assets/fallback.png', import.meta.url)
  .href;

export const iconAac = new URL('../assets/aac.png', import.meta.url).href;
export const iconFlac = new URL('../assets/flac.png', import.meta.url).href;
export const iconMp3 = new URL('../assets/mp3.png', import.meta.url).href;
export const iconOgg = new URL('../assets/ogg.png', import.meta.url).href;
export const iconVorbis = new URL('../assets/vorbis.png', import.meta.url).href;
export const iconM4a = new URL('../assets/m4a.png', import.meta.url).href;
export const iconHiRes = new URL('../assets/hires.png', import.meta.url).href;

export const getProviderIcon = function (provider: ProviderType) {
  if (provider == ProviderType.SPOTIFY) return iconSpotify;
  if (provider == ProviderType.QOBUZ) return iconQobuz;
  if (provider == ProviderType.TUNEIN) return iconTuneIn;
  if (provider == ProviderType.YTMUSIC) return iconYTMusic;
  return iconFilesystem;
};
export const getContentTypeIcon = function (contentType: ContentType) {
  if (contentType == ContentType.AAC) return iconAac;
  if (contentType == ContentType.FLAC) return iconFlac;
  if (contentType == ContentType.MP3) return iconMp3;
  if (contentType == ContentType.MPEG) return iconMp3;
  if (contentType == ContentType.OGG) return iconOgg;
  if (contentType == ContentType.M4A) return iconM4a;
  return iconFallback;
};
export const getQualityIcon = function (quality?: MediaQuality) {
  if (!quality) return iconFallback;
  if (quality == MediaQuality.LOSSY_AAC) return iconAac;
  if (quality == MediaQuality.LOSSY_MP3) return iconMp3;
  if (quality == MediaQuality.LOSSY_OGG) return iconOgg;
  if (quality == MediaQuality.LOSSY_M4A) return iconM4a;
  if (quality >= MediaQuality.LOSSLESS) return iconFlac;
  return iconFallback;
};

export const getQualityDesc = function (provDetails: MediaItemProviderId) {
  if (provDetails.details && !provDetails.details.includes('http')) {
    return provDetails.details;
  }
  if (!provDetails.quality) provDetails.quality = 0;
  if (provDetails.quality == MediaQuality.LOSSY_AAC) return 'Lossy aac';
  if (provDetails.quality == MediaQuality.LOSSY_MP3) return 'Lossy mp3';
  if (provDetails.quality == MediaQuality.LOSSY_OGG) return 'Lossy ogg';
  if (provDetails.quality == MediaQuality.LOSSY_M4A) return 'Lossy m4a';
  if (provDetails.quality > MediaQuality.LOSSLESS) return 'Lossless Hi-Res';
  if (provDetails.quality >= MediaQuality.LOSSLESS) return 'Lossless';
  return 'Unknown media quality ';
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
