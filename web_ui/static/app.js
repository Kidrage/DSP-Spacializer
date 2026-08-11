const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const ZONE_META = {
  bass: {label: "低频基座", short: "BASS", help: "保持低频位于正前方，距离变化会同时改变重量感和外部化。"},
  center_anchor: {label: "中央锚点", short: "CENTER", help: "主要承载居中的人声与主体。清晰度敏感时优先微调距离、直达比例和早反射。"},
  front_L_residual: {label: "前左残差", short: "FRONT L", help: "承载左侧前方的非中心内容。默认与前右镜像联动。"},
  front_R_residual: {label: "前右残差", short: "FRONT R", help: "承载右侧前方的非中心内容。默认与前左镜像联动。"},
  side_width: {label: "侧向宽度", short: "SIDE", help: "FOA 声床的侧向部分，只调能量与方向，不伪造距离或直达比例。"},
  rear_ambience: {label: "后方氛围", short: "REAR", help: "FOA 声床的后方扩散内容。过多会让清晰度下降或声像变空。"},
  high_air: {label: "高空空气感", short: "AIR", help: "高频扩散声床，负责上方与外侧的空气感。过多容易显薄。"},
};
const OBJECT_CONTROLS = [
  ["gain_db", "增益", -12, 6, .1, "dB"], ["azimuth_deg", "方位", -180, 180, 1, "°"],
  ["elevation_deg", "高度", -45, 60, 1, "°"], ["distance_m", "距离", .5, 4, .05, "m"],
  ["size", "声源尺寸", 0, 1, .01, ""], ["diffusion", "扩散", 0, 1, .01, ""],
  ["direct_ratio", "直达比例", .3, .95, .01, ""], ["early_reflection_trim_db", "早反射微调", -12, 9, .1, "dB"],
  ["late_reverb_trim_db", "后期混响微调", -12, 9, .1, "dB"],
];
const FIELD_CONTROLS = [["gain_db", "声床增益", -30, 3, .1, "dB"], ["azimuth_deg", "镜像方位", 30, 180, 1, "°"], ["elevation_deg", "高度", -45, 70, 1, "°"]];
const ROOM_CONTROLS = [["early_reflection_level_db", "首次早反射", -40, -10, .2, "dB"], ["late_reverb_level_db", "后期声场", -40, -12, .2, "dB"], ["late_rt60_s", "衰减时间 RT60", .15, 1.2, .01, "s"]];
const MONITOR_CONTROLS = [["output_gain_db", "监听总增益", -18, 9, .1, "dB"], ["balance_db", "左右平衡", -6, 6, .1, "dB"], ["low_db", "低频", -12, 12, .2, "dB"], ["low_mid_db", "低中频", -12, 12, .2, "dB"], ["mid_db", "中频", -12, 12, .2, "dB"], ["presence_db", "存在感", -12, 12, .2, "dB"], ["air_db", "空气感", -12, 12, .2, "dB"]];
const EXTRACTION_CONTROLS = [["bass_low_hz", "低频完全归属", 30, 250, 5, "Hz"], ["bass_high_hz", "低频过渡结束", 60, 400, 5, "Hz"], ["center_anchor", "中央提取强度", 0, 1, .01, ""], ["center_focus_low_hz", "中央聚焦起点", 200, 3000, 25, "Hz"], ["center_focus_high_hz", "中央聚焦终点", 800, 8000, 50, "Hz"], ["center_focus_floor", "高频中央保留", 0, 1, .01, ""], ["front_side_weight_low", "前方侧声低频权重", 0, 1, .01, ""], ["front_side_weight_high", "前方侧声高频权重", 0, 1, .01, ""], ["rear_strength", "后方提取强度", 0, 1, .01, ""], ["rear_low_hz", "后方过渡起点", 300, 6000, 50, "Hz"], ["rear_high_hz", "后方过渡终点", 800, 10000, 50, "Hz"], ["air_low_hz", "空气感起点", 2000, 12000, 50, "Hz"], ["air_high_hz", "空气感完全归属", 4000, 20000, 50, "Hz"]];

let state, selectedZone = "center_anchor", selectedChoice = "b", lastPreview = null;
let audioContext, audioItems = {}, activeVariant = "b", playing = false;
let patchTimer;

