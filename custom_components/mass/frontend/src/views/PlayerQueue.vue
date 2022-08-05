<template>
  <section>
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
      <v-progress-linear indeterminate v-if="loading"></v-progress-linear>
      <v-alert
        v-if="activePlayerQueue && activePlayerQueue?.radio_source.length > 0"
        color="primary"
        theme="dark"
        :icon="mdiRadioTower"
        prominent
        style="margin-right: 10px"
      >
        <b>{{ $t("queue_radio_enabled") }}</b>
        <br />
        {{
          $t("queue_radio_based_on", [
            $t(activePlayerQueue?.radio_source[0].media_type),
          ])
        }}
        <b
          ><a
            @click="
              activePlayerQueue
                ? gotoItem(activePlayerQueue?.radio_source[0])
                : ''
            "
            >{{ activePlayerQueue?.radio_source[0].name }}</a
          ></b
        ><span v-if="activePlayerQueue?.radio_source.length > 1">
          (+{{ activePlayerQueue?.radio_source.length - 1 }})</span
        >
      </v-alert>
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
            :disabled="item.item_id == curQueueItem?.item_id"
          >
            <template v-slot:prepend>
              <div class="listitem-thumb">
                <MediaItemThumb
                  :item="item"
                  :size="50"
                  width="50px"
                  height="50px"
                /></div
            ></template>

            <!-- title -->
            <template v-slot:title>
              {{ item.media_item ? item.media_item.name : item.name }}
            </template>

            <!-- subtitle -->
            <template v-slot:subtitle>
              <div
                v-if="
                  item.media_item &&
                  'artists' in item.media_item &&
                  item.media_item.artists.length > 0
                "
              >
                {{ item.media_item.artists[0].name }}
              </div>
              <div v-else-if="item.media_item">
                {{ item.media_item.metadata.description }}
              </div>
              <div v-else>{{ item.uri }}</div>
            </template>

            <!-- actions -->
            <template v-slot:append>
              <div class="listitem-actions">
                <!-- item duration -->
                <div
                  class="listitem-action"
                  v-if="
                    item.duration &&
                    item.media_item?.media_type != MediaType.RADIO
                  "
                >
                  <span>{{ formatDuration(item.duration) }}</span>
                </div>

                <!-- move up -->
                <div class="listitem-action" v-if="!$vuetify.display.mobile">
                  <v-tooltip location="bottom">
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
                  <v-tooltip location="bottom">
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
              </div>
            </template>
          </v-list-item>
          <v-divider></v-divider>
        </div>
      </RecycleScroller>
      <v-alert
        type="info"
        v-if="!loading && items.length == 0"
        style="margin: 20px"
        >{{ $t("no_content") }}</v-alert
      >
    </div>

    <!-- contextmenu -->
    <v-overlay
      v-model="showContextMenu"
      class="align-center justify-center"
      :scrim="false"
    >
      <v-menu class="fullscreen-menu" v-model="showContextMenu">
        <v-card>
          <v-toolbar sense dark color="primary">
            <v-icon :icon="mdiPlayCircleOutline"></v-icon>
            <v-toolbar-title v-if="selectedItem" style="padding-left: 10px"
              ><b>{{
                truncateString(
                  selectedItem?.name || "",
                  $vuetify.display.mobile ? 20 : 150
                )
              }}</b></v-toolbar-title
            >
            <v-toolbar-title v-else style="padding-left: 10px"
              ><b>{{ $t("settings") }}</b> |
              {{ activePlayerQueue?.name }}</v-toolbar-title
            >
            <v-btn
              :icon="mdiClose"
              dark
              text
              @click="closeContextMenu()"
            ></v-btn>
          </v-toolbar>

          <!-- QueueItem related content menu -->
          <v-card-text v-if="selectedItem">
            <v-list>
              <!-- play now -->
              <v-list-item
                @click="queueCommand(selectedItem, 'play_now')"
                :title="$t('play_now')"
              >
                <template v-slot:prepend>
                  <v-avatar style="padding-right: 10px">
                    <v-icon :icon="mdiPlayCircleOutline"></v-icon>
                  </v-avatar>
                </template>
              </v-list-item>
              <v-divider></v-divider>

              <!-- play next (move to next in line) -->
              <v-list-item
                @click="queueCommand(selectedItem, 'move_next')"
                :title="$t('play_next')"
              >
                <template v-slot:prepend>
                  <v-avatar style="padding-right: 10px">
                    <v-icon :icon="mdiSkipNextCircleOutline"></v-icon>
                  </v-avatar>
                </template>
              </v-list-item>
              <v-divider></v-divider>

              <!-- move up -->
              <v-list-item
                @click="queueCommand(selectedItem, 'up')"
                :title="$t('queue_move_up')"
              >
                <template v-slot:prepend>
                  <v-avatar style="padding-right: 10px">
                    <v-icon :icon="mdiArrowUp"></v-icon> </v-avatar
                ></template>
              </v-list-item>
              <v-divider></v-divider>

              <!-- move down -->
              <v-list-item
                @click="queueCommand(selectedItem, 'down')"
                :title="$t('queue_move_down')"
              >
                <template v-slot:prepend>
                  <v-avatar style="padding-right: 10px">
                    <v-icon :icon="mdiArrowDown"></v-icon>
                  </v-avatar>
                </template>
              </v-list-item>
              <v-divider></v-divider>

              <!-- delete -->
              <v-list-item
                @click="queueCommand(selectedItem, 'delete')"
                :title="$t('queue_delete')"
              >
                <template v-slot:prepend>
                  <v-avatar style="padding-right: 10px">
                    <v-icon :icon="mdiDelete"></v-icon> </v-avatar
                ></template>
              </v-list-item>
              <v-divider></v-divider>

              <!-- show info (track only) -->
              <v-list-item
                @click="
                  selectedItem?.media_item
                    ? gotoItem(selectedItem.media_item)
                    : ''
                "
                :title="$t('show_info')"
                v-if="selectedItem?.media_item?.media_type == MediaType.TRACK"
              >
                <template v-slot:prepend>
                  <v-avatar style="padding-right: 10px">
                    <v-icon :icon="mdiInformationOutline"></v-icon> </v-avatar
                ></template>
              </v-list-item>
              <v-divider></v-divider>
            </v-list>
          </v-card-text>

          <!-- PlayerQueue settings related content menu -->
          <v-card-text v-else @click.stop>
            <v-expansion-panels variant="accordion" v-model="panel">
              <!-- base settings -->
              <v-expansion-panel>
                <v-expansion-panel-title>
                  {{ t("basic_settings") }}
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <v-list
                    lines="one"
                    style="margin-left: -15px; margin-right: -15px"
                  >
                    <!-- shuffle -->
                    <v-list-item>
                      <v-select
                        :label="$t('shuffle')"
                        :prepend-icon="
                          $vuetify.display.mobile ? '' : mdiShuffle
                        "
                        :model-value="
                          activePlayerQueue?.settings.shuffle_enabled.toString()
                        "
                        :items="[
                          { title: $t('on'), value: 'true' },
                          { title: $t('off'), value: 'false' },
                        ]"
                        @update:model-value="
                          api.playerQueueSettings(activePlayerQueue?.queue_id, {
                            shuffle_enabled: parseBool($event),
                          })
                        "
                        hide-details
                      ></v-select>
                    </v-list-item>

                    <!-- repeat -->
                    <v-list-item>
                      <v-select
                        :label="$t('repeat')"
                        :prepend-icon="$vuetify.display.mobile ? '' : mdiRepeat"
                        :model-value="activePlayerQueue?.settings.repeat_mode"
                        hide-details
                        :items="[
                          {
                            title: $t('repeatmode.off'),
                            value: RepeatMode.OFF,
                          },
                          {
                            title: $t('repeatmode.one'),
                            value: RepeatMode.ONE,
                          },
                          {
                            title: $t('repeatmode.all'),
                            value: RepeatMode.ALL,
                          },
                        ]"
                        @update:model-value="
                          api.playerQueueSettings(activePlayerQueue?.queue_id, {
                            repeat_mode: $event,
                          })
                        "
                      ></v-select>
                    </v-list-item>

                    <!-- crossfade mode -->
                    <v-list-item>
                      <v-select
                        :model-value="
                          activePlayerQueue?.settings.crossfade_mode
                        "
                        :label="$t('crossfade')"
                        :prepend-icon="
                          $vuetify.display.mobile ? '' : mdiCameraTimer
                        "
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
                        hide-details
                      ></v-select>
                    </v-list-item>

                    <!-- crossfade duration -->
                    <v-list-item>
                      <div
                        style="
                          margin-top: 10px;
                          height: 70px;
                          padding-bottom: 10px;
                        "
                      >
                        <div
                          class="text-caption"
                          :style="
                            $vuetify.display.mobile ? '' : 'margin-left: 40px;'
                          "
                        >
                          {{ $t("crossfade_duration") }}
                        </div>
                        <v-slider
                          style="margin-left: 0; margin-right: 0"
                          :disabled="
                            activePlayerQueue?.settings.crossfade_mode ==
                            CrossFadeMode.DISABLED
                          "
                          color="primary"
                          :min="1"
                          :max="10"
                          :step="1"
                          :prepend-icon="
                            $vuetify.display.mobile ? '' : mdiCameraTimer
                          "
                          :model-value="
                            activePlayerQueue?.settings.crossfade_duration
                          "
                          @update:model-value="
                            api.playerQueueSettings(
                              activePlayerQueue?.queue_id || '',
                              {
                                crossfade_duration: $event,
                              }
                            )
                          "
                        >
                          <template v-slot:append>
                            <div class="text-caption">
                              {{
                                $t("crossfade_seconds", [
                                  activePlayerQueue?.settings
                                    .crossfade_duration,
                                ])
                              }}
                            </div>
                          </template>
                        </v-slider>
                      </div>
                    </v-list-item>

                    <!-- announce volume increase -->
                    <v-list-item>
                      <div
                        style="
                          margin-top: 10px;
                          height: 70px;
                          padding-bottom: 10px;
                        "
                      >
                        <div
                          class="text-caption"
                          :style="
                            $vuetify.display.mobile ? '' : 'margin-left: 40px'
                          "
                        >
                          {{ $t("announce_volume_increase") }}
                        </div>

                        <v-slider
                          style="margin-left: 0; margin-right: 0"
                          color="primary"
                          :label="$t('announce_volume_increase')"
                          :min="1"
                          :max="100"
                          :step="1"
                          :prepend-icon="
                            $vuetify.display.mobile ? '' : mdiVolumePlus
                          "
                          :model-value="
                            activePlayerQueue?.settings.announce_volume_increase
                          "
                          @update:model-value="
                            api.playerQueueSettings(
                              activePlayerQueue?.queue_id || '',
                              {
                                announce_volume_increase: $event,
                              }
                            )
                          "
                        >
                        </v-slider>
                      </div>
                    </v-list-item>
                  </v-list>
                </v-expansion-panel-text>
              </v-expansion-panel>
              <!-- advanced/pro settings -->
              <v-expansion-panel>
                <v-expansion-panel-title>
                  {{ t("advanced_settings") }}
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <v-list
                    lines="one"
                    style="margin-left: -15px; margin-right: -15px"
                  >
                    <!-- volume normalization enabled -->
                    <v-list-item>
                      <v-select
                        :label="$t('volume_normalization')"
                        :prepend-icon="
                          $vuetify.display.mobile ? '' : mdiChartBar
                        "
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
                        hide-details
                      ></v-select>
                    </v-list-item>

                    <!-- volume normalization target -->
                    <v-list-item>
                      <div
                        style="
                          margin-top: 10px;
                          height: 70px;
                          padding-bottom: 10px;
                        "
                      >
                        <div
                          class="text-caption"
                          :style="
                            $vuetify.display.mobile ? '' : 'margin-left: 40px;'
                          "
                        >
                          {{ $t("volume_normalization_target") }}
                        </div>
                        <v-slider
                          style="margin-left: 0; margin-right: 0"
                          :disabled="
                            !activePlayerQueue?.settings
                              .volume_normalization_enabled
                          "
                          :prepend-icon="
                            $vuetify.display.mobile ? '' : mdiChartBar
                          "
                          color="primary"
                          :min="-40"
                          :max="0"
                          :step="0.5"
                          :model-value="
                            activePlayerQueue?.settings
                              .volume_normalization_target
                          "
                          @update:model-value="
                            api.playerQueueSettings(
                              activePlayerQueue?.queue_id,
                              {
                                volume_normalization_target: $event,
                              }
                            )
                          "
                          hide-details
                        >
                          <template v-slot:append>
                            <div class="text-caption">
                              {{
                                $t("volume_normalization_lufs", [
                                  activePlayerQueue?.settings
                                    .volume_normalization_target,
                                ])
                              }}
                            </div>
                          </template>
                        </v-slider>
                      </div>
                    </v-list-item>

                    <!-- stream type -->
                    <v-list-item>
                      <v-select
                        :model-value="activePlayerQueue?.settings.stream_type"
                        :label="$t('stream_type')"
                        :prepend-icon="
                          $vuetify.display.mobile ? '' : mdiCastConnected
                        "
                        :items="['mp3', 'flac', 'wav', 'aac']"
                        @update:model-value="
                          api.playerQueueSettings(activePlayerQueue?.queue_id, {
                            stream_type: $event,
                          })
                        "
                        hide-details
                      ></v-select>
                    </v-list-item>

                    <!-- max sample rate -->
                    <v-list-item>
                      <v-select
                        :model-value="
                          activePlayerQueue?.settings.max_sample_rate
                        "
                        :label="$t('max_sample_rate')"
                        :prepend-icon="
                          $vuetify.display.mobile ? '' : mdiCastConnected
                        "
                        :items="[
                          '44100',
                          '48000',
                          '88200',
                          '96000',
                          '176000',
                          '192000',
                          '352000',
                          '384000',
                        ]"
                        @update:model-value="
                          api.playerQueueSettings(activePlayerQueue?.queue_id, {
                            max_sample_rate: $event,
                          })
                        "
                        hide-details
                      ></v-select>
                    </v-list-item>

                    <!-- metadata mode -->
                    <v-list-item>
                      <v-select
                        :model-value="activePlayerQueue?.settings.metadata_mode"
                        :label="$t('metadata_mode.title')"
                        :prepend-icon="
                          $vuetify.display.mobile ? '' : mdiCastConnected
                        "
                        :items="[
                          {
                            title: $t('metadata_mode.disabled'),
                            value: 'disabled',
                          },
                          {
                            title: $t('metadata_mode.default'),
                            value: 'default',
                          },
                          {
                            title: $t('metadata_mode.legacy'),
                            value: 'legacy',
                          },
                        ]"
                        @update:model-value="
                          api.playerQueueSettings(activePlayerQueue?.queue_id, {
                            metadata_mode: $event,
                          })
                        "
                        hide-details
                      ></v-select>
                    </v-list-item>
                  </v-list>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </v-card-text>
        </v-card>
      </v-menu>
    </v-overlay>
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
  mdiDelete,
  mdiCancel,
  mdiCogOutline,
  mdiCastConnected,
  mdiVolumePlus,
  mdiRadioTower,
} from "@mdi/js";
import { ref } from "@vue/reactivity";
import { RecycleScroller } from "vue-virtual-scroller";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";
import type { QueueItem, MassEvent, MediaItemType } from "../plugins/api";
import {
  RepeatMode,
  CrossFadeMode,
  MassEventType,
  MediaType,
  ContentType,
} from "../plugins/api";
import api from "../plugins/api";
import { computed, onBeforeUnmount, watchEffect } from "vue";
import { store } from "../plugins/store";
import { formatDuration, parseBool, truncateString } from "../utils";
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
const panel = ref(0);

