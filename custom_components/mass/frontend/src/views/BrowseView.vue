<template>
  <section>
    <div
      style="
        padding-left: 15px;
        padding-right: 15px;
        padding-top: 5px;
        padding-bottom: 20px;
      "
    >
      <!-- loading animation -->
      <v-progress-linear indeterminate v-if="loading"></v-progress-linear>

      <RecycleScroller
        v-slot="{ item }"
        :items="browseItem?.items || []"
        :item-size="66"
        key-field="uri"
        page-mode
      >
        <ListviewItem
          :item="item"
          :show-library="false"
          :show-menu="false"
          :show-providers="false"
          :is-selected="false"
          @click="onClick"
        ></ListviewItem>
      </RecycleScroller>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch, watchEffect } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";
import { RecycleScroller } from "vue-virtual-scroller";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";
import ListviewItem from "../components/ListviewItem.vue";
import {
  api,
  MediaType,
  type BrowseFolder,
  type MediaItemType,
} from "../plugins/api";
import { store } from "../plugins/store";
import { useRouter } from "vue-router";
import { getBrowseFolderName } from "../utils";

export interface Props {
  path?: string;
}
const props = defineProps<Props>();

const { t } = useI18n();
const router = useRouter();
const { mobile } = useDisplay();

const browseItem = ref<BrowseFolder>();
const loading = ref(false);

const loadData = async function () {
  loading.value = true;
  browseItem.value = await api.browse(props.path);

  // set header title to browse title
  if (!browseItem.value) store.topBarTitle = t("browse");
  else {
    if (mobile.value) store.topBarTitle = getBrowseFolderName(browseItem.value, t);
    else
      store.topBarTitle =
        t("browse") + " | " + getBrowseFolderName(browseItem.value, t);
  }
  loading.value = false;
};

onMounted(() => {
  loadData();
});

watch(
  () => props.path,
  () => {
    loadData();
  }
);

const onClick = function (mediaItem: MediaItemType) {
  if (mediaItem.media_type === MediaType.FOLDER) {
    router.push({
      name: "browse",
      params: { path: mediaItem.path },
    });
  } else {
    router.push({
      name: mediaItem.media_type,
      params: { item_id: mediaItem.item_id, provider: mediaItem.provider },
    });
  }
};
</script>