async function api(path, options = {}) {
  const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `请求失败 (${response.status})`);
  return payload;
}
function toast(message, error = false) { const node = $("#toast"); node.textContent = message; node.className = error ? "show error" : "show"; clearTimeout(node._timer); node._timer = setTimeout(() => node.className = "", 3200); }
function format(value, unit) { const digits = Math.abs(value) < 10 && !Number.isInteger(value) ? 2 : 1; return `${Number(value).toFixed(digits)}${unit}`; }
function rangeControl([key, label, min, max, step, unit], value, onInput) {
  const wrap = document.createElement("label"); wrap.className = "control";
  wrap.innerHTML = `<div class="control-head"><span>${label}</span><output>${format(value, unit)}</output></div><input type="range" min="${min}" max="${max}" step="${step}" value="${value}">`;
  wrap.querySelector("input").addEventListener("input", e => { wrap.querySelector("output").textContent = format(e.target.valueAsNumber, unit); onInput(key, e.target.valueAsNumber); });
  return wrap;
}
function scheduleDraft(patch) { clearTimeout(patchTimer); patchTimer = setTimeout(async () => { try { state = await api("/api/draft", {method: "PATCH", body: JSON.stringify(patch)}); renderAll(); toast("草稿已保存，旧试听缓存会自动失效"); } catch (error) { toast(error.message, true); await loadState(); } }, 180); }

