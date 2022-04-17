<template>
  <v-dialog
    :value="value"
    max-width="500px"
    overlay-opacity="0.8"
    overlay-color="grey"
    @input="$emit('input', $event)"
  >
    <v-card>
      <v-card-title v-if="items">{{ header }}</v-card-title>
      <!-- play contextmenu items -->
      <div v-if="playlists.length === 0 && playMenuItems.length > 0">
        <v-list-item-subtitle style="margin-left: 25px; margin-top: -10px"
          >{{ $t("play_on") }}
          <a @click="$store.state.showPlayersMenu = true">{{
            selectedPlayer.name || $t("no_player")
          }}</a></v-list-item-subtitle
        >
        <v-list>
          <div v-for="item of playMenuItems" :key="item.label">
            <v-list-item @click="item.action()">
              <v-list-item-avatar>
                <v-icon>{{ item.icon }}</v-icon>
              </v-list-item-avatar>
              <v-list-item-content>
                <v-list-item-title>{{ $t(item.label) }}</v-list-item-title>
              </v-list-item-content>
            </v-list-item>
            <v-divider></v-divider>
          </div>
        </v-list>
      </div>
      <!-- action contextmenu items -->
      <div v-if="playlists.length === 0 && actionMenuItems.length > 0">
        <v-list-item-subtitle style="margin-left: 25px; margin-top: 10px"
          >Acties</v-list-item-subtitle
        >
        <v-list v-if="playlists.length === 0">
          <div v-for="item of actionMenuItems" :key="item.label">
            <v-list-item @click="item.action()">
              <v-list-item-avatar>
                <v-icon>{{ item.icon }}</v-icon>
              </v-list-item-avatar>
              <v-list-item-content>
                <v-list-item-title>{{ $t(item.label) }}</v-list-item-title>
              </v-list-item-content>
            </v-list-item>
            <v-divider></v-divider>
          </div>
        </v-list>
      </div>
      <!-- playlists selection -->
      <div v-if="playlists.length > 0">
        <v-card-subtitle>{{ $t("add_playlist") }}</v-card-subtitle>
        <v-list>
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
            :onclick-handler="addToPlaylist"
          ></listviewItem>
        </v-list>
      </div>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
  import type { PropType } from "vue";
  import ListviewItem from "./ListviewItem.vue";
  import { MediaItem, MediaType, Playlist, QueueOption } from "../plugins/api";

  interface MenuItem {
    label: string;
    action: CallableFunction;
    icon: string;
  }

  interface ComponentData {
    actionMenuItems: MenuItem[];
    playMenuItems: MenuItem[];
    header: string;
    playlists: Playlist[];
    curPlaylist: Playlist | undefined;
  }

  export default Vue.extend({
    components: {
      ListviewItem,
    },
    props: {
      value: {
        type: Boolean,
        required: true,
        default: false,
      },
      items: {
        type: Array as PropType<MediaItem[]>,
        required: false,
        default() {
          return [];
        },
      },
      parentItem: {
        type: Object as PropType<MediaItem> | undefined,
        required: false,
        default: undefined,
      },
    },
    data: (): ComponentData => ({
      actionMenuItems: [],
      playMenuItems: [],
      header: "",
      playlists: [],
      curPlaylist: undefined,
    }),
    computed: {
      ...mapGetters(["getLibraryPlaylists", "getItem", "selectedPlayer"]),
    },
    watch: {
      value(newVal) {
        if (newVal) {
          this.showContextMenu();
        }
      },
    },
    mounted() {
      this.dispatchGetLibraryPlaylists;
    },
    methods: {
      ...mapActions([
        "playMedia",
        "addPlaylistTracks",
        "removePlaylistTracks",
        "addToLibrary",
        "removeFromLibrary",
        "refreshItems",
        "dispatchGetLibraryPlaylists",
      ]),
      showContextMenu() {
        // show contextmenu items for the selected mediaItem(s)
        this.dispatchGetLibraryPlaylists();
        this.playlists = [];
        if (!this.items) return;
        this.curPlaylist = undefined;
        const firstItem: MediaItem = this.items[0];
        const actionMenuItems: MenuItem[] = [];
        const playMenuItems: MenuItem[] = [];
        if (this.items.length === 1) this.header = firstItem.name;
        else
          this.header = this.$t("items_selected", [
            this.items.length,
          ]).toString();
        // Play NOW
        if (this.itemIsAvailable(firstItem)) {
          playMenuItems.push({
            label: "play_now",
            action: () => {
              this.playMedia({
                items: this.items,
                queueOpt: QueueOption.PLAY,
              });
              this.close();
            },
            icon: "play_circle_outline",
          });
        }
        // Play NEXT
        if (
          this.itemIsAvailable(firstItem) &&
          (this.items.length === 1 || firstItem.media_type === MediaType.TRACK)
        ) {
          playMenuItems.push({
            label: "play_next",
            action: () => {
              this.playMedia({
                items: this.items,
                queueOpt: QueueOption.NEXT,
              });
              this.close();
            },
            icon: "queue_play_next",
          });
        }
        // Add to Queue
        if (this.itemIsAvailable(firstItem)) {
          playMenuItems.push({
            label: "add_queue",
            action: () => {
              this.playMedia({
                items: this.items,
                queueOpt: QueueOption.ADD,
              });
              this.close();
            },
            icon: "playlist_add",
          });
        }
        this.playMenuItems = playMenuItems;
        // show info
        if (
          this.items.length === 1 &&
          firstItem !== this.parentItem &&
          this.itemIsAvailable(firstItem)
        ) {
          actionMenuItems.push({
            label: "show_info",
            action: () => {
              this.close();
              this.$router.push({
                name: firstItem.media_type,
                params: {
                  id: firstItem.item_id,
                  provider: firstItem.provider,
                },
              });
            },
            icon: "info",
          });
        }
        // add to library
        if (!firstItem.in_library && this.itemIsAvailable(firstItem)) {
          actionMenuItems.push({
            label: "add_library",
            action: () => {
              this.addToLibrary(this.items);
              this.close();
            },
            icon: "favorite_border",
          });
        }
        // remove from library
        if (firstItem.in_library) {
          actionMenuItems.push({
            label: "remove_library",
            action: () => {
              this.removeFromLibrary(this.items);
              this.close();
            },
            icon: "favorite",
          });
        }
        // remove from playlist (playlist tracks only)
        if (
          this.parentItem &&
          this.parentItem.media_type === MediaType.PLAYLIST
        ) {
          const playlist = this.parentItem as Playlist;
          if (
            firstItem.media_type === MediaType.TRACK &&
            playlist.is_editable
          ) {
            actionMenuItems.push({
              label: "remove_playlist",
              action: () => {
                this.removePlaylistTracks({
                  playlistId: playlist.item_id,
                  tracks: this.items,
                });
                this.close();
              },
              icon: "remove_circle_outline",
            });
          }
        }
        // add to playlist action (tracks only)
        if (firstItem.media_type === "track") {
          actionMenuItems.push({
            label: "add_playlist",
            action: this.showPlaylistsMenu,
            icon: "add_circle_outline",
          });
        }
        // refresh item
        if (!this.itemIsAvailable(firstItem)) {
          actionMenuItems.push({
            label: "refresh_item",
            action: () => {
              this.close();
              this.refreshItems(this.items);
            },
            icon: "refresh",
          });
        }
        this.actionMenuItems = actionMenuItems;
      },
      async showPlaylistsMenu() {
        // get all editable playlists
        const items = [];
        for (const playlist of this.getLibraryPlaylists) {
          if (
            playlist.is_editable &&
            !(
              this.parentItem &&
              this.parentItem.media_type === MediaType.PLAYLIST &&
              playlist.item_id === this.parentItem.item_id
            )
          ) {
            items.push(playlist);
          }
        }
        this.playlists = items;
      },
      addToPlaylist(playlist: Playlist) {
        /// add track(s) to playlist
        this.addPlaylistTracks({
          playlistId: playlist.item_id,
          tracks: this.items,
        });
        this.close();
      },
      itemIsAvailable(item: MediaItem) {
        for (const x of item.provider_ids) {
          if (x.available) return true;
        }
        return false;
      },
      close() {
        this.$emit("input", false);
      },
    },
  });
</script>
