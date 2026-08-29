import js from "@eslint/js";
import pluginVue from "eslint-plugin-vue";
import globals from "globals";
// Disables all formatting-domain rules that Prettier owns. Required because
// this project formats with Prettier (see the `format` npm script). The legacy
// .eslintrc.cjs used @vue/eslint-config-prettier for this; when the config was
// migrated to flat config that integration was dropped, which re-enabled ~900
// formatting warnings and (with --max-warnings=0) broke the CI lint step.
import prettierConfig from "eslint-config-prettier";

export default [
  {
    ignores: ["dist/**", "node_modules/**"],
  },
  js.configs.recommended,
  ...pluginVue.configs["flat/recommended"],
  {
    files: ["src/**/*.{js,vue}"],
    // Ports the environment the removed .eslintrc.cjs declared
    // (env: { browser, node, es2021 }). eslint 9 shipped these browser/node
    // globals transitively; eslint 10 dropped the bundled `globals` re-export,
    // so the flat config must declare them itself or every DOM/Node global
    // (window, document, localStorage, fetch, console, self, setTimeout, …)
    // trips no-undef. Without this the eslint 9 -> 10 bump raises ~1000
    // no-undef errors that are purely a missing-globals artifact, not real bugs.
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      "vue/multi-word-component-names": "off",
      "vue/singleline-html-element-content-newline": "off",
      "vue/max-attributes-per-line": "off",
      "vue/html-self-closing": "off",
      "vue/require-default-prop": "off",
      "vue/html-closing-bracket-newline": "off",
    },
  },
  // Must come last so it can turn off any stylistic rules enabled above.
  prettierConfig,
];
