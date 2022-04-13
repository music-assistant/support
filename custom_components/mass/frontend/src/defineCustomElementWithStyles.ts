/* eslint-disable @typescript-eslint/no-explicit-any */
import {
  defineCustomElement as VueDefineCustomElement,
  h,
  createApp,
  getCurrentInstance,
  VueElement,
} from "vue";

import type { Component } from "vue";

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

      // install plugins
      plugins.forEach(app.use);

      app.mixin({
        mounted() {
          const insertStyles = (styles: any) => {
            if (styles?.length) {
              this.__style = document.createElement("style");
              this.__style.innerText = styles.join().replace(/\n/g, "");
              getNearestElementParent(this.$el).prepend(this.__style);
            }
          };

          // load own styles
          insertStyles(this.$?.type.styles);

          // load styles of child components
          if (this.$options.components) {
            for (const comp of Object.values(this.$options.components)) {
              insertStyles(comp.styles);
            }
          }
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
