<template>
  <div>
    <v-list-item
      ripple
      @click.stop="emit('click', item)"
      @click.right.prevent="emit('menu', item)"
      style="height: 60px"
      :disabled="!itemIsAvailable(item)"
      lines="two"
      density="compact"
    >
      <template v-slot:prepend>
        <div v-if="showCheckboxes" class="listitem-thumb">
          <v-checkbox
            :model-value="isSelected"
            @click.stop
            @update:model-value="
              (x) => {
                emit('select', item, x);
              }
            "
          />
        </div>
        <div
          v-else-if="item.media_type == MediaType.FOLDER"
          class="listitem-thumb"
        >
          <v-btn variant="plain" icon
            ><v-icon :icon="mdiFolder" size="60" style="align: center"> </v-icon
          ></v-btn>
        </div>
        <div v-else class="listitem-thumb">
          <MediaItemThumb
            :item="item"
            :size="50"
            width="50px"
            height="50px"
          /></div
      ></template>

      <!-- title -->
      <template v-slot:title>
        <span v-if="item.media_type == MediaType.FOLDER">
          <span>{{ getBrowseFolderName(item as BrowseFolder, t) }}</span>
        </span>
        <span v-else>
          {{ item.name }}
          <span v-if="'version' in item && item.version"
            >({{ item.version }})</span
          >
        </span>
        <!-- explicit icon -->
        <v-tooltip location="bottom">
          <template #activator="{ props }">
            <v-icon
              v-bind="props"
              class="listitem-action"
              :icon="mdiAlphaEBox"
              width="35"
              v-if="parseBool(item.metadata.explicit || false)"
            />
          </template>
          <span>{{ $t("tooltip.explicit") }}</span>
        </v-tooltip>
      </template>

      <!-- subtitle -->
      <template v-slot:subtitle>
        <!-- track: artists(s) + album -->
        <div
          v-if="
            item.media_type == MediaType.TRACK && item.album && !showTrackNumber
          "
        >
          {{ getArtistsString(item.artists) }} • {{ item.album.name }}
        </div>
        <!-- albumtrack: artists(s) + disc/track number -->
        <div
          v-else-if="
            item.media_type == MediaType.TRACK &&
            item.track_number &&
            showTrackNumber
          "
        >
          {{ getArtistsString(item.artists) }} • disc
          {{ item.disc_number }} track
          {{ item.track_number }}
        </div>
        <!-- album: albumtype + artists + year -->
        <div
          v-else-if="
            item.media_type == MediaType.ALBUM && item.artists && item.year
          "
        >
          {{ $t("album_type." + item.album_type) }} •
          {{ getArtistsString(item.artists) }} • {{ item.year }}
        </div>
        <!-- album: albumtype + artists -->
        <div v-else-if="item.media_type == MediaType.ALBUM && item.artists">
          {{ $t("album_type." + item.album_type) }} •
          {{ getArtistsString(item.artists) }}
        </div>
        <!-- track/album falback: artist present -->
        <div v-else-if="'artists' in item && item.artists">
          {{ getArtistsString(item.artists) }}
        </div>
        <!-- playlist owner -->
        <div v-else-if="'owner' in item && item.owner">{{ item.owner }}</div>
        <!-- radio description -->
        <div
          v-if="item.media_type == MediaType.RADIO && item.metadata.description"
        >
          {{ item.metadata.description }}
        </div>
      </template>

      <!-- actions -->
      <template v-slot:append>
        <div class="listitem-actions">
          <!-- hi res icon -->
          <v-img
            class="listitem-action"
            v-if="highResDetails"
            :src="iconHiRes"
            width="35"
            :style="
              $vuetify.theme.current.dark
                ? 'margin-top:5px;'
                : 'margin-top:5px;filter: invert(100%);'
            "
          >
            <v-tooltip activator="parent" location="bottom">{{
              highResDetails
            }}</v-tooltip>
          </v-img>

          <!-- provider icons -->
          <ProviderIcons
            v-if="
              item.provider_ids && showProviders && !$vuetify.display.mobile
            "
            :provider-ids="item.provider_ids"
            :height="20"
            class="listitem-actions"
          />

          <!-- in library (heart) icon -->
          <div
            class="listitem-action"
            v-if="
              'in_library' in item && showLibrary && !$vuetify.display.mobile
            "
          >
            <v-tooltip location="bottom">
              <template #activator="{ props }">
                <v-btn
                  variant="plain"
                  ripple
                  v-bind="props"
                  @click="api.toggleLibrary(item)"
                  @click.prevent
                  @click.stop
                  :icon="item.in_library ? mdiHeart : mdiHeartOutline"
                >
                </v-btn>
              </template>
              <span>{{ $t("tooltip.library") }}</span>
            </v-tooltip>
          </div>

          <!-- islinked icon -->
          <v-tooltip location="bottom">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                class="listitem-action"
                :icon="mdiLinkVariant"
                size="30"
                v-if="
                  parentItem &&
                  parentItem.provider_ids.find(
                    (x) => x.item_id === item.item_id
                  )
                "
              />
            </template>
            <span>{{ $t("tooltip.linked") }}</span>
          </v-tooltip>

          <!-- track duration -->
          <div
            class="listitem-action"
            v-if="
              showDuration &&
              item.media_type == MediaType.TRACK &&
              !$vuetify.display.mobile
            "
          >
            <span>{{ formatDuration(item.duration) }}</span>
          </div>
        </div>

        <v-menu location="bottom end" v-if="showDetails" @click:outside.stop>
          <template v-slot:activator="{ props }">
            <v-icon
              :icon="mdiInformationOutline"
              size="30"
              class="listitem-action"
              style="margin-left: 10px; margin-right: 5px"
              v-bind="props"
            />
          </template>
          <v-card class="mx-auto" min-width="300">
            <v-list style="overflow: hidden">
              <span class="text-h5" style="padding: 10px">{{
                $t("provider_details")
              }}</span>
              <v-divider></v-divider>
              <!-- provider icon + name -->
              <div style="height: 50px; display: flex; align-items: center">
                <img
                  height="30"
                  width="50"
                  center
                  :src="getProviderIcon(item.provider)"
                  style="object-fit: contain;"
                />
                {{
                  truncateString(
                    api.providers[item.provider_ids[0].prov_id].name,
                    25
                  )
                }}
              </div>

              <!-- item ID -->
              <div style="height: 50px; display: flex; align-items: center">
                <v-icon
                  size="40"
                  :icon="mdiIdentifier"
                  style="margin-left: 10px;padding-right: 10px"
                />
                {{ truncateString(item.item_id, 30) }}
              </div>

              <!-- link to web location of item (provider share link -->
              <div style="height: 50px; display: flex; align-items: center"
                v-if="
                  item.provider_ids[0].url && !item.provider.includes('file')
                "
              >
                <v-icon
                  size="40"
                  :icon="mdiShareOutline"
                  style="margin-left: 10px; padding-right: 5px"
                />
                <a :href="item.provider_ids[0].url" target="_blank">{{
                  truncateString(item.provider_ids[0].url, 25)
                }}</a>
              </div>

              <!-- quality details -->
              <div style="height: 50px; display: flex; align-items: center">
                <img
                  height="30"
                  width="50"
                  :src="getQualityIcon(item.provider_ids[0].quality)"
                  :style="
                    $vuetify.theme.current.dark
                      ? 'object-fit: contain;'
                      : 'object-fit: contain;filter: invert(100%);'
                  "
                />
                {{ getQualityDesc(item.provider_ids[0]) }}
              </div>

              <!-- track preview -->
              <div v-if="item.media_type == MediaType.TRACK">
                <div style="height: 50px; display: flex; align-items: center">
                  <v-icon
                    :icon="mdiHeadphones"
                    size="40"
                    style="margin-left: 10px; padding-right: 15px"
                  />
                  Preview
                </div>
                <div
                  style="
                    height: 50px;
                    display: flex;
                    align-items: center;
                    margin-left: 10px;
                    margin-right: 10px;
                  "
                  @mouseover="fetchPreviewUrl(item.provider, item.item_id)"
                >
                  <audio
                    controls
                    :src="previewUrls[`${item.provider}.${item.item_id}`]"
                  ></audio>
                </div>
              </div>
            </v-list>
          </v-card>
        </v-menu>

        <!-- menu button/icon -->
        <v-btn
          v-if="showMenu"
          @click.stop="emit('menu', item)"
          :icon="mdiDotsVertical"
          variant="plain"
          style="position: absolute; right: -3px;width:10px"
        ></v-btn>
      </template>
    </v-list-item>
    <v-divider></v-divider>
  </div>
</template>

<script setup lang="ts">
import {
  mdiHeart,
  mdiHeartOutline,
  mdiDotsVertical,
  mdiShareOutline,
  mdiAlphaEBox,
  mdiFolder,
  mdiInformationOutline,
  mdiHeadphones,
  mdiIdentifier,
  mdiLinkVariant,
} from "@mdi/js";
import { ref, computed, reactive } from "vue";
import { useRouter } from "vue-router";
import { VTooltip } from "vuetify/components";

import MediaItemThumb from "./MediaItemThumb.vue";
import ProviderIcons from "./ProviderIcons.vue";
import {
  iconHiRes,
  getProviderIcon,
  getQualityIcon,
  getQualityDesc,
} from "./ProviderIcons.vue";
import type {
  Artist,
  BrowseFolder,
  MediaItem,
  MediaItemType,
  ProviderType,
} from "../plugins/api";
import { api, MediaQuality, MediaType } from "../plugins/api";
import {
  formatDuration,
  parseBool,
  getArtistsString,
  getBrowseFolderName,
  truncateString,
} from "../utils";
import { useTheme } from "vuetify";
import { useI18n } from "vue-i18n";

// properties
export interface Props {
  item: MediaItemType;
  showTrackNumber?: boolean;
  showProviders?: boolean;
  showMenu?: boolean;
  showLibrary?: boolean;
  showDuration?: boolean;
  isSelected: boolean;
  showCheckboxes?: boolean;
  showDetails?: boolean;
  parentItem?: MediaItemType;
}

// global refs
const router = useRouter();
const { t } = useI18n();
const actionInProgress = ref(false);
const theme = useTheme();
const previewUrls = reactive<Record<string, string>>({});

const props = withDefaults(defineProps<Props>(), {
  showTrackNumber: true,
  showProviders: true,
  showMenu: true,
  showLibrary: true,
  showDuration: true,
  showCheckboxes: false,
});

// computed properties
const highResDetails = computed(() => {
  if (!props.item.provider_ids) return "";
  for (const prov of props.item.provider_ids) {
    if (!prov.quality) continue;
    if (prov.quality >= MediaQuality.LOSSLESS_HI_RES_1) {
      if (prov.details) {
        return prov.details;
      } else if (prov.quality === MediaQuality.LOSSLESS_HI_RES_1) {
        return "44.1/48khz 24 bits";
      } else if (prov.quality === MediaQuality.LOSSLESS_HI_RES_2) {
        return "88.2/96khz 24 bits";
      } else if (prov.quality === MediaQuality.LOSSLESS_HI_RES_3) {
        return "176/192khz 24 bits";
      } else {
        return "+192kHz 24 bits";
      }
    }
  }
  return "";
});

// emits
const emit = defineEmits<{
  (e: "menu", value: MediaItemType): void;
  (e: "click", value: MediaItemType): void;
  (e: "select", value: MediaItemType, selected: boolean): void;
}>();

// methods

const itemIsAvailable = function (item: MediaItem) {
  if (item.media_type == MediaType.FOLDER) return true;
  if (!props.item.provider_ids) return true;
  for (const x of item.provider_ids) {
    if (x.available && x.prov_id in api.providers) return true;
  }
  return false;
};

const fetchPreviewUrl = async function (
  provider: ProviderType,
  item_id: string
) {
  const key = `${provider}.${item_id}`;
  if (key in previewUrls) return;
  const url = await api.getTrackPreviewUrl(provider, item_id);
  previewUrls[key] = url;
};
</script>
