import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import fs from "node:fs";
import path from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";

function formSubmissionPlugin(): Plugin {
  return {
    name: "form-submission-plugin",
    configureServer(server) {
      server.middlewares.use((req: IncomingMessage, res: ServerResponse, next: (err?: unknown) => void) => {
        if (req.method !== "POST" || req.url !== "/api/form-submissions") {
          next();
          return;
        }

        let body = "";
        req.on("data", (chunk: Buffer) => {
          body += chunk.toString();
        });

        req.on("end", () => {
          try {
            const payload = JSON.parse(body);
            const outputPath = path.resolve(process.cwd(), "public", "form-submissions.json");
            const now = new Date().toISOString();
            const entry = {
              submittedAt: now,
              ...payload,
            };

            let existing: unknown[] = [];
            if (fs.existsSync(outputPath)) {
              const raw = fs.readFileSync(outputPath, "utf8");
              existing = raw.trim() ? JSON.parse(raw) : [];
              if (!Array.isArray(existing)) existing = [];
            } else {
              fs.mkdirSync(path.dirname(outputPath), { recursive: true });
            }

            const nextData = [...existing, entry];
            fs.writeFileSync(outputPath, JSON.stringify(nextData, null, 2), "utf8");

            res.statusCode = 200;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ ok: true }));
          } catch (error) {
            res.statusCode = 500;
            res.setHeader("Content-Type", "application/json");
            res.end(
              JSON.stringify({
                ok: false,
                error: error instanceof Error ? error.message : "Failed to save form submission",
              })
            );
          }
        });
      });
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), formSubmissionPlugin()],
});
