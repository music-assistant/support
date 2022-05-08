<template>
  <section>
    <v-progress-linear indeterminate v-if="loading"></v-progress-linear>

    <v-tabs v-model="activePanel" show-arrows grow>
      <v-tab :value="0">{{
        $t("queue_next_items") + " (" + nextItems.length + ")"
      }}</v-tab>
      <v-tab :value="1">{{
        $t("queue_previous_items") + " (" + previousItems.length + ")"
      }}</v-tab>
    </v-tabs>

    <div
      style="
        padding-left: 15px;
        padding-right: -15px;
        padding-top: 10px;
        padding-bottom: 20px;
      "
    >
      <RecycleScroller
        v-slot="{ item }"
        :items="tabItems"
        :item-size="66"
        key-field="item_id"
        page-mode
      >
        <div>
          <v-list-item
            ripple
            @click.stop="onClick(item)"
            @click.right.prevent="onClick(item)"
          >
            <template v-slot:prepend
              ><v-list-item-avatar rounded="0" class="listitem-thumb">
                <MediaItemThumb :item="item" :size="50" /> </v-list-item-avatar
            ></template>

            <!-- title -->
            <template v-slot:title>
              {{ item.name }}

              <b v-if="!item.available"> UNAVAILABLE</b>
            </template>

            <!-- subtitle -->
            <template v-slot:subtitle>
              {{ item.uri }}
            </template>

            <!-- actions -->
            <template v-slot:append>
              <div class="listitem-actions">
                <!-- move up -->
                <div class="listitem-action" v-if="!$vuetify.display.mobile">
                  <v-tooltip anchor="bottom">
                    <template #activator="{ props }">
                      <v-btn
                        variant="plain"
                        ripple
                        v-bind="props"
                        @click="
                          api.queueCommandMoveUp(
                            activePlayerQueue?.queue_id,
                            item.item_id
                          )
                        "
                        @click.prevent
                        @click.stop
                        :icon="mdiArrowUp"
                      >
                      </v-btn>
                    </template>
                    <span>{{ $t("queue_move_up") }}</span>
                  </v-tooltip>
                </div>

                <!-- move down -->
                <div class="listitem-action" v-if="!$vuetify.display.mobile">
                  <v-tooltip anchor="bottom">
                    <template #activator="{ props }">
                      <v-btn
                        variant="plain"
                        ripple
                        v-bind="props"
                        @click="
                          api.queueCommandMoveDown(
                            activePlayerQueue?.queue_id,
                            item.item_id
                          )
                        "
                        @click.prevent
                        @click.stop
                        :icon="mdiArrowDown"
                      >
                      </v-btn>
                    </template>
                    <span>{{ $t("queue_move_down") }}</span>
                  </v-tooltip>
                </div>

                <!-- item duration -->
                <div class="listitem-action">
                  <span>{{ formatDuration(item.duration) }}</span>
                </div>
              </div>
            </template>
          </v-list-item>
          <v-divider></v-divider>
        </div>
      </RecycleScroller>
      <v-alert type="info" v-if="!loading && items.length == 0" style="margin: 20px">{{
        $t("no_content")
      }}</v-alert>
    </div>

    <!-- contextmenu -->
    <v-dialog
      v-model="showContextMenu"
      transition="dialog-bottom-transition"
      overlay-opacity="0.8"
      fullscreen
      :class="$vuetify.display.mobile ? '' : 'padded-overlay'"
      @click="showContextMenu = false"
    >
      <v-card>
        <v-toolbar dark color="primary">
          <v-icon :icon="mdiPlayCircleOutline"></v-icon>
          <v-toolbar-title v-if="selectedItem" style="padding-left: 10px"
            ><b>{{ selectedItem?.name }}</b></v-toolbar-title
          >
          <v-toolbar-title v-else style="padding-left: 10px"
            ><b>{{ $t("settings") }}</b> | {{ activePlayerQueue?.name }}</v-toolbar-title
          >
          <v-btn :icon="mdiClose" dark text @click="closeContextMenu()">{{
            $t("close")
          }}</v-btn>
        </v-toolbar>
        <!-- QueueItem related content menu -->
        <v-card-text v-if="selectedItem">
          <v-list>
            <!-- play now -->
            <v-list-item
              @click="
                api.queueCommandPlayIndex(
                  activePlayerQueue?.queue_id,
                  selectedItem?.item_id
                )
              "
            >
              <v-list-item-avatar style="padding-right: 10px">
                <v-icon :icon="mdiPlayCircleOutline"></v-icon>
              </v-list-item-avatar>
              <v-list-item-title>{{ $t("play_now") }}</v-list-item-title>
            </v-list-item>
            <v-divider></v-divider>

            <!-- play next (move to next in line) -->
            <v-list-item
              @click="
                api.queueCommandMoveNext(
                  activePlayerQueue?.queue_id,
                  selectedItem?.item_id
                )
              "
            >
              <v-list-item-avatar style="padding-right: 10px">
                <v-icon :icon="mdiSkipNextCircleOutline"></v-icon>
              </v-list-item-avatar>
              <v-list-item-title>{{ $t("play_next") }}</v-list-item-title>
            </v-list-item>
            <v-divider></v-divider>

            <!-- move up -->
            <v-list-item
              @click="
                api.queueCommandMoveUp(activePlayerQueue?.queue_id, selectedItem?.item_id)
              "
            >
              <v-list-item-avatar style="padding-right: 10px">
                <v-icon :icon="mdiArrowUp"></v-icon>
              </v-list-item-avatar>
              <v-list-item-title>{{ $t("queue_move_up") }}</v-list-item-title>
            </v-list-item>
            <v-divider></v-divider>

            <!-- move down -->
            <v-list-item
              @click="
                api.queueCommandMoveDown(
                  activePlayerQueue?.queue_id,
                  selectedItem?.item_id
                )
              "
            >
              <v-list-item-avatar style="padding-right: 10px">
                <v-icon :icon="mdiArrowDown"></v-icon>
              </v-list-item-avatar>
              <v-list-item-title>{{ $t("queue_move_down") }}</v-list-item-title>
            </v-list-item>
            <v-divider></v-divider>

            <!-- show info (track only) -->
            <v-list-item
              @click="gotoTrack(selectedItem?.uri)"
              v-if="selectedItem?.media_type == MediaType.TRACK"
            >
              <v-list-item-avatar style="padding-right: 10px">
                <v-icon :icon="mdiInformationOutline"></v-icon>
              </v-list-item-avatar>
              <v-list-item-title>{{ $t("show_info") }}</v-list-item-title>
            </v-list-item>
            <v-divider></v-divider>
          </v-list>
        </v-card-text>
        <!-- PlayerQueue settings related content menu -->
        <v-card-text v-else @click.stop>
          <v-list lines="one">
            <!-- shuffle -->
            <v-list-item>
              <v-select
                :label="$t('shuffle')"
                :prepend-icon="mdiShuffle"
                :model-value="activePlayerQueue?.settings.shuffle_enabled.toString()"
                :items="[
                  { title: $t('on'), value: 'true' },
                  { title: $t('off'), value: 'false' },
                ]"
                @update:model-value="
                  api.playerQueueSettings(activePlayerQueue?.queue_id, {
                    shuffle_enabled: parseBool($event),
                  })
                "
              ></v-select>
            </v-list-item>

            <!-- repeat -->
            <v-list-item>
              <v-select
                :label="$t('repeat')"
                :prepend-icon="mdiRepeat"
                :model-value="activePlayerQueue?.settings.repeat_mode"
                :items="[
                  { title: $t('repeatmode.off'), value: RepeatMode.OFF },
                  { title: $t('repeatmode.one'), value: RepeatMode.ONE },
                  { title: $t('repeatmode.all'), value: RepeatMode.ALL },
                ]"
                @update:model-value="
                  api.playerQueueSettings(activePlayerQueue?.queue_id, {
                    repeat_mode: $event,
                  })
                "
              ></v-select>
            </v-list-item>

            <!-- volume normalization enabled -->
            <v-list-item>
              <v-select
                :label="$t('volume_normalization')"
                :prepend-icon="mdiChartBar"
                :model-value="
                  activePlayerQueue?.settings.volume_normalization_enabled.toString()
                "
                :items="[
                  { title: $t('on'), value: 'true' },
                  { title: $t('off'), value: 'false' },
                ]"
                @update:model-value="
                  api.playerQueueSettings(activePlayerQueue?.queue_id, {
                    volume_normalization_enabled: parseBool($event),
                  })
                "
              ></v-select>
            </v-list-item>

            <!-- volume normalization target -->
            <v-list-item>
              <v-slider
                style="
                  margin-left: 40px;
                  padding-top: 0;
                  padding-bottom: 0;
                  margin-top: -40px;
                "
                :disabled="!activePlayerQueue?.settings.volume_normalization_enabled"
                color="primary"
                :min="-50"
                :max="10"
                :step="0.5"
                :model-value="activePlayerQueue?.settings.volume_normalization_target"
                @update:model-value="
                  api.playerQueueSettings(activePlayerQueue?.queue_id, {
                    volume_normalization_target: $event,
                  })
                "
              >
                <template v-slot:append>
                  <div class="text-caption">
                    {{
                      $t("volume_normalization_target", [
                        activePlayerQueue?.settings.volume_normalization_target,
                      ])
                    }}
                  </div>
                </template>
              </v-slider>
            </v-list-item>

            <!-- crossfade mode -->
            <v-list-item>
              <v-select
                :model-value="activePlayerQueue?.settings.crossfade_mode"
                :label="$t('crossfade')"
                :prepend-icon="mdiCameraTimer"
                :items="[
                  {
                    title: $t('crossfademode.disabled'),
                    value: CrossFadeMode.DISABLED,
                  },
                  {
                    title: $t('crossfademode.strict'),
                    value: CrossFadeMode.STRICT,
                  },
                  {
                    title: $t('crossfademode.smart'),
                    value: CrossFadeMode.SMART,
                  },
                  {
                    title: $t('crossfademode.always'),
                    value: CrossFadeMode.ALWAYS,
                  },
                ]"
                @update:model-value="
                  api.playerQueueSettings(activePlayerQueue?.queue_id, {
                    crossfade_mode: $event,
                  })
                "
              ></v-select>
            </v-list-item>

            <!-- crossfade duration -->
            <v-list-item>
              <v-slider
                style="
                  margin-left: 40px;
                  padding-top: 0;
                  padding-bottom: 0;
                  margin-top: -40px;
                "
                :disabled="
                  activePlayerQueue?.settings.crossfade_mode == CrossFadeMode.DISABLED
                "
                color="primary"
                :label="$t('crossfade_duration')"
                :min="1"
                :max="10"
                :step="1"
                :model-value="activePlayerQueue?.settings.crossfade_duration"
                @update:model-value="
                  api.playerQueueSettings(activePlayerQueue?.queue_id, {
                    crossfade_duration: $event,
                  })
                "
              >
                <template v-slot:append>
                  <div class="text-caption">
                    {{
                      $t("crossfade_duration", [
                        activePlayerQueue?.settings.crossfade_duration,
                      ])
                    }}
                  </div>
                </template>
              </v-slider>
            </v-list-item>

            <!-- clear queue button -->
            <v-list-item>
              <v-btn
                :disabled="items.length == 0"
                width="100%"
                @click="api.queueCommandClear(activePlayerQueue?.queue_id)"
                >{{ $t("queue_clear") }}</v-btn
              >
            </v-list-item>
          </v-list>
        </v-card-text>
      </v-card>
    </v-dialog>
  </section>