function renderAll() {
  $("#draft-hash").textContent = `B ${state.draft.profile_hash.slice(0, 10)}`;
  renderStrips(); renderInspector(); renderStage(); renderRoom(); renderWarnings(); renderCalibration(); renderMonitor(); renderExtraction();
}
function renderTracks() { const select = $("#track-select"); const previous = select.value; select.innerHTML = state.tracks.map(t => `<option value="${t.track_id}">${t.name}</option>`).join(""); if (state.tracks.some(t => t.track_id === previous)) select.value = previous; }
function renderStrips() {
  const zones = state.draft.profile.zones, audition = state.audition; const root = $("#channel-strips"); root.innerHTML = "";
  Object.entries(zones).forEach(([name, zone]) => {
    const strip = document.createElement("article"); strip.className = `strip ${name === selectedZone ? "selected" : ""}`;
    const mute = audition.muted.includes(name), solo = audition.soloed.includes(name);
    strip.innerHTML = `<p class="strip-type">${zone.kind === "object" ? "DIRECT OBJECT" : "FOA FIELD"}</p><h3>${ZONE_META[name].label}</h3><div class="strip-meter"><input aria-label="${name} gain" type="range" min="-30" max="6" step=".1" value="${zone.gain_db}"></div><div class="strip-value">${format(zone.gain_db, "dB")}</div><div class="strip-actions"><button class="${mute ? "active" : ""}">MUTE</button><button class="${solo ? "active" : ""}">SOLO</button></div>`;
    strip.addEventListener("click", () => { selectedZone = name; renderAll(); });
    strip.querySelector("input").addEventListener("input", e => { e.stopPropagation(); scheduleZone(name, "gain_db", e.target.valueAsNumber); strip.querySelector(".strip-value").textContent = format(e.target.valueAsNumber, "dB"); });
    const [muteButton, soloButton] = strip.querySelectorAll("button");
    muteButton.addEventListener("click", e => { e.stopPropagation(); toggleAudition("muted", name); }); soloButton.addEventListener("click", e => { e.stopPropagation(); toggleAudition("soloed", name); }); root.appendChild(strip);
  });
}
function scheduleZone(name, key, value) {
  const patch = {zones: {[name]: {[key]: value}}};
  if ($("#front-link").checked && ["front_L_residual", "front_R_residual"].includes(name) && ["gain_db", "azimuth_deg", "elevation_deg", "distance_m", "size", "diffusion", "direct_ratio", "early_reflection_trim_db", "late_reverb_trim_db"].includes(key)) {
    const partner = name === "front_L_residual" ? "front_R_residual" : "front_L_residual"; patch.zones[partner] = {[key]: key === "azimuth_deg" ? -value : value};
  }
  scheduleDraft(patch);
}
async function toggleAudition(key, name) { const values = new Set(state.audition[key]); values.has(name) ? values.delete(name) : values.add(name); try { state = await api("/api/audition", {method: "PATCH", body: JSON.stringify({[key]: [...values]})}); renderAll(); } catch (error) { toast(error.message, true); } }
function renderInspector() {
  const zone = state.draft.profile.zones[selectedZone], meta = ZONE_META[selectedZone]; $("#inspector-title").textContent = meta.label; $("#inspector-kind").textContent = zone.kind === "object" ? "直达对象" : "FOA 声床"; $("#inspector-help").textContent = meta.help;
  const root = $("#inspector-controls"); root.innerHTML = ""; (zone.kind === "object" ? OBJECT_CONTROLS : FIELD_CONTROLS).forEach(spec => root.appendChild(rangeControl(spec, zone[spec[0]], (key, value) => scheduleZone(selectedZone, key, value))));
  $("#front-link").parentElement.style.display = selectedZone.startsWith("front_") ? "flex" : "none";
}
function renderStage() {
  $$(".stage-node").forEach(n => n.remove()); const stage = $("#spatial-stage");
  Object.entries(state.draft.profile.zones).forEach(([name, z]) => { const isField = z.kind !== "object"; const az = z.azimuth_deg; const distance = isField ? 3.2 : z.distance_m; const radians = az * Math.PI / 180; const x = 50 + Math.sin(radians) * Math.min(distance / 4, 1) * 43; const y = 84 - Math.cos(radians) * Math.min(distance / 4, 1) * 71 - (z.elevation_deg || 0) * .18; const node = document.createElement("button"); node.className = `stage-node ${isField ? "field" : ""} ${name === selectedZone ? "selected" : ""}`; node.style.left = `${x}%`; node.style.top = `${Math.max(8, Math.min(90, y))}%`; node.textContent = ZONE_META[name].short; node.onclick = () => { selectedZone = name; renderAll(); }; stage.appendChild(node); });
}
function renderRoom() { const root = $("#room-controls"); root.innerHTML = ""; ROOM_CONTROLS.forEach(spec => root.appendChild(rangeControl(spec, state.draft.profile.room[spec[0]], (key, value) => scheduleDraft({room: {[key]: value}})))); }
function renderWarnings() { const root = $("#warnings"); root.innerHTML = state.warnings.length ? state.warnings.map(w => `⚠ ${w}`).join(" · ") : "✓ 当前参数位于建议范围内。客观指标仍以每首试听分析为准。"; }
function renderMonitor() { const root = $("#monitor-controls"); root.innerHTML = ""; MONITOR_CONTROLS.forEach(spec => root.appendChild(rangeControl(spec, state.monitor[spec[0]], async (key, value) => { try { state = await api("/api/monitor", {method: "PATCH", body: JSON.stringify({[key]: value})}); $("#draft-hash").textContent = `B ${state.draft.profile_hash.slice(0, 10)}`; } catch (e) { toast(e.message, true); } }))); }
function renderExtraction() { const root = $("#extraction-controls"); root.innerHTML = ""; EXTRACTION_CONTROLS.forEach(spec => root.appendChild(rangeControl(spec, state.draft.profile.extraction[spec[0]], (key, value) => scheduleDraft({extraction: {[key]: value}})))); }
function renderCalibration() {
  const current = state.comparisons.filter(c => c.profile_hash === state.draft.profile_hash); const byTrack = Object.fromEntries(current.map(c => [c.track_id, c])); $("#validation-progress").textContent = `${Object.keys(byTrack).length} / 9 · ${new Set(current.map(c => c.category)).size} / 6 类`;
  $("#validation-table").innerHTML = state.tracks.slice(0, 9).map(t => { const c = byTrack[t.track_id]; return `<tr><td>${t.name}</td><td>${c?.category || "—"}</td><td>${c?.choice?.toUpperCase() || "—"}</td><td>${c ? `<span class="pill ${c.objective_gate.pass ? "green" : "red"}">${c.objective_gate.pass ? "通过" : "告警"}</span>` : "—"}</td><td>${c ? "已评价" : "待试听"}</td></tr>`; }).join("");
}
function setupScores() { const labels = {clarity: "整体清晰", bass: "低频完整", depth: "距离深度", externalization: "出头感"}; $("#score-controls").innerHTML = Object.entries(labels).map(([key,label]) => `<label class="score-control">${label}<span id="score-${key}-value">7</span><input id="score-${key}" type="range" min="0" max="10" step=".5" value="7"></label>`).join(""); Object.keys(labels).forEach(key => $(`#score-${key}`).oninput = e => $(`#score-${key}-value`).textContent = e.target.value); }

