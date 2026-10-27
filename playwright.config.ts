import { defineConfig } from '@playwright/test'

// ./test runs one project per invocation; each writes test-results/<project>/junit.xml.
export default defineConfig({
  fullyParallel: true,
  globalSetup: './tests/e2e/global-setup.ts',
  outputDir: 'test-results/playwright',
  reporter: [
    ['list'],
    ['junit', { outputFile: `test-results/${process.env.EX_PROJECT ?? 'playwright'}/junit.xml` }]
  ],
  projects: [
    { name: 'unit', testDir: 'tests/unit' },
    { name: 'e2e', testDir: 'tests/e2e', testIgnore: '**/packaged.spec.ts' },
    { name: 'packaged', testDir: 'tests/e2e', testMatch: '**/packaged.spec.ts' }
  ]
})
