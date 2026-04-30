window.GVAI_API_BASE = (() => {
  const host = window.location.hostname;

  // Local Codespaces / localhost use same origin
  if (
    host.includes("github.dev") ||
    host === "localhost" ||
    host === "127.0.0.1"
  ) {
    return "";
  }

  // Production frontend
  return "https://web-production-8e937.up.railway.app";
})();
