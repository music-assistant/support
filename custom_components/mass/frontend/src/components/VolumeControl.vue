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
        width="60"
        height="30"
        size="x-large"
        @click="
          api.queueCommandGroupPower(player.player_id, !player.group_powered)
        "
      >
        <v-icon :icon="mdiPower" />
      </v-btn>
      <span class="text-body-2" style="position: absolute; margin-top: 3px">{{
        truncateString(player.group_name, 27)
      }}</span>
      <div
        class="text-caption"
        style="
          position: absolute;
          width: 60px;
          text-align: center;
          margin-left: 0px;
        "
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
        style="margin-left: 5px"
        @update:model-value="
          api.queueCommandGroupVolume(player.player_id, $event)
        "
      />
    </div>
    <v-divider
      v-if="player.is_group"
      style="margin-top: 10px; margin-bottom: 10px"
    />

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
          width="60"
          height="30"
          size="x-large"
          style=""
          @click="api.queueCommandPowerToggle(childPlayer.player_id)"
        >
          <v-icon :icon="mdiPower" />
        </v-btn>
        <span
          v-if="player.group_members.includes(childPlayer.player_id)"
          class="text-body-2"
          style="position: absolute; margin-top: 3px"
          >{{ truncateString(childPlayer.name, 27) }}</span
        >
        <span
          v-else
          class="text-body-2"
          style="position: absolute; margin-top: 3px"
          >{{ truncateString(childPlayer.group_name, 27) }}</span
        >
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
        style="margin-left: 5px"
        @update:model-value="
          api.queueCommandVolume(childPlayer.player_id, $event)
        "
      />
    </div>
  </v-list>
</template>

<script setup lang="ts">
import type { Player } from '../plugins/api';
import { mdiPower } from '@mdi/js';
import { api } from '../plugins/api';
import { truncateString } from '../utils';

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
