import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vuetify from "@vuetify/vite-plugin";
import vueI18n from "@intlify/vite-plugin-vue-i18n";

const path = require("path");

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    // vue({ customElement: true }),
    vue(),
    // https://github.com/vuetifyjs/vuetify-loader/tree/next/packages/vite-plugin
    vuetify({
      autoImport: true,
      // styles: "expose"
    })
    // vueI18n({
    //   include: path.resolve(__dirname, '../translations/**')
    // })
  ],
  define: { "process.env": {} },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src")
    }
  },
  build: {
    // inject css into lib only works in umd mode
    // https://github.com/vitejs/vite/issues/1579
    cssCodeSplit: true,
    lib: {
      entry: path.resolve(__dirname, "src/main.ts"),
      name: "MusicAssistant",
      fileName: (format) => `mass.${format}.js`,
      formats: ["iife", "umd"]
    },
    rollupOptions: {
      output: {
        inlineDynamicImports: true
      }
    }
  },
  server: {
    host: true
  }
  /* remove the need to specify .vue files https://vitejs.dev/config/#resolve-extensions
  resolve: {
    extensions: [
      '.js',
      '.json',
      '.jsx',
      '.mjs',
      '.ts',
      '.tsx',
      '.vue',
    ]
  },
  */
});
