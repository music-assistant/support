import { defineCustomElement as rootDefineCustomElement } from "vue";
import { kebabize } from "./utils";
export const getChildrenComponentsStyles = (component) => {
  let componentStyles = [];
  if (component.components) {
    componentStyles = Object.values(component.components).reduce(
      (aggregatedStyles, nestedComponent) => {
        if (nestedComponent?.components) {
          aggregatedStyles = [
            ...aggregatedStyles,
            ...getChildrenComponentsStyles(nestedComponent)
          ];
        }
        return nestedComponent.styles
          ? [...aggregatedStyles, ...nestedComponent.styles]
          : aggregatedStyles;
      },
      []
    );
  }
  if (component.styles) {
    componentStyles.push(...component.styles);
  }

  return [...new Set(componentStyles)];
};

export const defineCustomElement = (component) => {
  // Attach children styles to main element
  // Should be removed once https://github.com/vuejs/vue-next/pull/4695
  // gets merged
  component.styles = getChildrenComponentsStyles(component);
  const cElement = rootDefineCustomElement(component);

  // Programmatically generate name for component tag
  const componentName = kebabize(component.name?.replace(/\.[^/.]+$/, "") || 'music-assistant');
  // eslint-disable-next-line tree-shaking/no-side-effects-in-initialization
  customElements.define(componentName, cElement);

  // Here we are attaching a <ling ref="style" href="/style.css" ...
  // This is to have the css outside of the shadow dom
  // also available inside the shadow root without inlining them
  // The browser will automatically use the available declaration and won't
  // make multiple calls
  const componentShadowDom = document.querySelector(componentName)?.shadowRoot;
  if (componentShadowDom) {
    const styleLink = document.createElement("link");
    styleLink.setAttribute("rel", "stylesheet");
    styleLink.setAttribute("href", "style.css");
    componentShadowDom.appendChild(styleLink);
  }
};
