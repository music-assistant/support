<template>
  <v-footer
    bottom
    fixed
    class="d-flex flex-column"
    style="width: 100%; border-top-style: ridge"
    elevation="5"
    app
  >
    <v-divider />
    <v-img
      class="bg-image"
      width="100%"
      cover
      :src="fanartImage"
      :gradient="
        $vuetify.theme.current.dark
          ? 'to bottom, rgba(0,0,0,.80), rgba(0,0,0,.75)'
          : 'to bottom, rgba(255,255,255,.85), rgba(255,255,255,.65)'
      "
      style="position: absolute; background-size: 100%; padding: 0; margin-top: -10px"
    />
    <!-- now playing media -->
    <div
      class="mediadetails"
      v-if="activePlayerQueue?.active && (curMediaItem || curQueueItem)"
    >
      <media-item-thumb
        class="mediadetails-thumb"
        :key="curMediaItem.item_id"
        :item="curMediaItem"
        :size="50"
        :min-width="50"
        :min-height="50"
        :width="50"
        :height="50"
        :cover="true"
        :border="true"
        v-if="curMediaItem"
      />

      <v-list-item two-line class="mediadetails-title" v-if="curMediaItem">
        <div>
          <v-list-item-title v-if="$vuetify.display.mobile">
            {{ truncateString(curMediaItem.name, 30) }}</v-list-item-title
          >
          <v-list-item-title v-else> {{ curMediaItem.name }}</v-list-item-title>
          <v-list-item-subtitle
            v-if="curMediaItem && 'artists' in curMediaItem && !$vuetify.display.mobile"
            style="margin-top: 5px; text-overflow: ellipsis; height: 30px;"
          >
            <span
              v-for="(artist, artistindex) in getTrackArtists(curMediaItem)"
              :key="artistindex"
            >
              <a @click="artistClick(artist)">{{ artist.name }}</a>
              <label
                v-if="artistindex + 1 < getTrackArtists(curMediaItem).length"
                :key="artistindex"
              >
                /
              </label>
            </span>
          </v-list-item-subtitle>
          <v-list-item-subtitle
            v-else-if="curMediaItem && 'artists' in curMediaItem"
            style="margin-top: 5px; text-overflow: ellipsis; height: 30px;"
          >
            <span
              v-for="(artist, artistindex) in getTrackArtists(curMediaItem).slice(0, 1)"
              :key="artistindex"
            >
              <a @click="artistClick(artist)">{{ artist.name }}</a>
            </span>
          </v-list-item-subtitle>
          <v-list-item-subtitle
            v-else-if="curQueueItem?.streamdetails?.stream_title"
            style="margin-top: 5px; text-overflow: ellipsis; height: 30px"
            >{{ curQueueItem?.streamdetails?.stream_title }}</v-list-item-subtitle
          >
          <v-list-item-subtitle
            v-else-if="curMediaItem.metadata.description"
            style="margin-top: 5px; text-overflow: ellipsis; height: 30px"
            >{{ curMediaItem.metadata.description }}</v-list-item-subtitle
          >
        </div>
      </v-list-item>
      <v-list-item two-line class="mediadetails-title" v-else-if="curQueueItem">
        <div>
          <v-list-item-title>{{ activePlayerQueue.name }}</v-list-item-title>
          <v-list-item-subtitle
            style="margin-top: 5px; text-overflow: ellipsis; height: 30px"
            >{{
              curQueueItem?.streamdetails?.stream_title || curQueueItem.name
            }}</v-list-item-subtitle
          >
        </div>
      </v-list-item>

      <!-- streaming quality details -->

      <v-menu location="bottom end" v-if="streamDetails">
        <template v-slot:activator="{ props }">
          <v-img
            contain
            :src="
              streamDetails.bit_depth > 16
                ? iconHiRes
                : getContentTypeIcon(streamDetails.content_type)
            "
            height="25"
            :style="$vuetify.theme.current.dark ? '' : 'filter: invert(100%)'"
            class="v-list-item-subtitle mediadetails-streamdetails"
            v-bind="props"
          />
        </template>
        <v-card class="mx-auto" width="300">
          <v-list style="overflow: hidden">
            <span class="text-h5" style="padding: 10px">{{ $t("stream_details") }}</span>
            <v-divider></v-divider>
            <v-list-item style="height: 50px; display: flex; align-items: center">
              <img
                height="30"
                width="50"
                center
                :src="getProviderIcon(streamDetails.provider)"
                style="object-fit: contain; margin-left: -15px"
              />
              {{ $t("providers." + streamDetails.provider) }}
            </v-list-item>

            <div style="height: 50px; display: flex; align-items: center">
              <img
                height="30"
                width="50"
                :src="getContentTypeIcon(streamDetails.content_type)"
                :style="
                  $vuetify.theme.current.dark
                    ? 'object-fit: contain;'
                    : 'object-fit: contain;filter: invert(100%);'
                "
              />
              {{ streamDetails.sample_rate / 1000 }} kHz /
              {{ streamDetails.bit_depth }} bits
            </div>

            <div
              style="height: 50px; display: flex; align-items: center"
              v-if="
                activePlayerQueue && activePlayerQueue.settings.crossfade_duration > 0
              "
            >
              <img
                height="30"
                width="50"
                contain
                :src="iconCrossfade"
                :style="
                  $vuetify.theme.current.dark
                    ? 'object-fit: contain;'
                    : 'object-fit: contain;filter: invert(100%);'
                "
              />
              {{ $t("crossfade_enabled") }}
            </div>

            <div
              style="height: 50px; display: flex; align-items: center"
              v-if="streamDetails.gain_correct"
            >
              <img
                height="30"
                width="50"
                contain
                :src="iconLevel"
                :style="
                  $vuetify.theme.current.dark
                    ? 'object-fit: contain;'
                    : 'object-fit: contain;filter: invert(100%);'
                "
              />
              {{ streamDetails.gain_correct }} dB
            </div>
          </v-list>
        </v-card>
      </v-menu>

      <!-- time details -->
      <div
        v-if="
          !$vuetify.display.mobile &&
          streamDetails &&
          curMediaItem?.media_type !== MediaType.RADIO
        "
        class="mediadetails-time text-caption"
      >
        {{ playerCurTimeStr }} / {{ playerTotalTimeStr }}
      </div>
    </div>

    <!-- progress bar -->
    <div
      style="width: 100%; height: 5px; padding-bottom: 15px; margin-top: -5px"
      v-if="
        activePlayerQueue?.active &&
        curQueueItem &&
        curQueueItem.media_type != MediaType.RADIO
      "
    >
      <v-slider
        v-bind:model-value="curQueueItemTime"
        height="3"
        color="primary"
        :min="0"
        :max="curQueueItem.duration"
        :thumb-size="10"
        @update:model-value="
          api.queueCommandSeek(activePlayerQueue?.queue_id, Math.round($event))
        "
        style="margin-left: 0; margin-right: 0"
      />
    </div>

    <!-- Control buttons -->
    <div class="mediacontrols">
      <!-- left side: playback buttons -->
      <div class="mediacontrols-left" v-if="activePlayerQueue && activePlayerQueue.available">
        <!-- prev track -->
        <v-btn
          small
          icon
          variant="plain"
          :disabled="!activePlayerQueue || !activePlayerQueue?.active || activePlayerQueue?.items == 0"
          @click="api.queueCommandPrevious(activePlayerQueue?.queue_id)"
        >
          <v-icon :icon="mdiSkipPrevious" />
        </v-btn>
        <!-- play/pause button: only when MA queue is active -->
        <v-btn
          icon
          x-large
          variant="plain"
          v-if="activePlayerQueue && activePlayerQueue?.active"
          :disabled="activePlayerQueue && activePlayerQueue?.items == 0"
          @click="api.queueCommandPlayPause(activePlayerQueue?.queue_id)"
        >
          <v-icon size="50">{{
            activePlayerQueue?.state == "playing" ? mdiPause : mdiPlay
          }}</v-icon>
        </v-btn>
        <!-- stop button: player is playing other source (not MA)-->
        <v-btn
          icon
          x-large
          variant="plain"
          v-else-if="store.selectedPlayer?.state == PlayerState.PLAYING"
          @click="api.queueCommandStop(activePlayerQueue?.queue_id)"
        >
          <v-icon size="50">{{ mdiStop }}</v-icon>
        </v-btn>
        <!-- play button: all other situations - resume the queue (disabled if queue is empty)-->
        <v-btn
          icon
          x-large
          variant="plain"
          v-else
          :disabled="activePlayerQueue && activePlayerQueue?.items == 0"
          @click="api.queueCommandPlay(activePlayerQueue?.queue_id)"
        >
          <v-icon size="50">{{ mdiPlay }}</v-icon>
        </v-btn>
        <v-btn
          icon
          small
          variant="plain"
          :disabled="!activePlayerQueue || !activePlayerQueue?.active || activePlayerQueue?.items == 0"
          @click="api.queueCommandNext(activePlayerQueue?.queue_id)"
        >
          <v-icon :icon="mdiSkipNext" />
        </v-btn>
      </div>

      <!-- active player btn -->
      <v-btn
        icon
        variant="plain"
        @click="store.showPlayersMenu = true"
        class="mediacontrols-right"
        height="50"
        width="70"
      >
        <v-icon :icon="mdiSpeaker" />
        <div v-if="activePlayerQueue">{{ activePlayerQueue.name }}</div>
      </v-btn>
      <!-- active player volume -->
      <div v-if="!$vuetify.display.mobile && activePlayerQueue">
        <v-menu location="bottom end" :close-on-content-click="false">
          <template v-slot:activator="{ props }">
            <v-btn
              icon
              variant="plain"
              v-bind="props"
              class="mediacontrols-right"
              height="50"
              width="70"
            >
              <v-icon :icon="mdiVolumeHigh" />
              <div>
                {{ Math.round(api.players[activePlayerQueue?.player]?.volume_level) }}
              </div>
            </v-btn>
          </template>
          <VolumeControl :player="api.players[activePlayerQueue?.queue_id]" />
        </v-menu>
      </div>
      <!-- active player queue button -->
      <v-btn
        text
        icon
        variant="plain"
        height="50"
        width="70"
        @click="$router.push('/playerqueue/')"
        v-if="activePlayerQueue"
        class="mediacontrols-right"
      >
        <v-icon :icon="mdiPlaylistMusic" />
        <div>{{ $t("queue") }}</div>
      </v-btn>
    </div>
  </v-footer>
