<template>
  <v-dialog :model-value="modelValue" transition="dialog-bottom-transition" fullscreen>
    <v-card>
      <v-toolbar density="compact" dark color="primary">
        <v-icon :icon="mdiPlayCircleOutline"></v-icon>
        <v-toolbar-title style="padding-left: 10px"
          ><b>{{ header }}</b>
          <span v-if="showPlaylistsMenu">
            | {{ $t("add_playlist") }}
          </span></v-toolbar-title
        >
        <v-btn :icon="mdiClose" dark text @click="close()"></v-btn>
      </v-toolbar>
      <!-- play contextmenu items -->
      <v-card-text v-if="!showPlaylistsMenu && playMenuItems.length > 0">
        <v-select
          v-model="queueName"
          :items="Object.values(api.queues).map((x: PlayerQueue) => x.name)"
          :label="$t('play_on')"
          dense
        ></v-select>
        <v-list>
          <div v-for="item of playMenuItems" :key="item.label">
            <v-list-item @click="itemClicked(item)">
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
      <v-card-text v-if="!showPlaylistsMenu && actionMenuItems.length > 0">
        <v-list-item-subtitle style="margin-left: 25px; margin-top: 10px">{{
          $t("actions")
        }}</v-list-item-subtitle>
        <v-list>
          <div v-for="item of actionMenuItems" :key="item.label">
            <v-list-item @click="itemClicked(item)">
              <v-list-item-avatar style="padding-right: 10px">
                <v-icon :icon="item.icon"></v-icon>
              </v-list-item-avatar>
              <v-list-item-title>{{ $t(item.label, item.labelArgs) }}</v-list-item-title>
            </v-list-item>
            <v-divider></v-divider>
          </div>
        </v-list>
      </v-card-text>
      <!-- playlists selection -->
      <v-card-text v-if="showPlaylistsMenu">
        <v-list>
          <div v-for="playlist of playlists" :key="playlist.item_id">
            <v-list-item ripple @click="addToPlaylist(playlist)">
              <template v-slot:prepend>
                <div class="listitem-thumb">
                  <MediaItemThumb
                    :item="playlist"
                    :size="50"
                    width="50px"
                    height="50px"
                  /></div
              ></template>
              <template v-slot:title>
                <div>{{ playlist.name }}</div>
              </template>
              <template v-slot:subtitle>
                <div>{{ playlist.owner }}</div>
              </template>
              <template v-slot:append>
                <div class="listitem-actions">
                  <ProviderIcons
                    v-if="playlist.provider_ids"
                    :provider-ids="playlist.provider_ids"
                    :height="20"
                    class="listitem-actions"
                  />
                </div>
              </template>
            </v-list-item>
            <v-divider></v-divider>
          </div>
          <!-- create playlist row(s) -->
          <div v-for="prov of api.providers" :key="prov.id">
            <div
              v-if="
                prov.supported_features.includes(MusicProviderFeature.PLAYLIST_CREATE)
              "
            >
              <v-list-item ripple>
                <template v-slot:prepend>
                  <div class="listitem-thumb">
                    <img
                      v-bind="props"
                      :height="40"
                      :src="getProviderIcon(prov.type)"
                      style="margin-left: 5px; margin-top: 5px"
                    />
                  </div>
                </template>
                <template v-slot:title>
                  <v-text-field
                    :label="$t('create_playlist', [prov.name])"
                    :append-icon="mdiPlaylistPlus"
                    variant="plain"
                    hide-details
                    @update:model-value="
                      (txt) => {
                        newPlaylistName = txt;
                      }
                    "
                    @click:append="newPlaylist(prov.id)"
                    @keydown.enter="newPlaylist(prov.id)"
                  ></v-text-field>
                </template>
              </v-list-item>
              <v-divider></v-divider>
            </div>
          </div>
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
  mdiCancel,
  mdiAccountMusic,
  mdiAlbum,
  mdiRadioTower
} from "@mdi/js";
import MediaItemThumb from "./MediaItemThumb.vue";
import ProviderIcons from "./ProviderIcons.vue";
import { getProviderIcon } from "./ProviderIcons.vue";
import {
  MediaType,
  ProviderType,
  QueueOption,
  type Album,
} from "../plugins/api";
import type { MediaItem, MediaItemType, Playlist, Track } from "../plugins/api";
import { ref, watch } from "vue";
import api, { MusicProviderFeature } from "../plugins/api";
import { useI18n } from "vue-i18n";
import { store } from "../plugins/store";

// properties
export interface Props {
  items: MediaItemType[];
  parentItem?: MediaItemType;
  modelValue: boolean;
}
const props = defineProps<Props>();

