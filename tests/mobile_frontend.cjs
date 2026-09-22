const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.join(__dirname, '../medrag_frontend');
const html = fs.readFileSync(path.join(root, 'llm_index.html'), 'utf8');
const css = fs.readFileSync(path.join(root, 'mobile.css'), 'utf8');
const vue = fs.readFileSync(require.resolve('vue/dist/vue.global.prod.js', {
  paths: [process.env.VISUAL_NODE_MODULES || __dirname],
}), 'utf8');
const sizes = [[320, 568], [360, 800], [375, 667], [390, 844], [412, 915], [430, 932], [768, 1024], [1280, 900], [844, 390]];
const questionSet = round => [
  { question_id: `r${round}a`, question: '是否已完成相关检查？', input_type: 'yesno' },
  { question_id: `r${round}b`, question: '当前症状与活动是否有关？', input_type: 'single', options: ['活动后出现，但目前缺少进一步检查结果', '不清楚'] },
  { question_id: `r${round}c`, question: '本轮需要记录的情况有哪些？', input_type: 'multiple', options: ['未检查', '无用药记录'] },
  { question_id: `r${round}d`, question: '症状的严重程度如何？', input_type: 'severity' },
  { question_id: `r${round}e`, question: '请补充症状发生的时间和变化。', input_type: 'text' },
];
async function checkLayout(page, width) {
  const result = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    width: innerWidth,
    smallTargets: [...document.querySelectorAll('button, select, .gender-option, .severity-btn, .option-btn, .yesno-btn')]
      .filter(e => e.getBoundingClientRect().height > 0 && e.getBoundingClientRect().height < 43)
      .map(e => e.textContent.trim()),
  }));
  assert.equal(result.width, width);
  assert.ok(result.scroll <= width, `Horizontal overflow: ${JSON.stringify(result)}`);
  assert.deepEqual(result.smallTargets, []);
}
(async () => {
  const browser = await chromium.launch({ headless: true,
    executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  try {
    for (const [width, height] of sizes) {
      const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: width < 500 ? 2 : 1 });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      let completed = 0;
      let startCalls = 0;
      let finalCalls = 0;
      let releaseStart;
      const gate = new Promise(resolve => { releaseStart = resolve; });
      await page.route('**/*', async route => {
        const url = route.request().url();
        if (url.includes('vue.global')) return route.fulfill({ contentType: 'text/javascript', body: vue });
        if (url.includes('/mobile.css')) return route.fulfill({ contentType: 'text/css', body: css });
        if (route.request().resourceType() === 'document') return route.fulfill({ contentType: 'text/html', body: html });
        let data = { status: 'ok' };
        if (url.endsWith('/start')) {
          startCalls++;
          const body = route.request().postDataJSON();
          assert.equal(body.symptoms.length, 1);
          assert.equal(body.symptoms[0].duration_years, 10);
          assert.equal(body.symptoms[0].severity, 3);
          await gate;
          data = { session_id: 'synthetic-test', round_count: 1, max_rounds: 6, first_round_questions: questionSet(1) };
        } else if (url.endsWith('/follow-up')) {
          const body = route.request().postDataJSON();
          assert.equal(body.answers.length, 5);
          assert.equal(body.answers[0].answer, '否');
          assert.deepEqual(body.answers[2].answer, ['未检查', '无用药记录']);
          assert.equal(body.answers[3].answer, 3);
          completed++;
          data = { round_count: Math.min(completed + 1, 6), max_rounds: 6,
            is_diagnosis_clear: completed === 6, next_round_questions: questionSet(completed + 1) };
        } else if (url.endsWith('/final')) {
          assert.equal(completed, 6);
          finalCalls++;
          data = { diagnoses: [], clinical_reasoning: '合成测试：尚需补充临床检查信息。', care_plan: ['面诊复评'] };
        }
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
      });
      await page.goto('http://127.0.0.1/medrag/');
      await page.getByRole('heading', { name: '患者信息与症状' }).waitFor();
      await checkLayout(page, width);
      await page.locator('.footer-disclaimer').scrollIntoViewIfNeeded();
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      const footer = await page.locator('.footer-disclaimer').boundingBox();
      const dock = await page.locator('.action-dock').boundingBox();
      assert.ok(footer.y + footer.height <= dock.y, 'Bottom action bar must not cover the last content');
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: path.join(os.tmpdir(), `medrag-mobile-home-${width}.png`) });
      await page.getByRole('button', { name: '开始智能诊断', exact: true }).click();
      await page.locator('.form-error').waitFor();
      assert.equal(startCalls, 0);
      await page.getByLabel('年龄（岁）').fill('42');
      if (width < 601) {
        // Simulate visual viewport reduction without accessing any real patient data.
        await page.evaluate(() => {
          Object.defineProperty(window.visualViewport, 'height', { configurable: true, value: innerHeight - 300 });
          window.visualViewport.dispatchEvent(new Event('resize'));
        });
        await page.locator('.keyboard-open').waitFor();
        assert.equal(await page.locator('.action-dock').evaluate(e => getComputedStyle(e).position), 'static');
        await page.evaluate(() => {
          delete window.visualViewport.height;
          window.visualViewport.dispatchEvent(new Event('resize'));
        });
        await page.locator('.keyboard-open').waitFor({ state: 'detached' });
        assert.equal(await page.locator('.action-dock').evaluate(e => getComputedStyle(e).position), 'fixed');
      }
      await page.locator('.gender-option').filter({ hasText: '女' }).click();
      await page.getByRole('button', { name: '咳嗽', exact: true }).click();
      assert.equal(await page.locator('.symptom-item').count(), 1);
      assert.equal(await page.getByRole('button', { name: '咳嗽', exact: true }).count(), 0);
      await page.getByLabel('症状1持续年数', { exact: true }).selectOption('10');
      await page.locator('.severity-btn').filter({ hasText: '中度' }).click();
      await page.getByRole('button', { name: '乏力', exact: true }).click();
      await page.getByRole('button', { name: '删除症状2', exact: true }).click();
      assert.equal(await page.getByRole('button', { name: '乏力', exact: true }).count(), 1);
      await checkLayout(page, width);
      await page.getByRole('button', { name: '开始智能诊断', exact: true }).click();
      assert.equal(await page.getByLabel('年龄（岁）').isDisabled(), true);
      releaseStart();
      await page.getByRole('heading', { name: 'AI智能追问', exact: true }).waitFor();
      assert.equal(startCalls, 1);
      await checkLayout(page, width);
      await page.screenshot({ path: path.join(os.tmpdir(), `medrag-mobile-questions-${width}.png`) });
      const rounds = width === 390 ? 6 : 1;
      for (let round = 1; round <= rounds; round++) {
        const cards = page.locator('.question-card');
        await cards.nth(0).getByLabel('否', { exact: true }).check();
        await cards.nth(1).getByLabel('不清楚', { exact: true }).check();
        await cards.nth(2).getByLabel('未检查', { exact: true }).check();
        await cards.nth(2).getByLabel('无用药记录', { exact: true }).check();
        await cards.nth(3).locator('.severity-btn').filter({ hasText: '中度' }).click();
        await cards.nth(4).locator('textarea').fill('三天，合成测试病例。');
        await cards.nth(4).locator('textarea').blur();
        await page.getByRole('button', { name: '提交本轮回答', exact: true }).click();
        if (round < 6) await page.locator(`#question-r${round + 1}a`).waitFor();
      }
      if (rounds === 6) {
        await page.getByRole('heading', { name: '辅助诊断结论', exact: true }).waitFor();
        assert.equal(finalCalls, 1);
        page.once('dialog', dialog => dialog.dismiss());
        await page.getByRole('button', { name: '开始新的诊断', exact: true }).click();
        assert.equal(await page.getByRole('heading', { name: '辅助诊断结论', exact: true }).count(), 1);
        page.once('dialog', dialog => dialog.accept());
        await page.getByRole('button', { name: '开始新的诊断', exact: true }).click();
        await page.getByRole('heading', { name: '患者信息与症状' }).waitFor();
      }
      assert.deepEqual(errors, []);
      console.log(`PASS ${width}x${height}: layout, controls, validation, deduplication, ${rounds} rounds`);
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