</template>

<script setup lang="ts">
/* eslint-disable @typescript-eslint/no-unused-vars,vue/no-setup-props-destructure */
import {
  mdiSpeaker,
  mdiSpeakerMultiple,
  mdiSkipNext,
  mdiSkipPrevious,
  mdiVolumeHigh,
  mdiPlaylistMusic,
  mdiPlay,
  mdiPause,
  mdiStop,
} from "@mdi/js";

import { watchEffect, ref, computed, watch } from "vue";
import { useDisplay, useTheme } from "vuetify";
import type {
  Artist,
  PlayerQueue,
  QueueItem,
  StreamDetails,
  MediaItemType,
  MusicAssistantApi,
  ItemMapping,
  Track,
  Radio,
  Player,
} from "../plugins/api";
import { api, PlayerState, ContentType, MediaType, ImageType } from "../plugins/api";
import { store } from "../plugins/store";
import VolumeControl from "./VolumeControl.vue";
import MediaItemThumb, { getImageThumbForItem } from "./MediaItemThumb.vue";
import { formatDuration, truncateString } from "../utils";
import { useRouter } from "vue-router";
import { getContentTypeIcon, iconHiRes, getProviderIcon } from "./ProviderIcons.vue";

const iconCrossfade = new URL("../assets/crossfade.png", import.meta.url).href;
const iconLevel = new URL("../assets/level.png", import.meta.url).href;