const { t } = useI18n();

const actionMenuItems = ref<ContextMenuItem[]>([]);
const playMenuItems = ref<ContextMenuItem[]>([]);
const header = ref("");
const playlists = ref<Playlist[]>([]);
const showPlaylistsMenu = ref(false);
const newPlaylistName = ref("");
// TEMP TODO // vuetify select has bug that object does not work so using plain text instead
const queueName = ref("");

const emit = defineEmits<{
  (e: "refresh", value: MediaItemType): void;
  (e: "clear"): void;
  (e: "update:modelValue", value: boolean): void;
  (e: "update:items", value: MediaItemType[]): void;
}>();

watch(
  () => props.modelValue,
  (val) => {
    if (val) showContextMenu();
  }
);

const showContextMenu = async function () {
  showPlaylistsMenu.value = false;
  // show contextmenu items for the selected mediaItem(s)
  queueName.value = store.selectedPlayer?.name || "";
  playlists.value = [];
  if (!props.items) return;

  if (props.items.length === 1) header.value = props.items[0].name;
  else header.value = t("items_selected", [props.items.length]).toString();

  if (store.selectedPlayer && store.selectedPlayer.available) {
    playMenuItems.value = getPlayMenuItems(props.items);
  } else {
    playMenuItems.value = [];
  }

  // grab the full (lazy) fullItem so we have details about in-library etc.
  let firstItem: MediaItem = props.items[0];
  if (firstItem.provider !== ProviderType.DATABASE) {
    firstItem = await api.getItem(props.items[0].uri);
    const items = props.items;
    items[0] = firstItem;
    emit("update:items", items);
  }
  actionMenuItems.value = getContextMenuItems(props.items, props.parentItem);
  fetchPlaylists();
};
const fetchPlaylists = async function () {
  // get all editable playlists
  playlists.value = [];
  const playlistResults = await api.getPlaylists();
  for (const playlist of playlistResults.items) {
    if (
      playlist.is_editable &&
      !(
        props.parentItem &&
        props.parentItem.media_type === MediaType.PLAYLIST &&
        playlist.item_id === props.parentItem.item_id
      )
    ) {
      playlists.value.push(playlist as Playlist);
    }
  }
};
const addToPlaylist = function (value: MediaItemType) {
  /// add track(s) to playlist
  api.addPlaylistTracks(
    value.item_id,
    props.items.map((x) => x.uri)
  );
  close();
};
const newPlaylist = async function (provId: string) {
  const newPlaylist = await api.createPlaylist(newPlaylistName.value, provId);
  addToPlaylist(newPlaylist);
};

const itemClicked = async function (item: ContextMenuItem) {
  if (item.actionStr == "add_playlist") {
    showPlaylistsMenu.value = true;
  } else if (item.actionStr == "clear") {
    emit("clear");
    close();
  } else if (item.action && item.actionStr == "play") {
    item.action();
    emit("clear");
    close();
  } else if (item.action) {
    close();
    item.action();
  }
};

const close = function () {
  if (props.items.length == 1) {
    emit("clear");
  }
  emit("update:modelValue", false);
};
</script>

<script lang="ts">
import router from "@/plugins/router";

export interface ContextMenuItem {
  label: string;
  labelArgs: Array<string | number>;
  action?: CallableFunction;
  icon: string;
  actionStr?: string;
}

export const itemIsAvailable = function (item: MediaItem) {
  for (const x of item.provider_ids) {
    if (x.available) return true;
  }
  return false;
};

export const radioSupported = function (item: MediaItemType) {
  for (const provId of item.provider_ids) {
    if (
      api.providers[provId.prov_id].supported_features.includes(
        MusicProviderFeature.SIMILAR_TRACKS
      )
    )
      return true;
  }
  return false;
};

export const getPlayMenuItems = function (items: MediaItem[]) {
  const playMenuItems: ContextMenuItem[] = [];
  if (items.length == 0 || !itemIsAvailable(items[0])) {
    return playMenuItems;
  }
  // Play NOW
  playMenuItems.push({
    label: "play_now",
    action: () => {
      api.playMedia(items, QueueOption.PLAY);
    },
    icon: mdiPlayCircleOutline,
    labelArgs: [],
    actionStr: "play",
  });

  // Start Radio
  if (radioSupported(items[0])) {
    playMenuItems.push({
      label: "play_radio",
      action: () => {
        api.playMedia(items, QueueOption.RADIO);
      },
      icon: mdiRadioTower,
      labelArgs: [],
      actionStr: "play",
    });
  }

  // Play NEXT
  if (items.length === 1 || items[0].media_type === MediaType.TRACK) {
    playMenuItems.push({
      label: "play_next",
      action: () => {
        api.playMedia(items, QueueOption.NEXT);
      },
      icon: mdiSkipNextCircleOutline,
      labelArgs: [],
      actionStr: "play",
    });
  }
  // Add to Queue
  playMenuItems.push({
    label: "add_queue",
    action: () => {
      api.playMedia(items, QueueOption.ADD);
    },
    icon: mdiPlaylistPlus,
    labelArgs: [],
    actionStr: "play",
  });

  return playMenuItems;
};

