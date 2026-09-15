import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";
import { demoWorkspaceMock } from "./server";

function headerMap(request: IncomingMessage): Record<string, string | undefined> {
  const headers: Record<string, string | undefined> = {};
  for (const [key, value] of Object.entries(request.headers)) {
    headers[key] = Array.isArray(value) ? value[0] : value;
  }
  return headers;
}

function readBody(request: IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    request.on("data", (chunk: Buffer) => chunks.push(chunk));
    request.on("end", () => {
      if (chunks.length === 0) {
        resolve(undefined);
        return;
      }
      const text = Buffer.concat(chunks).toString("utf8");
      try {
        resolve(JSON.parse(text) as unknown);
      } catch {
        resolve(Symbol.for("invalid-json"));
      }
    });
    request.on("error", reject);
  });
}

function isWorkspaceApi(pathname: string): boolean {
  return (
    pathname.startsWith("/api/projects/") ||
    pathname.startsWith("/api/issues/") ||
    pathname === "/api/demo/workspace/reset"
  );
}

async function respond(request: IncomingMessage, response: ServerResponse, next: () => void): Promise<void> {
  const raw = request.url ?? "/";
  const pathname = raw.split("?")[0] ?? "/";
  if (request.method === "GET" && pathname === "/api/projects") {
    next();
    return;
  }
  if (request.method === "GET" && /^\/api\/projects\/[^/]+$/.test(pathname)) {
    next();
    return;
  }
  if (!isWorkspaceApi(pathname)) {
    next();
    return;
  }
  const body = request.method === "POST" || request.method === "PATCH" ? await readBody(request) : undefined;
  if (body === Symbol.for("invalid-json")) {
    response.statusCode = 400;
    response.setHeader("Content-Type", "application/json");
    response.setHeader("Cache-Control", "no-store");
    response.end(JSON.stringify({ error: { code: "INVALID_JSON", message: "无法解析 JSON。", fieldErrors: [], requestId: "req_demo" } }));
    return;
  }
  const result = demoWorkspaceMock.handle({ method: request.method ?? "GET", path: raw, headers: headerMap(request), body });
  response.statusCode = result.status;
  response.setHeader("Content-Type", "application/json");
  response.setHeader("Cache-Control", "no-store");
  response.end(JSON.stringify(result.body));
}

export function workspaceMockPlugin(): Plugin {
  return {
    name: "workspace-mock-api",
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        void respond(request, response, next);
      });
    },
    configurePreviewServer(server) {
      server.middlewares.use((request, response, next) => {
        void respond(request, response, next);
      });
    },
  };
}