async function createPreview() { const track = $("#track-select").value; if (!track) return toast("曲库中没有可试听的音频", true); $("#render-preview").disabled = true; $("#render-preview").textContent = "正在渲染…"; try { lastPreview = await api("/api/preview", {method: "POST", body: JSON.stringify({track_id: track, start_s: $("#start").valueAsNumber, duration_s: Number($("#duration").value)})}); await loadAudio(lastPreview); toast(lastPreview.cached ? "已载入缓存试听" : "A/B 试听已生成"); renderCalibration(); } catch (e) { toast(e.message, true); } finally { $("#render-preview").disabled = false; $("#render-preview").textContent = "生成 A/B 试听"; } }
async function loadAudio(preview) { if (!audioContext) audioContext = new AudioContext(); Object.values(audioItems).forEach(item => { item.element.pause(); item.source.disconnect(); }); audioItems = {}; for (const variant of ["reference", "a", "b"]) { const element = new Audio(`/api/audio/${preview.preview_id}/${variant}`); element.preload = "auto"; const source = audioContext.createMediaElementSource(element); const gain = audioContext.createGain(); gain.gain.value = variant === activeVariant ? 1 : 0; source.connect(gain).connect(audioContext.destination); audioItems[variant] = {element, source, gain}; } $("#play-pause").disabled = false; playing = false; $("#play-pause").textContent = "播放"; }
async function togglePlay() { if (!lastPreview) return; await audioContext.resume(); if (playing) { Object.values(audioItems).forEach(x => x.element.pause()); playing = false; $("#play-pause").textContent = "播放"; } else { const time = audioItems[activeVariant].element.currentTime; Object.values(audioItems).forEach(x => { x.element.currentTime = time; x.element.play(); }); playing = true; $("#play-pause").textContent = "暂停"; } }
function switchVariant(variant) { activeVariant = variant; $$("[data-variant]").forEach(b => b.classList.toggle("active", b.dataset.variant === variant)); if (!audioContext) return; const now = audioContext.currentTime; Object.entries(audioItems).forEach(([name,item]) => { item.gain.gain.cancelScheduledValues(now); item.gain.gain.setValueAtTime(item.gain.gain.value, now); item.gain.gain.linearRampToValueAtTime(name === variant ? 1 : 0, now + .025); }); }
async function saveComparison() { if (!lastPreview || lastPreview.track_id !== $("#track-select").value) return toast("请先生成当前曲目的 A/B 试听", true); const scores = {}; ["clarity","bass","depth","externalization"].forEach(key => scores[key] = Number($(`#score-${key}`).value)); try { state = await api("/api/comparisons", {method: "POST", body: JSON.stringify({track_id: lastPreview.track_id, category: $("#evaluation-category").value, choice: selectedChoice, scores, objective_gate: lastPreview.objective_gate, notes: $("#evaluation-notes").value})}); renderAll(); toast("评价已绑定到当前草稿版本"); } catch(e) { toast(e.message, true); } }
async function promote() { try { const result = await api("/api/promote", {method: "POST", body: JSON.stringify({override_reason: $("#override-reason").value})}); state = await api("/api/state"); renderAll(); toast(`通用配置已发布：${result.profile_hash.slice(0, 10)}`); } catch(e) { toast(e.message, true); } }
async function analyzeLab() { try { const result = await api("/api/extraction/analyze", {method: "POST", body: JSON.stringify({track_id: $("#track-select").value, start_s: $("#start").valueAsNumber, duration_s: Number($("#duration").value)})}); const max = Math.max(...Object.values(result.zones).map(z => z.rms), 1e-9); $("#lab-result").className = "lab-result"; $("#lab-result").innerHTML = `<p class="lead">重构误差 <strong>${result.reconstruction_error_db.toFixed(1)} dB</strong> · 安全</p>${Object.entries(result.zones).map(([name,z]) => `<div class="zone-stat"><span>${ZONE_META[name].label}</span><div class="stat-bar"><i style="width:${Math.max(1,z.rms/max*100)}%"></i></div></div>`).join("")}`; } catch(e) { toast(e.message, true); } }

async function loadState() { try { state = await api("/api/state"); renderTracks(); renderAll(); } catch (e) { toast(e.message, true); } }
$$('.tab').forEach(tab => tab.onclick = () => { $$('.tab').forEach(x => x.classList.remove('active')); $$('.page').forEach(x => x.classList.remove('active')); tab.classList.add('active'); $(`#page-${tab.dataset.page}`).classList.add('active'); });
$("#start").oninput = e => $("#start-value").textContent = `${e.target.value}s`; $("#render-preview").onclick = createPreview; $("#play-pause").onclick = togglePlay; $$('[data-variant]').forEach(b => b.onclick = () => switchVariant(b.dataset.variant)); $$('.choice-row button').forEach(b => b.onclick = () => { selectedChoice = b.dataset.choice; $$('.choice-row button').forEach(x => x.classList.toggle('active', x === b)); }); $("#save-comparison").onclick = saveComparison; $("#promote-profile").onclick = promote; $("#analyze-extraction").onclick = analyzeLab;
setupScores(); loadState();
