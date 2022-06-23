<template>
  <v-dialog
    v-model="store.showContextMenu"
    transition="dialog-bottom-transition"
    overlay-opacity="0.8"
    fullscreen
    :class="$vuetify.display.mobile ? '' : 'padded-overlay'"
  >
    <v-card>
      <v-toolbar dark color="primary">
        <v-icon :icon="mdiPlayCircleOutline"></v-icon>
        <v-toolbar-title style="padding-left: 10px"
          ><b>{{ header }}</b>
          <span v-if="playlists.length > 0">
            | {{ $t("add_playlist") }}
          </span></v-toolbar-title
        >

        <v-btn :icon="mdiClose" dark text @click="close()">{{
          $t("close")
        }}</v-btn>
      </v-toolbar>
      <!-- play contextmenu items -->
      <v-card-text v-if="playlists.length === 0 && playMenuItems.length > 0">
        <v-select
          v-model="queueName"
          :items="Object.values(api.queues).map((x: PlayerQueue) => x.name)"
          :label="$t('play_on')"
          dense
        ></v-select>
        <v-list>
          <div v-for="item of playMenuItems" :key="item.label">
            <v-list-item @click="item.action()">
              <v-list-item-avatar style="padding-right: 10px">
                <v-icon :icon="item.icon"></v-icon>
              </v-list-item-avatar>
              <v-list-item-title>{{ $t(item.label) }}</v-list-item-title>
            </v-list-item>
            <v-divider></v-divider>
          </div>
        </v-list>
      </v-card-text>
      <!-- action contextmenu items -->
      <v-card-text v-if="playlists.length === 0 && actionMenuItems.length > 0">
        <v-list-item-subtitle style="margin-left: 25px; margin-top: 10px">{{
          $t("actions")
        }}</v-list-item-subtitle>
        <v-list v-if="playlists.length === 0">
          <div v-for="item of actionMenuItems" :key="item.label">
            <v-list-item @click="item.action()">
              <v-list-item-avatar style="padding-right: 10px">
                <v-icon :icon="item.icon"></v-icon>
              </v-list-item-avatar>
              <v-list-item-title>{{ $t(item.label) }}</v-list-item-title>
            </v-list-item>
            <v-divider></v-divider>
          </div>
        </v-list>
      </v-card-text>
      <!-- playlists selection -->
      <v-card-text v-if="playlists.length > 0">
        <v-list style="overflow: hidden">
          <listviewItem
            v-for="(item, index) in playlists"
            :key="item.item_id"
            :item="item"
            :totalitems="playlists.length"
            :index="index"
            :hideavatar="false"
            :hidetracknum="true"
            :hideproviders="false"
            :hidelibrary="true"
            :hidemenu="true"
            :is-selected="false"
            @click="addToPlaylist"
          ></listviewItem>
        </v-list>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import {
  mdiHeart,
  mdiHeartOutline,
  mdiPlayCircleOutline,
  mdiSkipNextCircleOutline,
  mdiPlaylistPlus,
  mdiInformationOutline,
  mdiMinusCircleOutline,
  mdiPlusCircleOutline,
  mdiClose,
  mdiRefresh,
  mdiCancel
} from "@mdi/js";
import ListviewItem from "./ListviewItem.vue";
import { MediaType, QueueOption } from "../plugins/api";
import type { MediaItem, MediaItemType, Playlist, Track, PlayerQueue } from "../plugins/api";
import { ref, watch } from "vue";
import api from "../plugins/api";
import { useI18n } from "vue-i18n";
import { store } from "../plugins/store";
import { useRouter } from "vue-router";

const { t } = useI18n();
const router = useRouter();

interface MenuItem {
  label: string;
  action: CallableFunction;
  icon: string;
}

const actionMenuItems = ref<MenuItem[]>([]);
const playMenuItems = ref<MenuItem[]>([]);
const header = ref("");
const playlists = ref<Playlist[]>([]);
const curPlaylist = ref<Playlist>();
// TEMP TODO // vuetify select has bug that object does not work so using plain text instead
const queueName = ref("");

watch(
  () => store.showContextMenu,
  (val) => {
    if (val) showContextMenu();
  }
);

