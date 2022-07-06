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
        :items="browseItems"
        :item-size="66"
        key-field="item_id"
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
import { ref, watchEffect } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";
import { RecycleScroller } from "vue-virtual-scroller";
import "vue-virtual-scroller/dist/vue-virtual-scroller.css";
import ListviewItem from "../components/ListviewItem.vue";
import { api, MediaType, type MediaItemType } from "../plugins/api";
import { store } from "../plugins/store";
import { useRouter } from "vue-router";

export interface Props {
  uri?: string;
  title?: string;
}
const props = defineProps<Props>();

const { t } = useI18n();
const router = useRouter();
const { mobile } = useDisplay();

const browseItems = ref<MediaItemType[]>([]);
const loading = ref(false);

watchEffect(async () => {
  console.log("browse", props);

  // set header title to browse title
  if (!props.title) store.topBarTitle = t("browse");
  else if (mobile.value) store.topBarTitle = props.title;
  else store.topBarTitle = t("browse") + " | " + props.title;

  loading.value = true;
  browseItems.value = await api.browse(props.uri);
  loading.value = false;
});

const onClick = function (mediaItem: MediaItemType) {
  console.log("onClick", mediaItem.uri);

  if (mediaItem.media_type === MediaType.FOLDER) {
    let title = props.title || "";
    if (title) title = title + " | ";
    if ("label" in mediaItem && mediaItem.label)
      title = title + t(mediaItem.label);
    else title = title + mediaItem.name;
    router.replace({
      name: "browse",
      params: { uri: mediaItem.uri, title: title },
    });
  } else {
    router.push({
      name: mediaItem.media_type,
      params: { item_id: mediaItem.item_id, provider: mediaItem.provider },
    });
  }
};
</script>
