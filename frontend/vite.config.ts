import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vitest/config";
import react from "@vitejs/plugin-react";

const practiceRulesModuleId = "virtual:practice-semantic-rules";
const resolvedPracticeRulesModuleId = `\0${practiceRulesModuleId}`;

function practiceSemanticRulesPlugin(): Plugin {
  return {
    name: "practice-semantic-rules",
    resolveId(id) {
      return id === practiceRulesModuleId ? resolvedPracticeRulesModuleId : null;
    },
    load(id) {
      if (id !== resolvedPracticeRulesModuleId) return null;
      const scenariosRoot = fileURLToPath(
        new URL("../data/sample/practice-scenarios/", import.meta.url),
      );
      const rulesByScenario = Object.fromEntries(
        readdirSync(scenariosRoot, { withFileTypes: true })
          .filter((entry) => entry.isDirectory())
          .map((entry) => {
            const answerKeyPath = fileURLToPath(
              new URL(
                `../data/sample/practice-scenarios/${entry.name}/answer-key.json`,
                import.meta.url,
              ),
            );
            const answerKey = JSON.parse(readFileSync(answerKeyPath, "utf8")) as {
              scenario_id: string;
              deterministic_semantic_rules?: unknown[];
              debrief?: {
                defensive_stop_action_ids?: string[];
                ending_reports?: Record<string, unknown>;
              };
            };
            return [
              answerKey.scenario_id,
              answerKey.deterministic_semantic_rules ?? [],
            ];
          }),
      );
      const debriefByScenario = Object.fromEntries(
        readdirSync(scenariosRoot, { withFileTypes: true })
          .filter((entry) => entry.isDirectory())
          .map((entry) => {
            const answerKeyPath = fileURLToPath(
              new URL(
                `../data/sample/practice-scenarios/${entry.name}/answer-key.json`,
                import.meta.url,
              ),
            );
            const answerKey = JSON.parse(readFileSync(answerKeyPath, "utf8")) as {
              scenario_id: string;
              debrief?: {
                defensive_stop_action_ids?: string[];
                ending_reports?: Record<string, unknown>;
              };
            };
            return [
              answerKey.scenario_id,
              {
                defensive_stop_action_ids:
                  answerKey.debrief?.defensive_stop_action_ids ?? [],
                ending_reports: answerKey.debrief?.ending_reports ?? {},
              },
            ];
          }),
      );
      return [
        `const semanticRulesByScenario = ${JSON.stringify(rulesByScenario)};`,
        `export const debriefByScenario = ${JSON.stringify(debriefByScenario)};`,
        "export default semanticRulesByScenario;",
      ].join("\n");
    },
  };
}

export default defineConfig({
  test: { exclude: ["e2e/**", "node_modules/**", "dist/**"] },
  plugins: [react(), practiceSemanticRulesPlugin()],
  server: {
    // 기본값은 Windows에서 ::1(IPv6)에만 바인딩돼 127.0.0.1 접속·cloudflared 원본 연결이 거부된다.
    host: "127.0.0.1",
    port: 5173,
    // Cloudflare Quick Tunnel 등으로 B PC 서버를 A·C가 원격 접속할 때 Host 헤더 허용
    allowedHosts: [".trycloudflare.com"],
    proxy: {
      "/api": {
        // 기본 8301. 로컬에서 포트 충돌 시 VITE_BACKEND_TARGET로 덮어쓴다.
        target: process.env.VITE_BACKEND_TARGET ?? "http://127.0.0.1:8301",
        changeOrigin: true,
      },
    },
  },
});