const showContextMenu = function () {
  // show contextmenu items for the selected mediaItem(s)
  queueName.value = store.selectedPlayer?.name || "";
  playlists.value = [];
  if (!store.contextMenuItems) return;
  curPlaylist.value = undefined;
  const firstItem: MediaItem = store.contextMenuItems[0];
  playMenuItems.value = [];
  actionMenuItems.value = [];
  if (store.contextMenuItems.length === 1) header.value = firstItem.name;
  else
    header.value = t("items_selected", [
      store.contextMenuItems.length,
    ]).toString();
  // Play NOW
  if (itemIsAvailable(firstItem)) {
    playMenuItems.value.push({
      label: "play_now",
      action: () => {
        api.playMedia(
          queueIdFromName(queueName.value),
          store.contextMenuItems,
          QueueOption.PLAY
        );
        close();
      },
      icon: mdiPlayCircleOutline,
    });
  }
  // Play NEXT
  if (
    itemIsAvailable(firstItem) &&
    (store.contextMenuItems.length === 1 ||
      firstItem.media_type === MediaType.TRACK)
  ) {
    playMenuItems.value.push({
      label: "play_next",
      action: () => {
        api.playMedia(
          queueIdFromName(queueName.value),
          store.contextMenuItems,
          QueueOption.NEXT
        );
        close();
      },
      icon: mdiSkipNextCircleOutline,
    });
  }
  // Add to Queue
  if (itemIsAvailable(firstItem)) {
    playMenuItems.value.push({
      label: "add_queue",
      action: () => {
        api.playMedia(
          queueIdFromName(queueName.value),
          store.contextMenuItems,
          QueueOption.ADD
        );
        close();
      },
      icon: mdiPlaylistPlus,
    });
  }

  // show info
  if (
    store.contextMenuItems.length === 1 &&
    firstItem !== store.contextMenuParentItem &&
    itemIsAvailable(firstItem)
  ) {
    actionMenuItems.value.push({
      label: "show_info",
      action: () => {
        close();
        router.push({
          name: firstItem.media_type,
          params: {
            item_id: firstItem.item_id,
            provider: firstItem.provider,
          },
        });
      },
      icon: mdiInformationOutline,
    });
  }
  // refresh item
  if (
    store.contextMenuItems.length === 1 &&
    firstItem == store.contextMenuParentItem
  ) {
    actionMenuItems.value.push({
      label: "refresh_item",
      action: () => {
        close();
        api.getItem(firstItem.uri, false, true);
      },
      icon: mdiRefresh,
    });
  }
  // add to library
  if (!firstItem.in_library && itemIsAvailable(firstItem)) {
    actionMenuItems.value.push({
      label: "add_library",
      action: () => {
        api.addToLibrary(store.contextMenuItems);
        close();
      },
      icon: mdiHeartOutline,
    });
  }
  // remove from library
  if (firstItem.in_library) {
    actionMenuItems.value.push({
      label: "remove_library",
      action: () => {
        api.removeFromLibrary(store.contextMenuItems);
        close();
      },
      icon: mdiHeart,
    });
  }
  // remove from playlist (playlist tracks only)
  if (
    store.contextMenuParentItem &&
    store.contextMenuParentItem.media_type === MediaType.PLAYLIST
  ) {
    const playlist = store.contextMenuParentItem as Playlist;
    if (firstItem.media_type === MediaType.TRACK && playlist.is_editable) {
      actionMenuItems.value.push({
        label: "remove_playlist",
        action: () => {
          api.removePlaylistTracks(
            playlist.item_id,
            store.contextMenuItems.map((x) => (x as Track).position as number)
          );
          close();
        },
        icon: mdiMinusCircleOutline,
      });
    }
  }
  // add to playlist action (tracks only)
  if (firstItem.media_type === "track") {
    actionMenuItems.value.push({
      label: "add_playlist",
      action: showPlaylistsMenu,
      icon: mdiPlusCircleOutline,
    });
  }
  // clear selection
  if (store.contextMenuItems.length > 1) {
    actionMenuItems.value.push({
      label: "clear_selection",
      action: () => {
        store.contextMenuItems = [];
        close();
      },
      icon: mdiCancel,
    });
  }
};
const showPlaylistsMenu = async function () {
  // get all editable playlists
  const items = [];
  for (const playlist of api.library.playlists) {
    if (
      playlist.is_editable &&
      !(
        store.contextMenuParentItem &&
        store.contextMenuParentItem.media_type === MediaType.PLAYLIST &&
        playlist.item_id === store.contextMenuParentItem.item_id
      )
    ) {
      items.push(playlist);
    }
  }
  playlists.value = items;
};
const addToPlaylist = function (value: MediaItemType) {
  /// add track(s) to playlist
  api.addPlaylistTracks(
    value.item_id,
    store.contextMenuItems.map((x) => x.uri)
  );
  close();
};
const itemIsAvailable = function (item: MediaItem) {
  for (const x of item.provider_ids) {
    if (x.available) return true;
  }
  return false;
};
const close = function () {
  if (store.contextMenuItems.length == 1) {
    store.contextMenuItems = [];
  }
  store.showContextMenu = false;
};
const queueIdFromName = function (name: string) {
  for (const queueId in api.queues) {
    if (api.queues[queueId].name == name) return queueId;
  }
  return "";
};
</script>
