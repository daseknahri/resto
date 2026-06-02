import js from "@eslint/js";
import pluginVue from "eslint-plugin-vue";
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
