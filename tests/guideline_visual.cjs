// Isolated rendering fixture; never submits patient data or calls the clinical model.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const vue = fs.readFileSync(require.resolve('vue/dist/vue.global.prod.js', {
  paths: [process.env.VISUAL_NODE_MODULES || __dirname],
}), 'utf8');
const quote = 'is most commonly caused by a viral upper respiratory tract infection, such as a cold or flu';
const reference = {
  source_id: 'nice:ng120:ng120-1_1_1', title: 'Cough (acute): antimicrobial prescribing',
  guideline_code: 'NG120', publisher: 'NICE', section: '1.1.1', published_date: '2019-02-07',
  source_url: 'https://www.nice.org.uk/guidance/ng120/chapter/recommendations#ng120-1_1_1',
  quote, highlights: [quote], relation: 'evaluation', checked_at: '2026-09-22T00:00:00+00:00',
  translation: '最常见由病毒性上呼吸道感染引起，例如感冒或流感。',
  applicability: '合成测试病例：短期咳嗽可与该病因概述对照。',
  limitations: '本条不是确诊标准，仍需结合实际病史、体格检查及必要的辅助检查。',
};
const diagnoses = [{ disease: '急性咳嗽（合成测试病例）', diagnosis_type: '辅助诊断方向',
  reasoning: '需要结合临床情况进一步评估。', uncertainties: ['尚未面诊查体'],
  evidence: ['合成病例：咳嗽三天'], suggestions: [], references: [reference], guideline_status: 'matched' },
{ disease: '其他待排除原因（合成测试）', diagnosis_type: '待排除', reasoning: '',
  uncertainties: [], evidence: [], suggestions: [], references: [], guideline_status: 'not_found' }];
const html = fs.readFileSync(path.join(__dirname, '../medrag_frontend/llm_index.html'), 'utf8')
  .replace(/<link rel="stylesheet" href="\.\/mobile.css[^\"]*">/, () => `<style>${fs.readFileSync(path.join(__dirname, '../medrag_frontend/mobile.css'), 'utf8')}</style>`)
  .replace('<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>', () => `<script>${vue}</script>`)
  .replace('const currentStep = ref(1);', 'const currentStep = ref(3);')
  .replace('const finalDiagnoses = ref([]);', () => `const finalDiagnoses = ref(${JSON.stringify(diagnoses)});`);
(async () => {
  const browser = await chromium.launch({ headless: true,
    executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  try {
    for (const width of [390, 1280]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/*', route => route.request().resourceType() === 'document'
        ? route.fulfill({ contentType: 'text/html', body: html })
        : route.fulfill({ contentType: 'application/json', body: '{"status":"ok"}' }));
      await page.goto('http://127.0.0.1/medrag/');
      await page.locator('.guideline-match').waitFor();
      assert.equal(await page.locator('.guideline-match').textContent(), quote);
      const metrics = await page.evaluate(() => ({
        width: innerWidth, scroll: document.documentElement.scrollWidth,
        color: getComputedStyle(document.querySelector('.guideline-match')).color,
      }));
      assert.ok(metrics.scroll <= metrics.width, JSON.stringify(metrics));
      assert.equal(metrics.color, 'rgb(180, 35, 24)');
      await page.locator('.guideline-reference summary').click();
      assert.equal(await page.locator('.guideline-reference').getAttribute('open'), null);
      await page.locator('.guideline-reference summary').click();
      assert.deepEqual(errors, []);
      const output = path.join(os.tmpdir(), `medrag-guideline-${width}.png`);
      await page.locator('.guideline-quote').scrollIntoViewIfNeeded();
      await page.screenshot({ path: output });
      console.log(output);
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