// computed properties
const activePlayerQueue = computed(() => {
  if (store.selectedPlayer) {
    return api.queues[store.selectedPlayer.active_queue];
  }
  return undefined;
});

const curQueueItem = computed(() => {
  if (activePlayerQueue.value) return activePlayerQueue.value.current_item;
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
const unsub = api.subscribe(
  MassEventType.QUEUE_ITEMS_UPDATED,
  (evt: MassEvent) => {
    if (evt.object_id == activePlayerQueue.value?.queue_id) {
      loadItems();
    }
  }
);
onBeforeUnmount(unsub);

store.topBarContextMenuItems = [
  {
    label: "settings",
    labelArgs: [],
    action: () => {
      showContextMenu.value = true;
    },
    icon: mdiCogOutline,
  },
  {
    label: "queue_clear",
    labelArgs: [],
    action: () => {
      api.queueCommandClear(activePlayerQueue.value?.queue_id);
    },
    icon: mdiCancel,
  },
];
onBeforeUnmount(() => {
  store.topBarContextMenuItems = [];
});

// methods
const loadItems = async function () {
  loading.value = true;
  if (activePlayerQueue.value) {
    store.topBarTitle = t("queue") + ": " + activePlayerQueue.value.name;
    items.value = await api.getPlayerQueueItems(
      activePlayerQueue.value.queue_id
    );
  } else {
    store.topBarTitle = t("queue");
    items.value = [];
  }
  loading.value = false;
};

const onClick = function (item: QueueItem) {
  // mediaItem in the list is clicked
  selectedItem.value = item;
  showContextMenu.value = true;
};

const gotoItem = function (item: MediaItemType) {
  closeContextMenu();
  router.push({
    name: item.media_type,
    params: { item_id: item.item_id, provider: item.provider },
  });
};

const queueCommand = function (item: QueueItem | undefined, command: string) {
  closeContextMenu();
  if (!item || !activePlayerQueue.value) return;
  if (command == "play_now") {
    api.queueCommandPlayIndex(activePlayerQueue?.value.queue_id, item.item_id);
  } else if (command == "move_next") {
    api.queueCommandMoveNext(activePlayerQueue?.value.queue_id, item.item_id);
  } else if (command == "up") {
    api.queueCommandMoveUp(activePlayerQueue?.value.queue_id, item.item_id);
  } else if (command == "down") {
    api.queueCommandMoveDown(activePlayerQueue?.value.queue_id, item.item_id);
  } else if (command == "delete") {
    api.queueCommandDelete(activePlayerQueue?.value.queue_id, item.item_id);
  }
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
