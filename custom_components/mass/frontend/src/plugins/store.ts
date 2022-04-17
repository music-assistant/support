import type { PlayerQueue } from "./api";
import { reactive, type App } from "vue";

interface Store {
  activePlayerQueue?: PlayerQueue;
  isInStandaloneMode: boolean;
  showPlayersMenu: boolean;
  darkTheme: boolean;
  isMobile: boolean;
  topBarTitle: string;
  topBarTransparent: boolean;
}

export const store: Store = reactive({
  activePlayerQueue: undefined,
  isInStandaloneMode: false,
  showPlayersMenu: false,
  darkTheme: false,
  isMobile: false,
  topBarTitle: 'Muaisc Assistant',
  topBarTransparent: false
});
