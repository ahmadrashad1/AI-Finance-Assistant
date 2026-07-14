import type { TableSegment } from "./markdown";
import styles from "./ResultTable.module.css";

export interface ResultTableProps {
  table: TableSegment;
}

function displayText(cell: string): string {
  return cell.replace(/\*\*/g, "").replace(/`/g, "");
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
  const headerCells = table.headerCells.map(displayText);
  const bodyRows = table.bodyRows.map((row) => row.map((cell) => displayText(cell ?? "")));
  const cleanedTable: TableSegment = { ...table, headerCells, bodyRows };
  const numeric = numericColumns(cleanedTable);

  const bucketCol = headerCells.findIndex((h) => /bucket/i.test(h));
  const balanceCol = headerCells.findIndex((h) => /balance|total/i.test(h));
  const totalBalance =
    bucketCol !== -1 && balanceCol !== -1
      ? bodyRows.reduce((sum, row) => sum + Math.max(parseNumeric(row[balanceCol] ?? "") ?? 0, 0), 0)
      : 0;

  return (
    <div className={styles.card}>
      <table className={styles.table}>
        <thead>
          <tr>
            {headerCells.map((cell, i) => (
              <th key={i} className={numeric[i] ? `${styles.header} ${styles.numeric}` : styles.header}>
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bodyRows.map((row, r) => (
            <tr key={r} className={styles.row}>
              {row.map((cell, c) => (
                <td key={c} className={cellClass(headerCells[c] ?? "", cell ?? "", numeric[c] ?? false)}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {bucketCol !== -1 && balanceCol !== -1 && totalBalance > 0 && (
        <div className={styles.distribution} aria-hidden="true">
          {bodyRows.map((row, i) => {
            const value = parseNumeric(row[balanceCol] ?? "") ?? 0;
            if (value <= 0) return null;
            const bucket = (row[bucketCol] ?? "").toLowerCase();
            const tone =
              bucket === "current"
                ? styles.segmentSage
                : bucket.includes("90+") || bucket.includes("90 +")
                  ? styles.segmentEmber
                  : styles.segmentBrass;
            return (
              <span
                key={i}
                className={`${styles.segment} ${tone}`}
                style={{ width: `${(value / totalBalance) * 100}%` }}
                title={`${row[bucketCol]}: ${row[balanceCol]}`}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
