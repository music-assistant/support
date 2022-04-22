export const parseBool = (val: string | boolean) => {
  if (val == undefined) return false;
  if (typeof val === "boolean") return val;
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
  return str.slice(0, num) + "...";
};

export const isColorDark = function (hexColor: string) {
  if (hexColor.includes("var")) {
    hexColor = getComputedStyle(document.documentElement).getPropertyValue(
      hexColor
    );
  }
  let r = 0;
  let g = 0;
  let b = 0;
  if (hexColor.includes("rgb(")) {
    const parts = hexColor.split("(")[1].split(")")[0].split(",");
    r = parseInt(parts[0]);
    g = parseInt(parts[1]);
    b = parseInt(parts[2]);
  } else {
    const c = hexColor.substring(1); // strip #
    const rgb = parseInt(c, 16); // convert rrggbb to decimal
    r = (rgb >> 16) & 0xff; // extract red
    g = (rgb >> 8) & 0xff; // extract green
    b = (rgb >> 0) & 0xff; // extract blue
  }
  const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b; // per ITU-R BT.709

  return luma < 128;
};

export const kebabize = (str: string) => {
  return str
    .split("")
    .map((letter, idx) => {
      return letter.toUpperCase() === letter
        ? `${idx !== 0 ? "-" : ""}${letter.toLowerCase()}`
        : letter;
    })
    .join("");
};

export const mergeDeep = function (
  target: Record<string, any>,
  source: Record<string, any>
) {
  const isObject = (obj) => obj && typeof obj === "object";

  if (!isObject(target) || !isObject(source)) {
    return source;
  }

  Object.keys(source).forEach((key) => {
    const targetValue = target[key];
    const sourceValue = source[key];

    if (Array.isArray(targetValue) && Array.isArray(sourceValue)) {
      target[key] = targetValue.concat(sourceValue);
    } else if (isObject(targetValue) && isObject(sourceValue)) {
      target[key] = mergeDeep(Object.assign({}, targetValue), sourceValue);
    } else {
      target[key] = sourceValue;
    }
  });

  return target;
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
