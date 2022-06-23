import type { Player } from "./api";
import { reactive } from "vue";
import type { MediaItemType } from "./api";
import type { LocationQuery, RouteParams, RouteMeta } from "vue-router";

interface ContextMenuItem {
  title: string;
  link: () => void;
}

interface Store {
  selectedPlayer?: Player;
  isInStandaloneMode: boolean;
  showPlayersMenu: boolean;
  showContextMenu: boolean;
  darkTheme: boolean;
  topBarTitle?: string;
  topBarColor: string;
  topBarTextColor: string;
  defaultTopBarTitle: string;
  contextMenuItems: MediaItemType[];
  contextMenuParentItem?: MediaItemType;
  customContextMenuCallback?: () => void;
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
  showContextMenu: false,
  darkTheme: false,
  topBarColor: "#424242",
  topBarTextColor: "#ffffff",
  defaultTopBarTitle: "Music Assistant",
  contextMenuItems: [],
  contextMenuParentItem: undefined,
  topBarContextMenuItems: [],
  alwaysShowMenuButton: false,
  prevRoutes: [],
});
