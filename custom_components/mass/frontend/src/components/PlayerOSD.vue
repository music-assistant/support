<template>
  <v-footer
    bottom
    fixed
    class="d-flex flex-column"
    style="width: 100%; border-top-style: ridge"
    elevation="5"
  >
    <v-divider />
    <v-img
      class="bg-image"
      width="100%"
      cover
      :src="api.getFanartUrl(curMediaItem)"
      :gradient="
        $vuetify.theme.current == 'dark'
          ? 'to bottom, rgba(0,0,0,.80), rgba(0,0,0,.75)'
          : 'to bottom, rgba(255,255,255,.85), rgba(255,255,255,.65)'
      "
      style="position: absolute; background-size: 100%; padding: 0; margin-top: -10px"
    />
    <!-- now playing media -->
    <div class="mediadetails">
      <v-list-item-avatar tile class="mediadetails-thumb">
        <media-item-thumb
          :key="curMediaItem.item_id"
          :item="curMediaItem"
          :size="50"
          v-if="curMediaItem"
          style="width: 50px; border: 1px solid rgba(0, 0, 0, 0.54)"
        />
        <v-icon v-else :icon="mdiSpeaker" />
      </v-list-item-avatar>
      <v-list-item two-line class="mediadetails-title">
        <v-list-item-avatar> </v-list-item-avatar>
        <div>
          <v-list-item-title v-if="curMediaItem">
            {{ curMediaItem.name }}</v-list-item-title
          >
          <v-list-item-title v-else-if="store.activePlayerQueue">
            {{ store.activePlayerQueue.name }}</v-list-item-title
          >
          <v-list-item-subtitle
            v-if="curMediaItem && 'artists' in curMediaItem"
            style="margin-top: 5px; text-overflow: ellipsis; height: 30px"
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
        </div>
      </v-list-item>

      <!-- streaming quality details -->

      <v-menu anchor="bottom end" v-if="streamDetails">
        <template v-slot:activator="{ props }">
          <v-btn
            icon
            x-small
            variant="plain"
            v-bind="props"
            class="mediadetails-streamdetails"
          >
            <v-img
              v-if="streamDetails.bit_depth > 16"
              contain
              :src="iconHiRes"
              height="25"
              :style="$vuetify.theme.current == 'light' ? 'filter: invert(100%)' : ''"
            />
            <v-img
              v-if="streamDetails.bit_depth <= 16"
              contain
              :src="getContentTypeIcon(streamDetails.content_type)"
              height="25"
              :style="$vuetify.theme.current == 'light' ? 'filter: invert(100%)' : ''"
            />
          </v-btn>
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
                style="object-fit: contain"
              />
              {{ streamDetails.provider }}
            </v-list-item>

            <div style="height: 50px; display: flex; align-items: center">
              <img
                height="30"
                width="50"
                :src="getContentTypeIcon(streamDetails.content_type)"
                :style="
                  $vuetify.theme.current == 'light'
                    ? 'object-fit: contain;filter: invert(100%);'
                    : 'object-fit: contain;'
                "
              />
              {{ streamDetails.sample_rate / 1000 }} kHz /
              {{ streamDetails.bit_depth }} bits
            </div>

            <div
              style="height: 50px; display: flex; align-items: center"
              v-if="
                store.activePlayerQueue && store.activePlayerQueue.crossfade_duration > 0
              "
            >
              <img
                height="30"
                width="50"
                contain
                :src="iconCrossfade"
                :style="
                  $vuetify.theme.current == 'light'
                    ? 'object-fit: contain;filter: invert(100%);'
                    : 'object-fit: contain;'
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
                  $vuetify.theme.current == 'light'
                    ? 'object-fit: contain;filter: invert(100%);'
                    : 'object-fit: contain;'
                "
              />
              {{ streamDetails.gain_correct }} dB
            </div>
          </v-list>
        </v-card>
      </v-menu>

      <!-- time details -->
      <div v-if="!$vuetify.display.mobile" class="mediadetails-time text-caption">
        {{ playerCurTimeStr }} / {{ playerTotalTimeStr }}
      </div>
    </div>

    <!-- progress bar -->
    <div style="width: 100%; height: 5px">
      <v-progress-linear v-bind:model-value="progress" height="3" color="primary" />
    </div>

    <!-- Control buttons -->
    <div class="mediacontrols">
      <!-- left side: playback buttons -->
      <div class="mediacontrols-left">
        <v-btn
          small
          icon
          variant="plain"
          :disabled="!store.activePlayerQueue"
          @click="api.queueCommandPrevious(store.activePlayerQueue?.queue_id)"
        >
          <v-icon :icon="mdiSkipPrevious" />
        </v-btn>
        <v-btn
          icon
          x-large
          variant="plain"
          :disabled="!store.activePlayerQueue"
          @click="api.queueCommandPlayPause(store.activePlayerQueue.queue_id)"
        >
          <v-icon size="50">{{
            store.activePlayerQueue?.state == "playing" ? mdiPause : mdiPlay
          }}</v-icon>
        </v-btn>
        <v-btn
          icon
          small
          variant="plain"
          :disabled="!store.activePlayerQueue"
          @click="api.queueCommandNext(store.activePlayerQueue?.queue_id)"
        >
          <v-icon :icon="mdiSkipNext" />
        </v-btn>
      </div>

      <!-- active player btn -->
      <v-btn
        text
        large
        variant="plain"
        @click="store.showPlayersMenu = true"
        class="mediacontrols-right"
        height="50"
        width="70"
      >
        <v-icon :icon="mdiSpeaker" />
        <span v-if="store.activePlayerQueue">{{ store.activePlayerQueue.name }}</span>
        <span v-else class="text-caption"> </span>
      </v-btn>
      <!-- active player volume -->
      <div v-if="!$vuetify.display.mobile">
        <v-menu anchor="bottom end">
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
              <span>{{
                Math.round(api.players[store.activePlayerQueue?.player]?.volume_level)
              }}</span>
            </v-btn>
          </template>
          <VolumeControl :player="api.players[store.activePlayerQueue?.queue_id]" />
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
        v-if="store.activePlayerQueue"
        class="mediacontrols-right"
      >
        <v-icon :icon="mdiPlaylistMusic" />
        <span>{{ $t("queue") }}</span>
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
} from "@mdi/js";
const iconCrossfade = new URL("../assets/crossfade.png", import.meta.url).href;
const iconLevel = new URL("../assets/level.png", import.meta.url).href;
import { watchEffect, ref, computed } from "vue";
import { useDisplay } from "vuetify";
import type {
  Artist,
  PlayerQueue,
  QueueItem,
  StreamDetails,
  MediaItemType,
  MusicAssistantApi,
  ItemMapping,
  Track,
} from "../plugins/api";
import { api, PlayerState, ContentType } from "../plugins/api";
import { store } from "../plugins/store";
import VolumeControl from "./VolumeControl.vue";
import MediaItemThumb from "./MediaItemThumb.vue";
import { formatDuration, truncateString } from "../utils";
import { useRouter } from "vue-router";
import { getContentTypeIcon, iconHiRes, getProviderIcon } from "./ProviderIcons.vue";

