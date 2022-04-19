import { createRouter, createWebHashHistory } from "vue-router";
import HomeView from "../views/Home.vue";
import LibraryArtistsView from "../views/LibraryArtists.vue";
import LibraryTracksView from "../views/LibraryTracks.vue";
import LibraryAlbumsView from "@/views/LibraryAlbums.vue";
import LibraryPlaylistsView from "@/views/LibraryPlaylists.vue";
import LibraryRadiosView from "@/views/LibraryRadios.vue";
import ArtistDetailsView from "@/views/ArtistDetails.vue";
import AlbumDetailsView from "@/views/AlbumDetails.vue";
import TrackDetailsView from "@/views/TrackDetails.vue";
import PlaylistDetailsView from "@/views/PlaylistDetails.vue";

const routes = [
  { name: "home", path: "/", component: HomeView, props: true },
  {
    name: "artists",
    path: "/artists",
    component: LibraryArtistsView,
    props: true
  },
  {
    name: "tracks",
    path: "/tracks",
    component: LibraryTracksView,
    props: true
  },
  {
    name: "albums",
    path: "/albums",
    component: LibraryAlbumsView,
    props: true
  },
  {
    name: "playlists",
    path: "/playlists",
    component: LibraryPlaylistsView,
    props: true
  },
  {
    name: "radios",
    path: "/radios",
    component: LibraryRadiosView,
    props: true
  },
  { name: "artist", path: "/artist", component: ArtistDetailsView, props: true },
  { name: "album", path: "/album", component: AlbumDetailsView, props: true },
  { name: "track", path: "/track", component: TrackDetailsView, props: true },
  { name: "playlist", path: "/playlist", component: PlaylistDetailsView, props: true }
];

export default createRouter({
  history: createWebHashHistory(),
  routes
});
