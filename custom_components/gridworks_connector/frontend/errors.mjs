/** Extract readable text from HA callApi errors without displaying object coercions. */
export function describeApiError(error) {
  const status = error?.status_code ?? error?.status;
  const prefix = status ? `Home Assistant request failed (HTTP ${status}): ` : "";
  function text(value, depth = 0) {
    if (typeof value === "string" && value.trim()) return value;
    if (!value || typeof value !== "object" || depth > 2) return null;
    for (const key of ["message", "error", "detail", "body"]) {
      const found = text(value[key], depth + 1);
      if (found) return found;
    }
    return null;
  }
  return prefix + (text(error) || "The commissioning request could not be completed. Refresh to retry.");
}
