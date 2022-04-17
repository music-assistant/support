/* eslint-disable @typescript-eslint/no-explicit-any */
import {
  defineCustomElement as VueDefineCustomElement,
  h,
  createApp,
  getCurrentInstance,
  VueElement
} from "vue";

import type { Component } from "vue";
import { loadFonts } from "./plugins/webfontloader";

const getNearestElementParent = (el: VueElement) => {
  while (el?.nodeType !== 1 /* ELEMENT */) {
    el = (el as any).parentElement;
  }
  return el;
};

export const defineCustomElement = (component: Component, { plugins = [] }) =>
  VueDefineCustomElement({
    // render: () => h(component),
    setup(props) {
      const app = createApp();
      console.log('component', component)

      // install plugins
      plugins.forEach(app.use);

      loadFonts();

      app.mixin({
        mounted() {
          console.log('mixin called')
          this.__style = document.createElement("style");
          // copy vuetify theme styles from head (hack, otherwise they wont work)
          const themestyles = document.querySelector(
            "#vuetify-theme-stylesheet"
          )?.innerHTML;
          this.__style.innerText = themestyles;

          const insertStyles = (styles: any) => {
            if (styles?.length) {
              this.__style.innerText += styles.join().replace(/\n/g, "");
            }
          };

          // load own styles
          insertStyles(this.$?.type.styles);

          getNearestElementParent(this.$el).prepend(this.__style);
        },
        unmounted() {
          this.__style?.remove();
        }
      });

      const inst = getCurrentInstance();

      Object.assign(inst.appContext, app._context);
      Object.assign(inst.provides, app._context.provides);

      return () => h(component, props);
    }
  });
