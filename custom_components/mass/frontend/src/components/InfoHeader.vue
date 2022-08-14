<template>
  <div>
    <v-card
      flat
      :img="imgGradient"
      style="margin-top: -10px; z-index: 0"
      height="30vh"
      max-height="500px"
      min-height="340px"
    >
      <!-- loading animation -->
      <v-progress-linear v-if="!item" indeterminate />
      <v-img
        width="100%"
        height="100%"
        cover
        class="background-image"
        :src="fanartImage"
        :gradient="
          store.darkTheme
            ? 'to bottom, rgba(0,0,0,.90), rgba(0,0,0,.75)'
            : 'to bottom, rgba(255,255,255,.90), rgba(255,255,255,.75)'
        "
      />
      <v-layout
        v-if="item"
        style="
          margin: 0;
          position: absolute;
          top: 50%;
          -ms-transform: translateY(-50%);
          transform: translateY(-50%);
          padding-left: 15px;
          align-items: center;
          padding-right: 15px;
        "
      >
        <!-- left side: cover image -->
        <div v-if="!$vuetify.display.mobile" xs5 pa-5>
          <div v-if="'artists' in item && item.media_type">
            <MediaItemThumb
              :item="item"
              :minSize="192"
              style="margin-top: 15px; margin-bottom: 15px; margin-right: 24px"
            />
          </div>
          <div v-else-if="'owner' in item && item.media_type">
            <MediaItemThumb
              :item="item"
              :minSize="192"
              style="margin-top: 15px; margin-bottom: 15px; margin-right: 24px"
            />
          </div>
          <div v-else>
            <MediaItemThumb
              :item="item"
              :tile="false"
              :minSize="192"
              style="margin-top: 15px; margin-bottom: 15px; margin-right: 24px"
            />
          </div>
        </div>

        <div>
          <!-- Main title -->
          <v-card-title>
            {{ item.name }}
          </v-card-title>

          <!-- other details -->
          <div style="padding-bottom: 10px">
            <!-- version -->
            <v-card-subtitle
              v-if="'version' in item && item.version"
              class="caption"
            >
              {{ item.version }}
            </v-card-subtitle>

            <!-- item artists -->
            <v-card-subtitle
              v-if="'artists' in item && item.artists"
              class="title accent--text"
            >
              <v-icon
                style="margin-left: -3px; margin-right: 3px"
                small
                color="primary"
                :icon="mdiAccountMusic"
              />
              <span
                v-for="(artist, artistindex) in item.artists"
                :key="artist.item_id"
              >
                <a style="color: accent" @click="artistClick(artist)">{{
                  artist.name
                }}</a>
                <span
                  v-if="artistindex + 1 < item.artists.length"
                  :key="artistindex"
                  style="color: accent"
                  >{{ ' / ' }}</span
                >
              </span>
            </v-card-subtitle>

            <!-- album artist -->
            <v-card-subtitle
              v-if="'artist' in item && item.artist"
              class="title"
            >
              <v-icon
                style="margin-left: -3px; margin-right: 3px"
                small
                color="primary"
                :icon="mdiAccountMusic"
              />
              <a @click="artistClick(item.artist)">{{ item.artist.name }}</a>
            </v-card-subtitle>

            <!-- playlist owner -->
            <v-card-subtitle v-if="'owner' in item && item.owner" class="title">
              <v-icon
                color="primary"
                style="margin-left: -3px; margin-right: 3px"
                small
                :icon="mdiAccountMusic"
              />
              <a style="color: primary">{{ item.owner }}</a>
            </v-card-subtitle>

            <v-card-subtitle v-if="'album' in item && item.album">
              <v-icon
                color="primary"
                style="margin-left: -3px; margin-right: 3px"
                small
                :icon="mdiAlbum"
              />
              <a style="color: secondary" @click="albumClick(item.album)">{{
                item.album.name
              }}</a>
            </v-card-subtitle>
          </div>

          <!-- play/info buttons -->
          <div style="display: flex; margin-left: 14px; padding-bottom: 10px">
            <v-menu location="bottom">
              <template #activator="{ props }">
                <v-btn
                  color="primary"
                  v-bind="props"
                  :prepend-icon="mdiPlayCircle"
                  :disabled="
                    !store.selectedPlayer?.available ||
                    store.blockGlobalPlayMenu
                  "
                >
                  {{ $t('play') }}
                </v-btn>
              </template>

              <v-card min-width="300">
                <v-list lines="one" density="comfortable">
                  <!-- play now -->
                  <v-list-item
                    v-for="menuItem in getPlayMenuItems([item])"
                    :key="menuItem.label"
                    :title="$t(menuItem.label, menuItem.labelArgs)"
                    @click="menuItem.action ? menuItem.action() : ''"
                  >
                    <template #prepend>
                      <v-avatar style="padding-right: 10px">
                        <v-icon :icon="menuItem.icon" />
                      </v-avatar>
                    </template>
                  </v-list-item>
                </v-list>
              </v-card>
            </v-menu>

            <v-btn
              v-if="!$vuetify.display.mobile && !item.in_library"
              style="margin-left: 10px"
              color="primary"
              tile
              :prepend-icon="mdiHeartOutline"
              @click="api.addToLibrary([item])"
            >
              {{ $t('add_library') }}
            </v-btn>
            <v-btn
              v-if="!$vuetify.display.mobile && item.in_library"
              style="margin-left: 10px"
              color="primary"
              tile
              :prepend-icon="mdiHeart"
              @click="api.removeFromLibrary([item])"
            >
              {{ $t('remove_library') }}
            </v-btn>
          </div>

          <!-- Description/metadata -->
          <v-card-subtitle
            v-if="description"
            class="body-2 justify-left"
            style="padding-bottom: 10px; white-space: pre-line; cursor: pointer"
            @click="showFullInfo = !showFullInfo"
            v-html="description"
          />

          <!-- genres/tags -->
          <div
            v-if="item && item.metadata.genres"
            class="justify-center"
            style="margin-left: 15px; padding-bottom: 20px"
          >
            <v-chip
              v-for="tag of item.metadata.genres"
              :key="tag"
              color="blue-grey lighten-1"
              style="margin-right: 5px; margin-bottom: 5px"
              small
              outlined
            >
              {{ tag }}
            </v-chip>
          </div>
        </div>
      </v-layout>
      <v-layout
        v-if="item"
        style="z-index: 800; height: 100%; padding-left: 15px"
      >
        <!-- provider icons -->
        <div style="position: absolute; float: right; right: 15px; top: 15px">
          <ProviderIcons
            :provider-ids="item.provider_ids"
            :height="25"
            :enable-link="true"
          />
        </div>
      </v-layout>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import ProviderIcons from './ProviderIcons.vue';
