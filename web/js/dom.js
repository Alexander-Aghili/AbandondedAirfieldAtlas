export const $ = (id) => document.getElementById(id);
export const num = (n) => n.toLocaleString();
export const validSource = (value) => {
  try {
    const u = new URL(value);
    return (
      ["https:", "http:"].includes(u.protocol) &&
      ["airfields-freeman.com", "www.airfields-freeman.com"].includes(
        u.hostname,
      ) &&
      !u.username &&
      !u.password
    );
  } catch {
    return false;
  }
};
export function sourceLink(p) {
  const a = document.createElement("a");
  a.className = "result-title";
  a.append(document.createTextNode(p.name));
  const arrow = document.createElement("span");
  arrow.className = "arrow";
  arrow.textContent = "↗";
  arrow.setAttribute("aria-hidden", "true");
  a.append(arrow);
  if (validSource(p.source_url)) {
    a.href = p.source_url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.setAttribute("aria-label", `${p.name} (opens a new tab)`);
  }
  return a;
}
