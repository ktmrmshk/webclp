const DEFAULT_API = "http://127.0.0.1:3847";

document.addEventListener("DOMContentLoaded", async () => {
  const { apiBase, bearerToken } = await chrome.storage.sync.get({
    apiBase: DEFAULT_API,
    bearerToken: "",
  });
  document.getElementById("apiBase").value = apiBase || DEFAULT_API;
  document.getElementById("bearerToken").value = bearerToken || "";
});

document.getElementById("save").addEventListener("click", async () => {
  let v = document.getElementById("apiBase").value.trim() || DEFAULT_API;
  v = v.replace(/\/$/, "");
  const bearerToken = document.getElementById("bearerToken").value.trim();
  await chrome.storage.sync.set({ apiBase: v, bearerToken });
  const st = document.getElementById("status");
  st.hidden = false;
  setTimeout(() => {
    st.hidden = true;
  }, 2000);
});