export const getContextMenuItems = function (items: MediaItem[], parentItem?: MediaItem) {
  const contextMenuItems: ContextMenuItem[] = [];
  if (items.length == 0) {
    return contextMenuItems;
  }

  // show info
  if (items.length === 1 && items[0] !== parentItem && itemIsAvailable(items[0])) {
    contextMenuItems.push({
      label: "show_info",
      labelArgs: [],
      action: () => {
        router.push({
          name: items[0].media_type,
          params: {
            item_id: items[0].item_id,
            provider: items[0].provider,
          },
        });
      },
      icon: mdiInformationOutline,
    });
  }

  // go to artist(s)
  if (
    items.length === 1 &&
    itemIsAvailable(items[0]) &&
    "artists" in items[0] &&
    (items[0] as Track | Album).artists.length === 1
  ) {
    for (const artist of (items[0] as Track).artists) {
      contextMenuItems.push({
        label: "goto_artist",
        labelArgs: [artist.name],
        action: () => {
          router.push({
            name: "artist",
            params: {
              item_id: artist.item_id,
              provider: artist.provider,
            },
          });
        },
        icon: mdiAccountMusic,
      });
    }
  }
  // go to album
  if (
    items.length === 1 &&
    itemIsAvailable(items[0]) &&
    "album" in items[0] &&
    (items[0] as Track).album
  ) {
    contextMenuItems.push({
      label: "goto_album",
      labelArgs: [items[0].album.name],
      action: () => {
        router.push({
          name: "album",
          params: {
            item_id: items[0].album.item_id,
            provider: items[0].album.provider,
          },
        });
      },
      icon: mdiAlbum,
    });
  }

  // refresh item
  if (items.length === 1 && items[0] == parentItem) {
    contextMenuItems.push({
      label: "refresh_item",
      labelArgs: [],
      action: () => {
        api.getItem(items[0].uri, false, true);
      },
      icon: mdiRefresh,
    });
  }
  // add to library
  if (!items[0].in_library && itemIsAvailable(items[0])) {
    contextMenuItems.push({
      label: "add_library",
      labelArgs: [],
      action: () => {
        api.addToLibrary(items);
      },
      icon: mdiHeartOutline,
    });
  }
  // remove from library
  if (items[0].in_library) {
    contextMenuItems.push({
      label: "remove_library",
      labelArgs: [],
      action: () => {
        api.removeFromLibrary(items);
      },
      icon: mdiHeart,
    });
  }
  // remove from playlist (playlist tracks only)
  if (parentItem && parentItem.media_type === MediaType.PLAYLIST) {
    const playlist = parentItem as Playlist;
    if (items[0].media_type === MediaType.TRACK && playlist.is_editable) {
      contextMenuItems.push({
        label: "remove_playlist",
        labelArgs: [],
        action: () => {
          api.removePlaylistTracks(
            playlist.item_id,
            items.map((x) => (x as Track).position as number)
          );
        },
        icon: mdiMinusCircleOutline,
      });
    }
  }
  // add to playlist action (tracks only)
  if (items[0].media_type === "track") {
    contextMenuItems.push({
      label: "add_playlist",
      labelArgs: [],
      actionStr: "add_playlist",
      icon: mdiPlusCircleOutline,
    });
  }
  // delete from db
  if (items.length == 1 && items[0].provider == ProviderType.DATABASE) {
    contextMenuItems.push({
      label: "delete_db",
      labelArgs: [],
      action: () => {
        api.deleteDbItem(items[0].media_type, items[0].item_id, true);
        if (parentItem && parentItem.item_id == items[0].item_id) {
          // refresh UI if paremtItem deleted
          router.push({
            name: `${parentItem.media_type}s`,
          });
        }
      },
      icon: mdiCancel,
    });
  }
  // clear selection
  if (items.length > 1) {
    contextMenuItems.push({
      label: "clear_selection",
      labelArgs: [],
      actionStr: "clear",
      icon: mdiCancel,
    });
  }
  return contextMenuItems;
};
</script>
