// Deliberately minimal: escapes HTML first, then applies a handful of
// markdown transforms. No new dependency, per the Milestone 2 design doc.
// Escaping before transforming is what makes this safe to render with
// dangerouslySetInnerHTML - raw "<script>" etc. in model output becomes
// inert text, not markup.
export function renderInlineMarkdown(text: string): string {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return escaped
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+?)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br />");
}
