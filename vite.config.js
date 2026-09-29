import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";

// Frontend web do BlazesBot (pywebview + WebView2).
// root: 'web' → o Vite procura o index.html lá dentro.
// build.outDir: '../dist' → gera os arquivos finais fora da pasta web.
// base: './' → URLs RELATIVAS nos assets. O pywebview abre o dist/index.html
// via file://; com base absoluta ('/assets/...') o arquivo não carregaria CSS/JS.
export default defineConfig({
  root: "web",
  base: "./",
  plugins: [vue(), tailwindcss()],
  build: {
    outDir: "../dist",
    emptyOutDir: true,
  },
});