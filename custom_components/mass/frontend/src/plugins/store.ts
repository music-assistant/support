import type { Player } from "./api";
import { reactive } from "vue";

interface Store {
  players: { [player_id: string]: Player };
  activePlayer?: string;
}

export const store: Store = reactive({
  players: {},
  activePlayer: undefined,
});
