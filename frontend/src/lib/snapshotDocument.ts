const REMOVED_TAGS = [
  "script",
  "noscript",
  "template",
  "iframe",
  "object",
  "embed",
  "form",
];

/**
 * Prepare collected HTML for a static, same-page preview.
 *
 * The browser snapshot is untrusted input. Scripts and active containers stay
 * disabled, while a base URL lets relative stylesheets and images resolve as
 * they did on the collected page.
 */
export function prepareSnapshotDocument(rawHtml: string, pageUrl: string): string {
  if (!rawHtml.trim()) return "";
  if (typeof DOMParser === "undefined") return rawHtml;

  const document = new DOMParser().parseFromString(rawHtml, "text/html");
  const head = document.head || document.documentElement.insertBefore(
    document.createElement("head"),
    document.documentElement.firstChild,
  );

  document.querySelectorAll(REMOVED_TAGS.join(",")).forEach((node) => node.remove());
  document
    .querySelectorAll("meta[http-equiv], base")
    .forEach((node) => {
      const httpEquiv = node.getAttribute("http-equiv")?.toLowerCase();
      if (node.tagName.toLowerCase() === "base" || httpEquiv === "refresh" ||
          httpEquiv === "content-security-policy") {
        node.remove();
      }
    });
  document.querySelectorAll("*").forEach((element) => {
    Array.from(element.attributes)
      .filter((attribute) => attribute.name.toLowerCase().startsWith("on"))
      .forEach((attribute) => element.removeAttribute(attribute.name));
  });

  try {
    const base = document.createElement("base");
    base.href = new URL(pageUrl, window.location.href).href;
    head.prepend(base);
  } catch {
    // Keep the preview usable for malformed or non-HTTP source URLs.
  }

  const style = document.createElement("style");
  style.textContent = `
    html, body { min-height: 100%; }
    body { margin: 0; overflow-wrap: anywhere; }
    img, video, iframe { max-width: 100%; }
  `;
  head.append(style);

  return `<!doctype html>${document.documentElement.outerHTML}`;
}
