const path = require('node:path');
const { defineConfig, devices } = require('../../../../../../web/node_modules/@playwright/test');
module.exports = defineConfig({
 testDir:path.resolve(__dirname,'../../../../../../web/e2e/mf'),
 fullyParallel:false,workers:1,retries:0,timeout:60000,
 reporter:[['list'],['json',{outputFile:path.resolve(__dirname,'../evidence/'+(process.env.AUDIT_PREFIX || '')+'mf-browser-results.json')}]],
 outputDir:path.resolve(__dirname,'../evidence/'+(process.env.AUDIT_PREFIX || '')+'mf-browser-artifacts'),
 use:{baseURL:process.env.AUDIT_BASE || 'http://localhost:8000',trace:'retain-on-failure'},
 projects:[{name:'served-chromium',use:{...devices['Desktop Chrome']}}]
});
