<template>
  <v-footer app fixed padless :height="$store.state.isInStandaloneMode ? '180' : '150'" :style="
    $vuetify.theme.dark
      ? 'box-shadow: 0px 5px 3px 6px rgba(180, 180, 180, 0.75);'
      : 'box-shadow: 0px 5px 3px 7px rgba(30, 30, 30, 0.75);'
  ">
    <v-img class="bg-image" :height="$store.state.isInStandaloneMode ? '180' : '150'" width="100%" position="center"
      :src="getFanart(curQueueItem)" :gradient="
        $vuetify.theme.dark
          ? 'to bottom, rgba(0,0,0,.80), rgba(0,0,0,.75)'
          : 'to bottom, rgba(255,255,255,.80), rgba(255,255,255,.75)'
      " style="position:absolute;margin-left-20px;margin-right:-20px" />
    <!-- now playing media -->
    <v-list-item two-line>
      <v-list-item-avatar v-if="curQueueItem" tile>
        <MediaItemThumb :key="curQueueItem.item_id" :item="curQueueItem" :size="80"
          style="margin-left: 0px; border: 1px solid rgba(0, 0, 0, 0.54)" />
      </v-list-item-avatar>
      <v-list-item-avatar v-else>
        <v-icon>speaker</v-icon>
      </v-list-item-avatar>

      <v-list-item-content>
        <v-list-item-title v-if="curQueueItem">
          {{ curQueueItem.name }}</v-list-item-title>
        <v-list-item-title v-else-if="selectedPlayer">
          {{ selectedPlayer.name }}</v-list-item-title>
        <v-list-item-subtitle v-if="curQueueItem && curQueueItem.artists" style="color: primary">
          <span v-for="(artist, artistindex) in curQueueItem.artists" :key="artistindex">
            <a @click="artistClick(artist)" @click.stop="">{{ artist.name }}</a>
            <label v-if="artistindex + 1 < curQueueItem.artists.length" :key="artistindex">
              /
            </label>
          </span>
        </v-list-item-subtitle>
      </v-list-item-content>
      <!-- streaming quality details -->
      <v-list-item-action v-if="streamDetails">
        <v-menu :close-on-content-click="false" :nudge-width="250" offset-x top @click.native.prevent>
          <template #activator="{ on }">
            <v-btn icon style="margin-right: -10px; margin-top: -20px" x-small v-on="on">
              <v-img v-if="streamDetails.bit_depth > 16" contain :src="require('../assets/hires.png')" height="25"
                :style="
                  $vuetify.theme.dark
                    ? 'filter: invert(100%);margin-right:10px'
                    : 'margin-right:10px'
                " />
              <v-img v-if="streamDetails.bit_depth <= 16" contain :src="
                streamDetails.content_type
                  ? require('../assets/' +
                    streamDetails.content_type +
                    '.png')
                  : ''
              " height="25" :style="
  !$vuetify.theme.dark
    ? 'filter: invert(100%);margin-right:10px'
    : 'margin-right:10px'
