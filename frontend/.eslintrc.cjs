/* eslint-env node */

module.exports = {
  root: true,
  env: { browser: true, es2021: true, node: true },
  extends: [
    'plugin:vue/vue3-recommended',
    'eslint:recommended',
    '@vue/eslint-config-typescript',
    '@vue/eslint-config-prettier/skip-formatting',
    './.eslintrc-auto-import.json',
  ],
  parserOptions: { ecmaVersion: 'latest' },
  rules: {
    // 禁止残留 console.log（允许 warn / error）
    'no-console': ['error', { allow: ['warn', 'error'] }],
    'no-debugger': 'error',
    'vue/multi-word-component-names': 'off',
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
  },
  ignorePatterns: ['dist', 'node_modules', 'src/types/auto-imports.d.ts', 'src/types/components.d.ts'],
}
