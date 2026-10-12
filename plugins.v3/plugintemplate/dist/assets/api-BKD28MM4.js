const PLUGIN_ID = "PluginTemplate";
const API_BASE = `plugin/${PLUGIN_ID}`;
function resolveApi(props) {
  if (props && props.api) return props.api;
  const globalApi = typeof window !== "undefined" ? window.MoviePilotAPI : null;
  return globalApi ?? null;
}
function unwrap(raw) {
  if (raw && typeof raw === "object" && "success" in raw) {
    return raw;
  }
  const nested = raw?.data;
  return nested ?? raw;
}

export { API_BASE as A, resolveApi as r, unwrap as u };
