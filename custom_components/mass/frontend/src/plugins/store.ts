import type { PlayerQueue } from "./api";
import { reactive, type App } from "vue";

interface Store {
  activePlayerQueue?: PlayerQueue;
  isInStandaloneMode: boolean;
  showPlayersMenu: boolean;
  darkTheme: boolean;
  topBarTitle?: string;
  topBarTransparent: boolean;
  topBarDefaultColor: string;
  defaultTopBarTitle: string;
}

export const store: Store = reactive({
  activePlayerQueue: undefined,
  isInStandaloneMode: false,
  showPlayersMenu: false,
  darkTheme: false,
  topBarTransparent: false,
  topBarDefaultColor: '#03A9F4',
  defaultTopBarTitle: 'Music Assistant'
});