import {
  mdiHeart,
  mdiHeartOutline,
  mdiAccountMusic,
  mdiAlbum,
  mdiPlayCircle,
} from '@mdi/js';

import { store } from '../plugins/store';
import { useDisplay } from 'vuetify';
import { api } from '../plugins/api';
import { ImageType } from '../plugins/api';
import type { Album, Artist, ItemMapping, MediaItemType } from '../plugins/api';
import { computed, ref, watchEffect, onBeforeUnmount } from 'vue';
import MediaItemThumb from './MediaItemThumb.vue';
import { getImageThumbForItem } from './MediaItemThumb.vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { truncateString } from '@/utils';
import {
  getPlayMenuItems,
  getContextMenuItems,
} from './MediaItemContextMenu.vue';

// properties
export interface Props {
  item?: MediaItemType;
}
const props = defineProps<Props>();
const showFullInfo = ref(false);
const fanartImage = ref();
const { mobile } = useDisplay();

const imgGradient = new URL('../assets/info_gradient.jpg', import.meta.url)
  .href;

const { t } = useI18n();
const router = useRouter();

const activePlayerQueue = computed(() => {
  if (store.selectedPlayer) {
    return api.queues[store.selectedPlayer.active_queue];
  }
  return undefined;
});

watchEffect(async () => {
  if (props.item) {
    if (mobile.value) {
      store.topBarTitle = truncateString(props.item.name, 30);
    } else {
      store.topBarTitle =
        '<span style="opacity:0.5">' +
        t(props.item.media_type + 's') +
        ` | </span>${props.item.name}`;
    }

    fanartImage.value =
      (await getImageThumbForItem(props.item, ImageType.FANART)) ||
      (await getImageThumbForItem(props.item, ImageType.THUMB));

    store.topBarContextMenuItems = getContextMenuItems(
      [props.item],
      props.item
    );
  }
});

onBeforeUnmount(() => {
  store.topBarContextMenuItems = [];
});

const albumClick = function (item: Album | ItemMapping) {
  // album entry clicked
  router.push({
    name: 'album',
    params: {
      item_id: item.item_id,
      provider: item.provider,
    },
  });
};
const artistClick = function (item: Artist | ItemMapping) {
  // album entry clicked
  router.push({
    name: 'artist',
    params: {
      item_id: item.item_id,
      provider: item.provider,
    },
  });
};
const description = computed(() => {
  let desc = '';
  if (!props.item) return '';
  if (props.item.metadata && props.item.metadata.description) {
    desc = props.item.metadata.description;
  } else if (props.item.metadata && props.item.metadata.copyright) {
    desc = props.item.metadata.copyright;
  } else if ('artists' in props.item) {
    props.item.artists.forEach(function (artist: Artist | ItemMapping) {
      if ('metadata' in artist && artist.metadata.description) {
        desc = artist.metadata.description;
      }
    });
  }
  const maxChars = mobile.value ? 160 : 260;
  desc = desc.replace('\r\n', '<br /><br /><br />');
  desc = desc.replace('\r', '<br /><br />');
  desc = desc.replace('\n', '<br /><br />');
  if (showFullInfo.value) return desc;
  if (desc.length > maxChars) {
    return desc.substring(0, maxChars) + '...';
  }
  return desc;
});
</script>

<style>
.background-image {
  position: absolute;
}

.background-image .v-img__img--cover {
  object-position: 50% 20%;
}
</style>
