import { createRouter, createWebHistory } from "vue-router";
import HomeView from "../views/Home.vue";
import LibraryArtistsView from "../views/LibraryArtists.vue";
import LibraryTracksView from "../views/LibraryTracks.vue";

const routes = [
  { path: "/", component: HomeView, props: true },
  { path: "/artists", component: LibraryArtistsView, props: true },
  { path: "/tracks", component: LibraryTracksView, props: true }
];

export const setupRouter = function (basePath: string) {
  return createRouter({
    history: createWebHistory(basePath),
    routes
  });
};
