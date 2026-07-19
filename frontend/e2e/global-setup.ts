import { fileURLToPath } from "node:url";
import { createServer } from "vite";

export default async function startE2eServer() {
  const frontendRoot = fileURLToPath(new URL("..", import.meta.url));
  process.env.VITE_ENABLE_MSW = "true";

  const server = await createServer({
    root: frontendRoot,
    configFile: fileURLToPath(new URL("../vite.config.ts", import.meta.url)),
    server: {
      host: "127.0.0.1",
      port: 5173,
      strictPort: true,
    },
  });
  await server.listen();

  return async () => {
    await server.close();
  };
}