</template>

<script setup lang="ts">
import {
  mdiSkipNextCircleOutline,
  mdiPlayCircleOutline,
  mdiClose,
  mdiArrowUp,
  mdiArrowDown,
  mdiInformationOutline,
  mdiShuffle,
  mdiRepeat,
  mdiChartBar,
  mdiCameraTimer,
} from "@mdi/js";
import { ref } from "@vue/reactivity";
import { RecycleScroller } from "vue-virtual-scroller";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";
import type { QueueItem, MassEvent } from "../plugins/api";
import { RepeatMode, CrossFadeMode, MassEventType, MediaType } from "../plugins/api";
import api from "../plugins/api";
import { computed, onBeforeUnmount, watchEffect } from "vue";
import { store } from "../plugins/store";
import { formatDuration, parseBool } from "../utils";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import MediaItemThumb from "../components/MediaItemThumb.vue";

// global refs
const { t } = useI18n();
const router = useRouter();

// local refs
const activePanel = ref(0);
const selectedItem = ref<QueueItem>();
const showContextMenu = ref(false);

const items = ref<QueueItem[]>([]);
const loading = ref(true);

// computed properties
const activePlayerQueue = computed(() => {
  if (store.selectedPlayer) {
    return api.queues[store.selectedPlayer.active_queue];
  }
  return undefined;
});
const nextItems = computed(() => {
  if (activePlayerQueue.value) {
    return items.value.slice(activePlayerQueue.value.current_index);
  } else return [];
});
const previousItems = computed(() => {
  if (activePlayerQueue.value) {
    return items.value.slice(0, activePlayerQueue.value.current_index);
  } else return [];
});
const tabItems = computed(() => {
  if (activePanel.value == 1) return previousItems.value;
  else return nextItems.value;
});

