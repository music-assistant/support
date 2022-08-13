import { createRouter, createWebHashHistory, type Router } from 'vue-router';
import HomeView from '../views/HomeView.vue';
import BrowseView from '../views/BrowseView.vue';
import LibraryArtists from '../views/LibraryArtists.vue';
import LibraryTracks from '../views/LibraryTracks.vue';
import LibraryAlbums from '@/views/LibraryAlbums.vue';
import LibraryPlaylists from '@/views/LibraryPlaylists.vue';
import LibraryRadios from '@/views/LibraryRadios.vue';
import ArtistDetails from '@/views/ArtistDetails.vue';
import AlbumDetails from '@/views/AlbumDetails.vue';
import TrackDetails from '@/views/TrackDetails.vue';
import RadioDetails from '@/views/RadioDetails.vue';
import PlaylistDetails from '@/views/PlaylistDetails.vue';
import PlayerQueue from '@/views/PlayerQueue.vue';
import { store } from './store';

declare module 'vue-router' {
  interface RouteMeta {
    scrollPos?: number;
  }
}

const routes = [
  { name: 'home', path: '/', component: HomeView, props: true },
  { name: 'browse', path: '/browse', component: BrowseView, props: true },
  {
    name: 'artists',
    path: '/artists',
    component: LibraryArtists,
    props: true,
  },
  {
    name: 'tracks',
    path: '/tracks',
    component: LibraryTracks,
    props: true,
  },
  {
    name: 'albums',
    path: '/albums',
    component: LibraryAlbums,
    props: true,
  },
  {
    name: 'playlists',
    path: '/playlists',
    component: LibraryPlaylists,
    props: true,
  },
  {
    name: 'radios',
    path: '/radios',
    component: LibraryRadios,
    props: true,
  },
  {
    name: 'artist',
    path: '/artists/:provider/:item_id',
    component: ArtistDetails,
    props: true,
  },
  {
    name: 'album',
    path: '/albums/:provider/:item_id',
    component: AlbumDetails,
    props: true,
  },
  {
    name: 'track',
    path: '/tracks/:provider/:item_id',
    component: TrackDetails,
    props: true,
  },
  {
    name: 'radio',
    path: '/radio/:provider/:item_id',
    component: RadioDetails,
    props: true,
  },
  {
    name: 'playlist',
    path: '/playlists/:provider/:item_id',
    component: PlaylistDetails,
    props: true,
  },
  {
    name: 'playerqueue',
    path: '/playerqueue',
    component: PlayerQueue,
    props: true,
  },
];

const router: Router = createRouter({
  history: createWebHashHistory(),
  routes,
});

router.beforeEach((to, from) => {
  if (!from.name) return;
  if (to.params['backnav']) return;
  from.meta.scrollPos = window.scrollY;
  store.prevRoutes.push({
    name: from.name as string,
    query: from.query,
    params: from.params,
    meta: from.meta,
  });
});

export default router;
