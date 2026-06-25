import * as duckdb from "@duckdb/duckdb-wasm";
import { R2_BASE_URL } from "@/lib/data";

let db: duckdb.AsyncDuckDB | null = null;
let initPromise: Promise<duckdb.AsyncDuckDB> | null = null;

const PARQUET_URL = `${R2_BASE_URL}/block_groups.parquet`;

async function initDuckDB(): Promise<duckdb.AsyncDuckDB> {
  if (db) return db;
  if (initPromise) return initPromise;

  initPromise = (async () => {
    const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles();
    const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES);

    const workerUrl = URL.createObjectURL(
      new Blob([`importScripts("${bundle.mainWorker!}");`], {
        type: "text/javascript",
      }),
    );

    const worker = new Worker(workerUrl);
    const logger =
      process.env.NODE_ENV === "development"
        ? new duckdb.ConsoleLogger()
        : new duckdb.VoidLogger();
    const instance = new duckdb.AsyncDuckDB(logger, worker);
    await instance.instantiate(bundle.mainModule, bundle.pthreadWorker);
    URL.revokeObjectURL(workerUrl);

    const conn = await instance.connect();
    await conn.query(`
      CREATE VIEW block_groups AS
      SELECT * FROM read_parquet('${PARQUET_URL}')
    `);
    await conn.close();

    db = instance;
    return instance;
  })().catch((err) => {
    initPromise = null;
    throw err;
  });

  return initPromise;
}

export async function queryBlockGroups(
  metroId?: string,
): Promise<Record<string, string | number | null>[]> {
  const instance = await initDuckDB();
  const conn = await instance.connect();

  try {
    let result;
    if (metroId) {
      const stmt = await conn.prepare(
        "SELECT * FROM block_groups WHERE metro_id = $1",
      );
      result = await stmt.query(metroId);
    } else {
      result = await conn.query("SELECT * FROM block_groups");
    }
    return arrowToRows(result);
  } finally {
    await conn.close();
  }
}

function arrowToRows(
  table: { numRows: number; schema: { fields: Array<{ name: string }> }; getChild: (name: string) => { get: (i: number) => unknown } | null },
): Record<string, string | number | null>[] {
  const rows: Record<string, string | number | null>[] = [];
  for (let i = 0; i < table.numRows; i++) {
    const row: Record<string, string | number | null> = {};
    for (const field of table.schema.fields) {
      const col = table.getChild(field.name);
      const val = col?.get(i) ?? null;
      if (val === null) {
        row[field.name] = null;
      } else if (typeof val === "bigint") {
        row[field.name] = Number(val);
      } else if (typeof val === "string" || typeof val === "number") {
        row[field.name] = val;
      } else {
        row[field.name] = String(val);
      }
    }
    rows.push(row);
  }
  return rows;
}
