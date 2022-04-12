import { defineStore } from "pinia";

export const mainStore = defineStore({
  id: "main",
  state: () => ({
    isInStandaloneMode: false
  }),
  getters: {
    // doubleCount: (state) => state.counter * 2
  },
  actions: {
    // increment() {
    //   this.counter++
    // }
  }
});
