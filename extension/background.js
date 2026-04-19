const DEFAULT_API = "http://127.0.0.1:3847";

async function getApiBase() {
  const { apiBase } = await chrome.storage.sync.get({ apiBase: DEFAULT_API });
  return (apiBase || DEFAULT_API).replace(/\/$/, "");
}

async function getAuthHeaders() {
  const { bearerToken } = await chrome.storage.sync.get({ bearerToken: "" });
  const headers = { "Content-Type": "application/json" };
  if (bearerToken) headers["Authorization"] = "Bearer " + bearerToken;
  return headers;
}

function extractPageData() {
  const metaContent = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    return el.getAttribute("content");
  };

  const ogTitle = metaContent('meta[property="og:title"]');
  const ogDesc = metaContent('meta[property="og:description"]');
  const ogImage = metaContent('meta[property="og:image"]');
  const twImage = metaContent('meta[name="twitter:image"]');
  const desc = metaContent('meta[name="description"]');

  const title = ogTitle || document.title || "";

  const root =
    document.querySelector("article") ||
    document.querySelector('[role="main"]') ||
    document.querySelector("main") ||
    document.body;
  let text = "";
  if (root) {
    text = root.innerText || "";
    text = text.replace(/\s+/g, " ").trim();
    if (text.length > 50000) text = text.slice(0, 50000);
  }

  let summary = ogDesc || desc || "";
  if (!summary && text) summary = text.slice(0, 500);

  const imageUrl = ogImage || twImage || null;

  return {
    url: location.href,
    title,
    summary: summary || "",
    image_url: imageUrl,
    body_text: text,
  };
}

async function clipCurrentTab(tab) {
  if (!tab?.id) {
    console.error("Webclip: no active tab");
    return;
  }

  let data;
  try {
    const injected = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractPageData,
    });
    const first = injected[0];
    if (!first || first.error) {
      throw new Error(first?.error ? String(first.error) : "no injection result");
    }
    data = first.result;
  } catch (e) {
    console.error("Webclip: extract failed", e);
    alert(
      "ページの読み取りに失敗しました。chrome:// や Web Store など、拡張機能が使えないページの可能性があります。"
    );
    return;
  }

  const base = await getApiBase();
  try {
    const res = await fetch(`${base}/api/clips`, {
      method: "POST",
      headers: await getAuthHeaders(),
      body: JSON.stringify({
        url: data.url,
        title: data.title,
        summary: data.summary,
        image_url: data.image_url,
        body_text: data.body_text,
      }),
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(t || res.statusText);
    }
    await chrome.action.setBadgeText({ text: "ok", tabId: tab.id });
    await chrome.action.setBadgeBackgroundColor({ color: "#2e7d32" });
    setTimeout(() => chrome.action.setBadgeText({ text: "" }), 2000);
  } catch (e) {
    console.error("Webclip: API failed", e);
    alert(
      `Webclip: サーバーに送信できませんでした。\n${base} が起動しているか確認してください。\n\n${e.message || e}`
    );
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "webclip-page",
    title: "Clip this page",
    contexts: ["page", "frame"],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "webclip-page") clipCurrentTab(tab);
});

chrome.action.onClicked.addListener((tab) => clipCurrentTab(tab));
