import type { PlayerQueue } from "./api";
import { reactive } from "vue";
import type { MediaItemType } from "./api";
import type { LocationQuery, RouteParams, RouteMeta } from "vue-router";

interface Store {
  activePlayerQueue?: PlayerQueue;
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
  prevRoutes: Array<{
    name: string;
    params: RouteParams;
    query: LocationQuery;
    meta: RouteMeta;
  }>;
}

export const store: Store = reactive({
  activePlayerQueue: undefined,
  isInStandaloneMode: false,
  showPlayersMenu: false,
  showContextMenu: false,
  darkTheme: false,
  topBarColor: "#424242",
  topBarTextColor: "#ffffff",
  defaultTopBarTitle: "Music Assistant",
  contextMenuItems: [],
  contextMenuParentItem: undefined,
  prevRoutes: [],
});
