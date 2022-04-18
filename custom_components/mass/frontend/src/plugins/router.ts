import { createRouter, createWebHashHistory } from "vue-router";
import HomeView from "../views/Home.vue";
import LibraryArtistsView from "../views/LibraryArtists.vue";
import LibraryTracksView from "../views/LibraryTracks.vue";
import LibraryAlbumsView from "@/views/LibraryAlbums.vue";
import LibraryPlaylistsView from "@/views/LibraryPlaylists.vue";
import LibraryRadiosView from "@/views/LibraryRadios.vue";

const routes = [
  { path: "/", component: HomeView, props: true },
  { path: "/artists", component: LibraryArtistsView, props: true },
  { path: "/tracks", component: LibraryTracksView, props: true },
  { path: "/albums", component: LibraryAlbumsView, props: true },
  { path: "/playlists", component: LibraryPlaylistsView, props: true },
  { path: "/radios", component: LibraryRadiosView, props: true }
];

export default createRouter({
  history: createWebHashHistory(),
  routes
});
