<template>
  <v-list style="overflow: hidden" lines="2">
    <!-- special group volume -->
    <div
      v-if="player.is_group"
      class="volumerow"
      :style="player.group_powered ? 'opacity: 0.75' : 'opacity: 0.5'"
    >
      <v-btn
        icon
        variant="plain"
        @click="api.queueCommandGroupPower(player.player_id, !player.group_powered)"
        width="60"
        height="30"
        size="x-large"
      >
        <v-icon :icon="mdiPower"></v-icon>
      </v-btn>
      <span
        class="text-body-2"
        style="position: absolute; margin-left: 65px;margin-top:-25px"
        >{{ player.group_name }}</span
      >
      <div
        class="text-caption"
        style="position: absolute; width: 60px; text-align: center; margin-left: 0px"
      >
        {{ player.group_volume_level }}
      </div>

      <v-slider
        lazy
        density="compact"
        step="2"
        track-size="2"
        thumb-size="10"
        thumb-label
        :disabled="!player.group_powered"
        :model-value="Math.round(player.group_volume_level)"
        @update:model-value="api.queueCommandGroupVolume(player.player_id, $event)"
      ></v-slider>
    </div>
    <v-divider
      v-if="player.is_group"
      style="margin-top: 10px; margin-bottom: 10px"
    ></v-divider>

    <div
      v-for="childPlayer in getVolumePlayers(player)"
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
        <span
        class="text-body-2"
        style="position: absolute; margin-left: 65px;margin-top:-25px"
        >{{ childPlayer.name }}</span
      >
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
</template>

<script setup lang="ts">
import type { Player } from "../plugins/api";
import { mdiPower } from "@mdi/js";
import { api } from "../plugins/api";

export interface Props {
  player: Player;
}
defineProps<Props>();

const getVolumePlayers = function (player: Player) {
  const items: Player[] = [];
  if (!player.is_group) {
    return [player];
  }
  for (const groupChildId of player.group_members) {
    const volumeChild = api?.players[groupChildId];

    if (volumeChild && volumeChild.available) {
      items.push(volumeChild);
    }
  }
  items.sort((a, b) => (a.name.toUpperCase() > b.name.toUpperCase() ? 1 : -1));
  return items;
};
</script>
