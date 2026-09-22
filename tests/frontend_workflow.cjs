const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../medrag_frontend/llm_index.html'), 'utf8');
const script = html.slice(html.lastIndexOf('<script>') + 8, html.lastIndexOf('</script>'));
let app;
let completed = 0;
let finalCalls = 0;
const question = round => ({ question_id: `r${round}`, question: '待补充信息', input_type: 'text' });
const context = {
  Vue: { ref: value => ({ value }), computed: fn => ({ get value() { return fn(); } }), watch() {}, nextTick: async () => {}, onMounted() {}, onBeforeUnmount() {},
    createApp: config => ({ mount() { app = config.setup(); } }) },
  window: { location: { hostname: 'maoni.icu', pathname: '/medrag/' } },
  document: { querySelector: () => null },
  AbortController, URL, console, setTimeout: () => 1, clearTimeout() {}, setInterval: () => 1, clearInterval() {},
  alert: message => { throw new Error(message); },
  fetch: async (url, options) => {
    let data;
    if (url.endsWith('/health')) data = { status: 'ok' };
    else if (url.endsWith('/start')) data = { session_id: 'test', round_count: 1, max_rounds: 6, first_round_questions: [question(1)] };
    else if (url.endsWith('/follow-up')) {
      const body = JSON.parse(options.body);
      assert.equal(body.answers[0].question_id, `r${completed + 1}`);
      completed++;
      data = { round_count: Math.min(completed + 1, 6), max_rounds: 6, is_diagnosis_clear: completed === 6,
        next_round_questions: completed < 6 ? [question(completed + 1)] : [] };
    } else {
      assert.equal(completed, 6, 'Final report requested before answering round six');
      assert.deepEqual(JSON.parse(options.body).answers, []);
      finalCalls++;
      data = { diagnoses: [{ disease: '测试方向', basis: ['病例事实'], references: [{ source_id: 'nice:test',
        source_url: 'https://www.nice.org.uk/guidance/ng120/chapter/recommendations#test', quote: 'Do not assume a result.', highlights: ['not assume'] }], guideline_status: 'matched' },
        { disease: '另一方向', basis: [], references: [], guideline_status: 'not_found' }], clinical_reasoning: '信息不足', care_plan: ['面诊复评'] };
    }
    return { ok: true, json: async () => data };
  },
};
vm.runInNewContext(script, context);
(async () => {
  await app.submitSymptoms();
  assert.ok(app.formError.value);
  app.addQuickSymptom('咳嗽');
  assert.equal(app.symptoms.value.length, 1, 'Quick selection reuses empty symptom');
  assert.ok(!app.availableCommonSymptoms.value.includes('咳嗽'));
  app.addQuickSymptom('咳嗽');
  assert.equal(app.symptoms.value.length, 1, 'Quick selection is deduplicated');
  app.patientInfo.value = { age: 42, gender: 'female' };
  app.symptoms.value = [{ description: '咳嗽' }];
  await app.submitSymptoms();
  for (let round = 1; round <= 6; round++) {
    assert.equal(app.currentRound.value, round);
    assert.equal(app.currentStep.value, 2);
    app.currentQuestions.value[0].answer = '未检查';
    await app.nextRound();
  }
  assert.equal(finalCalls, 1);
  assert.equal(app.currentStep.value, 3);
  assert.equal(app.finalDiagnoses.value[0].references.length, 1);
  assert.equal(app.finalDiagnoses.value[1].references.length, 0);
  const parts = app.guidelineSegments('Do not assume a result.', ['not assume']);
  assert.equal(parts.map(p => p.text).join(''), 'Do not assume a result.');
  assert.equal(parts.filter(p => p.highlight).map(p => p.text).join(''), 'not assume');
  assert.equal(app.safeGuidelineUrl('javascript:alert(1)'), '');
  assert.equal(app.safeGuidelineUrl('https://evil.test/guidance/ng120'), '');
  assert.equal(app.guidelineSegments('<img src=x onerror=alert(1)>', ['unrelated'])[0].highlight, false);
  assert.ok(!html.includes('v-html="highlightText(ref.content)"'));
  console.log('Frontend completes all six answered rounds before requesting the report.');
})().catch(error => { console.error(error); process.exitCode = 1; });