// listen for item updates to refresh items when that happens
const unsub = api.subscribe(MassEventType.QUEUE_ITEMS_UPDATED, (evt: MassEvent) => {
  if (evt.object_id == activePlayerQueue.value?.queue_id) {
    loadItems();
  }
});
onBeforeUnmount(unsub);
onBeforeUnmount(() => {
  store.customContextMenuCallback = undefined;
});

// methods
const loadItems = async function () {
  loading.value = true;
  if (activePlayerQueue.value) {
    store.topBarTitle = t("queue") + ": " + activePlayerQueue.value.name;
    store.customContextMenuCallback = () => {
      selectedItem.value = undefined;
      showContextMenu.value = true;
    };
    items.value = await api.getPlayerQueueItems(activePlayerQueue.value.queue_id);
  } else {
    store.topBarTitle = t("queue");
    items.value = [];
    store.customContextMenuCallback = undefined;
  }
  loading.value = false;
};

const onClick = function (item: QueueItem) {
  // mediaItem in the list is clicked
  selectedItem.value = item;
  showContextMenu.value = true;
};

const gotoTrack = function (trackUri: string) {
  const provider = trackUri.split(":")[0];
  const item_id = trackUri.split("/").pop();
  router.push({
    name: "track",
    params: { item_id, provider },
  });
};

const closeContextMenu = function () {
  selectedItem.value = undefined;
  showContextMenu.value = false;
};

// watchers
watchEffect(() => {
  if (activePlayerQueue.value) {
    loadItems();
  }
  loading.value = false;
});
</script>

<style scoped>
.listitem-actions {
  display: flex;
  justify-content: end;
  width: auto;
  height: 50px;
  vertical-align: middle;
  align-items: center;
  padding: 0px;
}
.listitem-action {
  padding-left: 5px;
}
.listitem-thumb {
  padding-left: 0px;
  margin-right: 10px;
  margin-left: -15px;
  width: 50px;
  height: 50px;
}
</style>