" />
            </v-btn>
          </template>
          <v-list v-if="streamDetails">
            <v-subheader class="title">{{ $t("stream_details") }}</v-subheader>
            <v-list-item tile dense>
              <v-list-item-icon>
                <v-img max-width="50" contain :src="getProviderIcon(streamDetails.provider)" />
              </v-list-item-icon>
              <v-list-item-content>
                <v-list-item-title style="text-transform: capitalize">{{
                  streamDetails.provider
                }}</v-list-item-title>
              </v-list-item-content>
            </v-list-item>
            <v-divider></v-divider>
            <v-list-item tile dense>
              <v-list-item-icon>
                <v-img max-width="50" contain :src="
                  streamDetails.content_type
                    ? require('../assets/' +
                      streamDetails.content_type +
                      '.png')
                    : ''
                " :style="$vuetify.theme.dark ? 'filter: invert(100%);' : ''" />
              </v-list-item-icon>
              <v-list-item-content>
                <v-list-item-title>{{ streamDetails.sample_rate / 1000 }} kHz /
                  {{ streamDetails.bit_depth }} bits
                </v-list-item-title>
              </v-list-item-content>
            </v-list-item>
            <v-divider></v-divider>
            <div v-if="
              selectedPlayerQueue && selectedPlayerQueue.crossfade_enabled
            ">
              <v-list-item tile dense>
                <v-list-item-icon>
                  <v-img max-width="50" contain :src="require('../assets/crossfade.png')" />
                </v-list-item-icon>
                <v-list-item-content>
                  <v-list-item-title>{{
                    $t("crossfade_enabled")
                  }}</v-list-item-title>
                </v-list-item-content>
              </v-list-item>
              <v-divider></v-divider>
            </div>
            <div v-if="streamDetails.gain_correct">
              <v-list-item tile dense>
                <v-list-item-icon>
                  <v-icon style="margin-left: 13px">volume_up</v-icon>
                </v-list-item-icon>
                <v-list-item-content>
                  <v-list-item-title style="margin-left: 12px">{{ streamDetails.gain_correct }} dB</v-list-item-title>
                </v-list-item-content>
              </v-list-item>
              <v-divider></v-divider>
            </div>
          </v-list>
        </v-menu>
      </v-list-item-action>
    </v-list-item>

    <!-- progress bar and time details -->
    <span v-if="!$store.state.isMobile" class="right caption" style="
        position: absolute;
        width: 80px;
        color: grey;
        right: 15px;
        margin-top: -30px;
      ">{{ playerCurTimeStr }} / {{ playerTotalTimeStr }}</span>
    <div :style="`height:10px;margin-left:15px;margin-right:15px;width:${progressBarWidth}px;`">
      <v-progress-linear :value="progress" height="3" :style="'width:' + progressBarWidth + 'px;'" />
    </div>

    <!-- Control buttons -->
    <v-list-item dense style="
        height: 62px;
        margin-bottom: 5px;
        margin-top: -4px;
        background-color: transparent;
      ">
      <v-list-item-action v-if="selectedPlayer" style="margin-top: 15px">
        <v-btn small icon @click="$api.playerCommandPrevious(selectedPlayerId)">
          <v-icon>skip_previous</v-icon>
        </v-btn>
      </v-list-item-action>
      <v-list-item-action v-if="selectedPlayer" style="margin-left: -32px; margin-top: 15px">
        <v-btn icon x-large @click="$api.playerCommandPlayPause(selectedPlayerId)">
          <v-icon size="50">{{
            selectedPlayer.state == "playing" ? "pause" : "play_arrow"
          }}</v-icon>
        </v-btn>
      </v-list-item-action>
      <v-list-item-action v-if="selectedPlayer" style="margin-top: 15px">
        <v-btn icon small @click="$api.playerCommandNext(selectedPlayerId)">
          <v-icon>skip_next</v-icon>
        </v-btn>
      </v-list-item-action>
      <!-- player controls -->
      <v-list-item-content> </v-list-item-content>

      <!-- active player queue button -->
      <v-list-item-action v-if="selectedPlayer" style="padding: 16px">
        <v-btn text icon @click="$router.push('/playerqueue/')">
          <v-flex xs12 class="vertical-btn">
            <v-icon>queue_music</v-icon>
            <span class="caption" style="padding-top: 5px">{{
              $t("queue")
            }}</span>
          </v-flex>
        </v-btn>
      </v-list-item-action>

      <!-- active player volume -->
      <v-list-item-action v-if="selectedPlayer && !$store.state.isMobile" style="padding-left: 25px">
        <v-dialog :transition="false" overlay-opacity="0.1">
          <template #activator="{ on, attrs }">
            <v-btn icon v-bind="attrs" v-on="on">
              <v-flex xs12 class="vertical-btn">
                <v-icon>volume_up</v-icon>
                <span class="caption" style="padding-top: 5px">{{
                  Math.round(selectedPlayer.volume_level)
                }}</span>
              </v-flex>
            </v-btn>
          </template>
          <VolumeControl :player="selectedPlayer" />
        </v-dialog>
      </v-list-item-action>

      <!-- active player btn -->
      <v-list-item-action style="padding-left: 25px; margin-right: 15px">
        <v-btn text icon @click="$store.state.showPlayersMenu = true">
          <v-flex xs12 class="vertical-btn">
            <v-icon>speaker</v-icon>
            <span v-if="selectedPlayer" class="caption" style="padding-top: 5px">{{
              truncateString(selectedPlayer.name,
                12)
            }}</span>
            <span v-else class="caption"> </span>
          </v-flex>
        </v-btn>
      </v-list-item-action>
    </v-list-item>
  </v-footer>