const router = useRouter();
const display = useDisplay();

// local refs
const curMediaItem = ref<MediaItemType>();
const showStreamDetails = ref(false);

// computed properties
const curQueueItem = computed(() => {
  if (store.activePlayerQueue) return store.activePlayerQueue.current_item;
  return undefined;
});
const progress = computed(() => {
  if (!curQueueItem.value) return 0;
  const totalSecs: number = curQueueItem.value.duration;
  const curPercent = (curQueueItemTime.value / totalSecs) * 100;
  return curPercent;
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
const progressBarWidth = computed(() => {
  return window.innerWidth - 45;
});
const streamDetails = computed(() => {
  return store.activePlayerQueue?.current_item?.streamdetails;
});
const curQueueItemTime = computed(() => {
  if (store.activePlayerQueue) return store.activePlayerQueue.elapsed_time;
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
  } else {
    curMediaItem.value = await api?.getItem(curQueueItem.value.uri);
  }
});

watchEffect(async () => {
  // pick default/start queue at startup
  if (api?.queues && !store.activePlayerQueue) {
    // prefer playing player
    for (const queue_id in api?.queues) {
      const queue = api.queues[queue_id];
      if (queue.current_item && queue.state == PlayerState.PLAYING) {
        store.activePlayerQueue = queue;
        return;
      }
    }
    // fallback to just a player with item in queue
    for (const queue_id in api?.queues) {
      const queue = api.queues[queue_id];
      if (queue.current_item) {
        store.activePlayerQueue = queue;
        return;
      }
    }
    // last resort: just the first queue
    for (const queue_id in api?.queues) {
      store.activePlayerQueue = api.queues[queue_id];
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
  width: auto;
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
  margin-top: -10px;
  position: absolute;
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

.mediacontrols-right span {
  width: 80px;
  font-size: xx-small;
  padding-top: 5px;
  text-overflow: ellipsis;

  /* Required for text-overflow to do anything */
  white-space: nowrap;
  overflow: hidden;
}
</style>