const router = useRouter();
const display = useDisplay();
const theme = useTheme();

// local refs
const showStreamDetails = ref(false);
const curMediaItem = ref<Track | Radio>();
const fanartImage = ref();

// computed properties
const activePlayerQueue = computed(() => {
  if (store.selectedPlayer) {
    return api.queues[store.selectedPlayer.active_queue];
  }
  return undefined;
});
const curQueueItem = computed(() => {
  if (activePlayerQueue.value) return activePlayerQueue.value.current_item;
  return undefined;
});
const playerCurTimeStr = computed(() => {
  if (!curQueueItem.value) return "0:00";
  return formatDuration(curQueueItemTime.value);
});
const playerTotalTimeStr = computed(() => {
  if (!curQueueItem.value) return "0:00";
  const totalSecs = curQueueItem.value.duration;
  return formatDuration(totalSecs);
});
const streamDetails = computed(() => {
  return activePlayerQueue.value?.current_item?.streamdetails;
});
const curQueueItemTime = computed(() => {
  if (activePlayerQueue.value) return activePlayerQueue.value.elapsed_time;
  return 0;
});

// methods
const artistClick = function (item: Artist | ItemMapping) {
  router.push({
    name: "artist",
    params: { item_id: item.item_id, provider: item.provider },
  });
};
const getTrackArtists = function (item: Track) {
  if (display.mobile.value) return item.artists.slice(0, 2);
  return item.artists;
};

