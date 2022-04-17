export const parseBool = (val: string) => {
  return !!JSON.parse(String(val).toLowerCase());
};

export const formatDuration = function (totalSeconds: number) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds - hours * 3600) / 60);
  const seconds = totalSeconds - hours * 3600 - minutes * 60;
  let hoursStr = hours.toString();
  let minutesStr = minutes.toString();
  let secondsStr = seconds.toString();
  if (hours < 10) {
    hoursStr = "0" + hours;
  }
  if (minutes < 10) {
    minutesStr = "0" + minutes;
  }
  if (seconds < 10) {
    secondsStr = "0" + seconds;
  }
  if (hoursStr === "00") {
    return minutesStr + ":" + secondsStr;
  } else {
    return hoursStr + ":" + minutesStr + ":" + secondsStr;
  }
};

export const truncateString = function (str: string, num: number) {
  // If the length of str is less than or equal to num
  // just return str--don't truncate it.
  if (str.length <= num) {
    return str;
  }
  // Return str truncated with '...' concatenated to the end of str.
  return str.slice(0, num);
};

/**
 * Whether the current browser supports `adoptedStyleSheets`.
 */
export const supportsAdoptingStyleSheets =
  window.ShadowRoot &&
  "adoptedStyleSheets" in Document.prototype &&
  "replaceSync" in CSSStyleSheet.prototype;

/**
 * Add constructed Stylesheet or style tag to Shadowroot of VueCE.
 * @param renderRoot The shadowroot of the vueCE..
 * @param styles The styles of the Element.
 * @param __hmrId hmr id of vite used as an UUID.
 */
export const adoptStyles = (
  renderRoot: ShadowRoot,
  styles: string,
  __hmrId: string
) => {
  if (supportsAdoptingStyleSheets) {
    const sheets = renderRoot.adoptedStyleSheets;
    const oldSheet = sheets.find((sheet) => sheet.__hmrId === __hmrId);

    // Check if this StyleSheet exists already. Replace content if it does. Otherwise construct a new CSSStyleSheet.
    if (oldSheet) {
      oldSheet.replaceSync(styles);
    } else {
      const styleSheet: CSSStyleSheet = new CSSStyleSheet();
      styleSheet.__hmrId = __hmrId;
      styleSheet.replaceSync(styles);
      renderRoot.adoptedStyleSheets = [
        ...renderRoot.adoptedStyleSheets,
        styleSheet
      ];
    }
  } else {
    const existingStyleElements = renderRoot.querySelectorAll("style");
    const oldStyleElement = Array.from(existingStyleElements).find(
      (sheet) => sheet.title === __hmrId
    );

    // Check if this Style Element exists already. Replace content if it does. Otherwise construct a new HTMLStyleElement.
    if (oldStyleElement) {
      oldStyleElement.innerHTML = styles;
    } else {
      const styleElement = document.createElement("style");
      styleElement.title = __hmrId;
      styleElement.innerHTML = styles;
      renderRoot.appendChild(styleElement);
    }
  }
};
