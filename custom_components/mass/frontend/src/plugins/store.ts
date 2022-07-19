import type { Player } from "./api";
import { reactive } from "vue";
import type { LocationQuery, RouteParams, RouteMeta } from "vue-router";

import type { ContextMenuItem } from "../components/MediaItemContextMenu.vue";

interface Store {
  selectedPlayer?: Player;
  isInStandaloneMode: boolean;
  showPlayersMenu: boolean;
  darkTheme: boolean;
  topBarTitle?: string;
  topBarColor: string;
  topBarTextColor: string;
  defaultTopBarTitle: string;
  topBarContextMenuItems: ContextMenuItem[];
  alwaysShowMenuButton: boolean;
  prevRoutes: Array<{
    name: string;
    params: RouteParams;
    query: LocationQuery;
    meta: RouteMeta;
  }>;
}

export const store: Store = reactive({
  selectedPlayer: undefined,
  isInStandaloneMode: false,
  showPlayersMenu: false,
  darkTheme: false,
  topBarColor: "#424242",
  topBarTextColor: "#ffffff",
  defaultTopBarTitle: "Music Assistant",
  topBarContextMenuItems: [],
  alwaysShowMenuButton: false,
  prevRoutes: [],
});
