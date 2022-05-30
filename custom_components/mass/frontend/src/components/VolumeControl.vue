<template>
  <v-card min-width="300">
    <v-list style="overflow: hidden" lines="2">
      <v-list-item style="padding: 0; margin-left: 9px; margin-bottom: 9px">
        <template v-slot:prepend>
          <v-icon
            size="45"
            :icon="player.is_group ? mdiSpeakerMultiple : mdiSpeaker"
            color="accent"
          />
        </template>

        <template v-slot:title>
          <div class="text-subtitle-1" style="margin-left: 10px">
            <b>{{ player.name.substring(0, 25) }}</b>
          </div>
        </template>

        <template v-slot:subtitle>
          <div
            :key="player.state"
            class="text-body-2"
            style="margin-left: 10px; text-align: left; width: 100%"
          >
            {{ $t("state." + player.state) }}
          </div>
        </template>
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
          style="
            position: absolute;
            width: 60px;
            text-align: center;
            margin-left: 0px;
          "
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
          @update:model-value="
            api.queueCommandVolume(childPlayer.player_id, $event)
          "
        ></v-slider>
      </div>
    </v-list>
  </v-card>
</template>

<script setup lang="ts">
import type { Player } from "../plugins/api";
import { getVolumePlayers } from "./PlayerSelect.vue";
import { mdiSpeaker, mdiSpeakerMultiple, mdiPower } from "@mdi/js";
import { api } from "../plugins/api";

export interface Props {
  player: Player;
}
defineProps<Props>();
</script>
