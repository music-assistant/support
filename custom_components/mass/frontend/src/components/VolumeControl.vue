<template>
  <v-card class="mx-auto" min-width="300">
    <v-list style="overflow: hidden">
      <v-list-item
        dense
        two-line
        style="padding: 0; margin-left: 9px; margin-bottom: 9px"
      >
        <v-list-item-avatar tile>
          <v-icon
            size="45"
            v-if="player.is_group"
            :icon="mdiSpeakerMultiple"
            color="primary"
          />
          <v-icon size="45" v-else :icon="mdiSpeaker" color="primary" />
        </v-list-item-avatar>
        <div>
          <v-list-item-title class="text-subtitle-1" style="margin-left: 10px"
            ><b>{{ player.name.substring(0, 25) }}</b></v-list-item-title
          >

          <v-list-item-subtitle
            :key="player.state"
            class="text-body-2"
            style="margin-left: 10px; text-align: left; width: 100%"
          >
            {{ $t("state." + player.state) }}
          </v-list-item-subtitle>
        </div>
      </v-list-item>
      <v-divider></v-divider>

      <div
        v-for="childPlayer in getVolumePlayers(player.player_id)"
        :key="childPlayer.player_id"
        class="volumerow"
        :style="childPlayer.powered ? 'opacity: 0.75' : 'opacity: 0.5'"
      >
        <span class="text-body-2">
          <v-btn
            icon
            variant="plain"
            @click="api.queueCommandPowerToggle(childPlayer.player_id)"
            width="60"
            height="30"
            size="x-large"
            style=""
          >
            <v-icon :icon="mdiPower"></v-icon>
          </v-btn>
          {{ childPlayer.name }}
        </span>
        <div
          class="text-caption"
          style="position: absolute; width: 60px; text-align: center; margin-left: 0px"
        >
          {{ childPlayer.volume_level }}
        </div>

        <v-slider
          lazy
          density="compact"
          step="2"
          track-size="2"
          thumb-size="10"
          thumb-label
          :disabled="!childPlayer.powered"
          :model-value="Math.round(childPlayer.volume_level)"
          @update:model-value="api.queueCommandVolume(childPlayer.player_id, $event)"
        ></v-slider>
      </div>
    </v-list>
  </v-card>
</template>

<script setup lang="ts">
import type { Player, MusicAssistantApi } from "../plugins/api";
import { getVolumePlayers } from "./PlayerSelect.vue";
import { mdiSpeaker, mdiSpeakerMultiple, mdiPower } from "@mdi/js";
import { api } from "../plugins/api";

interface Props {
  player: Player;
}
const props = defineProps<Props>();
</script>

<style lang="scss">
@use "vuetify/styles";
.volumerow {
  height: 60px;
  padding-top: 5px;
  padding-bottom: 0px;
}

.volumerow .v-slider .v-slider__container {
  margin-left: 57px;
  margin-right: 15px;
  margin-top: -10px;
}

.slider .div.v-input__append {
  padding-top: 0px;
  margin-top: -10px;
}
.playerrow {
  height: 60px;
}
</style>
