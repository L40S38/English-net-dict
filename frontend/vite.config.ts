import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { sharedConfigPlugin } from "./vite-plugin-config";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), sharedConfigPlugin()],
  server: {
    // 5173 は他プロジェクト（extract-short-movie）が使用中のため、この
    // プロジェクト専用のポートに固定する。strictPort により、万一衝突した
    // 場合は Vite が別ポートへ黙って切り替えず、エラーで気付けるようにする
    // （黙って切り替わるとバックエンドの CORS 許可オリジンと不一致になり、
    // 単語一覧が無言で空になる不具合につながっていた）。
    port: 5190,
    strictPort: true,
  },
});
