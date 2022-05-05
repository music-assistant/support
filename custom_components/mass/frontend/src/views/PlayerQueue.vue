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
      <v-list>
        <div v-for="item of tabItems" :key="item.item_id">
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
                            store.activePlayerQueue.queue_id,
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
                            store.activePlayerQueue.queue_id,
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
      </v-list>
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
            ><b>{{ $t("settings") }}</b> |
            {{ store.activePlayerQueue?.name }}</v-toolbar-title
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
                  store.activePlayerQueue.queue_id,
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
                  store.activePlayerQueue.queue_id,
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
                api.queueCommandMoveUp(
                  store.activePlayerQueue.queue_id,
                  selectedItem?.item_id
                )
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
                  store.activePlayerQueue.queue_id,
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
              <template v-slot:prepend>
                <v-list-item-avatar style="padding-right: 10px">
                  <v-icon :icon="mdiShuffle"></v-icon>
                </v-list-item-avatar>
              </template>
              <template v-slot:title>
                {{ $t("shuffle_enabled") }}
              </template>
              <template v-slot:append>
                <v-switch
                  class="listitem-actions"
                  color="primary"
                  density="compact"
                  v-model="store.activePlayerQueue.shuffle_enabled"
                  @update:model-value="
                    api.queueCommandShuffle(store.activePlayerQueue?.queue_id, $event)
                  "
                ></v-switch>
              </template>
            </v-list-item>

            <!-- repeat -->
            <v-list-item>
              <template v-slot:prepend>
                <v-list-item-avatar style="padding-right: 10px">
                  <v-icon :icon="mdiRepeat"></v-icon>
                </v-list-item-avatar>
              </template>
              <template v-slot:title>
                {{ $t("repeat_enabled") }}
              </template>
              <template v-slot:append>
                <v-switch
                  class="listitem-actions"
                  color="primary"
                  v-model="store.activePlayerQueue.repeat_enabled"
                  @update:model-value="
                    api.queueCommandRepeat(store.activePlayerQueue?.queue_id, $event)
                  "
                ></v-switch>
              </template>
            </v-list-item>

            <!-- volume normalization enabled -->
            <v-list-item>
              <template v-slot:prepend>
                <v-list-item-avatar style="padding-right: 10px">
                  <v-icon :icon="mdiChartBar"></v-icon>
                </v-list-item-avatar>
              </template>
              <template v-slot:title>
                {{ $t("volume_normalization_enabled") }}
              </template>
              <template v-slot:append>
                <v-switch
                  class="listitem-actions"
                  color="primary"
                  v-model="store.activePlayerQueue.volume_normalization_enabled"
                  @update:model-value="
                    api.queueCommandSetVolumeNormalizationEnabled(
                      store.activePlayerQueue?.queue_id,
                      $event
                    )
                  "
                ></v-switch>
              </template>
            </v-list-item>

            <!-- volume normalization target -->
            <v-list-item>
              <template v-slot:prepend>
                <v-list-item-avatar style="padding-right: 10px">
                  <v-icon :icon="mdiChartBar"></v-icon>
                </v-list-item-avatar>
              </template>
              <template v-slot:title>
                {{ $t("volume_normalization_target") }}
                </template>
                <template v-slot:append>
                <v-slider
                style="vertical-align: middle; margin-top: 15px;"
                  color="primary"
                  thumb-label="always"
                  :min="-50"
                  :max="10"
                  v-model="store.activePlayerQueue.volume_normalization_target"
                  @update:model-value="
                    api.queueCommandSetVolumeNormalizationTarget(
                      store.activePlayerQueue?.queue_id,
                      $event
                    )
                  "
                ></v-slider>
              </template>
            </v-list-item>

            <!-- crossfade duration -->
            <v-list-item>
              <template v-slot:prepend>
                <v-list-item-avatar style="padding-right: 15px">
                  <v-icon :icon="mdiCameraTimer"></v-icon>
                </v-list-item-avatar>
              </template>
              <template v-slot:title>
                {{ $t("crossfade_duration") }}
                </template>
                <template v-slot:append>
                <v-slider
                  style="vertical-align: middle;margin-top: 10px;"
                  color="primary"
                  thumb-label="always"
                  :min="0"
                  :max="10"
                  v-model="store.activePlayerQueue.crossfade_duration"
                  @update:model-value="
                    api.queueCommandSetCrossfadeDuration(
                      store.activePlayerQueue?.queue_id,
                      $event
                    )
                  "
                ></v-slider>
              </template>
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
  mdiCameraTimer

  } from "@mdi/js";
import { ref } from "@vue/reactivity";
import { type QueueItem, MassEventType, type MassEvent , MediaType} from "../plugins/api";
import api from "../plugins/api";
import { computed, onBeforeUnmount, watchEffect } from "vue";
import { store } from "../plugins/store";
import { formatDuration } from "../utils";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

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
const nextItems = computed(() => {
  if (store.activePlayerQueue) {
    return items.value.slice(store.activePlayerQueue.current_index);
  } else return [];
});
const previousItems = computed(() => {
  if (store.activePlayerQueue) {
    return items.value.slice(0, store.activePlayerQueue.current_index);
  } else return [];
});
const tabItems = computed(() => {
  if (activePanel.value == 1) return previousItems.value;
  else return nextItems.value;
});

// listen for item updates to refresh items when that happens
const unsub = api.subscribe(
  MassEventType.QUEUE_ITEMS_UPDATED,
  (evt: MassEvent) => {
    if (evt.object_id == store.activePlayerQueue?.queue_id) {
      loadItems();
    }
  }
);
onBeforeUnmount(unsub);

// methods
const loadItems = async function () {
  loading.value = true;
  if (store.activePlayerQueue) {
    store.topBarTitle = t("queue") + ": " + store.activePlayerQueue.name;
    store.customContextMenuCallback = () => {
      selectedItem.value = undefined;
      showContextMenu.value = true;
    }
    items.value = await api.getPlayerQueueItems(
      store.activePlayerQueue.queue_id
    );
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

const onTest = function(val) {
  console.log("bval", val)
}

const gotoTrack = function (trackUri: string) {
  const provider = trackUri.split(':')[0];
  const item_id = trackUri.split("/").pop();
  router.push({
      name: "track",
      params: { item_id, provider },
    });
}

const closeContextMenu = function() {
  selectedItem.value = undefined;
  showContextMenu.value = false;
}

// watchers
watchEffect(() => {
  if (store.activePlayerQueue) {
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