</template>

<script lang="ts">
import Vue from "vue";
import VolumeControl from "@/components/VolumeControl.vue";
import MediaItemThumb from "@/components/MediaItemThumb.vue";
import { mapGetters } from "vuex";
import {
  Artist,
  PlayerState,
  PlayerQueue,
  QueueItem,
  StreamDetails,
} from "@/plugins/api";
import { formatDuration } from "@/utils";
import mitt from 'mitt'
const emitter = mitt()

interface ComponentData {
  curQueueItemTime: number;
}

export default {
  components: {
    VolumeControl,
    MediaItemThumb,
  },
  data: (): ComponentData => ({
    curQueueItemTime: 0,
  }),
  computed: {
    ...mapGetters([
      "selectedPlayer",
      "selectedPlayerQueue",
      "selectedPlayerId",
      "getPlayers",
      "getProviderIcon",
      "getFanart",
    ]),
    curQueueItem(): QueueItem | undefined {
      if (this.selectedPlayerQueue) {
        return this.selectedPlayerQueue.cur_item;
      } else {
        return undefined;
      }
    },
    progress(): number {
      if (!this.curQueueItem) return 0;
      const totalSecs: number = (this.curQueueItem as QueueItem).duration;
      const curPercent = (this.curQueueItemTime / totalSecs) * 100;
      return curPercent;
    },
    playerCurTimeStr(): string {
      if (!this.curQueueItem) return "0:00";
      return formatDuration(this.curQueueItemTime);
    },
    playerTotalTimeStr(): string {
      if (!this.curQueueItem) return "0:00";
      const totalSecs = (this.curQueueItem as QueueItem).duration;
      return formatDuration(totalSecs);
    },
    progressBarWidth(): number {
      return window.innerWidth - 45;
    },
    streamDetails(): StreamDetails | undefined {
      return this.selectedPlayerQueue?.cur_item?.streamdetails;
    },
  },
  created() {
    const timer = setInterval(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (this as any).updateCurQueueItemTime();
    }, 1000);

    emitter.on("hook:beforeDestroy", () => {
      clearInterval(timer);
    })

  },

  methods: {
    artistClick(item: Artist) {
      this.$router.push({
        name: "artist",
        params: { id: item.item_id, provider: item.provider },
      });
    },
    truncateString(str: string, num: number) {
      // If the length of str is less than or equal to num
      // just return str--don't truncate it.
      if (str.length <= num) {
        return str;
      }
      // Return str truncated with '...' concatenated to the end of str.
      return str.slice(0, num);
    },
    updateCurQueueItemTime() {
      let total = 0;
      if (!this.selectedPlayerQueue || !this.curQueueItem) {
        // no active queue or no active item
        total = 0;
      } else if (
        // queue is idle/paused
        (this.selectedPlayerQueue as PlayerQueue).state !==
        PlayerState.PLAYING
      ) {
        total = (this.selectedPlayerQueue as PlayerQueue).cur_item_time;
      } else {
        // queue is playing, calculate current progress from last known timestamp
        const curSecs = (this.selectedPlayerQueue as PlayerQueue)
          .cur_item_time;
        const lastUpdated = new Date(
          (this.selectedPlayerQueue as PlayerQueue).updated_at
        );
        const lastTimestamp = Math.floor(
          (lastUpdated.getTime() +
            lastUpdated.getTimezoneOffset() * 60 * 1000) /
          1000
        );
        const curDateTime = new Date();
        const curTimestamp = Math.floor(
          (curDateTime.getTime() +
            curDateTime.getTimezoneOffset() * 60 * 1000) /
          1000
        );
        total = curSecs + (curTimestamp - lastTimestamp);
      }
      if (this.curQueueItemTime !== total) {
        this.curQueueItemTime = total;
      }
    },
  },
};
</script>

<style scoped>
.vertical-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.right {
  float: right;
}

.left {
  float: left;
}

.bg-image {
  /* Add the blur effect */
  filter: blur(20px);
  -webkit-filter: blur(20px);
  /* Center and scale the image nicely */
  background-position: center;
  background-size: cover;
}
</style>
