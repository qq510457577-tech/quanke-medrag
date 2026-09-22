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
  Vue: { ref: value => ({ value }), computed: fn => ({ get value() { return fn(); } }),
    createApp: config => ({ mount() { app = config.setup(); } }) },
  window: { location: { hostname: 'maoni.icu', pathname: '/medrag/' } },
  AbortController, console, setTimeout: () => 1, clearTimeout() {}, setInterval: () => 1, clearInterval() {},
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
      data = { diagnoses: [], clinical_reasoning: '信息不足', care_plan: ['面诊复评'] };
    }
    return { ok: true, json: async () => data };
  },
};
vm.runInNewContext(script, context);
(async () => {
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
  console.log('Frontend completes all six answered rounds before requesting the report.');
})().catch(error => { console.error(error); process.exitCode = 1; });
