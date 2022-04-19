import type { PlayerQueue } from "./api";
import { reactive, type App } from "vue";
import type { MediaItemType } from "./api";

interface Store {
  activePlayerQueue?: PlayerQueue;
  isInStandaloneMode: boolean;
  showPlayersMenu: boolean;
  showContextMenu: boolean;
  darkTheme: boolean;
  topBarTitle?: string;
  topBarTransparent: boolean;
  topBarDefaultColor: string;
  defaultTopBarTitle: string;
  contextMenuItems: MediaItemType[];
  contextMenuParentItem?: MediaItemType;
}

export const store: Store = reactive({
  activePlayerQueue: undefined,
  isInStandaloneMode: false,
  showPlayersMenu: false,
  showContextMenu: false,
  darkTheme: false,
  topBarTransparent: false,
  topBarDefaultColor: "#03A9F4",
  defaultTopBarTitle: "",
  contextMenuItems: [],
  contextMenuParentItem: undefined
});
