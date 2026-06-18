import { readFileSync } from "fs";
import { resolve } from "path";
import { type NextRequest } from "next/server";

let cachedKey: string | undefined;
function loadApiKey(): string | undefined {
  if (cachedKey !== undefined) return cachedKey || undefined;
  if (process.env.TOMTOM_API_KEY) {
    cachedKey = process.env.TOMTOM_API_KEY;
    return cachedKey;
  }
  try {
    const envPath = resolve(process.cwd(), "..", ".env");
    const content = readFileSync(envPath, "utf-8");
    const key = content.match(/^TOMTOM_API_KEY=(.+)$/m)?.[1]?.trim();
    cachedKey = key ?? "";
    return key;
  } catch {
    cachedKey = "";
    return undefined;
  }
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const z = searchParams.get("z");
  const x = searchParams.get("x");
  const y = searchParams.get("y");

  if (!z || !x || !y) {
    return new Response("Missing z, x, or y query params", { status: 400 });
  }

  const apiKey = loadApiKey();
  if (!apiKey) {
    return new Response("TOMTOM_API_KEY not configured", { status: 503 });
  }

  const style = "relative";
  const url = `https://api.tomtom.com/traffic/map/4/tile/flow/${style}/${z}/${x}/${y}.png?key=${apiKey}&tileSize=256`;

  try {
    const upstream = await fetch(url);
    if (!upstream.ok) {
      return new Response(`TomTom API error: ${upstream.status}`, {
        status: upstream.status,
      });
    }

    const body = upstream.body;
    return new Response(body, {
      status: 200,
      headers: {
        "Content-Type": "image/png",
        "Cache-Control": "public, max-age=120",
      },
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Upstream fetch failed";
    return new Response(msg, { status: 502 });
  }
}