// watchers
watchEffect(async () => {
  if (curQueueItem.value == undefined) {
    curMediaItem.value = undefined;
  } else if (
    curQueueItem.value.media_item &&
    curQueueItem.value.media_item.provider == "database"
  ) {
    curMediaItem.value = await api?.getItem(curQueueItem.value.uri);
  } else {
    curMediaItem.value = curQueueItem.value.media_item;
  }
  if (curMediaItem.value) {
    fanartImage.value =
      (await getImageThumbForItem(curMediaItem.value, ImageType.FANART)) ||
      (await getImageThumbForItem(curMediaItem.value, ImageType.THUMB));
  }
});

watch(
  () => store.selectedPlayer,
  (newVal) => {
    if (newVal) localStorage.setItem("mass.LastPlayerId", newVal.player_id);
  }
);

watchEffect(async () => {
  // pick default/start player at startup
  const lastPlayerId = localStorage.getItem("mass.LastPlayerId");
  if (lastPlayerId) {
    if (lastPlayerId in api.players) {
      store.selectedPlayer = api.players[lastPlayerId];
      return;
    }
  }
  if (api?.players && !store.selectedPlayer) {
    // prefer playing player
    for (const playerId in api?.players) {
      const player = api.players[playerId];
      if (player.state == PlayerState.PLAYING) {
        store.selectedPlayer = player;
        return;
      }
    }
    // fallback to just a player with item in queue
    for (const playerId in api?.queues) {
      const player = api.players[playerId];
      if (player.elapsed_time) {
        store.selectedPlayer = player;
        return;
      }
    }
    // last resort: just the first queue
    for (const playerId in api?.queues) {
      store.selectedPlayer = api.players[playerId];
      return;
    }
  }
});
</script>

<style scoped>
.bg-image {
  /* Add the blur effect */
  filter: blur(20px);
  -webkit-filter: blur(20px);
  /* Center and scale the image nicely */
  background-position: center;
  background-size: cover;
}

.mediadetails {
  display: inline-block;
  width: 100%;
  height: 55px;
  margin-top: 0px;
  margin-left: 0px;
  margin-bottom: 6px;
  padding-top: 5px;
}

.mediadetails-thumb {
  width: 50px;
  float: left;
  height: 50px;
}
.mediadetails-title {
  width: auto;
  padding-left: 10px;
  padding-top: 0px;
  float: left;
}

.mediadetails-time {
  float: right;
  width: auto;
  margin-top: 30px;

  position: absolute;
  right: 15px;
}
.mediadetails-streamdetails {
  float: right;
  width: 40px;
  right: 10px;
  margin-top: -2px;
  position: absolute;
  cursor: pointer;
}

.mediadetails-streamdetails .icon {
  opacity: 100;
}

.mediacontrols {
  display: inline-block;
  width: 100%;
  height: 55px;
  margin-top: 5px;
  margin-left: 0px;
  padding-bottom: 5px;
}
.mediacontrols-left {
  width: auto;
  margin-left: -15px;
  padding-top: 0px;
  float: left;
}
.mediacontrols-right {
  float: right;
  padding-left: 10px;
  padding-right: 0px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.mediacontrols-right div {
  width: 80px;
  font-size: xx-small;
  padding-top: 5px;
  text-overflow: ellipsis;

  /* Required for text-overflow to do anything */
  white-space: nowrap;
  overflow: hidden;
}
</style>
