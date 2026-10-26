<template>
  <div class="page">
    <!-- 渐变头部：与 Streamlit 版视觉一致 -->
    <header class="tcm-header">
      <h1>中医在线问诊系统</h1>
      <p>基于名老中医医案 RAG 系统 | 结构化问诊单 · 向量检索 + LLM 推理</p>
    </header>

    <!-- 问诊单：七个分组（spec-004） -->
    <section class="card">
      <h3>中医问诊单</h3>
      <form @submit.prevent="startDiagnose">
        <h5>基本信息</h5>
        <div class="grid four">
          <label>姓名（选填）<input v-model.trim="form.姓名" placeholder="请输入姓名" /></label>
          <label>性别
            <span class="radio-row">
              <label><input type="radio" value="男" v-model="form.性别" /> 男</label>
              <label><input type="radio" value="女" v-model="form.性别" /> 女</label>
            </span>
          </label>
          <label>年龄<input type="number" min="0" max="120" v-model.number="form.年龄" /></label>
          <label>病程
            <select v-model="form.病程">
              <option v-for="opt in options.duration" :key="opt">{{ opt }}</option>
            </select>
          </label>
        </div>

        <h5>望诊与切诊（舌、面、脉）</h5>
        <div class="grid four">
          <label>面色<select v-model="form.望诊.面色"><option v-for="opt in options.face" :key="opt">{{ opt }}</option></select></label>
          <label>舌质<select v-model="form.望诊.舌质"><option v-for="opt in options.tongueBody" :key="opt">{{ opt }}</option></select></label>
          <label>舌苔<select v-model="form.望诊.舌苔"><option v-for="opt in options.tongueCoat" :key="opt">{{ opt }}</option></select></label>
          <label>脉象（选填）<input v-model.trim="form.脉象" placeholder="示例：脉细弱" /></label>
        </div>

        <h5>寒热与汗出</h5>
        <div class="grid two">
          <label>寒热<select v-model="form.寒热"><option v-for="opt in options.coldHeat" :key="opt">{{ opt }}</option></select></label>
          <label>汗出<select v-model="form.汗出"><option v-for="opt in options.sweating" :key="opt">{{ opt }}</option></select></label>
        </div>

        <h5>头身胸腹</h5>
        <div class="chips">
          <button type="button" v-for="opt in options.torso" :key="opt"
                  :class="{ active: form.头身胸腹不适.includes(opt) }"
                  @click="toggle(form.头身胸腹不适, opt)">{{ opt }}</button>
        </div>

        <h5>饮食口味</h5>
        <div class="grid three">
          <label>饮食<select v-model="form.饮食"><option v-for="opt in options.diet" :key="opt">{{ opt }}</option></select></label>
          <label>口渴<select v-model="form.口渴"><option v-for="opt in options.thirst" :key="opt">{{ opt }}</option></select></label>
          <label>口味<select v-model="form.口味"><option v-for="opt in options.taste" :key="opt">{{ opt }}</option></select></label>
        </div>

        <h5>睡眠情志</h5>
        <div class="grid two">
          <label>睡眠<select v-model="form.睡眠"><option v-for="opt in options.sleep" :key="opt">{{ opt }}</option></select></label>
          <label>情志<select v-model="form.情志"><option v-for="opt in options.emotion" :key="opt">{{ opt }}</option></select></label>
        </div>

        <h5>二便与经期</h5>
        <div class="grid three">
          <label>大便<select v-model="form.大便"><option v-for="opt in options.stool" :key="opt">{{ opt }}</option></select></label>
          <label>小便<select v-model="form.小便"><option v-for="opt in options.urine" :key="opt">{{ opt }}</option></select></label>
          <label>经期（女性）<select v-model="form.经期"><option v-for="opt in options.menstruation" :key="opt">{{ opt }}</option></select></label>
        </div>

        <h5>主诉与既往史</h5>
        <label class="full">主诉（主要不适症状、必填）
          <textarea v-model.trim="form.主诉" rows="3" placeholder="例如：反复入睡困难，多梦易醒，白天精神不振"></textarea>
        </label>
        <label class="full">既往史 / 过敏史（选填）
          <textarea v-model.trim="form.既往史" rows="2" placeholder="手术史、慢性病史、药物过敏等"></textarea>
        </label>

        <h5>其他伴随症状</h5>
        <div class="chips">
          <button type="button" v-for="opt in options.symptoms" :key="opt"
                  :class="{ active: form.其他伴随症状.includes(opt) }"
                  @click="toggle(form.其他伴随症状, opt)">{{ opt }}</button>
        </div>

        <button class="submit" type="submit" :disabled="loading">
          {{ loading ? '诊断进行中 ...' : '开始诊断' }}
        </button>
      </form>
    </section>

    <!-- 诊断结果区域 -->
    <section class="card">
      <h3>诊断结果</h3>
      <div v-if="error" class="step error">✕ {{ error }}</div>

      <template v-else>
        <div class="step" :class="stepState('query')">
          步骤 1/3 由大模型生成检索语句
          <code v-if="query">{{ query }}</code>
        </div>
        <div class="step" :class="stepState('evidences')">
          步骤 2/3 混合检索医案（取前 {{ evidences.length || 6 }} 条）
        </div>
        <div v-if="evidences.length" class="step-body">
          <table>
            <thead>
              <tr><th>编号</th><th>出处</th><th>标题层级</th><th>向量分</th><th>关键词分</th><th>融合分</th></tr>
            </thead>
            <tbody>
              <tr v-for="(ev, i) in evidences" :key="i">
                <td>[{{ i + 1 }}]</td>
                <td>{{ ev.metadata?.source || '未知医案' }}</td>
                <td>{{ origin(ev.metadata) }}</td>
                <td>{{ (ev.vec_score ?? 0).toFixed(3) }}</td>
                <td>{{ (ev.bm25_score ?? 0).toFixed(3) }}</td>
                <td>{{ (ev.score ?? 0).toFixed(3) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="step" :class="stepState('diagnosis')">
          步骤 3/3 生成诊断结果
          <span v-if="loading && !diagnosisText">（大模型推理通常需要 2~3 分钟才返回首个输出，请耐心等待）</span>
        </div>
        <div v-if="diagnosisText" class="diagnosis">{{ diagnosisText }}</div>

        <details v-if="sections" class="sections">
          <summary>按小节查看诊断结果</summary>
          <div v-for="(body, title) in sections" :key="title">
            <strong>{{ title }}</strong>
            <div class="section-body">{{ body }}</div>
          </div>
        </details>

        <details v-if="evidences.length && !loading" class="sections">
          <summary>参考医案来源</summary>
          <div v-for="(ev, i) in evidences" :key="i" class="evidence">
            <strong>[{{ i + 1 }}] {{ ev.metadata?.source || '未知医案' }}</strong>
            {{ origin(ev.metadata) }}
            （融合 {{ (ev.score ?? 0).toFixed(3) }} · 向量 {{ (ev.vec_score ?? 0).toFixed(3) }} · 关键词 {{ (ev.bm25_score ?? 0).toFixed(3) }}）
            <div class="section-body">{{ (ev.text || '').slice(0, 200) }}{{ (ev.text || '').length > 200 ? '...' : '' }}</div>
          </div>
        </details>
      </template>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'

// 下拉与多选选项：与 Streamlit 版 app.py 保持一致（spec-004）
const options = {
  duration: ['1天内', '1周内', '1月内', '半年内', '1年以上'],
  face: ['正常', '萎黄', '苍白', '㿠白', '潮红', '晦暗'],
  tongueBody: ['淡红', '淡白', '红', '绛', '紫暗', '淡胖有齿痕'],
  tongueCoat: ['薄白', '薄黄', '白厚', '黄厚', '少苔', '剥苔'],
  coldHeat: ['无特殊', '畏寒怕冷', '发热', '恶寒发热', '寒热往来', '五心烦热'],
  sweating: ['正常', '无汗', '自汗', '盗汗', '动则汗出'],
  torso: ['头晕', '头痛', '胸闷', '心悸', '胁胀', '脘腹胀满', '腰膝酸软', '身重困倦', '关节酸痛'],
  diet: ['正常', '纳呆食少', '多食易饥', '饥不欲食', '食后腹胀'],
  thirst: ['不渴', '口干欲饮', '渴喜冷饮', '渴喜热饮', '渴不欲饮'],
  taste: ['正常', '口苦', '口淡', '口甜', '口酸', '口黏'],
  sleep: ['正常', '入睡困难', '多梦易醒', '早醒', '嗜睡'],
  emotion: ['平稳', '急躁易怒', '情绪低落', '焦虑不安', '多思多虑'],
  stool: ['正常', '干结', '便秘', '溏薄', '腹泻', '先干后溏'],
  urine: ['正常', '小便短赤', '小便清长', '尿频', '夜尿多', '淋沥不畅'],
  menstruation: ['不适用', '正常', '提前', '推后', '先后不定期', '痛经', '闭经'],
  symptoms: ['咳嗽', '乏力', '气短', '咽干', '目眩', '耳鸣', '食不知味', '肢体麻木', '下肢水肿'],
}

const form = reactive({
  姓名: '',
  性别: '女',
  年龄: 30,
  病程: '1月内',
  望诊: reactive({ 面色: '正常', 舌质: '淡红', 舌苔: '薄白' }),
  脉象: '',
  寒热: '无特殊',
  汗出: '正常',
  头身胸腹不适: [],
  饮食: '正常',
  口渴: '不渴',
  口味: '正常',
  睡眠: '正常',
  情志: '平稳',
  大便: '正常',
  小便: '正常',
  经期: '不适用',
  主诉: '',
  既往史: '',
  其他伴随症状: [],
})

const loading = ref(false)
const error = ref('')
const query = ref('')
const evidences = ref([])
const diagnosisText = ref('')
const sections = ref(null)
const finished = ref({ query: false, evidences: false, diagnosis: false })

function stepState(step) {
  if (finished.value[step]) return 'done'
  if (loading.value) return 'active'
  return ''
}

function origin(meta) {
  if (!meta) return ''
  return Object.entries(meta)
    .filter(([key, value]) => key !== 'source' && value)
    .map(([, value]) => value)
    .join(' > ')
}

function toggle(list, item) {
  const index = list.indexOf(item)
  if (index >= 0) list.splice(index, 1)
  else list.push(item)
}

function reset() {
  error.value = ''
  query.value = ''
  evidences.value = []
  diagnosisText.value = ''
  sections.value = null
  finished.value = { query: false, evidences: false, diagnosis: false }
}

// 发起 SSE 流式诊断：POST 无法用 EventSource，改用 fetch + ReadableStream 解析
async function startDiagnose() {
  if (!form.主诉) {
    error.value = '主诉为必填项，请填写主要不适症状'
    return
  }
  reset()
  loading.value = true
  try {
    const response = await fetch('/api/diagnose/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...form, 望诊: { ...form.望诊 } }),
    })
    if (!response.ok || !response.body) {
      throw new Error(`后端响应异常：HTTP ${response.status}`)
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let index
      while ((index = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, index)
        buffer = buffer.slice(index + 2)
        const line = frame.split('\n').find((l) => l.startsWith('data: '))
        if (line) handleEvent(JSON.parse(line.slice(6)))
      }
    }
  } catch (exc) {
    error.value = `诊断失败：${exc.message}`
  } finally {
    loading.value = false
  }
}

function handleEvent(event) {
  if (event.type === 'query') {
    query.value = event.query
    finished.value.query = true
  } else if (event.type === 'evidences') {
    evidences.value = event.items || []
    finished.value.evidences = true
  } else if (event.type === 'chunk') {
    diagnosisText.value += event.text
    finished.value.diagnosis = true
  } else if (event.type === 'sections') {
    sections.value = event.sections
  } else if (event.type === 'error') {
    error.value = event.message
  }
}
</script>

<style>
* { box-sizing: border-box; }
body { margin: 0; background: #f5f6fa; font-family: 'Microsoft YaHei', sans-serif; color: #222; }
.page { max-width: 1080px; margin: 0 auto; padding: 24px 16px 60px; }
.tcm-header {
  background: linear-gradient(90deg, #7b2ff7 0%, #f107a3 100%);
  border-radius: 12px; padding: 28px 20px; text-align: center; color: #fff; margin-bottom: 24px;
}
.tcm-header h1 { margin: 0; font-size: 2rem; letter-spacing: 2px; }
.tcm-header p { margin: 6px 0 0; font-size: 0.9rem; opacity: 0.92; }
.card { background: #fff; border-radius: 12px; padding: 20px 24px; margin-bottom: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.card h3 { margin-top: 0; }
h5 { margin: 18px 0 8px; color: #7b2ff7; }
.grid.four { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.grid.three { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.grid.two { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
label { display: block; font-size: 0.85rem; color: #555; }
label input, label select, label textarea {
  width: 100%; margin-top: 4px; padding: 7px 10px; border: 1px solid #d6d6e0;
  border-radius: 6px; font-size: 0.9rem; background: #fff;
}
label textarea { resize: vertical; }
label.full { margin-bottom: 10px; }
.radio-row { display: flex; gap: 16px; margin-top: 8px; }
.radio-row input { width: auto; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chips button {
  border: 1px solid #d6d6e0; background: #fff; border-radius: 16px;
  padding: 5px 14px; font-size: 0.85rem; cursor: pointer;
}
.chips button.active { background: #7b2ff7; border-color: #7b2ff7; color: #fff; }
.submit {
  margin-top: 20px; width: 100%; padding: 10px; border: none; border-radius: 6px;
  background: #e63946; color: #fff; font-size: 1rem; font-weight: 600; cursor: pointer;
}
.submit:hover { background: #d62839; }
.submit:disabled { background: #f2a0a6; cursor: not-allowed; }
.step { padding: 10px 14px; border-left: 4px solid #d6d6e0; background: #fafafc; margin: 8px 0; }
.step.active { border-left-color: #f4a300; background: #fff8e9; }
.step.done { border-left-color: #2a9d8f; background: #effaf7; }
.step.error { border-left-color: #e63946; background: #fdeef0; color: #b02a37; }
.step code { display: block; margin-top: 6px; color: #555; }
.step-body { margin: 8px 0; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th, td { border: 1px solid #ececf4; padding: 6px 10px; text-align: left; }
th { background: #f5f4fb; }
.diagnosis { white-space: pre-wrap; line-height: 1.7; margin-top: 12px; }
.sections { margin-top: 14px; }
.section-body { white-space: pre-wrap; margin: 6px 0 12px; line-height: 1.6; }
.evidence { margin: 10px 0; }
</style>
