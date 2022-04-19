<template>
  <v-dialog
    :model-value="modelValue"
    fullscreen
    :scrim="false"
    transition="dialog-bottom-transition"
    @click:outside="emit('update:model-value', false)"
  >
    <v-card min-width="400px">
      <v-toolbar dark color="primary">
        <v-icon :icon="mdiPlayCircleOutline"></v-icon>
        <v-toolbar-title style="padding-left: 10px">{{ header }}</v-toolbar-title>
        <v-spacer></v-spacer>
        <v-toolbar-items>
          <v-btn dark text @click="emit('update:model-value', false)">{{
            $t("close")
          }}</v-btn>
        </v-toolbar-items>
      </v-toolbar>
      <!-- play contextmenu items -->
      <v-card-text v-if="playlists.length === 0 && playMenuItems.length > 0">
        <v-select
          :model-value="store.activePlayerQueue?.name"
          :items="Object.values(api.queues).map((x) => x.name)"
          :label="$t('play_on')"
          dense
          :disabled="true"
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
        <v-list-item-subtitle style="margin-left: 25px; margin-top: 10px"
          >Acties</v-list-item-subtitle
        >
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
        <v-card-subtitle>{{ $t("add_playlist") }}</v-card-subtitle>
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
            :onclick-handler="addToPlaylist"
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
} from "@mdi/js";
import ListviewItem from "./ListviewItem.vue";
import { MediaType, QueueOption } from "../plugins/api";
import type { MediaItem, MediaItemType, Playlist } from "../plugins/api";
import { ref, watch, watchEffect } from "vue";
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

interface Props {
  modelValue: boolean;
  items: MediaItemType[];
  parentItem?: MediaItemType;
}
const props = defineProps<Props>();
const actionMenuItems = ref<MenuItem[]>([]);
const playMenuItems = ref<MenuItem[]>([]);
const header = ref("");
const playlists = ref<Playlist[]>([]);
const curPlaylist = ref<Playlist>();

const emit = defineEmits<{
  (e: "update:model-value", value: boolean): void;
}>();

watch(
  () => props.modelValue,
  (val) => {
    if (val) showContextMenu();
  }
);

const showContextMenu = function () {
  // show contextmenu items for the selected mediaItem(s)
  playlists.value = [];
  if (!props.items) return;
  curPlaylist.value = undefined;
  const firstItem: MediaItem = props.items[0];
  playMenuItems.value = [];
  actionMenuItems.value = [];
  if (props.items.length === 1) header.value = firstItem.name;
  else header.value = t("items_selected", [props.items.length]).toString();
  // Play NOW
  if (itemIsAvailable(firstItem)) {
    playMenuItems.value.push({
      label: "play_now",
      action: () => {
        api.playMedia(
          store.activePlayerQueue?.queue_id || "",
          props.items.map((x) => x.uri),
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
    (props.items.length === 1 || firstItem.media_type === MediaType.TRACK)
  ) {
    playMenuItems.value.push({
      label: "play_next",
      action: () => {
        api.playMedia(
          store.activePlayerQueue?.queue_id || "",
          props.items.map((x) => x.uri),
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
          store.activePlayerQueue?.queue_id || "",
          props.items.map((x) => x.uri),
          QueueOption.ADD
        );
        close();
      },
      icon: mdiPlaylistPlus,
    });
  }

  // show info
  if (
    props.items.length === 1 &&
    firstItem !== props.parentItem &&
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
  // add to library
  if (!firstItem.in_library && itemIsAvailable(firstItem)) {
    actionMenuItems.value.push({
      label: "add_library",
      action: () => {
        api.addToLibrary(props.items);
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
        api.removeFromLibrary(props.items);
        close();
      },
      icon: mdiHeart,
    });
  }
  // remove from playlist (playlist tracks only)
  if (props.parentItem && props.parentItem.media_type === MediaType.PLAYLIST) {
    const playlist = props.parentItem as Playlist;
    if (firstItem.media_type === MediaType.TRACK && playlist.is_editable) {
      actionMenuItems.value.push({
        label: "remove_playlist",
        action: () => {
          api.removePlaylistTracks(
            playlist.provider,
            playlist.item_id,
            props.items.map((x) => x.uri)
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
};
const showPlaylistsMenu = async function () {
  // get all editable playlists
  const items = [];
  for (const playlist of await api.getLibraryPlaylists()) {
    if (
      playlist.is_editable &&
      !(
        props.parentItem &&
        props.parentItem.media_type === MediaType.PLAYLIST &&
        playlist.item_id === props.parentItem.item_id
      )
    ) {
      items.push(playlist);
    }
  }
  playlists.value = items;
};
const addToPlaylist = function (playlist: Playlist) {
  /// add track(s) to playlist
  api.addPlaylistTracks(
    playlist.provider,
    playlist.item_id,
    props.items.map((x) => x.uri)
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
  emit("update:model-value", false);
};
const getPlayerQueues = function () {
  const result = [];
  for (const queueId in api.queues) {
    result.push({
      title: api.queues[queueId].name,
      value: api.queues[queueId].queue_id,
    });
  }
  return result;
};
</script>
