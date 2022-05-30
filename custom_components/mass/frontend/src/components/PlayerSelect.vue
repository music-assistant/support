<template>
  <!-- players side menu -->
  <v-navigation-drawer
    v-model="store.showPlayersMenu"
    position="right"
    app
    clipped
    temporary
    width="300"
    style="z-index: 99999"
  >
    <v-card-title class="headline">
      <b>{{ $t("players") }}</b>
    </v-card-title>
    <v-divider></v-divider>
    <v-expansion-panels v-model="panelItem" focusable accordion flat>
      <v-expansion-panel
        v-for="player in availablePlayers"
        :id="player.player_id"
        :key="player.player_id"
        flat
      >
        <v-expansion-panel-title
          class="playerrow"
          :style="
            store.selectedPlayer?.player_id == player.player_id
              ? 'padding:0;background-color:rgba(50, 115, 220, 0.2);'
              : 'padding:0'
          "
          :expand-icon="mdiChevronDown"
          :collapse-icon="mdiChevronUp"
          @click="
            store.selectedPlayer = player;
            scrollToTop(player.player_id);
          "
        >
          <v-list-item dense two-line style="padding: 0; margin-left: 9px">
            <v-icon
              size="45"
              :icon="player.is_group ? mdiSpeakerMultiple : mdiSpeaker"
              color="accent"
            />
            <div style="margin-left: 10px; text-align: left">
              <v-list-item-title class="text-subtitle-1"
                ><b>{{ player.name.substring(0, 25) }}</b></v-list-item-title
              >
              <v-list-item-subtitle :key="player.state" class="text-body-2">
                {{ $t("state." + player.state) }}
              </v-list-item-subtitle>
            </div>
          </v-list-item>
        </v-expansion-panel-title>
        <v-expansion-panel-text variant="contain">
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
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </v-navigation-drawer>
</template>

<script setup lang="ts">
import { computed, getCurrentInstance, onMounted, ref, watch } from "vue";
import {
  mdiSpeaker,
  mdiSpeakerMultiple,
  mdiPower,
  mdiChevronUp,
  mdiChevronDown,
} from "@mdi/js";
import type { Player } from "../plugins/api";
import { store } from "../plugins/store";

const panelItem = ref<number | undefined>(undefined);

// computed properties
const availablePlayers = computed(() => {
  const res: Player[] = [];
  for (const player_id in api?.players) {
    const player = api?.players[player_id];
    if (player?.available) res.push(player);
  }
  return res
    .slice()
    .sort((a, b) => (a.name.toUpperCase() > b.name.toUpperCase() ? 1 : -1));
});

//watchers
watch(
  () => store.showPlayersMenu,
  (newVal) => {
    if (!newVal) {
      panelItem.value = undefined;
    }
  }
);

const shadowRoot = ref<ShadowRoot>();
const lastClicked = ref();
onMounted(() => {
  shadowRoot.value = getCurrentInstance()?.vnode?.el?.getRootNode();
});
const scrollToTop = function (playerId: string) {
  if (lastClicked.value == playerId) return;
  lastClicked.value = playerId;
  setTimeout(() => {
    const elmnt = shadowRoot.value?.getElementById(playerId);
    elmnt?.scrollIntoView({ behavior: "smooth" });
  }, 0);
};
</script>

<script lang="ts">
import { api } from "../plugins/api";
export const getVolumePlayers = function (playerId: string) {
  const items: Player[] = [];
  const finalItems: Player[] = [];
  const player = api?.players[playerId];
  if (player) {
    for (const groupChildId of player.group_childs) {
      const volumeChild = api?.players[groupChildId];
      if (volumeChild && volumeChild.available) {
        items.push(volumeChild);
      }
    }
    finalItems.push(player);
  }
  items.sort((a, b) => (a.name.toUpperCase() > b.name.toUpperCase() ? 1 : -1));
  finalItems.push(...items);
  return finalItems;
};
</script>

<style>
.playerrow {
  height: 60px;
}

div.v-expansion-panel-text__wrapper {
  padding-left: 0px;
  padding-right: 0px;
  padding-top: 0px;
  padding-bottom: 0px;
}

div.v-expansion-panel--active:not(:first-child),
.v-expansion-panel--active + .v-expansion-panel {
  margin-top: 0px;
}
div.v-expansion-panel__shadow {
  box-shadow: none;
}
</style>
