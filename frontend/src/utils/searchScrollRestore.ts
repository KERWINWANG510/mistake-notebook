/** 搜索页滚动还原：记录点击的结果在视口中的位置，返回后对齐 */

export type SearchScrollSnapshot = {
  mistakeId: string;
  scrollTop: number;
  /** 结果卡片顶部相对滚动容器可视区域顶部的距离（px） */
  viewportOffset: number;
  /** 用于定位真实滚动容器的标记 */
  scrollHost: "app-content" | "layout-scroll";
};

const STORAGE_KEY = "mistake-search-scroll-v1";

let memorySnapshot: SearchScrollSnapshot | null = null;

function scrollHostElement(host: SearchScrollSnapshot["scrollHost"]): HTMLElement | null {
  if (host === "layout-scroll") {
    return document.querySelector(".app-shell .n-layout-scroll-container") as HTMLElement | null;
  }
  return document.querySelector(".app-content") as HTMLElement | null;
}

/** 解析当前页面实际产生滚动的容器（PC 上可能是 app-content 或 layout-scroll-container） */
export function resolveScrollHost(): { el: HTMLElement; host: SearchScrollSnapshot["scrollHost"] } | null {
  const content = document.querySelector(".app-content") as HTMLElement | null;
  const layoutScroll = document.querySelector(
    ".app-shell .n-layout-scroll-container",
  ) as HTMLElement | null;
  const candidates: { el: HTMLElement; host: SearchScrollSnapshot["scrollHost"] }[] = [];
  if (content) candidates.push({ el: content, host: "app-content" });
  if (layoutScroll) candidates.push({ el: layoutScroll, host: "layout-scroll" });

  if (!candidates.length) return null;

  let picked = candidates[0];
  let bestScore = -1;
  for (const c of candidates) {
    const style = getComputedStyle(c.el);
    const canScroll = /auto|scroll|overlay/.test(style.overflowY);
    const range = c.el.scrollHeight - c.el.clientHeight;
    const score = (canScroll ? 1_000_000 : 0) + range + c.el.scrollTop * 10;
    if (score > bestScore) {
      bestScore = score;
      picked = c;
    }
  }
  return picked;
}

function offsetTopInScrollContent(el: HTMLElement, scrollEl: HTMLElement): number {
  const elRect = el.getBoundingClientRect();
  const scrollRect = scrollEl.getBoundingClientRect();
  return elRect.top - scrollRect.top + scrollEl.scrollTop;
}

export function saveSearchScrollSnapshot(mistakeId: string): void {
  const hostInfo = resolveScrollHost();
  const node = document.getElementById(`search-result-${mistakeId}`);
  if (!hostInfo || !node) return;
  const { el, host } = hostInfo;
  const itemTop = offsetTopInScrollContent(node, el);
  const snapshot: SearchScrollSnapshot = {
    mistakeId,
    scrollTop: el.scrollTop,
    viewportOffset: itemTop - el.scrollTop,
    scrollHost: host,
  };
  memorySnapshot = snapshot;
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    /* 存储不可用时仅保留内存 */
  }
}

export function loadSearchScrollSnapshot(): SearchScrollSnapshot | null {
  if (memorySnapshot) return memorySnapshot;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SearchScrollSnapshot;
    if (!parsed?.mistakeId || typeof parsed.scrollTop !== "number") return null;
    memorySnapshot = parsed;
    return parsed;
  } catch {
    return null;
  }
}

export function clearSearchScrollSnapshot(): void {
  memorySnapshot = null;
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

function isVisuallyRestored(state: SearchScrollSnapshot, container: HTMLElement): boolean {
  const node = document.getElementById(`search-result-${state.mistakeId}`);
  if (!node) return false;
  const itemTop = offsetTopInScrollContent(node, container);
  const currentOffset = itemTop - container.scrollTop;
  return Math.abs(currentOffset - state.viewportOffset) <= 6;
}

function applySnapshot(state: SearchScrollSnapshot): boolean {
  const container = scrollHostElement(state.scrollHost) ?? resolveScrollHost()?.el;
  if (!container) return false;

  const node = document.getElementById(`search-result-${state.mistakeId}`);
  let target = state.scrollTop;
  if (node) {
    const itemTop = offsetTopInScrollContent(node, container);
    target = itemTop - state.viewportOffset;
  }
  const maxScroll = Math.max(0, container.scrollHeight - container.clientHeight);
  const nextTop = Math.max(0, Math.min(target, maxScroll));
  container.scrollTop = nextTop;
  return isVisuallyRestored(state, container);
}

let restoreGeneration = 0;

/** 在布局稳定后多次尝试还原滚动（供 onActivated / afterEach 调用） */
export function scheduleSearchScrollRestore(): void {
  const state = loadSearchScrollSnapshot();
  if (!state) return;

  const gen = ++restoreGeneration;

  const tryOnce = () => {
    if (gen !== restoreGeneration) return;
    return applySnapshot(state);
  };

  const finishIfDone = (ok: boolean) => {
    if (ok) clearSearchScrollSnapshot();
  };

  nextFrame(() => {
    if (gen !== restoreGeneration) return;
    if (tryOnce()) {
      finishIfDone(true);
      return;
    }
    const delays = [0, 50, 120, 240, 400, 600];
    delays.forEach((ms) => {
      window.setTimeout(() => {
        if (gen !== restoreGeneration) return;
        if (tryOnce()) finishIfDone(true);
      }, ms);
    });
    window.setTimeout(() => {
      if (gen !== restoreGeneration) return;
      if (tryOnce()) finishIfDone(true);
      else finishIfDone(false);
    }, 800);
  });
}

function nextFrame(fn: () => void) {
  requestAnimationFrame(() => requestAnimationFrame(fn));
}

/** 离开搜索页且不是进入详情时丢弃快照 */
export function discardSearchScrollUnlessToDetail(nextPath: string): void {
  const toDetail = /^\/mistakes\/[^/]+$/.test(nextPath);
  if (!toDetail) clearSearchScrollSnapshot();
}
