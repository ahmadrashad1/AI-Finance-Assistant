// Deliberately minimal: escapes HTML first, then applies a handful of
// markdown transforms (bold, inline code, line breaks, and GFM-style pipe
// tables). No new dependency, per the Milestone 2 design doc - Milestone 5
// adds table support by hand rather than pulling in a markdown library,
// since a full-dependency renderer is out of scope for one syntax feature.
// Escaping before transforming is what makes this safe to render with
// dangerouslySetInnerHTML - raw "<script>" etc. in model output becomes
// inert text, not markup.

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderInlineSpan(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+?)`/g, "<code>$1</code>");
}

function parseTableRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((cell) => cell.trim());
}

function isTableRowLine(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.startsWith("|") && trimmed.endsWith("|") && trimmed.length > 1;
}

function isSeparatorRow(cells: string[]): boolean {
  return cells.length > 0 && cells.every((cell) => /^:?-+:?$/.test(cell));
}

function renderTable(headerCells: string[], bodyRows: string[][]): string {
  const thead = `<thead><tr>${headerCells
    .map((cell) => `<th>${renderInlineSpan(escapeHtml(cell))}</th>`)
    .join("")}</tr></thead>`;
  const tbody = `<tbody>${bodyRows
    .map(
      (row) =>
        `<tr>${row
          .map((cell) => `<td>${renderInlineSpan(escapeHtml(cell))}</td>`)
          .join("")}</tr>`,
    )
    .join("")}</tbody>`;
  return `<table>${thead}${tbody}</table>`;
}

export function renderInlineMarkdown(text: string): string {
  const lines = text.split("\n");
  const htmlParts: string[] = [];
  let proseBuffer: string[] = [];

  const flushProse = () => {
    if (proseBuffer.length === 0) {
      return;
    }
    const joined = proseBuffer.join("\n");
    htmlParts.push(renderInlineSpan(escapeHtml(joined)).replace(/\n/g, "<br />"));
    proseBuffer = [];
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i]!;
    const next = lines[i + 1];
    if (
      isTableRowLine(line) &&
      next !== undefined &&
      isTableRowLine(next) &&
      isSeparatorRow(parseTableRow(next))
    ) {
      flushProse();
      const headerCells = parseTableRow(line);
      const bodyRows: string[][] = [];
      let j = i + 2;
      while (j < lines.length) {
        const rowLine = lines[j]!;
        if (!isTableRowLine(rowLine)) {
          break;
        }
        bodyRows.push(parseTableRow(rowLine));
        j++;
      }
      htmlParts.push(renderTable(headerCells, bodyRows));
      i = j;
    } else {
      proseBuffer.push(line);
      i++;
    }
  }
  flushProse();
  return htmlParts.join("");
}
