import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'

export default [
  { ignores: ['dist/', 'node_modules/'] },

  // ── JS baseline ───────────────────────────────────────────────────────────
  js.configs.recommended,

  // ── Vue SFCs ──────────────────────────────────────────────────────────────
  // pluginVue flat/recommended sets vue-eslint-parser as the main parser for .vue
  ...pluginVue.configs['flat/recommended'],
  // Add tseslint.parser as the embedded <script lang="ts"> parser
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: { parser: tseslint.parser },
    },
    rules: {
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/multiline-html-element-content-newline': 'off',
      'vue/html-indent': 'off',
      'vue/require-default-prop': 'off',
      'vue/multi-word-component-names': 'off',
      'vue/no-v-html': 'off',
      'vue/html-self-closing': ['warn', {
        html: { void: 'always', normal: 'always', component: 'always' },
      }],
    },
  },

  // ── TypeScript (.ts files only, NOT .vue) ─────────────────────────────────
  // Scope each TS config to .ts files so it doesn't override the Vue parser
  ...tseslint.configs.recommended.map(config => ({
    ...config,
    files: ['**/*.ts'],
  })),

  // ── TypeScript rule overrides ─────────────────────────────────────────────
  {
    files: ['**/*.ts'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
      }],
    },
  },
]
