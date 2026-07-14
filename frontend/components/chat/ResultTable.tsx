import type { TableSegment } from "./markdown";
import styles from "./ResultTable.module.css";

export interface ResultTableProps {
  table: TableSegment;
}

function parseNumeric(cell: string): number | null {
  const cleaned = cell.replace(/[$,\s]/g, "");
  if (cleaned === "" || !/^-?\d+(\.\d+)?$/.test(cleaned)) {
    return null;
  }
  return Number(cleaned);
}

function numericColumns(table: TableSegment): boolean[] {
  return table.headerCells.map((_, col) => {
    const cells = table.bodyRows.map((row) => row[col] ?? "");
    const nonEmpty = cells.filter((c) => c.trim() !== "");
    if (nonEmpty.length === 0) {
      return false;
    }
    const numeric = nonEmpty.filter((c) => parseNumeric(c) !== null);
    return numeric.length / nonEmpty.length > 0.5;
  });
}

function cellClass(header: string, cell: string, isNumeric: boolean): string {
  const value = cell.trim().toLowerCase();
  if (/status/i.test(header)) {
    if (value === "paid") {
      return `${styles.cell ?? ""} ${styles.sage ?? ""}`;
    }
    if (value === "overdue") {
      return `${styles.cell ?? ""} ${styles.ember ?? ""}`;
    }
  }
  if (/days/i.test(header)) {
    const n = parseNumeric(cell);
    if (n !== null && n > 0) {
      return `${styles.cell ?? ""} ${styles.numeric ?? ""} ${styles.ember ?? ""}`;
    }
  }
  return isNumeric ? `${styles.cell ?? ""} ${styles.numeric ?? ""}` : (styles.cell ?? "");
}

export function ResultTable({ table }: ResultTableProps) {
  const numeric = numericColumns(table);
  return (
    <div className={styles.card}>
      <table className={styles.table}>
        <thead>
          <tr>
            {table.headerCells.map((cell, i) => (
              <th key={i} className={numeric[i] ? `${styles.header} ${styles.numeric}` : styles.header}>
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.bodyRows.map((row, r) => (
            <tr key={r} className={styles.row}>
              {row.map((cell, c) => (
                <td key={c} className={cellClass(table.headerCells[c] ?? "", cell ?? "", numeric[c] ?? false)}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
