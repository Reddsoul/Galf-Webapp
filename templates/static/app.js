/* ================================================================
   STANDALONE / PWA VIEWPORT INIT (was inline in <head>)
   Adds is-standalone class + pins app height to screen in PWA mode.
   ================================================================ */
if(window.navigator.standalone||window.matchMedia('(display-mode:standalone)').matches){
  document.documentElement.classList.add('is-standalone');
}
function _setAppH(){
  var a=document.getElementById('app');
  if(!a)return;
  if(window.navigator.standalone||window.matchMedia('(display-mode:standalone)').matches){
    var sh=window.screen.height;
    var bottomGap=Math.max(0,sh-window.innerHeight);
    document.documentElement.style.setProperty('--js-safe-b',bottomGap+'px');
    document.documentElement.style.height=sh+'px';
    document.body.style.height=sh+'px';
    a.style.height=sh+'px';
  }
}
window.addEventListener('resize',_setAppH);
document.addEventListener('DOMContentLoaded',_setAppH);
_setAppH();

/* ================================================================
   LEAK → DRILL MAP (shared by home + stats)
   ================================================================ */
const LEAK_DRILL_MAP = {
  putting:       { cat:'Putting',  drills:["20 in a row from 3'","8/10 from 6'","3 Strikes and You're Out"] },
  putting_avg:   { cat:'Putting',  drills:["10 in a row from 20 ft","10 in a row from 30 ft","8/10 from 50 ft"] },
  three_putts:   { cat:'Putting',  drills:["10 in a row from 30 ft","8/10 from 50 ft","20 Tee Game"] },
  tee_shots_par3:{ cat:'Irons',    drills:["9 Iron","8 Iron","7 Iron"] },
  approach:      { cat:'Irons',    drills:["7 Iron","6 Iron","5 Iron","4 Iron"] },
  gir:           { cat:'Irons',    drills:["7 Iron","6 Iron","5 Iron"] },
  scrambling:    { cat:'Chipping', drills:["8/10 — 1st bounce in circle (10 yd carry)","10 in a row from 15 yds","10 in a row from 25 yds"] },
};

/* ================================================================
   STATE
   ================================================================ */
const S = {
  courses:[], clubs:[], handicap:null, stats:null, editingClub:null,
  // Log round
  logCourse:null, logTee:null, logHoles:'full_18', logType:'solo',
  logSerious:true, logMode:'quick', logDate:'',
  logIsSim:false,
  holesToScore:[], currentHoleIdx:0,
  holeScores:[], holeClubs:[],
  holeSimPutts:null,
  clubOptions:[], clubFullNames:{}, distByAbbr:{},
  clubUsage:{}, wedgeMatrix:[],
  logClubMap:{},
  // Scorecard
  viewRound:null, viewRoundIdx:null,
  // Course editor
  editCourse:null,
};

/* ================================================================
   CUSTOM DIALOGS — replaces native alert/confirm with iOS-style
   action sheets (Phase 2 HIG compliance)
   ================================================================ */
function _showDialog(html) {
  const backdrop = document.createElement('div');
  backdrop.className = 'dialog-backdrop';
  backdrop.innerHTML = html;
  document.body.appendChild(backdrop);
  // Tap backdrop to cancel
  backdrop.addEventListener('click', e => { if(e.target===backdrop) backdrop.remove(); });
  return backdrop;
}

function showConfirm(title, body, destructiveLabel, onConfirm, cancelLabel='Cancel') {
  const el = _showDialog(`
    <div class="dialog-sheet">
      <div class="dialog-card">
        <div class="dialog-title">${esc(title)}</div>
        ${body ? `<div class="dialog-body">${esc(body)}</div>` : ''}
        <div class="dialog-sep"></div>
        <button class="dialog-btn is-destructive" id="dlg-ok">${esc(destructiveLabel)}</button>
      </div>
      <div class="dialog-card">
        <button class="dialog-btn is-cancel" id="dlg-cancel">${esc(cancelLabel)}</button>
      </div>
    </div>`);
  el.querySelector('#dlg-ok').addEventListener('click', () => { el.remove(); onConfirm(); });
  el.querySelector('#dlg-cancel').addEventListener('click', () => el.remove());
}

function showAlert(title, body, btnLabel='OK') {
  const el = _showDialog(`
    <div class="dialog-sheet">
      <div class="dialog-card">
        <div class="dialog-title">${esc(title)}</div>
        ${body ? `<div class="dialog-body">${esc(body)}</div>` : ''}
        <div class="dialog-sep"></div>
        <button class="dialog-btn" id="dlg-ok">${esc(btnLabel)}</button>
      </div>
    </div>`);
  el.querySelector('#dlg-ok').addEventListener('click', () => el.remove());
}

/* ================================================================
   API
   ================================================================ */
async function api(path, opts={}) {
  const res = await fetch(path, {headers:{'Content-Type':'application/json',...opts.headers},...opts});
  return res.json();
}
const GET=p=>api(p);
const POST=(p,d)=>api(p,{method:'POST',body:JSON.stringify(d)});
const PUT=(p,d)=>api(p,{method:'PUT',body:JSON.stringify(d)});
const DEL=p=>api(p,{method:'DELETE'});

// Cached media query — created once, reused by ico() and the change listener.
const DARK_MQ = window.matchMedia('(prefers-color-scheme: dark)');

/* ================================================================
   ROUND DRAFT — localStorage persistence for in-progress rounds
   Saves after every score/club action so a navigation away or
   Safari reload won't lose the holes already entered.
   ================================================================ */
const DRAFT_KEY = 'galf_draft_v1';

function saveDraft() {
  if (!S.logCourse || !S.holesToScore.length) return;
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({
      courseName: S.logCourse.name,
      logTee: S.logTee,
      logHoles: S.logHoles,
      logType: S.logType,
      logSerious: S.logSerious,
      logMode: S.logMode,
      logDate: S.logDate,
      logIsSim: S.logIsSim,
      holesToScore: S.holesToScore,
      currentHoleIdx: S.currentHoleIdx,
      holeScores: S.holeScores,
      holeClubs: S.holeClubs,
      holeSimPutts: S.holeSimPutts,
    }));
  } catch(e) {}
}

function clearDraft() {
  try { localStorage.removeItem(DRAFT_KEY); } catch(e) {}
}

function getDraft() {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch(e) { return null; }
}

const TRAINING_DRAFT_KEY = 'galf_training_draft_v1';
function saveTrainingDraft() {
  if (!T.drillStates.length) return;
  try { localStorage.setItem(TRAINING_DRAFT_KEY, JSON.stringify({ date: T.date, notes: T.notes, drillStates: T.drillStates, selectedCategories: T.selectedCategories, selectedClubs: T.selectedClubs, activeCatIdx: T.activeCatIdx, wedgeMatrix: T.wedgeMatrix })); } catch(e) {}
}
function clearTrainingDraft() {
  try { localStorage.removeItem(TRAINING_DRAFT_KEY); } catch(e) {}
}
function getTrainingDraft() {
  try { const r = localStorage.getItem(TRAINING_DRAFT_KEY); return r ? JSON.parse(r) : null; } catch(e) { return null; }
}
function resumeTrainingDraft() {
  const draft = getTrainingDraft();
  if (!draft) return;
  if (draft.drillStates && draft.drillStates.length === T.drillStates.length) {
    T.drillStates = draft.drillStates;
    T.date = draft.date || T.date;
    T.notes = draft.notes || '';
    T.selectedCategories = draft.selectedCategories || ['RANGE WARM-UP', 'PUTTING'];
    T.selectedClubs = draft.selectedClubs || _defaultSelectedClubs();
    T.activeCatIdx = draft.activeCatIdx || 0;
    T.wedgeMatrix = draft.wedgeMatrix || {};
  }
  clearTrainingDraft();
  renderTraining();
}

function resumeDraft(draft) {
  if (!draft) return;
  _cancelPending();
  const course = S.courses.find(c => c.name === draft.courseName);
  if (!course) { clearDraft(); renderLogSetup(); return; }
  S.logCourse = course;
  S.logTee = draft.logTee;
  S.logHoles = draft.logHoles;
  S.logType = draft.logType;
  S.logSerious = draft.logSerious;
  S.logMode = draft.logMode;
  S.logDate = draft.logDate;
  S.logIsSim = draft.logIsSim;
  S.holesToScore = draft.holesToScore;
  S.currentHoleIdx = draft.currentHoleIdx;
  S.holeScores = draft.holeScores;
  S.holeClubs = draft.holeClubs;
  S.holeSimPutts = draft.holeSimPutts;
  buildClubLookups(S.clubUsage);
  show('log-entry');
}

/* ================================================================
   NAVIGATION — mirrors show_page + _update_tab_bar
   ================================================================ */

// Single source of truth for page ▶ render function mapping.
// Used by show() and the dark-mode change listener.
const RENDERERS = {
  home:renderHome, rounds:renderRounds, scorecard:renderScorecard,
  'log-setup':renderLogSetup, 'log-entry':renderLogEntry, 'log-notes':renderLogNotes,
  courses:renderCourses, 'course-detail':renderCourseDetail, 'course-editor':renderCourseEditor,
  scan:renderScan,
  stats:renderStats,
  'training-setup':renderTrainingSetup, training:renderTraining,
  'training-history':renderTrainingHistory,
  'practice-detail':renderPracticeDetail,
};

function navRounds() {
  if (_currentPage === 'rounds') { nav('stats'); return; }
  nav('rounds');
}

function navHome() {
  if (_currentPage === 'home') { showStartSessionSheet(); return; }
  nav('home');
}

function navCourses() {
  if (_currentPage === 'courses') { editCourse(null); return; }
  nav('courses');
}

function nav(page) {
  document.querySelectorAll('.tab').forEach(t=>{
    t.classList.toggle('active', t.dataset.tab===page);
  });
  show(page);
}

// Cached static DOM refs — set once in init(), never re-queried.
let _contentEl, _tabbarEl;
// Currently visible page name — lets show() swap only two elements instead of all views.
let _currentPage = null;

function show(name) {
  if(_currentPage){const prev=document.getElementById('v-'+_currentPage);if(prev)prev.classList.remove('active');}
  const el=document.getElementById('v-'+name);
  if(el) el.classList.add('active');
  const isEntry = name==='log-entry';
  _contentEl.style.overflowY = isEntry ? 'hidden' : '';
  _contentEl.style.height = isEntry ? '100%' : '';
  _contentEl.scrollTop=0;
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active', t.dataset.tab===name));
  const isLogging = name==='log-setup'||name==='log-entry'||name==='log-notes'||name==='training-setup'||name==='training'||name==='course-editor';
  _tabbarEl.style.display = isLogging ? 'none' : '';
  _currentPage=name;
  if(RENDERERS[name]) RENDERERS[name]();
}

function esc(t){return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

// Map score-vs-par difference to the correct CSS class for scorecard markers.
function scoreClass(score, par) {
  const d = score - par;
  if (d <= -2) return 'sc-eagle';
  if (d === -1) return 'sc-birdie';
  if (d === 0)  return 'sc-par-score';
  if (d === 1)  return 'sc-bogey';
  return 'sc-dbl-bogey';
}

/* ================================================================
   HOME — _show_home_page
   ================================================================ */
// Build inner content for a best-round card. Returns {innerHtml, diff, hasData, idx}.
async function buildBestCard(bestData) {
  if(!bestData||!bestData.total_score||bestData._index==null) return {innerHtml:'',diff:Infinity,hasData:false,idx:null};
  const sc=await GET(`/api/rounds/${bestData._index}/scorecard`);
  const d=bestData.total_score-(bestData.par||72);
  const ds=d>0?`+${d}`:d===0?'E':`${d}`;
  const dsColor=d>0?'var(--red)':d<0?'var(--green)':'var(--text)';
  const dateStr=(bestData.date||'').substring(0,10);
  const teeColor=sc.tee_color||'White';
  const teeCSS=teeColorCSS(teeColor);
  const teeDotBorder=teeColor==='White'?'1px solid rgba(0,0,0,0.18)':'none';
  const scores=sc.scores||[]; const pars=sc.pars||[];
  const holesChoice=sc.holes_choice||'full_18';
  let hStart=0,hEnd=scores.length;
  if(holesChoice==='front_9'){hStart=0;hEnd=Math.min(9,scores.length);}
  else if(holesChoice==='back_9'){hStart=9;hEnd=Math.min(18,scores.length);}
  let holeHtml='';
  for(let i=hStart;i<hEnd;i++){
    const s=scores[i],p=pars[i];
    if(!s) continue;
    holeHtml+=`<div class="home-hole-cell"><div class="home-hole-num sc-score ${scoreClass(s,p)}">${i+1}</div></div>`;
  }
  const innerHtml=`
      <div class="home-best-stripe" style="background:${teeCSS}"></div>
      <div class="home-best-header">
        <div>
          <div class="home-best-meta">
            <span class="home-best-tee-dot" style="background:${teeCSS};border:${teeDotBorder}"></span>${esc(sc.course_name||'')} · ${dateStr}
          </div>
        </div>
        <div style="display:flex;align-items:baseline;gap:6px;justify-content:flex-end">
          <div class="home-best-score">${bestData.total_score}</div>
          <div class="home-best-diff" style="color:${dsColor}">${ds}</div>
        </div>
      </div>
      <div class="home-best-holes">${holeHtml}</div>`;
  return {innerHtml, diff:d, hasData:true, idx:bestData._index};
}

function switchBestTab(tab, evt) {
  document.getElementById('best-tab-irl').classList.toggle('active', tab==='irl');
  document.getElementById('best-tab-sim').classList.toggle('active', tab==='sim');
  document.getElementById('best-content-irl').style.display = tab==='irl' ? '' : 'none';
  document.getElementById('best-content-sim').style.display = tab==='sim' ? '' : 'none';
  if (evt) evt.stopPropagation();
}

function buildActivityMatrix(rounds, training) {
  const _MN = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const today = new Date(); today.setHours(0,0,0,0);
  const monthLabel = `${_MN[today.getMonth()]} ${today.getFullYear()}`;

  // Index played dates: round/practice/both (sim + IRL both count as 'irl')
  const dayMap = {};
  for (const rd of (rounds || [])) {
    const d = (rd.date || '').substring(0,10); if (!d) continue;
    const cur = dayMap[d];
    if (!cur) dayMap[d] = 'irl';
    else if (cur === 'practice') dayMap[d] = 'both';
  }
  for (const ts of (training || [])) {
    const d = (ts.date || '').substring(0,10); if (!d) continue;
    const cur = dayMap[d];
    if (!cur) dayMap[d] = 'practice';
    else if (cur !== 'practice') dayMap[d] = 'both';
  }

  // Build 18-week grid aligned to Monday
  const WEEKS = 18;
  const todayDow = (today.getDay() + 6) % 7;
  const start = new Date(today);
  start.setDate(today.getDate() - todayDow - (WEEKS - 1) * 7);

  const cur = new Date(start);
  let cells = '';
  for (let col = 0; col < WEEKS; col++) {
    for (let row = 0; row < 7; row++) {
      const ds = cur.toISOString().substring(0,10);
      const isFuture = cur > today;
      const type = dayMap[ds];
      let cls = 'hm-future';
      let tip = '';
      if (!isFuture) {
        if      (!type)           { cls = 'hm0';      tip = ds; }
        else if (type === 'both') { cls = 'hm-both';  tip = `${ds} · Round + Practice`; }
        else if (type === 'irl')  { cls = 'hm-irl';   tip = `${ds} · Round`; }
        else                      { cls = 'hm-prac';  tip = `${ds} · Practice`; }
      }
      cells += `<div class="hm-cell ${cls}" title="${tip}"></div>`;
      cur.setDate(cur.getDate() + 1);
    }
  }

  const dow = ['M','T','W','T','F','S','S'].map(l=>`<div class="hm-dow">${l}</div>`).join('');

  return `<div class="stat-card" style="margin:0 16px 16px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
      <div style="display:flex;align-items:baseline;gap:8px">
        <div class="stat-card-title" style="margin-bottom:0">Activity</div>
        <span style="font-size:11px;font-weight:500;color:var(--text2)">${monthLabel}</span>
      </div>
      <div class="hm-legend" style="margin-top:0">
        <div class="hm-legend-cell hm-irl"></div><span>Round</span>
        <div class="hm-legend-cell hm-prac"></div><span>Practice</span>
        <div class="hm-legend-cell hm-both"></div><span>Both</span>
      </div>
    </div>
    <div class="hm-wrap">
      <div class="hm-dow-col">${dow}</div>
      <div class="practice-heatmap">${cells}</div>
    </div>
  </div>`;
}

async function renderHome() {
  const v=document.getElementById('v-home');
  v.innerHTML='<div class="skeleton-card"><div class="skeleton skeleton-num" style="margin:20px auto"></div><div class="skeleton skeleton-line" style="margin:8px 20px"></div><div class="skeleton skeleton-line-sm" style="margin:4px 20px"></div></div>';
  const [stats,hc,best,bestSim,adv,allRounds,allTraining,leaks]=await Promise.all([
    GET('/api/stats'), GET('/api/stats/handicap'),
    GET('/api/stats/best-round'), GET('/api/stats/best-round?sim=true'),
    GET('/api/stats/advanced'),
    GET('/api/rounds?round_type=all&sort=recent'),
    GET('/api/training'),
    GET('/api/stats/stroke-leaks'),
  ]);
  S.stats=stats; S.handicap=hc.handicap_index;

  // Handicap hero
  const hasHC = S.handicap!==null;
  const hcStr = hasHC ? S.handicap.toFixed(1) : '--';
  let hcSub='';
  if(!hasHC){
    const rem=Math.max(0,54-(stats.total_holes_played||0));
    hcSub = rem>0 ? `Play ${rem} more holes to establish` : 'Calculating…';
  }

  // Build combined best-round widget (IRL + Sim toggle)
  const [irlCard, simCard] = await Promise.all([
    buildBestCard(best),
    buildBestCard(bestSim)
  ]);
  let bestWidgetHtml = '';
  if (irlCard.hasData || simCard.hasData) {
    if (irlCard.hasData && simCard.hasData) {
      const defIrl = irlCard.diff <= simCard.diff;
      bestWidgetHtml = `
        <div class="home-best">
          <div class="best-toggle-row">
            <span class="home-best-label">Best Round</span>
            <div class="best-toggle">
              <button class="best-toggle-opt${defIrl?' active':''}" id="best-tab-irl" onclick="switchBestTab('irl',event)">IRL</button>
              <button class="best-toggle-opt${defIrl?'':' active'}" id="best-tab-sim" onclick="switchBestTab('sim',event)">Sim</button>
            </div>
          </div>
          <div id="best-content-irl" style="${defIrl?'':'display:none'}" onclick="viewRound(${irlCard.idx})">${irlCard.innerHtml}</div>
          <div id="best-content-sim" style="${defIrl?'display:none':''}" onclick="viewRound(${simCard.idx})">${simCard.innerHtml}</div>
        </div>`;
    } else {
      const r = irlCard.hasData ? irlCard : simCard;
      bestWidgetHtml = `<div class="home-best" onclick="viewRound(${r.idx})"><div class="best-toggle-row"><span class="home-best-label">Best Round</span></div>${r.innerHtml}</div>`;
    }
  }

  const girVal  = adv && adv.gir_overall != null ? adv.gir_overall + '%' : '—';
  const girP3n  = adv?.gir_par3    ?? null;
  const girP4n  = adv?.gir_par4    ?? null;
  const girP5n  = adv?.gir_par5    ?? null;
  const girP3   = girP3n != null ? girP3n + '%' : '—';
  const girP4   = girP4n != null ? girP4n + '%' : '—';
  const girP5   = girP5n != null ? girP5n + '%' : '—';
  const mkBar   = (lbl, n) => `<div class="home-gir-bar-row">
    <span class="home-gir-bar-lbl">${lbl}</span>
    <div class="home-gir-track"><div class="home-gir-fill" style="width:${n ?? 0}%"></div></div>
    <span class="home-gir-bar-val">${n != null ? n + '%' : '—'}</span>
  </div>`;

  // Build nPractice widget (1st item only)
  let priorityHtml = '';
  if (leaks && leaks.length) {
    const seenCats = new Set();
    let topCat = null;
    for (const l of [...leaks].sort((a,b)=>(a.severity==='high'?0:1)-(b.severity==='high'?0:1))) {
      const map = LEAK_DRILL_MAP[l.area];
      if (map && !seenCats.has(map.cat)) { seenCats.add(map.cat); topCat = { cat: map.cat, drills: map.drills }; break; }
    }
    if (topCat) {
      priorityHtml = `<div class="stat-card" style="margin:0 16px 10px;display:flex;align-items:center;gap:12px">
        <div style="flex:1;min-width:0">
          <div style="font-size:11px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.5px;margin-bottom:2px">Practice</div>
          <div style="font-size:15px;font-weight:700">${esc(topCat.cat)}</div>
          <div style="font-size:12px;color:var(--text2);margin-top:1px">${topCat.drills.slice(0,2).map(d=>esc(d)).join(' · ')}</div>
        </div>
        <button onclick="statsTab='analysis';show('stats')" style="background:none;border:none;color:var(--accent);font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;padding:0;flex-shrink:0">More →</button>
      </div>`;
    }
  }

  v.innerHTML=`
    <div class="home-hero">
      <div class="home-hero-stripe"></div>
      <button class="manual-info-btn" onclick="showManual()" aria-label="Open manual">Manual</button>
      <div class="home-hero-body">
        <div class="home-hero-left">
          <div class="home-hc-label">Handicap Index</div>
          ${hcSub?`<div class="home-hc-sub" style="margin-top:8px">${hcSub}</div>`:''}
        </div>
        <div class="home-hero-right">
          <div class="home-hc-value${hasHC?'':' hc-pending'}">${hcStr}</div>
        </div>
      </div>
    </div>
    ${buildActivityMatrix(allRounds, allTraining)}
    ${bestWidgetHtml}
    <div class="home-stats-row">
      <div class="home-stat-cell" style="display:flex;flex-direction:column;align-items:center;justify-content:center">
        <div class="home-stat-val">${stats.total_rounds}</div>
        <div class="home-stat-lbl">Logged</div>
      </div>
      <div class="home-gir-card">
        <div class="home-gir-inner">
          <div class="home-gir-overall">
            <div class="home-gir-card-label">GIR</div>
            <div class="home-gir-big">${girVal}</div>
          </div>
          <div class="home-gir-rows">
            ${mkBar('Par 3', girP3n)}
            ${mkBar('Par 4', girP4n)}
            ${mkBar('Par 5', girP5n)}
          </div>
        </div>
      </div>
    </div>
    ${priorityHtml}
  `;
}

/* ================================================================
   ROUNDS — _show_rounds_page
   ================================================================ */
let roundsFilter='all';
let _practiceSessionsCache = null;
async function renderRounds() {
  const v=document.getElementById('v-rounds');
  v.innerHTML='<div class="page-header" style="text-align:right"><div class="page-title">Logbook</div></div><div style="padding:0 16px"><div class="skeleton skeleton-line" style="margin:12px 0"></div><div class="skeleton skeleton-line" style="margin:8px 0"></div><div class="skeleton skeleton-line" style="margin:8px 0"></div></div>';

  let filterHtml='';
  for(const [lbl,val] of [['All','all'],['Solo','solo'],['Scramble','scramble'],['Sim','sim'],['Practice','practice']]){
    filterHtml+=`<button class="stats-tab${roundsFilter===val?' active':''}" onclick="roundsFilter='${val}';renderRounds()">${lbl}</button>`;
  }
  const filterBar=`<div class="stats-tabs">${filterHtml}</div>`;

  // ── PRACTICE filter: show training sessions in table format ─────────────
  if (roundsFilter === 'practice') {
    const sessions = await GET('/api/training');
    _practiceSessionsCache = sessions;
    let rows = '';
    if (!sessions.length) {
      rows = `<div class="empty"><div class="empty-icon"><img src="/static/golf-clubs-96.png" style="width:80px;height:80px;object-fit:contain;display:block;margin:0 auto"></div><div class="empty-headline">No Sessions Yet</div><div class="empty-text">Start a practice session from the home screen.</div></div>`;
    } else {
      rows = '<div style="padding:0 16px;overflow-x:auto"><table class="tree-table"><tr><th style="width:80px">Date</th><th>Practice</th><th style="width:50px">Score</th><th style="width:45px">+/-</th><th style="width:45px">Holes</th></tr>';
      for (const ts of sessions) {
        const drills = ts.drills || [];
        const total = drills.length;
        const done = drills.filter(d => d.completed && !d.skipped).length;
        const pct = total ? Math.round(done / total * 100) : 0;
        const pctColor = pct >= 80 ? 'var(--green)' : pct >= 50 ? 'var(--orange)' : 'var(--red)';
        const dt = (ts.date || '').substring(0, 10);
        rows += `<tr id="prow-${ts.id}" onclick="viewPractice(${ts.id})">
          <td style="text-align:left">${dt}</td>
          <td>Practice</td>
          <td style="color:${pctColor};font-weight:700">${pct}%</td>
          <td></td>
          <td></td>
        </tr>`;
      }
      rows += '</table></div>';
    }
    v.innerHTML=`
      <div class="page-header" style="text-align:right"><div class="page-title">Logbook</div></div>
      ${filterBar}
      ${rows}`;
    return;
  }

  // ── ROUNDS filters ───────────────────────────────────────────────────────
  const [rounds, practiceSessions] = await Promise.all([
    GET(`/api/rounds?round_type=${roundsFilter}&sort=recent`),
    roundsFilter === 'all' ? GET('/api/training') : Promise.resolve([]),
  ]);
  if (roundsFilter === 'all') _practiceSessionsCache = practiceSessions;

  // Merge rounds + practice sessions into one date-sorted list for "all"
  let items = [];
  for (const rd of rounds) items.push({ _type: 'round', _date: (rd.date||'').substring(0,10), ...rd });
  for (const ts of practiceSessions) items.push({ _type: 'practice', _date: (ts.date||'').substring(0,10), ...ts });
  items.sort((a,b) => b._date.localeCompare(a._date));

  let rows='';
  if(!items.length){
    const isSimFilter = roundsFilter === 'sim';
    rows=`<div class="empty"><div class="empty-icon"><img src="${ico('golfer')}" style="width:80px;height:80px;object-fit:contain;display:block;margin:0 auto"></div><div class="empty-headline">No Rounds Yet</div><div class="empty-text">${isSimFilter?'No simulator rounds logged yet.':'Log your first round to start tracking your game.'}</div>${!isSimFilter?'<div class="empty-cta"><button class="btn btn-primary" style="max-width:200px;margin:0 auto" onclick="startLog()">Log a Round</button></div>':''}</div>`;
  } else {
    rows='<div style="padding:0 16px;overflow-x:auto"><table class="tree-table"><tr><th style="width:80px">Date</th><th>Course</th><th style="width:50px">Score</th><th style="width:45px">+/-</th><th style="width:45px">Holes</th></tr>';
    for(const item of items){
      if (item._type === 'practice') {
        const drills = item.drills || [];
        const total = drills.length;
        const done = drills.filter(d => d.completed && !d.skipped).length;
        const pct = total ? Math.round(done / total * 100) : 0;
        const pctColor = pct >= 80 ? 'var(--green)' : pct >= 50 ? 'var(--orange)' : 'var(--red)';
        rows+=`<tr id="prow-${item.id}" onclick="viewPractice(${item.id})"><td style="text-align:left">${item._date}</td><td>Practice</td><td style="color:${pctColor};font-weight:700">${pct}%</td><td></td><td></td></tr>`;
      } else {
        const rd = item;
        const diff=rd.total_score-(rd.par||72);
        const ds=diff>0?`+${diff}`:diff===0?'E':`${diff}`;
        const dc=diff>0?'badge-red':diff<0?'badge-green':'badge-even';
        const hc=rd.holes_choice;
        const hs=hc==='front_9'?'F9':hc==='back_9'?'B9':String(rd.holes_played||18);
        rows+=`<tr onclick="viewRound(${rd._index})"><td style="text-align:left">${rd._date}</td><td>${esc(rd.course_name).substring(0,18)}</td><td>${rd.total_score}</td><td class="${dc}">${ds}</td><td>${hs}</td></tr>`;
      }
    }
    rows+='</table></div>';
  }

  v.innerHTML=`
    <div class="page-header" style="text-align:right"><div class="page-title">Logbook</div></div>
    ${filterBar}
    ${rows}
  `;
}

function viewPractice(id) {
  const ts = _practiceSessionsCache && _practiceSessionsCache.find(s => s.id === id);
  if (!ts) return;
  S.viewPractice = ts;
  show('practice-detail');
}

function renderPracticeDetail() {
  const ts = S.viewPractice;
  if (!ts) { show('rounds'); return; }
  const v = document.getElementById('v-practice-detail');

  const drills = ts.drills || [];
  const total = drills.length;
  const done = drills.filter(d => d.completed && !d.skipped).length;
  const pct = total ? Math.round(done / total * 100) : 0;
  const pctColor = pct >= 80 ? 'var(--green)' : pct >= 50 ? 'var(--orange)' : 'var(--red)';
  const dateStr = (ts.date || '').substring(0, 10);

  const CAT_ORDER = ['RANGE WARM-UP','PUTTING','CHIPPING','WEDGE MATRIX','PITCHING','IRONS','WOODS'];
  const catMap = {};
  for (const d of drills) {
    const cat = d.category || 'Other';
    if (!catMap[cat]) catMap[cat] = [];
    catMap[cat].push(d);
  }
  const orderedCats = [...CAT_ORDER.filter(c => catMap[c]), ...Object.keys(catMap).filter(c => !CAT_ORDER.includes(c))];

  let catCards = '';
  for (const cat of orderedCats) {
    let drillRows = '';
    const catDrills = catMap[cat];
    for (let i = 0; i < catDrills.length; i++) {
      const d = catDrills[i];
      const isLast = i === catDrills.length - 1;
      const ok = d.completed && !d.skipped;
      const skip = d.skipped;
      const dotBg = skip ? 'var(--sep)' : ok ? 'var(--green)' : 'transparent';
      const dotBorder = (!skip && !ok) ? '1.5px solid var(--sep)' : 'none';
      const resultStr = (d.result !== null && d.result !== undefined && d.result !== '')
        ? `<span style="font-size:12px;color:var(--text2)">${esc(String(d.result))}</span>` : '';
      drillRows += `<div style="display:flex;align-items:center;gap:8px;padding:6px 0;${isLast?'':'border-bottom:0.5px solid var(--sep)'}">
        <span style="width:10px;height:10px;border-radius:50%;background:${dotBg};border:${dotBorder};flex-shrink:0;display:inline-block"></span>
        <span style="font-size:13px;flex:1;color:${(skip||!ok)?'var(--text2)':'var(--text)'}">${esc(d.name||'')}</span>
        ${resultStr}
      </div>`;
    }
    catCards += `<div class="sc-notes"><div class="sc-notes-title">${esc(cat)}</div>${drillRows}</div>`;
  }

  const notesCard = ts.notes
    ? `<div class="sc-notes"><div class="sc-notes-title">Notes</div><div class="sc-notes-body">${esc(ts.notes)}</div></div>` : '';

  const pillsHtml = orderedCats.map(c => `<span class="sc-pill">${esc(c)}</span>`).join('');

  v.innerHTML = `
    <div class="sc-header-card" style="background:var(--card);color:var(--text);border:1.5px solid var(--sep);margin-bottom:12px;box-shadow:none;border-radius:8px">
      <div class="sc-header-main">
        <div class="sc-header-left">
          <div class="sc-header-course">Practice Session</div>
          <div class="sc-header-meta">${dateStr}</div>
        </div>
        <div class="sc-header-right">
          <div class="sc-header-total" style="color:${pctColor}">${pct}%</div>
          <div class="sc-header-diff" style="color:var(--text2)">${done}/${total} drills</div>
        </div>
      </div>
      <div class="sc-header-footer" style="border-top-color:rgba(0,0,0,0.1)">${pillsHtml}</div>
    </div>
    ${catCards}
    ${notesCard}
    <div class="sc-actions">
      <button class="btn btn-red" style="flex:0;padding:10px 20px;font-size:13px;display:flex;align-items:center;gap:6px" onclick="deletePracticeSession(${ts.id})">
        <img src="/static/trash-96.png" class="icon-16"> Delete
      </button>
      <div style="flex:1"></div>
    </div>
  `;
}

function deletePracticeSession(id) {
  showConfirm('Delete Session?', 'This cannot be undone.', 'Delete', async () => {
    await fetch(`/api/training/${id}`, { method: 'DELETE' });
    _practiceSessionsCache = null;
    S.viewPractice = null;
    nav('rounds');
  });
}

async function viewRound(idx) {
  S.viewRoundIdx=idx;
  const sc=await GET(`/api/rounds/${idx}/scorecard`);
  S.viewRound=sc;
  show('scorecard');
}

/* ================================================================
   SCORECARD DETAIL — _show_scorecard_detail_page
   ================================================================ */
function renderScorecard() {
  const sc=S.viewRound; if(!sc) return;
  const v=document.getElementById('v-scorecard');
  const diff=sc.total_score-sc.par;
  const ds=diff>0?`+${diff}`:diff===0?'E':`${diff}`;
  const teeColor=sc.tee_color||'White';
  const teeCSS=teeColorCSS(teeColor);

  const headerBg=teeColor==='White'?'#F8F8F8':teeCSS;
  const headerFg=teeTextColor(headerBg);
  const headerBorder=teeColor==='White'?'1px solid var(--sep)':'none';

  // Date formatting
  const dateStr=(sc.date||'').substring(0,10);
  const totalYards=(sc.front_9.yards_total||0)+(sc.back_9.yards_total||0);

  // Score diff color
  const diffColor=diff>0?'rgba(255,59,48,0.9)':diff<0?'rgba(52,199,89,0.9)':'inherit';

  // Target
  let targetHtml='';
  if(sc.target_score && sc.target_score!=='N/A'){
    const td=sc.total_score-sc.target_score;
    targetHtml=`<span class="sc-header-target">Target ${sc.target_score} (${td>=0?'+':''}${td})</span>`;
  }

  // Round info pills
  const holesLabel=sc.holes_choice==='front_9'?'Front 9':sc.holes_choice==='back_9'?'Back 9':'18 Holes';
  let pills=`<span class="sc-pill">${holesLabel}</span>`;
  pills+=`<span class="sc-pill">${sc.round_type==='scramble'?'Scramble':'Solo'}</span>`;
  if(!sc.is_serious) pills+=`<span class="sc-pill">Casual</span>`;
  if(sc.is_sim) pills+=`<span class="sc-pill">Sim</span>`;

  // Tee dot pill
  const teeDotBorder=teeCSS==='#FFFFFF'?'1px solid rgba(0,0,0,0.2)':'none';
  const teePill=`<span class="sc-pill"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${teeCSS};border:${teeDotBorder};vertical-align:middle;margin-right:4px"></span>${teeColor} Tees</span>`;

  // Build scorecard grids — traditional horizontal format
  function buildNine(label, pars, scores, yardages, startHole) {
    if(!pars||!pars.length) return '';

    // Header row (hole numbers)
    let holeRow=`<div class="sc-cell sc-cell-header sc-cell-hole"></div>`;
    for(let i=0;i<pars.length;i++) holeRow+=`<div class="sc-cell sc-cell-header sc-cell-hole">${startHole+i+1}</div>`;
    holeRow+=`<div class="sc-cell sc-cell-header sc-cell-hole">${label}</div>`;

    // Yardage row
    let yardRow=`<div class="sc-cell sc-cell-header sc-cell-yard">YDS</div>`;
    let yardTotal=0;
    for(let i=0;i<pars.length;i++){
      const y=yardages&&yardages[i]?yardages[i]:'';
      yardTotal+=(yardages&&yardages[i])||0;
      yardRow+=`<div class="sc-cell sc-cell-yard">${y}</div>`;
    }
    yardRow+=`<div class="sc-cell sc-cell-total sc-cell-yard">${yardTotal||''}</div>`;

    // Par row
    let parRow=`<div class="sc-cell sc-cell-header" style="font-weight:700;font-size:10px;color:var(--text2)">PAR</div>`;
    let parTotal=0;
    for(let i=0;i<pars.length;i++){
      parTotal+=pars[i];
      parRow+=`<div class="sc-cell sc-cell-par">${pars[i]}</div>`;
    }
    parRow+=`<div class="sc-cell sc-cell-total">${parTotal}</div>`;

    // Score row
    let scoreRow=`<div class="sc-cell sc-cell-header" style="font-weight:700;font-size:10px;color:var(--text)">SCORE</div>`;
    let scoreTotal=0;
    let hasScores=false;
    for(let i=0;i<pars.length;i++){
      const s=scores&&i<scores.length?scores[i]:null;
      if(s!=null){
        hasScores=true;
        scoreTotal+=s;
        scoreRow+=`<div class="sc-cell"><div class="sc-score ${scoreClass(s,pars[i])}">${s}</div></div>`;
      } else {
        scoreRow+=`<div class="sc-cell" style="color:var(--text3)">—</div>`;
      }
    }
    scoreRow+=`<div class="sc-cell sc-cell-total">${hasScores?scoreTotal:''}</div>`;

    if(!hasScores && !scores.length) return '';

    return `
      <div class="sc-wrap">
        <div class="sc-grid sc-grid-9">
          ${holeRow}${yardRow}${parRow}${scoreRow}
        </div>
      </div>`;
  }

  const frontGrid=buildNine('FRONT OUT', sc.front_9.pars, sc.front_9.scores, sc.front_9.yardages, 0);
  const backGrid=buildNine('BACK IN', sc.back_9.pars, sc.back_9.scores, sc.back_9.yardages, 9);

  // Totals summary row — shown for all completed rounds
  let totalsHtml='';
  if(frontGrid || backGrid){
    const teeTopBorder=`border-top:2px solid ${teeCSS}`;
    let cols='';
    if(frontGrid && backGrid){
      const f9=sc.front_9.score_total, b9=sc.back_9.score_total;
      const f9p=sc.front_9.par_total, b9p=sc.back_9.par_total;
      cols=`
        <div><div class="muted-xs">FRONT</div><div style="font-size:18px;font-weight:700">${f9||'—'}</div></div>
        <div><div class="muted-xs">BACK</div><div style="font-size:18px;font-weight:700">${b9||'—'}</div></div>
        <div><div class="muted-xs">TOTAL</div><div style="font-size:22px;font-weight:800">${sc.total_score}</div></div>
        <div><div class="muted-xs">PAR</div><div style="font-size:18px;font-weight:700">${f9p+b9p}</div></div>
        <div><div class="muted-xs">+/−</div><div style="font-size:18px;font-weight:700;color:${diffColor}">${ds}</div></div>`;
    } else {
      const nine=frontGrid ? sc.front_9 : sc.back_9;
      const label=frontGrid ? 'FRONT' : 'BACK';
      cols=`
        <div><div class="muted-xs">${label}</div><div style="font-size:22px;font-weight:800">${nine.score_total||'—'}</div></div>
        <div><div class="muted-xs">PAR</div><div style="font-size:18px;font-weight:700">${nine.par_total}</div></div>
        <div><div class="muted-xs">+/−</div><div style="font-size:18px;font-weight:700;color:${diffColor}">${ds}</div></div>`;
    }
    totalsHtml=`<div class="sc-totals" style="${teeTopBorder}">${cols}</div>`;
  }

  v.innerHTML=`
    <!-- Tee-colored header card -->
    <div class="sc-header-card" style="background:${headerBg};color:${headerFg};border:${headerBorder}">
      <div class="sc-header-stripe" style="background:${teeCSS}"></div>
      <div class="sc-header-main">
        <div class="sc-header-left">
          <div class="sc-header-course">${esc(sc.course_name)}</div>
          <div class="sc-header-meta">${[sc.club_name,dateStr,totalYards?totalYards+' yds':''].filter(Boolean).join(' · ')}</div>
        </div>
        <div class="sc-header-right">
          <div class="sc-header-total">${sc.total_score}</div>
          <div class="sc-header-diff" style="color:${diffColor}">${ds}</div>
        </div>
      </div>
      <div class="sc-header-footer" style="border-top-color:${headerFg==='#FFFFFF'?'rgba(255,255,255,0.15)':'rgba(0,0,0,0.1)'}">
        ${teePill}${pills}${targetHtml}
      </div>
    </div>

    <!-- Scorecard grids -->
    ${frontGrid}
    ${backGrid}
    ${totalsHtml}

    ${sc.notes?`<div class="sc-notes"><div class="sc-notes-title">Notes</div><div class="sc-notes-body">${esc(sc.notes)}</div></div>`:''}

    <div class="sc-actions">
      <button class="btn btn-red" style="flex:0;padding:10px 20px;font-size:13px;display:flex;align-items:center;gap:6px" onclick="delRound(${S.viewRoundIdx})"><img src="/static/trash-96.png" class="icon-16"> Delete</button>
      <div style="flex:1"></div>
    </div>
  `;
}

async function delRound(idx){
  showConfirm('Delete Round?', 'This cannot be undone.', 'Delete', async () => {
    await DEL(`/api/rounds/${idx}`);
    clearStatsCache();
    nav('rounds');
  });
}

/* ================================================================
   START SESSION — action sheet: round vs practice
   ================================================================ */
function showStartSessionSheet() {
  const el = _showDialog(`
    <div class="dialog-sheet">
      <div class="dialog-card">
        <div class="dialog-title">Start Session</div>
        <div class="dialog-sep"></div>
        <button class="dialog-btn" id="dlg-round" style="display:flex;align-items:center;justify-content:center;gap:8px"><img src="/static/golf-cart-96.png" style="width:20px;height:20px;object-fit:contain"> Log a Round</button>
        <div class="dialog-sep"></div>
        <button class="dialog-btn" id="dlg-practice" style="display:flex;align-items:center;justify-content:center;gap:8px"><img src="/static/golf-clubs-96.png" style="width:20px;height:20px;object-fit:contain"> Practice Session</button>
      </div>
      <div class="dialog-card" style="margin-top:8px">
        <button class="dialog-btn" id="dlg-cancel">Cancel</button>
      </div>
    </div>`);
  el.querySelector('#dlg-round').onclick  = () => { el.remove(); startLog(); };
  el.querySelector('#dlg-practice').onclick = () => { el.remove(); startTraining(); };
  el.querySelector('#dlg-cancel').onclick  = () => el.remove();
}

/* ================================================================
   TRAINING SESSION
   ================================================================ */
let T = { template: [], drillStates: [], date: '', notes: '', selectedCategories: [], selectedClubs: {}, activeCatIdx: 0, wedgeMatrix: {} };
const CLUB_ORDER = ['LW','SW','GW','PW','9 Iron','8 Iron','7 Iron','6 Iron','5 Iron','4 Iron','3 Iron','2 Iron','5 Hybrid','4 Hybrid','3 Hybrid','2 Hybrid','7 Wood','5 Wood','3 Wood','Driver'];

async function startTraining() {
  T.template = await GET('/api/training/template');
  T.date = new Date().toISOString().substring(0, 10);
  T.notes = '';
  T.drillStates = [];
  T.wedgeMatrix = {};
  for (const cat of T.template) {
    if (cat.resultType === 'wedge_matrix') {
      T.drillStates.push({
        category: cat.category,
        name: 'Total Balls',
        resultType: 'wedge_matrix',
        completed: false,
        skipped: false,
        result: '',
        pendingPartialUpdates: [],
      });
    } else {
      for (const drill of cat.drills) {
        T.drillStates.push({
          category: cat.category,
          name: drill.name,
          club: (cat.clubs && cat.clubs.length === 1) ? cat.clubs[0] : null,
          resultType: drill.resultType,
          hint: drill.hint || '',
          completed: false,
          skipped: false,
          result: '',
        });
      }
    }
  }
  const draft = getTrainingDraft();
  if (draft && draft.drillStates && draft.drillStates.length === T.drillStates.length) {
    T.drillStates = draft.drillStates;
    T.date = draft.date || T.date;
    T.notes = draft.notes || '';
    T.selectedCategories = draft.selectedCategories || T.template.map(c => c.category);
    T.selectedClubs = draft.selectedClubs || _defaultSelectedClubs();
    T.activeCatIdx = draft.activeCatIdx || 0;
    T.wedgeMatrix = draft.wedgeMatrix || {};
    clearTrainingDraft();
    show('training');
    return;
  }
  T.selectedCategories = T.template.map(c => c.category);
  T.selectedClubs = _defaultSelectedClubs();
  T.wedgeMatrix = {};
  T.activeCatIdx = 0;
  show('training-setup');
}

function _defaultSelectedClubs() {
  const sc = {};
  for (const cat of T.template) {
    if (cat.resultType === 'wedge_matrix' && cat.wedge_clubs) {
      sc[cat.category] = cat.wedge_clubs.map(c => c.name);
    } else if (cat.clubs && cat.clubs.length) {
      sc[cat.category] = [...cat.clubs];
    }
  }
  return sc;
}

function _buildCatDrillMap() {
  const map = {};
  let idx = 0;
  for (const cat of T.template) {
    if (cat.resultType === 'wedge_matrix') {
      map[cat.category] = { baseIdx: idx, count: 1, isWedgeMatrix: true };
      idx++;
    } else {
      map[cat.category] = { baseIdx: idx, count: cat.drills.length, isWedgeMatrix: false };
      idx += cat.drills.length;
    }
  }
  return map;
}

function _renderDrillRows(cat, baseIdx) {
  if (cat.resultType === 'wedge_matrix') return _renderWedgeMatrix(cat);

  const selClubs = T.selectedClubs[cat.category];
  let drillRows = '';

  for (let i = 0; i < cat.drills.length; i++) {
    const drill = cat.drills[i];
    const idx = baseIdx + i;
    const state = T.drillStates[idx];
    if (!state) continue;

    // Filter by selected clubs when drill is per-club
    const drillClub = drill.clubName || null;
    if (drillClub && selClubs && !selClubs.includes(drillClub)) continue;

    const isDone = state.completed;

    if (drill.resultType === 'check') {
      drillRows += `
        <div class="drill-row" onclick="toggleDrill(${idx})">
          <div class="drill-row-check">
            <div class="drill-circle${isDone?' done':''}" id="circle-${idx}"></div>
            <div class="drill-body"><div class="drill-title">${esc(drill.name)}</div></div>
          </div>
        </div>`;

    } else if (drill.resultType === 'streak') {
      drillRows += `
        <div class="drill-row" style="display:flex;align-items:center;justify-content:space-between;gap:12px">
          <div class="drill-title" style="flex:1">${esc(drill.name)}</div>
          <input class="drill-streak-input" type="number" inputmode="numeric" placeholder="0"
                 value="${esc(state.result)}" style="width:64px"
                 oninput="handleStreak(${idx},this.value)">
        </div>`;

    } else if (drill.resultType === 'count') {
      const val = parseInt(state.result) || 0;
      const target = drill.target || null;
      const ydSpan = drill.distance ? ` <span style="font-size:14px;font-weight:500;color:var(--text2)">${drill.distance} yd</span>` : '';
      drillRows += `
        <div class="drill-row" style="display:flex;align-items:center;justify-content:space-between;gap:12px">
          <div style="flex:1">
            <div class="drill-title" style="font-size:17px">${esc(drill.name)}${ydSpan}</div>
          </div>
          <div style="display:flex;align-items:center;gap:6px">
            <div class="drill-stepper">
              <button class="drill-stepper-btn" onclick="stepCount(${idx},-1)">−</button>
              <div class="drill-stepper-val" id="step-val-${idx}">${val}</div>
              <button class="drill-stepper-btn" onclick="stepCount(${idx},1)">+</button>
            </div>
            ${target ? `<span class="drill-stepper-target">/ ${target}</span>` : ''}
          </div>
        </div>`;

    } else if (drill.resultType === 'pct') {
      const parts = (state.result || '').split('/');
      const made = parts[0] || '';
      const hit  = parts[1] || '';
      const pctTxt = (made && hit && parseInt(hit) > 0)
        ? Math.round(parseInt(made) / parseInt(hit) * 100) + '%' : '';
      drillRows += `
        <div class="drill-row" style="display:flex;align-items:center;justify-content:space-between;gap:12px">
          <div class="drill-title" style="flex:1">${esc(drill.name)}</div>
          <div class="drill-pct-row">
            <input class="drill-pct-input" type="number" inputmode="numeric" placeholder="0"
                   value="${esc(made)}" oninput="updatePct(${idx},'made',this.value)">
            <span class="drill-pct-sep">/</span>
            <input class="drill-pct-input" type="number" inputmode="numeric" placeholder="0"
                   value="${esc(hit)}" oninput="updatePct(${idx},'hit',this.value)">
            <span class="drill-pct-live" id="pct-live-${idx}">${pctTxt}</span>
          </div>
        </div>`;

    } else if (drill.resultType === 'distance') {
      const pitchDists = cat.distances && cat.distances.length ? cat.distances : [50,60,70,80,90,100,110,120,130];
      const chips = pitchDists.map(d =>
        `<button class="drill-distance-chip${state.result===String(d)?' selected':''}"
             onclick="pickPitchDist(${idx},${d})">${d}</button>`
      ).join('');
      const selTxt = state.result ? `<strong>${esc(state.result)} yds</strong>` : '';
      drillRows += `
        <div class="drill-row">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
            <div class="drill-title">${esc(drill.name)}</div>
            <div id="dist-sel-${idx}" style="font-size:13px;color:var(--accent)">${selTxt}</div>
          </div>
          <div class="drill-distance-chips" id="dist-chips-${idx}">${chips}</div>
        </div>`;
    }
  }
  return drillRows;
}

function _renderWedgeMatrix(cat) {
  const wedgeClubs = cat.wedge_clubs || [];
  const selectedWedges = new Set(Object.keys(T.wedgeMatrix));
  const swings = ['1/4', '1/2', '3/4', 'Full'];

  let clubCards = '';
  for (const c of wedgeClubs) {
    if (!selectedWedges.has(c.name)) continue;
    const wm = T.wedgeMatrix[c.name] || {};
    let rows = '';
    for (let si = 0; si < swings.length; si++) {
      const sw = swings[si];
      const isLast = si === swings.length - 1;
      const storedDist = sw === 'Full' ? (c.full || null) : ((c.partials || {})[sw] || null);
      const distLabel = storedDist ? `${storedDist} yd` : '—';
      const count = (wm[sw] || {}).count || 0;
      const showSaveBtn = (count >= 8 && storedDist !== null);
      const confirmBtn = showSaveBtn
        ? `<button style="font-size:11px;color:var(--accent);background:none;border:none;cursor:pointer;padding:0;margin-left:4px" onclick="confirmWedgeUpdate('${esc(c.name)}','${sw}',${storedDist})">💾</button>`
        : '';
      rows += `<div style="display:flex;align-items:center;gap:8px;padding:8px 0;${isLast?'':'border-bottom:1px solid var(--sep)'}">
        <div style="width:34px;font-size:13px;font-weight:600;color:var(--text2)">${sw}</div>
        <div style="width:44px;font-size:12px;color:var(--text2)">${distLabel}</div>
        <div style="flex:1"></div>
        <div class="drill-stepper">
          <button class="drill-stepper-btn" onclick="stepWedge('${esc(c.name)}','${sw}',-1)">−</button>
          <div class="drill-stepper-val" id="wm-${esc(c.name)}-${sw}">${count}</div>
          <button class="drill-stepper-btn" onclick="stepWedge('${esc(c.name)}','${sw}',1)">+</button>
        </div>
        <div style="width:28px;font-size:12px;color:var(--text2)">/10${confirmBtn}</div>
      </div>`;
    }
    clubCards += `<div style="margin-bottom:10px;background:var(--card);border-radius:12px;padding:2px 12px 4px;border:1px solid var(--sep)">
      <div style="font-size:14px;font-weight:700;padding:10px 0 4px;border-bottom:1px solid var(--sep)">${esc(c.name)}</div>
      ${rows}
    </div>`;
  }

  return clubCards;
}


function stepWedge(clubName, swing, delta) {
  if (!T.wedgeMatrix[clubName]) T.wedgeMatrix[clubName] = {};
  if (!T.wedgeMatrix[clubName][swing]) T.wedgeMatrix[clubName][swing] = {count:0};
  T.wedgeMatrix[clubName][swing].count = Math.max(0, Math.min(10, (T.wedgeMatrix[clubName][swing].count || 0) + delta));
  const el = document.getElementById(`wm-${clubName}-${swing}`);
  if (el) el.textContent = T.wedgeMatrix[clubName][swing].count;
  const wmStateIdx = T.drillStates.findIndex(d => d.resultType === 'wedge_matrix');
  if (wmStateIdx >= 0) {
    const total = Object.values(T.wedgeMatrix).flatMap(sw => Object.values(sw)).reduce((s, v) => s + (v.count||0), 0);
    T.drillStates[wmStateIdx].completed = total > 0;
    T.drillStates[wmStateIdx].result = total > 0 ? String(total) : '';
  }
  saveTrainingDraft();
}

async function confirmWedgeUpdate(clubName, swing, dist) {
  const club = await GET(`/api/clubs`);
  const c = (club || []).find(x => x.name === clubName);
  if (!c) return;
  const partials = Object.assign({}, c.partials || {});
  if (swing === 'Full') {
    await PUT(`/api/clubs/${encodeURIComponent(clubName)}`, { name: clubName, distance: dist, notes: c.notes || '', partials });
  } else {
    partials[swing] = dist;
    await PUT(`/api/clubs/${encodeURIComponent(clubName)}`, { name: clubName, distance: c.distance, notes: c.notes || '', partials });
  }
  // Record in pending updates on the wedge matrix drill state
  const wmStateIdx = T.drillStates.findIndex(d => d.resultType === 'wedge_matrix');
  if (wmStateIdx >= 0) {
    if (!T.drillStates[wmStateIdx].pendingPartialUpdates) T.drillStates[wmStateIdx].pendingPartialUpdates = [];
    T.drillStates[wmStateIdx].pendingPartialUpdates.push({ club: clubName, swing, dist });
  }
}

const _CAT_DISPLAY = { 'RANGE WARM-UP': 'WARMUP', 'WEDGE MATRIX': 'PITCHING' };
function _catDisplayName(n) { return _CAT_DISPLAY[n] || n; }

function _catClubNames(cat) {
  if (cat.resultType === 'wedge_matrix' && cat.wedge_clubs) {
    return cat.wedge_clubs.map(wc => wc.name);
  }
  return cat.clubs || [];
}

function renderTrainingSetup() {
  const v = document.getElementById('v-training-setup');
  if (!T.template.length) { v.innerHTML = '<div class="hint">Loading…</div>'; return; }

  const sections = T.template.map(cat => {
    const sel = T.selectedCategories.includes(cat.category);
    const displayName = _catDisplayName(cat.category);
    const clubs = _catClubNames(cat).slice().sort((a, b) => {
      const ai = CLUB_ORDER.indexOf(a), bi = CLUB_ORDER.indexOf(b);
      return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi);
    });
    const clubChips = (sel && clubs.length) ? clubs.map(c => {
      const isSel = (T.selectedClubs[cat.category] || []).includes(c);
      return `<button class="drill-distance-chip${isSel?' selected':''}" style="font-size:12px" onclick="tsClubToggle('${esc(cat.category)}','${esc(c)}')">${esc(c)}</button>`;
    }).join('') : '';
    const clubsRow = clubChips ? `<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px">${clubChips}</div>` : '';
    return `
      <div style="margin-bottom:${clubsRow?'18px':'10px'}">
        <button class="drill-distance-chip${sel?' selected':''}" style="font-size:13px" onclick="tsCatToggle('${esc(cat.category)}')">${esc(displayName)}</button>
        ${clubsRow}
      </div>`;
  }).join('');

  v.innerHTML = `
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center">
      <button class="back-btn" onclick="show('home')" style="margin-bottom:0">‹ Home</button>
      <div class="page-title">Practice</div>
    </div>
    <div style="padding:0 16px 12px;display:flex;align-items:center;gap:10px">
      <label style="font-size:13px;color:var(--text2);font-weight:600">Date</label>
      <input type="date" class="form-input" style="flex:1;max-width:180px" value="${T.date}" onchange="T.date=this.value">
    </div>
    <div style="padding:0 16px 16px">${sections}</div>
    <div style="padding:0 16px 8px">
      <button class="btn btn-primary" onclick="tsStartActive()">Start Session →</button>
    </div>
    <div style="height:16px"></div>
  `;
}

function tsCatToggle(catName) {
  const i = T.selectedCategories.indexOf(catName);
  if (i >= 0) T.selectedCategories.splice(i, 1);
  else T.selectedCategories.push(catName);
  renderTrainingSetup();
}

function tsClubToggle(catName, clubName) {
  if (!T.selectedClubs[catName]) {
    const cat = T.template.find(c => c.category === catName);
    T.selectedClubs[catName] = cat ? [..._catClubNames(cat)] : [];
  }
  const arr = T.selectedClubs[catName];
  const i = arr.indexOf(clubName);
  if (i >= 0) arr.splice(i, 1);
  else arr.push(clubName);
  renderTrainingSetup();
}

function tsStartActive() {
  // Filter selected categories: no-club cats kept as-is; club cats only if ≥1 club selected
  const sessionCats = T.template
    .filter(cat => {
      if (!T.selectedCategories.includes(cat.category)) return false;
      const clubs = _catClubNames(cat);
      if (!clubs.length) return true; // WARMUP, PUTTING — no club filter
      return (T.selectedClubs[cat.category] || []).length > 0;
    })
    .map(c => c.category);
  T.selectedCategories = sessionCats;

  // Init wedge matrix counts only for selected wedge clubs
  const wedgeCat = T.template.find(c => c.category === 'WEDGE MATRIX');
  if (wedgeCat) {
    const selWedges = new Set(T.selectedClubs['WEDGE MATRIX'] || []);
    const fresh = {};
    for (const wc of (wedgeCat.wedge_clubs || [])) {
      if (selWedges.has(wc.name)) {
        fresh[wc.name] = T.wedgeMatrix[wc.name] || { '1/4':{count:0}, '1/2':{count:0}, '3/4':{count:0}, 'Full':{count:0} };
      }
    }
    T.wedgeMatrix = fresh;
  }

  T.activeCatIdx = 0;
  show('training');
}

function renderTraining() {
  const v = document.getElementById('v-training');
  if (!T.template.length || !T.selectedCategories.length) {
    v.innerHTML = '<div class="hint">Loading…</div>'; return;
  }

  const catMap = _buildCatDrillMap();
  const selCats = T.selectedCategories;
  const total = selCats.length;
  const curIdx = Math.max(0, Math.min(T.activeCatIdx, total - 1));
  T.activeCatIdx = curIdx;
  const catName = selCats[curIdx];
  const cat = T.template.find(c => c.category === catName);
  if (!cat) { v.innerHTML = '<div class="hint">Category not found.</div>'; return; }

  const info = catMap[catName] || { baseIdx: 0 };
  const pct = Math.round(((curIdx) / total) * 100);
  const isLast = curIdx === total - 1;

  const instructionsBanner = cat.instructions
    ? `<div class="drill-instructions">${esc(cat.instructions)}</div>`
    : '';
  const drillRows = _renderDrillRows(cat, info.baseIdx);

  const notesHtml = isLast ? `
    <div class="card" style="margin-top:4px">
      <label class="form-label">Notes (optional)</label>
      <textarea class="form-input" rows="3" placeholder="How did the session go?" oninput="T.notes=this.value">${esc(T.notes)}</textarea>
    </div>` : '';

  const prevBtn = curIdx > 0
    ? `<button class="btn" style="flex:1" onclick="trainingNav(-1)">← Prev</button>`
    : `<button class="btn" style="flex:1;opacity:0.3" disabled>← Prev</button>`;
  const nextBtn = isLast
    ? `<button id="btn-save-session" class="btn btn-primary" style="flex:2" onclick="saveTrainingSession()">Save Session</button>`
    : `<button class="btn btn-primary" style="flex:2" onclick="trainingNav(1)">Next →</button>`;

  const instrBlock = instructionsBanner
    ? `<div class="drill-section" style="margin-bottom:4px"><div class="drill-card">${instructionsBanner}</div></div>`
    : '';

  v.innerHTML = `
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center">
      <button class="back-btn" onclick="saveTrainingDraft();show('training-setup')" style="margin-bottom:0">‹ Back</button>
      <div style="text-align:right">
        <div style="font-size:12px;color:var(--text2)">${curIdx+1} of ${total}</div>
      </div>
    </div>
    <div style="margin:0 16px 12px;background:var(--sep);border-radius:4px;height:4px">
      <div style="width:${pct}%;height:4px;background:var(--accent);border-radius:4px;transition:width 0.2s"></div>
    </div>
    ${instrBlock}
    <div class="drill-section" id="training-swipe-area">
      <div class="drill-section-header">
        <span class="drill-section-title">${esc(_catDisplayName(cat.category))}</span>
      </div>
      ${cat.resultType === 'wedge_matrix'
        ? `<div style="padding:4px 0">${drillRows}</div>`
        : `<div class="drill-card">${drillRows}</div>`}
    </div>
    ${notesHtml}
    <div style="padding:8px 16px 8px;display:flex;gap:8px">
      ${prevBtn}
      ${nextBtn}
    </div>
    <div style="height:16px"></div>
  `;

  // Touch swipe support
  let _tx = 0;
  const sw = document.getElementById('training-swipe-area');
  if (sw) {
    sw.addEventListener('touchstart', e => { _tx = e.touches[0].clientX; }, {passive:true});
    sw.addEventListener('touchend', e => {
      const dx = e.changedTouches[0].clientX - _tx;
      if (Math.abs(dx) >= 50) trainingNav(dx < 0 ? 1 : -1);
    }, {passive:true});
  }
}

function trainingNav(delta) {
  saveTrainingDraft();
  T.activeCatIdx = Math.max(0, Math.min(T.activeCatIdx + delta, T.selectedCategories.length - 1));
  renderTraining();
  document.getElementById('v-training') && (document.getElementById('v-training').scrollTop = 0);
  const contentEl = document.getElementById('content');
  if (contentEl) contentEl.scrollTop = 0;
}

function _updateDrillCounter() {
  const done = T.drillStates.filter(d => d.completed).length;
  const el = document.getElementById('drill-counter');
  if (el) el.textContent = `${done}/${T.drillStates.length} complete`;
  saveTrainingDraft();
}

function toggleDrill(idx) {
  const state = T.drillStates[idx];
  state.completed = !state.completed;
  const circle = document.getElementById(`circle-${idx}`);
  if (circle) circle.className = `drill-circle${state.completed ? ' done' : ''}`;
  _updateDrillCounter();
}

function handleStreak(idx, val) {
  T.drillStates[idx].result = val;
  T.drillStates[idx].completed = !!val;
  const circle = document.getElementById(`circle-${idx}`);
  if (circle) circle.className = `drill-circle${!!val ? ' done' : ''}`;
  _updateDrillCounter();
}

function stepCount(idx, delta) {
  const state = T.drillStates[idx];
  const next = Math.max(0, (parseInt(state.result) || 0) + delta);
  state.result = String(next);
  state.completed = next > 0;
  const el = document.getElementById(`step-val-${idx}`);
  if (el) el.textContent = next;
  const circle = document.getElementById(`circle-${idx}`);
  if (circle) circle.className = `drill-circle${state.completed ? ' done' : ''}`;
  _updateDrillCounter();
}

function updatePct(idx, field, val) {
  const state = T.drillStates[idx];
  const parts = (state.result || '/').split('/');
  const made = field === 'made' ? val : (parts[0] || '');
  const hit  = field === 'hit'  ? val : (parts[1] || '');
  state.result = `${made}/${hit}`;
  state.completed = !!(made && hit);
  const circle = document.getElementById(`circle-${idx}`);
  if (circle) circle.className = `drill-circle${state.completed ? ' done' : ''}`;
  const liveEl = document.getElementById(`pct-live-${idx}`);
  if (liveEl) {
    const m = parseInt(made), h = parseInt(hit);
    liveEl.textContent = (m >= 0 && h > 0) ? Math.round(m / h * 100) + '%' : '';
  }
  _updateDrillCounter();
}

function pickPitchDist(idx, dist) {
  const state = T.drillStates[idx];
  state.result = String(dist);
  state.completed = true;
  const chipContainer = document.getElementById(`dist-chips-${idx}`);
  if (chipContainer) {
    chipContainer.querySelectorAll('.drill-distance-chip').forEach(btn => {
      btn.classList.toggle('selected', btn.textContent === String(dist));
    });
  }
  const circle = document.getElementById(`circle-${idx}`);
  if (circle) circle.className = 'drill-circle done';
  const selEl = document.getElementById(`dist-sel-${idx}`);
  if (selEl) selEl.innerHTML = `Selected: <strong>${dist} yds</strong>`;
  _updateDrillCounter();
}

async function saveTrainingSession() {
  const btn=document.getElementById('btn-save-session');
  if(btn){btn.disabled=true;btn.style.opacity='0.6';}
  // ensure template and drills are populated
  if (!T.template.length) {
    T.template = await GET('/api/training/template');
  }
  if (!T.drillStates.length && T.template.length) {
    for (const cat of T.template) {
      if (cat.resultType === 'wedge_matrix') {
        T.drillStates.push({
          category: cat.category,
          name: 'Total Balls',
          resultType: 'wedge_matrix',
          completed: false,
          skipped: false,
          result: '',
          pendingPartialUpdates: [],
        });
      } else {
        for (const drill of cat.drills) {
          T.drillStates.push({
            category: cat.category,
            name: drill.name,
            club: (cat.clubs && cat.clubs.length === 1) ? cat.clubs[0] : null,
            resultType: drill.resultType,
            hint: drill.hint || '',
            completed: false,
            skipped: false,
            result: '',
          });
        }
      }
    }
  }
  // result already synced via oninput handlers
  const payload = {
    date: T.date,
    drills: T.drillStates,
    notes: T.notes,
  };
  const res=await POST('/api/training', payload);
  if(res&&res.ok===false){if(btn){btn.disabled=false;btn.style.opacity='1';}showAlert('Save Failed', res.error||'Unknown error');return;}
  clearTrainingDraft();
  const completed=T.drillStates.filter(d=>d.completed&&!d.skipped).length;
  showAlert('Session Saved!', `${completed}/${T.drillStates.length} complete · ${T.date}`);
  T = { template: [], drillStates: [], date: '', notes: '', selectedCategories: [], selectedClubs: {}, activeCatIdx: 0, wedgeMatrix: {} };
  navHome();
}

async function renderTrainingHistory() {
  const v = document.getElementById('v-training-history');
  v.innerHTML = '<div class="page-header"><div class="page-title">Practice History</div></div><div class="hint">Loading…</div>';
  const sessions = await GET('/api/training');
  if (!sessions.length) {
    v.innerHTML = `<div class="page-header"><button class="back-btn" onclick="show('home')">‹ Home</button><div class="page-title">Practice History</div></div>
      <div class="empty"><div class="empty-icon"><img src="/static/golf-clubs-96.png" style="width:80px;height:80px;object-fit:contain;display:block;margin:0 auto"></div><div class="empty-headline">No Sessions Yet</div><div class="empty-text">Start a practice session to track your improvement.</div></div>`;
    return;
  }
  let rows = '';
  for (const ts of sessions) {
    const drills = ts.drills || [];
    const total = drills.length;
    const done = drills.filter(d => d.completed && !d.skipped).length;
    const cats = [...new Set(drills.map(d => d.category))].join(' · ');
    const dateStr = (ts.date || '').substring(0, 10);

    // Drill detail rows
    let drillDetail = '';
    let lastCat = '';
    for (const d of drills) {
      if (d.category !== lastCat) {
        drillDetail += `<div style="font-size:11px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:0.5px;padding:8px 0 3px">${esc(d.category)}</div>`;
        lastCat = d.category;
      }
      const dotColor = d.completed ? 'var(--green)' : 'var(--sep)';
      const resultStr = d.result ? ` — ${esc(d.result)}` : '';
      drillDetail += `<div style="font-size:13px;padding:3px 0;display:flex;align-items:center;gap:6px"><span style="width:10px;height:10px;border-radius:50%;background:${dotColor};flex-shrink:0;display:inline-block"></span><span style="color:${d.completed?'var(--text)':'var(--text2)'}">${esc(d.name)}${resultStr}</span></div>`;
    }

    const noteHtml = ts.notes ? `<div style="font-size:13px;color:var(--text2);margin-top:8px;padding-top:8px;border-top:0.5px solid var(--sep)">${esc(ts.notes)}</div>` : '';

    rows += `<div class="card" style="margin-bottom:8px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
        <div>
          <div style="font-size:16px;font-weight:700">${dateStr}</div>
          <div style="font-size:12px;color:var(--text2);margin-top:1px">${esc(cats)}</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <span class="training-session-badge">${done}/${total}</span>
          <button onclick="deleteTrainingSession(${ts.id},this)" style="background:none;border:none;cursor:pointer;padding:4px"><img src="/static/trash-96.png" style="width:18px;height:18px;object-fit:contain"></button>
        </div>
      </div>
      ${drillDetail}
      ${noteHtml}
    </div>`;
  }

  v.innerHTML = `
    <div class="page-header">
      <button class="back-btn" onclick="show('home')">‹ Home</button>
      <div class="page-title">Practice History</div>
    </div>
    <div style="padding:0 16px">
      ${rows}
    </div>
    <div style="height:16px"></div>
  `;
}

async function deleteTrainingSession(id, btn) {
  showConfirm('Delete Session?', 'This cannot be undone.', 'Delete', async () => {
    await DEL(`/api/training/${id}`);
    renderTrainingHistory();
  });
}

/* ================================================================
   LOG ROUND SETUP — club ▶ course, tee pills, scramble=not serious
   ================================================================ */
async function startLog(){
  // S.clubs is kept current by all club mutators — no need to re-fetch
  const [courses,prefs]=await Promise.all([GET('/api/courses'),GET('/api/prefs')]);
  S.courses=courses;
  S.logMode=prefs.entry_mode||'quick';
  S.logType='solo'; S.logSerious=true; S.logHoles='full_18'; S.logIsSim=false;
  show('log-setup');
}

function renderLogSetup() {
  const v=document.getElementById('v-log-setup');
  if(!S.courses.length){
    v.innerHTML=`<div class="page-title">Log Round</div>
      <div class="card"><div class="section-head">No courses added yet</div><div style="font-size:11px;color:var(--text2);padding:12px 0">Add a course before logging a round.</div>
      <button class="btn btn-primary" onclick="nav('courses')">➕ Add Course</button></div>`;
    return;
  }

  // Group courses by club — stored on S so lsClubChanged() can reuse without rebuilding
  S.logClubMap={};
  for(const c of S.courses){const k=c.club||'Other';if(!S.logClubMap[k])S.logClubMap[k]=[];S.logClubMap[k].push(c);}
  const clubNames=Object.keys(S.logClubMap).sort();

  // Build club selector
  let clubOpts=`<option value="" disabled selected>Pick one</option>`+clubNames.map(cn=>`<option value="${esc(cn)}">${esc(cn)}</option>`).join('');

  const today=new Date().toISOString().substring(0,10);

  // Auto-select scramble disables serious
  const seriousDisabled=S.logType==='scramble';
  const seriousChecked=S.logSerious&&!seriousDisabled;

  const _draft = getDraft();
  let _draftBanner = '';
  if(_draft){
    const dc = S.courses.find(c => c.name === _draft.courseName);
    if(!dc){ clearDraft(); }
    else{
      const hole = (_draft.currentHoleIdx || 0) + 1;
      const total = (_draft.holesToScore || []).length;
      _draftBanner = `<div class="draft-banner">
      <div class="draft-banner-info">
        <div class="draft-banner-title">Resume in-progress round?</div>
        <div class="draft-banner-sub">${esc(_draft.courseName)} · Hole ${hole} of ${total}</div>
      </div>
      <div class="draft-banner-actions">
        <button class="draft-btn-resume" onclick="resumeDraft(getDraft())">Resume</button>
        <button class="draft-btn-discard" onclick="clearDraft();renderLogSetup()">Discard</button>
      </div>
    </div>`;
    }
  }

  v.innerHTML=`
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center">
      <button class="back-btn" onclick="show('home')" style="margin-bottom:0">‹ Home</button>
      <div class="page-title">Log Round</div>
    </div>

    ${_draftBanner}

    <div class="card">
      <div class="section-head" style="margin-bottom:8px">Club / Facility</div>
      <select class="form-select" id="ls-club" onchange="lsClubChanged()">${clubOpts}</select>
    </div>

    <div class="card">
      <div class="section-head" style="margin-bottom:8px">Course</div>
      <div id="ls-course-list"></div>
    </div>

    <div class="card">
      <div class="section-head" style="margin-bottom:8px">Tee Box</div>
      <div class="tee-pills" id="ls-tee-pills"></div>
    </div>

    <div class="card">
      <div class="form-group">
        <div class="form-label">Holes</div>
        <div class="radio-row" id="ls-holes">
          <button class="radio-opt${S.logHoles==='full_18'?' active':''}" onclick="setR(this,'ls-holes');S.logHoles='full_18'">18 Holes</button>
          <button class="radio-opt${S.logHoles==='front_9'?' active':''}" onclick="setR(this,'ls-holes');S.logHoles='front_9'">Front 9</button>
          <button class="radio-opt${S.logHoles==='back_9'?' active':''}" onclick="setR(this,'ls-holes');S.logHoles='back_9'">Back 9</button>
        </div>
      </div>
      <div class="form-group">
        <div class="form-label">Date</div>
        <input type="date" class="form-input" id="ls-date" value="${today}">
      </div>
    </div>

    <div class="card">
      <div class="section-head" style="margin-bottom:8px">Round Type</div>
      <div class="radio-row" id="ls-type">
        <button class="radio-opt${S.logType==='solo'?' active':''}" onclick="setR(this,'ls-type');S.logType='solo';lsTypeChanged()">Solo</button>
        <button class="radio-opt${S.logType==='scramble'?' active':''}" onclick="setR(this,'ls-type');S.logType='scramble';lsTypeChanged()">Scramble</button>
      </div>
      <div class="check-row" style="padding-top:8px" id="ls-serious-row">
        <input type="checkbox" id="ls-serious" ${seriousChecked?'checked':''} ${seriousDisabled?'disabled':''} onchange="S.logSerious=this.checked">
        <label for="ls-serious" style="${seriousDisabled?'opacity:0.4':''}">Serious round (counts toward handicap)</label>
      </div>
      <div class="check-row" id="ls-sim-row">
        <input type="checkbox" id="ls-sim" ${S.logIsSim?'checked':''} onchange="S.logIsSim=this.checked">
        <label for="ls-sim">Simulator Round</label>
      </div>
    </div>

    <div class="card">
      <div class="section-head" style="margin-bottom:8px">Entry Mode</div>
      <div class="radio-row" id="ls-mode">
        <button class="radio-opt${S.logMode==='quick'?' active':''}" onclick="setR(this,'ls-mode');S.logMode='quick'">Quick (scores only)</button>
        <button class="radio-opt${S.logMode==='detailed'?' active':''}" onclick="setR(this,'ls-mode');S.logMode='detailed'">Detailed (scores + clubs)</button>
      </div>
    </div>

    <div class="card">
      <button class="btn btn-primary" onclick="beginEntry()">▶ Start Entering Scores</button>
    </div>
  `;

  lsClubChanged();
}

function setR(el,gid){document.getElementById(gid).querySelectorAll('.radio-opt').forEach(b=>b.classList.remove('active'));el.classList.add('active');}

function lsTypeChanged(){
  const cb=document.getElementById('ls-serious');
  const row=document.getElementById('ls-serious-row');
  if(S.logType==='scramble'){
    S.logSerious=false;
    cb.checked=false; cb.disabled=true;
    row.querySelector('label').style.opacity='0.4';
  } else {
    cb.disabled=false;
    row.querySelector('label').style.opacity='1';
  }
}

function lsClubChanged(){
  const clubName=document.getElementById('ls-club').value;
  const container=document.getElementById('ls-course-list');
  if(!clubName){container.innerHTML='<div class="muted-sm">Select a club to see courses</div>';S.logCourse=null;document.getElementById('ls-tee-pills').innerHTML='';return;}
  const courses=(S.logClubMap||{})[clubName]||[];

  // Course list as tappable rows
  if(!courses.length){container.innerHTML='<div class="muted-sm">No courses for this club</div>';return;}

  let html='';
  courses.forEach((c,i)=>{
    const tp=c.pars.reduce((a,b)=>a+b,0);
    const sel=S.logCourse&&S.logCourse.name===c.name;
    const solo=courses.length===1;
    const br=solo?'10px':i===0?'10px 10px 0 0':i===courses.length-1?'0 0 10px 10px':'0';
    const borderTop=i>0&&!solo?'border-top:0.5px solid var(--sep);':'';
    html+=`<div class="ls-course-row" style="display:flex;align-items:center;padding:12px;cursor:pointer;border-radius:${br};overflow:hidden;border:2px solid ${sel?'var(--accent)':'transparent'};background:${sel?'rgba(0,122,255,0.06)':'var(--bg)'};${borderTop}" onclick="lsPickCourse('${esc(c.name)}')">
      <div style="flex:1">
        <div style="font-size:15px;font-weight:${sel?'600':'500'}">${esc(c.name)}</div>
        <div style="font-size:12px;color:var(--text2)">${c.pars.length} holes · Par ${tp}</div>
      </div>
      ${sel?'<div style="color:var(--accent);font-size:16px;font-weight:700">✓</div>':''}
    </div>`;
  });
  container.innerHTML=html;

  // Auto-select first if none selected or current not in this club
  if(!S.logCourse||!courses.find(c=>c.name===S.logCourse.name)){
    lsPickCourse(courses[0].name);
  } else {
    lsRefreshTees();
  }
}

function lsPickCourse(name){
  S.logCourse=S.courses.find(c=>c.name===name);
  lsClubChanged(); // Re-renders course list (with selection) and calls lsRefreshTees()
}

function lsRefreshTees(){
  const container=document.getElementById('ls-tee-pills');
  if(!container||!S.logCourse) return;
  const tees=S.logCourse.tee_boxes||[];
  if(!S.logTee||!tees.find(t=>t.color===S.logTee)){
    const pref=tees.find(t=>t.color==='White')||tees[0];
    S.logTee=pref?pref.color:null;
  }
  let html='';
  for(const t of tees){
    const active=t.color===S.logTee?' active':'';
    html+=`<div class="tee-pill${active}" onclick="S.logTee='${t.color}';lsRefreshTees()">
      <span class="tee-dot" style="background:${teeColorCSS(t.color)}"></span>
      <span>${t.color}</span>
      <span class="tee-pill-info">${t.rating}/${t.slope}</span>
    </div>`;
  }
  container.innerHTML=html;
}

// Build S.clubOptions / S.clubFullNames / S.distByAbbr from S.clubs.
// Also pre-sorts S.sortedClubs and S.sortedClubsNoDriver for suggestClubs,
// using clubUsage as a distance tiebreaker so the most-used club is preferred.
function buildClubLookups(clubUsage) {
  const usage = clubUsage || {};
  const byDist = [...S.clubs].sort((a,b) => (b.distance||0)-(a.distance||0));
  S.clubOptions = []; S.clubFullNames = {}; S.distByAbbr = {};
  for (const c of byDist) {
    const ab = abbrClub(c.name);
    S.clubOptions.push(ab); S.clubFullNames[ab] = c.name; S.distByAbbr[ab] = c.distance||0;
  }
  if (!S.clubOptions.includes('P') && !byDist.some(c => c.name.toLowerCase() === 'putter')) {
    S.clubOptions.push('P'); S.clubFullNames['P'] = 'Putter'; S.distByAbbr['P'] = 0;
  }
  // Pre-sorted usable clubs for suggestClubs (putter excluded, positive distance only)
  S.sortedClubs = byDist
    .filter(c => c.name.toLowerCase() !== 'putter' && (c.distance||0) > 0)
    .sort((a,b) => {
      if (b.distance !== a.distance) return (b.distance||0) - (a.distance||0);
      return (usage[b.name]||0) - (usage[a.name]||0);
    });
  S.sortedClubsNoDriver = S.sortedClubs.filter(c => !c.name.toLowerCase().includes('driver'));
  // Build wedge matrix: partial swing distances for clubs that have them
  S.wedgeMatrix = S.clubs
    .filter(c => c.partials && Object.keys(c.partials).length > 0)
    .flatMap(c => Object.entries(c.partials).map(([swing, dist]) => ({name: c.name, swing, dist})))
    .sort((a, b) => b.dist - a.dist);
}

function abbrClub(name){
  const n=name.toLowerCase();
  if(n.includes('driver'))return'D';if(n.includes('putter'))return'P';
  if(n.includes('hybrid')){for(const x of name.split(' '))if(/^\d+$/.test(x))return x+'H';return'H';}
  if(n.includes('wood')){for(const x of name.split(' '))if(/^\d+$/.test(x))return x+'W';return'W';}
  if(n.includes('iron')){for(const x of name.split(' '))if(/^\d+$/.test(x))return x+'i';return'i';}
  if(n==='pw')return'PW';if(n==='gw')return'GW';if(n==='sw')return'SW';if(n==='lw')return'LW';
  return name.substring(0,3).toUpperCase();
}

async function beginEntry(){
  if(!S.logCourse){showAlert('Select a Course','Pick a course before starting.');return;}
  if(!S.logTee){showAlert('Select a Tee Box','Pick a tee box before starting.');return;}
  S.logDate=document.getElementById('ls-date').value;
  const pars=S.logCourse.pars;
  if(S.logHoles==='front_9') S.holesToScore=[...Array(9).keys()];
  else if(S.logHoles==='back_9') S.holesToScore=[...Array(Math.min(9,pars.length-9)).keys()].map(i=>i+9);
  else S.holesToScore=[...Array(pars.length).keys()];
  S.currentHoleIdx=0;
  S.holeScores=new Array(S.holesToScore.length).fill(null);
  S.holeClubs=Array.from({length:S.holesToScore.length},()=>[]);
  // Initialize sim putts array (null = not yet rolled for this hole)
  S.holeSimPutts=(S.logIsSim&&S.logMode==='detailed')?new Array(S.holesToScore.length).fill(null):null;
  // Fetch club usage for hole suggestions (Feature 1), then build lookups with usage as tiebreaker
  try{
    const analytics=await GET('/api/stats/club-analytics');
    S.clubUsage={};
    for(const c of (analytics.ranked_clubs||[])) S.clubUsage[c.name]=c.count;
  }catch(e){ S.clubUsage={}; }
  buildClubLookups(S.clubUsage);
  saveDraft();
  show('log-entry');
}

/* ================================================================
   CLUB SUGGESTION (Feature 1)
   Greedy: pick longest club ≤ remaining, subtract, repeat.
   Uses clubUsage as tiebreaker for equal-distance clubs.
   ================================================================ */
// sortedClubs must be pre-sorted by (distance desc, usage desc) with putter and zero-distance clubs removed.
// Use S.sortedClubs (full) or S.sortedClubsNoDriver — both built by buildClubLookups().
function suggestClubs(yardage, sortedClubs){
  if(!yardage||!sortedClubs||!sortedClubs.length) return '';
  let remaining=yardage;
  const result=[];
  while(remaining>0){
    const club=sortedClubs.find(c=>{
      if((c.distance||0)>remaining) return false;
      if(c.name.toLowerCase()==='driver'&&result.length>0) return false; // driver: first shot only
      return true;
    });
    if(!club) break;
    result.push(abbrClub(club.name));
    remaining-=club.distance;
  }
  // Partial wedge fallback: no full club fits remaining yardage — suggest a partial swing
  if(remaining>0 && S.wedgeMatrix && S.wedgeMatrix.length){
    const partial=S.wedgeMatrix.find(p=>p.dist<=remaining);
    if(partial){
      const swingLabel={'3/4':'¾','1/2':'½','1/4':'¼'}[partial.swing]||partial.swing;
      result.push(`${abbrClub(partial.name)} ${swingLabel}`);
    }
  }
  return result.join(' ▶ ');
}

/* ================================================================
   LOG ROUND ENTRY — numpad: bottom row = Forfeit/0/Next
   Club grid: 3 cols, last row = Forfeit/Undo/Next
   ================================================================ */
function renderLogEntry(){
  const v=document.getElementById('v-log-entry');
  const hi=S.currentHoleIdx;
  const holeNum=S.holesToScore[hi];
  const par=S.logCourse.pars[holeNum];
  const yardages=S.logCourse.yardages?.[S.logTee]||[];
  const yard=yardages[holeNum]||'-';
  const isD=S.logMode==='detailed';
  const lastH=hi===S.holesToScore.length-1;
  const nextLabel=lastH?'✓ Done':'Next ▶';

  // Feature 3: Roll sim putts on first load of this hole
  if(isD&&S.logIsSim&&S.holeSimPutts&&S.holeSimPutts[hi]===null){
    const r=Math.random();
    S.holeSimPutts[hi]=r<0.022?1:r<0.600?2:3;
  }

  let score,clubsStr='';
  if(isD){
    const isForfeited=S.holeClubs[hi].length===1&&S.holeClubs[hi][0]==='X';
    if(isForfeited){
      score=par+2; clubsStr='Forfeited';
    } else {
      const committed=S.holeClubs[hi];
      const pendingClub=_kpPending?_kpPending.clubs[_kpPending.idx].abbr:null;
      const displayParts=[...committed.map(c=>c), ...(pendingClub?[`[${pendingClub}]`]:[])];
      score=(committed.length+(pendingClub?1:0))||null;
      clubsStr=displayParts.length?displayParts.join(' ▶ '):'Tap clubs in order';
    }
  }
  else{score=S.holeScores[hi];}
  const hasScore = score!=null&&score>0;
  const scoreStr = hasScore ? String(score) : '–';
  let diffStr='';
  if(hasScore){const d=score-par;diffStr=d>0?`+${d}`:d<0?String(d):'E';}

  // Feature 1: Compute club suggestion (detailed mode only)
  // If clubs already played, subtract their carry from hole yardage and re-suggest for the remainder.
  let suggestStr='';
  if(isD){
    const yardNum=yardages[holeNum]||0;
    if(yardNum&&S.clubs&&S.clubs.length){
      const played=S.holeClubs[hi].filter(c=>c!=='X'&&c!=='P');
      if(played.length===0){
        const s=suggestClubs(yardNum,S.sortedClubs||[]);
        if(s) suggestStr=`Suggested: ${s}`;
      } else {
        const playedDist=played.reduce((sum,c)=>sum+(S.distByAbbr[c]||0),0);
        const remaining=yardNum-playedDist;
        if(remaining>0){
          const s=suggestClubs(remaining,S.sortedClubsNoDriver||[]);
          if(s) suggestStr=`~${remaining} yds ▶ ${s}`;
        }
      }
    }
  }

  // Build bottom pad
  let bottomHtml='';
  if(isD){
    // Nokia fixed 3×4 keypad (rows 0-2: club cells, row 3: action row)
    bottomHtml = buildKeypadHtml(lastH);
  } else {
    // Quick mode numpad: 1-9, then Forfeit / 0 / Next
    let btns='';
    for(let n=1;n<=9;n++) btns+=`<button class="numpad-btn" onclick="inputScore(${n})">${n}</button>`;
    btns+=`<button class="numpad-btn forfeit" onclick="forfeitHole()">Forfeit</button>`;
    btns+=`<button class="numpad-btn" onclick="inputScore(0)">0</button>`;
    btns+=`<button class="numpad-btn next-hole" onclick="${lastH?'checkFinish()':'nextH()'}">${nextLabel}</button>`;
    bottomHtml=`<div class="numpad"><div class="numpad-grid">${btns}</div></div>`;
  }

  v.innerHTML=`
    <div class="entry-topbar">
      <div class="entry-hole-num">
        <div class="entry-hole-label">Hole</div>
        <div class="entry-hole-digit">${holeNum+1}</div>
      </div>
      <div class="entry-course-info">
        <div class="entry-course-name">${esc(S.logCourse.name)}</div>
        <div class="entry-hole-info">Par ${par} · ${yard} yds</div>
        <div class="entry-tee-info">${S.logTee} Tees</div>
      </div>
    </div>
    <div class="entry-middle">
      <button class="entry-nav-btn" onclick="prevH()">◀</button>
      <div class="entry-center">
        <div class="entry-stroke${hasScore?'':' entry-stroke-empty'}">${scoreStr}</div>
        ${!hasScore&&!isD?`<div class="entry-no-score-hint">Tap a number to enter score</div>`:''}
        ${isD?`<div class="entry-clubs-display">${esc(clubsStr)}</div>`:''}
        <div class="entry-diff">${diffStr}</div>
        ${suggestStr?`<div class="entry-suggest">${esc(suggestStr)}</div>`:''}
        ${isD&&S.logIsSim&&S.holeSimPutts&&S.holeSimPutts[hi]!==null?`<div class="entry-sim-putts">Sim putts: ${S.holeSimPutts[hi]}${S.holeClubs[hi].filter(c=>c==='P').length>0?' (overridden)':''}</div>`:''}
      </div>
      <button class="entry-nav-btn" onclick="nextH()" ${hi>=S.holesToScore.length-1?'disabled':''}>▶</button>
    </div>
    ${bottomHtml}
  `;
}

function inputScore(n){let c=S.holeScores[S.currentHoleIdx];if(c===null){if(n===0)return;c=n;}else{c=c*10+n;if(c>20)c=n;}if(c===0)return;S.holeScores[S.currentHoleIdx]=c;saveDraft();renderLogEntry();const el=document.querySelector('.entry-stroke');if(el){el.classList.remove('entry-stroke-pop');void el.offsetWidth;el.classList.add('entry-stroke-pop');}}

/* ================================================================
   NOKIA MULTI-TAP KEYPAD
   ================================================================ */

// Pending tap state: {cellKey, idx, clubs:[{name,abbr}], timerId}
let _kpPending = null;

// Build the 9-cell fixed layout from S.clubs.
// Returns array of 9 cell objects in grid order (row-major, rows 0-2).
// Row 0: Driver | Woods+Hybrids | empty
// Row 1: Long(2i-4i) | Mid(5i-7i) | Short(8i-9i)
// Row 2: Wedge group 1 | Wedge group 2 | Putter
function buildKeypadCells() {
  const CELLS = [
    { key:'driver',  clubs:[] },  // [0][0] Driver
    { key:'woods',   clubs:[] },  // [0][1] Woods (or Woods group 1)
    { key:'hybrids', clubs:[] },  // [0][2] Hybrids (or Woods group 2 if no hybrids)
    { key:'long',    clubs:[] },  // [1][0] 2i-4i
    { key:'mid',     clubs:[] },  // [1][1] 5i-7i
    { key:'short',   clubs:[] },  // [1][2] 8i-9i
    { key:'wedge1',  clubs:[] },  // [2][0] Wedge group 1
    { key:'wedge2',  clubs:[] },  // [2][1] Wedge group 2
    { key:'putter',  clubs:[] },  // [2][2] Putter
  ];

  const allWedges = [];

  function cellIdx(c) {
    const n = c.name.toLowerCase();
    const ab = abbrClub(c.name);
    if (ab === 'D' || n.includes('driver')) return 0;
    if (ab === 'P' || n.includes('putter')) return 8;
    if (n.includes('wood')) return 1;
    if (n.includes('hybrid')) return 2;
    if (ab.match(/^\d+[iI]$/)) {
      const num = parseInt(ab);
      if (num <= 4) return 3;  // long: 2i-4i
      if (num <= 7) return 4;  // mid: 5i-7i
      return 5;                // short: 8i-9i
    }
    return -1; // wedges handled separately
  }

  for (const c of S.clubs) {
    const ab = abbrClub(c.name);
    const n  = c.name.toLowerCase();
    const idx = cellIdx(c);
    if (idx >= 0) {
      CELLS[idx].clubs.push({ name: c.name, abbr: ab });
    } else if (ab === 'PW' || ab === 'GW' || ab === 'AW' || ab === 'SW' || ab === 'LW' || n.includes('wedge')) {
      allWedges.push({ name: c.name, abbr: ab, dist: S.distByAbbr[ab] || 0 });
    }
  }

  // If no hybrids, split woods evenly across both top-row cells
  if (!CELLS[2].clubs.length && CELLS[1].clubs.length) {
    CELLS[1].clubs.sort((a, b) => (S.distByAbbr[b.abbr] || 0) - (S.distByAbbr[a.abbr] || 0));
    const woodHalf = Math.ceil(CELLS[1].clubs.length / 2);
    CELLS[2].clubs = CELLS[1].clubs.slice(woodHalf);
    CELLS[1].clubs = CELLS[1].clubs.slice(0, woodHalf);
  }

  // Sort wedges longest carry first, then split evenly between the two wedge cells
  allWedges.sort((a, b) => b.dist - a.dist);
  const half = Math.ceil(allWedges.length / 2);
  CELLS[6].clubs = allWedges.slice(0, half).map(w => ({ name: w.name, abbr: w.abbr }));
  CELLS[7].clubs = allWedges.slice(half).map(w => ({ name: w.name, abbr: w.abbr }));

  // Sort non-wedge cells longest-distance first, cap at 3
  for (const cell of CELLS) {
    if (cell.key === 'wedge1' || cell.key === 'wedge2') continue;
    cell.clubs.sort((a, b) => (S.distByAbbr[b.abbr] || 0) - (S.distByAbbr[a.abbr] || 0));
    cell.clubs = cell.clubs.slice(0, 3);
  }

  // Putter always present even if not in bag
  if (!CELLS[8].clubs.length) CELLS[8].clubs = [{ name: 'Putter', abbr: 'P' }];

  return CELLS;
}

// Build the full 12-cell keypad HTML (9 club cells + 3 action cells).
function buildKeypadHtml(lastH) {
  const cells = buildKeypadCells();
  const nextLabel = lastH ? '✓ Done' : 'Next ▶';
  let html = '<div class="club-grid-container"><div class="club-grid">';

  for (const cell of cells) {
    const isPending = _kpPending && _kpPending.cellKey === cell.key;
    const isPutter  = cell.key === 'putter';
    const isEmpty   = !cell.clubs.length;

    if (isEmpty) { html += `<button class="club-grid-btn empty-cell" aria-hidden="true"></button>`; continue; }

    const activeIdx = isPending ? _kpPending.idx : -1;
    const cls = ['club-grid-btn', isPutter ? 'is-putter' : '', isPending ? 'is-pending' : ''].filter(Boolean).join(' ');
    const ariaLabel = cell.clubs.map(c => c.name).join(', ');

    // Build flat side-by-side club labels with separator dots
    let clubsHtml = '<div class="kp-clubs">';
    cell.clubs.forEach((c, i) => {
      if (i > 0) clubsHtml += '<span class="kp-sep">·</span>';
      const isActive = isPending && i === activeIdx;
      clubsHtml += `<span class="kp-club${isActive ? ' kp-active' : ''}">${c.abbr}</span>`;
    });
    clubsHtml += '</div>';

    html += `<button class="${cls}" onclick="keypadPress('${cell.key}')" aria-label="${ariaLabel}">
      ${clubsHtml}
    </button>`;
  }

  // Action row
  html += `<button class="club-grid-btn action-forfeit" onclick="forfeitHole()" aria-label="Forfeit hole">Forfeit</button>`;
  html += `<button class="club-grid-btn action-undo" onclick="undoClub()" aria-label="Undo last club">◀ Undo</button>`;
  html += `<button class="club-grid-btn action-next" onclick="${lastH ? 'checkFinish()' : 'nextH()'}" aria-label="${lastH ? 'Finish round' : 'Next ▶'}">${nextLabel}</button>`;

  html += '</div></div>';
  return html;
}

// Handle a keypad cell press (Nokia multi-tap logic).
function keypadPress(cellKey) {
  const cells = buildKeypadCells();
  const cell  = cells.find(c => c.key === cellKey);
  if (!cell || !cell.clubs.length) return;

  // Single-club cells commit immediately — no multi-tap buffer needed
  if (cell.clubs.length === 1) {
    _flushPending();
    S.holeClubs[S.currentHoleIdx].push(cell.clubs[0].abbr);
    saveDraft();
    renderLogEntry();
    return;
  }

  if (_kpPending && _kpPending.cellKey === cellKey) {
    // Same cell — cycle to next club, restart timer
    clearTimeout(_kpPending.timerId);
    _kpPending.idx = (_kpPending.idx + 1) % cell.clubs.length;
    _kpPending.timerId = setTimeout(commitKeypad, 900);
  } else {
    // Different cell — commit any pending (write to state only, skip re-render),
    // then immediately start new pending and do a single re-render.
    if (_kpPending) {
      clearTimeout(_kpPending.timerId);
      const club = _kpPending.clubs[_kpPending.idx];
      _kpPending = null;
      S.holeClubs[S.currentHoleIdx].push(club.abbr);
      saveDraft();
    }
    _kpPending = {
      cellKey,
      idx: 0,
      clubs: cell.clubs,
      timerId: setTimeout(commitKeypad, 900),
    };
  }
  renderLogEntry(); // single re-render shows updated committed + new pending
}

// Called by timer — commit pending and re-render.
function commitKeypad() {
  if (!_kpPending) return;
  clearTimeout(_kpPending.timerId);
  const club = _kpPending.clubs[_kpPending.idx];
  _kpPending = null;
  S.holeClubs[S.currentHoleIdx].push(club.abbr);
  saveDraft();
  renderLogEntry();
}

// Internal: write pending to state without re-rendering (caller handles render).
function _flushPending() {
  if (!_kpPending) return;
  clearTimeout(_kpPending.timerId);
  const club = _kpPending.clubs[_kpPending.idx];
  _kpPending = null;
  S.holeClubs[S.currentHoleIdx].push(club.abbr);
  saveDraft();
}

// Cancel pending without committing (used by forfeit / navigation).
function _cancelPending() {
  if (!_kpPending) return;
  clearTimeout(_kpPending.timerId);
  _kpPending = null;
}

function forfeitHole(){
  _cancelPending();
  const holeNum=S.holesToScore[S.currentHoleIdx];
  const par=S.logCourse.pars[holeNum];
  const maxScore=par+2;
  showConfirm(
    'Forfeit Hole?',
    `Records a score of ${maxScore} (double bogey max).`,
    'Forfeit',
    () => {
      if(S.logMode==='detailed'){S.holeClubs[S.currentHoleIdx]=['X'];}
      else{S.holeScores[S.currentHoleIdx]=maxScore;}
      saveDraft();
      if(S.currentHoleIdx<S.holesToScore.length-1){S.currentHoleIdx++;saveDraft();renderLogEntry();}
    }
  );
}

function addClub(c){S.holeClubs[S.currentHoleIdx].push(c);saveDraft();renderLogEntry();}

function undoClub(){
  if (_kpPending) {
    // Cancel pending instead of popping committed list
    _cancelPending();
    renderLogEntry();
  } else {
    S.holeClubs[S.currentHoleIdx].pop();
    saveDraft();
    renderLogEntry();
  }
}

function prevH(){
  _flushPending();
  if(S.currentHoleIdx>0){S.currentHoleIdx--;saveDraft();renderLogEntry();}
  else nav('home');
}
function nextH(){
  _flushPending();
  if(S.currentHoleIdx<S.holesToScore.length-1){S.currentHoleIdx++;saveDraft();renderLogEntry();}
}
// Compute per-hole results from S state. Returns one entry per hole in S.holesToScore.
// detailed mode: {score, putts, stg, allClubs}  quick mode: {score, putts:null, stg:null, allClubs:null}
function computeHoleScores() {
  const isD = S.logMode === 'detailed';
  const course = S.logCourse;
  return S.holesToScore.map((holeNum, i) => {
    if (!isD) return {score: S.holeScores[i], putts: null, stg: null, allClubs: null};
    const clubs = [...S.holeClubs[i]];
    const isForfeited = clubs.length === 1 && clubs[0] === 'X';
    if (isForfeited) {
      const sc = course.pars[holeNum] + 2;
      return {score: sc, putts: null, stg: null, allClubs: null};
    }
    const tappedPutts = clubs.filter(c => c === 'P').length;
    if (S.logIsSim && S.holeSimPutts && S.holeSimPutts[i] != null && tappedPutts === 0) {
      const putts = S.holeSimPutts[i];
      const shotClubs = clubs.filter(c => c !== 'P');
      const sc = shotClubs.length + putts;
      return {score: sc, putts, stg: shotClubs.length, allClubs: [...shotClubs, ...Array(putts).fill('P')]};
    }
    const sc = clubs.length;
    return {score: sc, putts: tappedPutts, stg: sc - tappedPutts, allClubs: clubs};
  });
}

function checkFinish(){
  _flushPending(); // commit any in-progress Nokia selection
  const isD=S.logMode==='detailed';
  const inc=[];
  for(let i=0;i<S.holesToScore.length;i++){
    if(isD){if(!S.holeClubs[i].length)inc.push(S.holesToScore[i]+1);}
    else{if(S.holeScores[i]===null||S.holeScores[i]===0)inc.push(S.holesToScore[i]+1);}
  }
  if(inc.length){
    showAlert('Missing Scores',`Enter scores for holes: ${inc.slice(0,5).join(', ')}${inc.length>5?' (+'+( inc.length-5)+' more)':''}`);
    return;
  }
  saveDraft();
  show('log-notes');
}

/* ================================================================
   LOG ROUND NOTES — shows scorecard + notes textarea
   ================================================================ */
function renderLogNotes(){
  const v=document.getElementById('v-log-notes');
  const isD=S.logMode==='detailed';
  const course=S.logCourse;
  const teeColor=S.logTee||'White';
  const teeCSS_=teeColorCSS(teeColor);
  const headerBg=teeColor==='White'?'#F8F8F8':teeCSS_;
  const headerFg=teeTextColor(headerBg);

  const scores=computeHoleScores().map(h=>h.score??0);
  const total=scores.reduce((a,b)=>a+b,0);
  const parTotal=S.holesToScore.reduce((a,hi)=>a+course.pars[hi],0);
  const diff=total-parTotal;
  const ds=diff>0?`+${diff}`:diff===0?'E':`${diff}`;
  const diffColor=diff>0?'rgba(255,59,48,0.9)':diff<0?'rgba(52,199,89,0.9)':'inherit';

  // Build scorecard grids (reuse the buildNine logic from renderScorecard)
  function buildMiniNine(label, startIdx, count) {
    const pars=[],sc=[],yds=[];
    const yardages=course.yardages?.[teeColor]||[];
    for(let i=startIdx;i<startIdx+count&&i<course.pars.length;i++){
      pars.push(course.pars[i]);
      // Find this hole in our holesToScore
      const hi=S.holesToScore.indexOf(i);
      sc.push(hi>=0?scores[hi]:null);
      yds.push(yardages[i]||null);
    }
    if(!sc.some(s=>s!=null)) return '';

    let holeRow='<div class="sc-cell sc-cell-header sc-cell-hole"></div>';
    for(let i=0;i<pars.length;i++) holeRow+=`<div class="sc-cell sc-cell-header sc-cell-hole">${startIdx+i+1}</div>`;
    holeRow+=`<div class="sc-cell sc-cell-header sc-cell-hole">TOT</div>`;

    let parRow='<div class="sc-cell sc-cell-header" style="font-weight:700;font-size:10px;color:var(--text2)">PAR</div>';
    let pt=0;
    for(const p of pars){pt+=p;parRow+=`<div class="sc-cell sc-cell-par">${p}</div>`;}
    parRow+=`<div class="sc-cell sc-cell-total">${pt}</div>`;

    let scoreRow='<div class="sc-cell sc-cell-header" style="font-weight:700;font-size:10px">SCORE</div>';
    let st=0;let has=false;
    for(let i=0;i<pars.length;i++){
      const s=sc[i];
      if(s!=null&&s>0){has=true;st+=s;
        scoreRow+=`<div class="sc-cell"><div class="sc-score ${scoreClass(s,pars[i])}">${s}</div></div>`;}
      else scoreRow+=`<div class="sc-cell" style="color:var(--text3)">—</div>`;
    }
    scoreRow+=`<div class="sc-cell sc-cell-total">${has?st:''}</div>`;
    if(!has) return '';

    return `<div class="sc-wrap"><div class="sc-grid sc-grid-9">${holeRow}${parRow}${scoreRow}</div></div>`;
  }

  let frontGrid='',backGrid='';
  if(S.logHoles==='front_9'){
    frontGrid=buildMiniNine('FRONT OUT',0,9);
  } else if(S.logHoles==='back_9'){
    backGrid=buildMiniNine('BACK IN',9,9);
  } else {
    frontGrid=buildMiniNine('FRONT OUT',0,9);
    backGrid=buildMiniNine('BACK IN',9,9);
  }

  const holesLabel=S.logHoles==='front_9'?'Front 9':S.logHoles==='back_9'?'Back 9':'18 Holes';
  let pills=`<span class="sc-pill">${holesLabel}</span>`;
  pills+=`<span class="sc-pill">${S.logType==='scramble'?'Scramble':'Solo'}</span>`;
  if(!S.logSerious) pills+=`<span class="sc-pill">Casual</span>`;
  if(S.logIsSim) pills+=`<span class="sc-pill">Sim</span>`;
  const teeDotBorder=teeCSS_==='#FFFFFF'?'1px solid rgba(0,0,0,0.2)':'none';
  const teePill=`<span class="sc-pill"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${teeCSS_};border:${teeDotBorder};vertical-align:middle;margin-right:4px"></span>${teeColor} Tees</span>`;

  v.innerHTML=`
    <div class="page-header">
      <div class="page-title">Review & Save</div>
    </div>

    <div class="sc-header-card" style="background:${headerBg};color:${headerFg};border:${teeColor==='White'?'1px solid var(--sep)':'none'}">
      <div class="sc-header-stripe" style="background:${teeCSS_}"></div>
      <div class="sc-header-main">
        <div class="sc-header-left">
          <div class="sc-header-course">${esc(course.name)}</div>
          <div class="sc-header-meta">${S.logDate}</div>
        </div>
        <div class="sc-header-right">
          <div class="sc-header-total">${total}</div>
          <div class="sc-header-diff" style="color:${diffColor}">${ds}</div>
        </div>
      </div>
      <div class="sc-header-footer" style="border-top-color:${headerFg==='#FFFFFF'?'rgba(255,255,255,0.15)':'rgba(0,0,0,0.1)'}">
        ${teePill}${pills}
      </div>
    </div>

    ${frontGrid}
    ${backGrid}

    <div class="sc-notes">
      <div class="sc-notes-title">Notes (optional)</div>
      <textarea class="form-input" id="ln-notes" placeholder="How was the round?" style="margin-top:6px"></textarea>
    </div>

    <div class="sc-actions">
      <button id="btn-submit-round" class="btn btn-green" style="flex:1;display:flex;align-items:center;justify-content:center;gap:6px" onclick="submitRound()"><img src="/static/save-96.png" class="icon-16"> Save Round</button>
    </div>
  `;
}
async function submitRound(){
  const btn=document.getElementById('btn-submit-round');
  if(btn){btn.disabled=true;btn.style.opacity='0.6';}
  const course=S.logCourse;
  const computed=computeHoleScores();
  const scores=computed.map(h=>h.score);
  const det=computed.map(h=>h.allClubs!=null
    ? {score:h.score,putts:h.putts,strokes_to_green:h.stg,clubs_used:h.allClubs.map(c=>S.clubFullNames[c]||c)}
    : {score:h.score});
  const total=scores.reduce((a,b)=>a+b,0);const parP=S.holesToScore.reduce((a,hi)=>a+course.pars[hi],0);
  const fullScores=new Array(course.pars.length).fill(null);const fullDet=new Array(course.pars.length).fill(null).map(()=>({}));
  for(let i=0;i<S.holesToScore.length;i++){fullScores[S.holesToScore[i]]=scores[i];fullDet[S.holesToScore[i]]=det[i];}
  const now=new Date();const dateStr=S.logDate+' '+String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0');
  const notes=(document.getElementById('ln-notes')||{}).value||'';
  const res=await POST('/api/rounds',{course_name:course.name,tee_color:S.logTee,scores:fullScores,is_serious:S.logSerious,is_sim:S.logIsSim||false,round_type:S.logType,notes,holes_played:S.holesToScore.length,holes_choice:S.logHoles,total_score:total,date:dateStr,entry_mode:S.logMode,detailed_stats:fullDet});
  if(res&&res.ok===false){if(btn){btn.disabled=false;btn.style.opacity='1';}showAlert('Save Failed', res.error||'Unknown error');return;}
  clearDraft();
  clearStatsCache();
  const diff=total-parP;
  const ds=diff>0?`+${diff}`:diff===0?'E':`${diff}`;
  showAlert('Round Saved!', `${total} (${ds}) · ${course.name} · ${S.holesToScore.length} holes`);
  navHome();
}

/* ================================================================
   COURSES LIST
   ================================================================ */
async function renderCourses(){
  // Re-fetch only when courses haven't been loaded yet; saveCourse() updates S.courses after mutations
  if(!S.courses.length) S.courses=await GET('/api/courses');
  const v=document.getElementById('v-courses');
  const sorted=[...S.courses].sort((a,b)=>(a.club||'').localeCompare(b.club||'')||a.name.localeCompare(b.name));
  let rows='';
  if(!sorted.length){
    rows=`<div class="empty"><div class="empty-icon"><img src="${ico('golf-course')}" style="width:80px;height:80px;object-fit:contain;display:block;margin:0 auto"></div><div class="empty-headline">No Courses Yet</div><div class="empty-text">Add a course to start logging rounds.</div><div class="empty-cta"><button class="btn btn-primary" style="max-width:220px;margin:0 auto" onclick="editCourse(null)">Add a Course</button></div></div>`;
  } else {
    // Group by club
    const clubs={};
    for(const c of sorted){const k=c.club||'Other';if(!clubs[k])clubs[k]=[];clubs[k].push(c);}
    for(const [clubName,courses] of Object.entries(clubs)){
      rows+=`<div class="club-section-label"><span class="club-section-label-title">${esc(clubName)}</span></div>`;
      rows+='<div class="club-items-card">';
      for(let i=0;i<courses.length;i++){
        const c=courses[i];
        const tp=c.pars.reduce((a,b)=>a+b,0);
        const teeColors=c.tee_boxes.map(t=>t.color);
        let dots='';for(const tc of teeColors) dots+=`<span class="tee-dot" style="width:10px;height:10px;display:inline-block;background:${teeColorCSS(tc)}"></span>`;
        const solo=courses.length===1;
        const br=solo?'12px':i===0?'12px 12px 0 0':i===courses.length-1?'0 0 12px 12px':'0';
        rows+=`<div class="course-row" style="display:flex;align-items:center;padding:14px 16px;cursor:pointer;background:var(--card);border-radius:${br};overflow:hidden;${i<courses.length-1?'border-bottom:0.5px solid var(--sep);':''}" onclick="viewCourse('${esc(c.name)}')">
          <div style="flex:1;min-width:0">
            <div style="font-size:16px;font-weight:500">${esc(c.name)}</div>
            <div style="font-size:12px;color:var(--text2);margin-top:2px;display:flex;align-items:center;gap:6px">
              ${c.pars.length} holes · Par ${tp} <span style="display:flex;gap:3px">${dots}</span>
            </div>
          </div>
          <div style="color:var(--text2);font-size:14px">›</div>
        </div>`;
      }
      rows+='</div>';
    }
  }

  v.innerHTML=`
    <div class="page-header" style="text-align:right"><div class="page-title">Courses</div></div>
    <div class="hint">Tap a course to view details</div>
    ${rows}
  `;
}

const _parseColorCache={};
function parseColor(css){
  if(_parseColorCache[css]) return _parseColorCache[css];
  let result;
  if(css.startsWith('#')){
    const h=css.slice(1);
    result=[parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)];
  } else {
    // Named color: resolve through a temporary DOM element (cached so this only runs once per color)
    const el=document.createElement('div');
    el.style.color=css;
    document.body.appendChild(el);
    const v=getComputedStyle(el).color.match(/\d+/g);
    document.body.removeChild(el);
    result=v?[+v[0],+v[1],+v[2]]:[142,142,147];
  }
  _parseColorCache[css]=result;
  return result;
}

function wcagLuminance(r,g,b){
  const lin=x=>{x/=255;return x<=0.04045?x/12.92:Math.pow((x+0.055)/1.055,2.4);};
  return 0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b);
}

// Returns '#FFFFFF' or '#1C1C1E' — whichever passes WCAG AA contrast on cssColor.
function teeTextColor(cssColor){
  // Design overrides: colors where convention beats pure luminance math.
  // Red (#FF3B30) computes to dark text at 5.5:1, but white on red is the
  // universal golf convention and looks far better in practice.
  const overrides={'#FF3B30':'#FFFFFF','#34C759':'#FFFFFF'};
  if(overrides[cssColor]) return overrides[cssColor];
  const[r,g,b]=parseColor(cssColor);
  const L=wcagLuminance(r,g,b);
  // Crossover point where white and dark text have equal contrast is L≈0.179
  return L<0.179?'#FFFFFF':'#1C1C1E';
}

function teeColorCSS(name){
  // Golf-specific overrides: names that exist in CSS but map to the wrong shade,
  // or names that need a specific brand/platform color.
  const m={
    'Black':'#1C1C1E',   // true near-black, not CSS black
    'Blue':'#007AFF',    // iOS blue, CSS blue (#0000FF) is too saturated
    'White':'#FFFFFF',
    'Yellow':'#FFD60A',  // warm gold-yellow, CSS yellow is too harsh
    'Red':'#FF3B30',     // iOS red
    'Gold':'#FFB800',    // warm amber gold, CSS gold (#FFD700) is too yellow
    'Green':'#34C759',   // bright fairway green, CSS green (#008000) is too dark
    'Silver':'#C7C7CC',  // iOS system gray, CSS silver (#C0C0C0) is close but mismatched
  };
  if(m[name]) return m[name];
  // For any other name (Purple, Pink, Brown, Maroon, Orange, Teal, etc.)
  // try it as a CSS named color directly — covers ~140 colors automatically.
  if(CSS.supports('color', name.toLowerCase())) return name.toLowerCase();
  return '#8E8E93'; // fallback gray
}

function viewCourse(name){
  S.viewCourseName=name;
  S.viewCourseTee=null;
  show('course-detail');
}

function editCourse(name){
  S.editCourse=name?S.courses.find(c=>c.name===name):null;
  show('course-editor');
}

/* ================================================================
   COURSE DETAIL — pretty read view with tee selector + hole grid
   ================================================================ */
async function renderCourseDetail(){
  const v=document.getElementById('v-course-detail');
  const c=S.courses.find(x=>x.name===S.viewCourseName);
  if(!c){nav('courses');return;}

  const totalPar=c.pars.reduce((a,b)=>a+b,0);
  const tees=c.tee_boxes||[];
  // Default tee selection
  if(!S.viewCourseTee){
    const pref=tees.find(t=>t.color==='White')||tees[0];
    S.viewCourseTee=pref?pref.color:null;
  }
  const activeTee=tees.find(t=>t.color===S.viewCourseTee)||tees[0];
  const yardages=c.yardages?.[S.viewCourseTee]||[];
  const totalYards=yardages.reduce((a,b)=>a+(b||0),0);

  // Tee pills
  let teePills='';
  for(const t of tees){
    const active=t.color===S.viewCourseTee?' active':'';
    teePills+=`<div class="tee-pill${active}" onclick="S.viewCourseTee='${t.color}';renderCourseDetail()">
      <span class="tee-dot" style="background:${teeColorCSS(t.color)}"></span>
      <span>${t.color}</span>
    </div>`;
  }

  // Hole grid table
  let holeRows='';
  let f9par=0,b9par=0,f9yds=0,b9yds=0;
  for(let i=0;i<c.pars.length;i++){
    const par=c.pars[i];
    const yd=yardages[i]||'';
    const parClass=par===3?'par-3':par===5?'par-5':'par-4';
    holeRows+=`<tr>
      <td class="hole-num">${i+1}</td>
      <td class="${parClass}">${par}</td>
      <td>${yd||'—'}</td>
    </tr>`;
    if(i<9){f9par+=par;f9yds+=(yd||0);}
    else{b9par+=par;b9yds+=(yd||0);}

    // Insert front-9 subtotal
    if(i===8&&c.pars.length>9){
      holeRows+=`<tr class="nine-sep"><td>OUT</td><td>${f9par}</td><td>${f9yds||'—'}</td></tr>`;
    }
  }
  // Back-9 subtotal + total
  if(c.pars.length>9){
    holeRows+=`<tr class="nine-sep"><td>IN</td><td>${b9par}</td><td>${b9yds||'—'}</td></tr>`;
  }
  holeRows+=`<tr class="total-row"><td>TOT</td><td>${totalPar}</td><td>${totalYards||'—'}</td></tr>`;

  // Tee detail card
  let teeDetailHtml='';
  if(activeTee){
    teeDetailHtml=`<div class="tee-detail">
      <div class="tee-detail-header">
        <span class="tee-dot" style="background:${teeColorCSS(activeTee.color)};width:18px;height:18px"></span>
        <span class="tee-detail-color">${activeTee.color} Tees</span>
      </div>
      <div class="tee-detail-row">
        <div class="tee-detail-item"><div class="tee-detail-val">${activeTee.rating}</div><div class="tee-detail-lbl">Rating</div></div>
        <div class="tee-detail-item"><div class="tee-detail-val">${activeTee.slope}</div><div class="tee-detail-lbl">Slope</div></div>
        <div class="tee-detail-item"><div class="tee-detail-val">${totalYards||'—'}</div><div class="tee-detail-lbl">Yards</div></div>
        <div class="tee-detail-item"><div class="tee-detail-val">${activeTee.handicap!=null?activeTee.handicap:'—'}</div><div class="tee-detail-lbl">HCP</div></div>
      </div>
    </div>`;
  }

  v.innerHTML=`
    <div class="course-hero">
      <div class="course-hero-name">${esc(c.name)}</div>
      <div class="course-hero-club">${esc(c.club||'')}</div>
      <div class="course-hero-stats">
        <div class="course-hero-stat"><div class="course-hero-stat-val">${c.pars.length}</div><div class="course-hero-stat-lbl">Holes</div></div>
        <div class="course-hero-stat"><div class="course-hero-stat-val">${totalPar}</div><div class="course-hero-stat-lbl">Par</div></div>
        <div class="course-hero-stat"><div class="course-hero-stat-val">${totalYards||'—'}</div><div class="course-hero-stat-lbl">Yards</div></div>
      </div>
    </div>

    <div class="tee-pills">${teePills}</div>

    ${teeDetailHtml}

    <div class="hole-grid">
      <div style="border-radius:12px;overflow:hidden;background:var(--card)">
        <table>
          <tr><th>Hole</th><th>Par</th><th>Yards</th></tr>
          ${holeRows}
        </table>
      </div>
    </div>

    <div style="padding:12px 16px;display:flex;gap:8px">
      <button class="btn btn-primary" style="flex:1;display:flex;align-items:center;justify-content:center;gap:6px" onclick="editCourse('${esc(c.name)}')"><img src="/static/pencil-96.png" class="icon-16"> Edit Course</button>
      <button class="btn btn-red" style="flex:0;padding:10px 20px" onclick="deleteCourse('${esc(c.name)}')"><img src="/static/trash-96.png" style="width:18px;height:18px;object-fit:contain"></button>
    </div>
  `;
}

async function deleteCourse(name){
  showConfirm(`Delete "${name}"?`, 'This cannot be undone.', 'Delete', async () => {
    await DEL(`/api/courses/${encodeURIComponent(name)}`);
    S.courses = S.courses.filter(c => c.name !== name);
    nav('courses');
  });
}

/* ================================================================
   COURSE EDITOR — full editor with per-hole par + yardage per tee
   ================================================================ */

// Temp storage for yardages while editing — keyed by tee color
let ceYardages = {};
let ceActiveTee = '';
let cePars = [];

function renderCourseEditor(){
  const v=document.getElementById('v-course-editor');
  const c=S.editCourse;
  const title=c?'Edit Course':'Add New Course';
  const numHoles=c?c.pars.length:18;

  // Initialize pars and yardages storage from course data
  cePars = c ? [...c.pars] : new Array(numHoles).fill(4);
  ceYardages = {};
  const tees=c?c.tee_boxes:[{color:'White',rating:72.0,slope:113}];
  for(const t of tees){
    ceYardages[t.color] = c?.yardages?.[t.color] ? [...c.yardages[t.color]] : new Array(numHoles).fill(0);
  }
  ceActiveTee = tees[0]?.color || 'White';

  // Tee boxes editor
  let teesHtml='';
  tees.forEach((t,i)=>{
    teesHtml+=`<div class="tee-editor-card" data-tee-idx="${i}">
      <button class="tee-editor-remove" onclick="removeTeeEditor(this)" title="Remove" aria-label="Remove tee box">✕</button>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <div class="form-group" style="flex:1;min-width:70px">
          <div class="form-label">Color</div>
          <input class="form-input tee-color" value="${t.color}" onchange="onTeeColorRenamed(this)">
        </div>
        <div class="form-group" style="flex:1;min-width:70px">
          <div class="form-label">Rating</div>
          <input class="form-input tee-rating" value="${t.rating}" type="number" inputmode="decimal" step="0.1">
        </div>
        <div class="form-group" style="flex:1;min-width:70px">
          <div class="form-label">Slope</div>
          <input class="form-input tee-slope" value="${t.slope}" type="number" inputmode="numeric">
        </div>
      </div>
    </div>`;
  });

  v.innerHTML=`
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center">
      <button class="back-btn" onclick="show('courses')" style="margin-bottom:0">‹ Courses</button>
      <div class="page-title">${title}</div>
    </div>

    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
        <div class="section-head">Course Information</div>
        ${!c ? `<button class="btn btn-primary" style="width:auto;padding:6px 12px;font-size:12px;display:flex;align-items:center;gap:5px" onclick="openScanForEditor()"><img src="/static/camera-w-96.png" style="width:14px;height:14px;object-fit:contain"> Scan Card</button>` : ''}
      </div>
      <div class="form-group">
        <div class="form-label">Course Name</div>
        <input class="form-input" id="ce-name" value="${c?esc(c.name):''}">
      </div>
      <div class="form-group">
        <div class="form-label">Club / Facility</div>
        <input class="form-input" id="ce-club" value="${c?esc(c.club||''):''}">
      </div>
    </div>

    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;cursor:pointer;user-select:none" onclick="toggleParGrid()">
        <div class="section-head">Hole Pars</div>
        <span id="ce-par-chevron" style="font-size:12px;color:var(--text2);transition:transform .2s">▼</span>
      </div>
      <div id="ce-par-grid" style="margin-top:8px"></div>
    </div>

        <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <div class="section-head">Tee Boxes</div>
        <button class="btn btn-primary" style="width:auto;padding:6px 14px;font-size:12px" onclick="addTeeBox()">+ Add Tee</button>
      </div>
      <div id="ce-tees">${teesHtml}</div>
    </div>

    <div class="card">
      <div class="section-head" style="margin-bottom:4px">Yardages by Tee</div>
      <div style="font-size:11px;color:var(--text2);margin-bottom:8px">Select a tee color to edit its yardages</div>
      <div class="tee-pills" id="ce-tee-pills" style="padding:4px 0 12px;justify-content:flex-start"></div>
      <div id="ce-hole-grid"></div>
    </div>

    <div style="padding:12px 16px;display:flex;gap:8px">
      <button class="btn btn-primary" style="flex:2;display:flex;align-items:center;justify-content:center;gap:6px" onclick="saveCourse()"><img src="/static/save-96.png" class="icon-16"> Save Course</button>
      <button class="btn" style="flex:1;background:var(--bg)" onclick="${c?`viewCourse('${esc(c.name)}')`:'nav(\'courses\')'}">Cancel</button>
    </div>
  `;

  refreshCeParGrid();
  refreshCeTeePills();
  refreshCeHoleGrid();
}

function toggleParGrid(){
  const grid=document.getElementById('ce-par-grid');
  const chev=document.getElementById('ce-par-chevron');
  if(!grid) return;
  const collapsed=grid.style.display==='none';
  grid.style.display=collapsed?'':'none';
  if(chev) chev.style.transform=collapsed?'':'rotate(-90deg)';
}

/** Render the static par-per-hole grid (shown once, independent of active tee) */
function refreshCeParGrid(){
  const container=document.getElementById('ce-par-grid');
  if(!container) return;
  const numHoles=cePars.length;
  let html=`<div class="hole-input-row" style="border-bottom:1px solid var(--sep)">
    <div class="hole-input-num" style="font-size:10px">Hole</div>
    <div class="hole-input-label" style="flex:1">Par</div>
  </div>`;
  for(let i=0;i<numHoles;i++){
    const p=cePars[i]||4;
    html+=`<div class="hole-input-row">
      <div class="hole-input-num">${i+1}</div>
      <div class="par-stepper">
        <button type="button" class="par-step-btn" onclick="ceAdjustPar(${i},-1)" aria-label="Decrease par for hole ${i+1}"${p<=PAR_MIN?' disabled':''}>−</button>
        <div class="par-step-val" id="ce-par-val-${i}" aria-live="polite">${p}</div>
        <button type="button" class="par-step-btn" onclick="ceAdjustPar(${i},1)" aria-label="Increase par for hole ${i+1}"${p>=PAR_MAX?' disabled':''}>+</button>
      </div>
      <input class="ce-par-input" type="hidden" value="${p}" data-hole="${i}">
    </div>`;
  }
  container.innerHTML=html;
}

const PAR_MIN=3, PAR_MAX=6;
/** Bump a hole's par by delta, clamped to [PAR_MIN, PAR_MAX], updating display + hidden input + state. */
function ceAdjustPar(i, delta){
  const cur=parseInt(cePars[i])||4;
  const next=Math.max(PAR_MIN, Math.min(PAR_MAX, cur+delta));
  if(next===cur) return;
  cePars[i]=next;
  const val=document.getElementById('ce-par-val-'+i);
  if(val) val.textContent=next;
  const row=val?val.closest('.hole-input-row'):null;
  if(row){
    const hidden=row.querySelector('.ce-par-input'); if(hidden) hidden.value=next;
    const [minus,plus]=row.querySelectorAll('.par-step-btn');
    if(minus) minus.disabled = next<=PAR_MIN;
    if(plus)  plus.disabled  = next>=PAR_MAX;
  }
  if(navigator.vibrate) navigator.vibrate(8);
}

/** Save current yardage inputs into ceYardages before switching tees */
function ceStashCurrentYards(){
  const inputs=document.querySelectorAll('.ce-yard-input');
  if(!inputs.length) return;
  const arr=[];
  inputs.forEach(inp=>{ arr.push(parseInt(inp.value)||0); });
  ceYardages[ceActiveTee]=arr;
}

/** Rebuild the tee pill selector based on current tee-editor cards */
function refreshCeTeePills(){
  const colors=getCurrentTeeColors();
  // Ensure ceYardages has an entry for every color
  const numHoles=cePars.length||18;
  for(const col of colors){
    if(!ceYardages[col]) ceYardages[col]=new Array(numHoles).fill(0);
  }
  // If active tee no longer exists, switch to first
  if(!colors.includes(ceActiveTee) && colors.length) ceActiveTee=colors[0];

  const container=document.getElementById('ce-tee-pills');
  if(!container) return;
  let html='';
  for(const col of colors){
    const active=col===ceActiveTee?' active':'';
    html+=`<div class="tee-pill${active}" onclick="ceSwitchTee('${esc(col)}')">
      <span class="tee-dot" style="background:${teeColorCSS(col)}"></span>
      <span>${col}</span>
    </div>`;
  }
  if(!colors.length) html='<div style="font-size:12px;color:var(--text2)">Add a tee box above first</div>';
  container.innerHTML=html;
}

function getCurrentTeeColors(){
  const cards=document.querySelectorAll('#ce-tees .tee-editor-card');
  const colors=[];
  cards.forEach(el=>{
    const c=el.querySelector('.tee-color').value.trim();
    if(c) colors.push(c);
  });
  return colors;
}

function ceSwitchTee(color){
  if(color===ceActiveTee) return;
  ceStashCurrentYards();
  ceActiveTee=color;
  refreshCeTeePills();
  refreshCeHoleGrid();
}

function refreshCeHoleGrid(){
  const container=document.getElementById('ce-hole-grid');
  if(!container) return;
  const numHoles=cePars.length;
  const yards=ceYardages[ceActiveTee]||[];

  let html=`<div class="hole-input-row" style="border-bottom:1px solid var(--sep)">
    <div class="hole-input-num" style="font-size:10px">Hole</div>
    <div class="hole-input-label" style="flex:1">${esc(ceActiveTee)} Yds</div>
  </div>`;

  for(let i=0;i<numHoles;i++){
    const yd=yards[i]||'';
    html+=`<div class="hole-input-row">
      <div class="hole-input-num">${i+1}</div>
      <input class="hole-input-field ce-yard-input" type="number" inputmode="numeric" value="${yd||''}" placeholder="—" data-hole="${i}" aria-label="Yardage for hole ${i+1}">
    </div>`;
  }
  container.innerHTML=html;
}

function removeTeeEditor(btn){
  const card=btn.closest('.tee-editor-card');
  const color=card.querySelector('.tee-color').value.trim();
  card.remove();
  // Remove yardages for this tee
  if(color) delete ceYardages[color];
  refreshCeTeePills();
  refreshCeHoleGrid();
}

function onTeeColorRenamed(input){
  // When a tee color is changed, refresh the pill selector
  refreshCeTeePills();
  refreshCeHoleGrid();
}

function addTeeBox(){
  const container=document.getElementById('ce-tees');
  const div=document.createElement('div');
  div.className='tee-editor-card';
  div.innerHTML=`<button class="tee-editor-remove" onclick="removeTeeEditor(this)" title="Remove" aria-label="Remove tee box">✕</button>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <div class="form-group" style="flex:1;min-width:70px"><div class="form-label">Color</div><input class="form-input tee-color" value="" onchange="onTeeColorRenamed(this)" placeholder="e.g. Blue"></div>
      <div class="form-group" style="flex:1;min-width:70px"><div class="form-label">Rating</div><input class="form-input tee-rating" value="" type="number" inputmode="decimal" step="0.1"></div>
      <div class="form-group" style="flex:1;min-width:70px"><div class="form-label">Slope</div><input class="form-input tee-slope" value="" type="number" inputmode="numeric"></div>
    </div>`;
  container.appendChild(div);
  refreshCeTeePills();
}

async function saveCourse(){
  const name=document.getElementById('ce-name').value.trim();
  const club=document.getElementById('ce-club').value.trim();
  if(!name){showAlert('Course Name Required','Enter a name for this course.');return;}

  // Stash current yardage inputs
  ceStashCurrentYards();

  // Collect pars
  const parInputs=document.querySelectorAll('.ce-par-input');
  const pars=[];
  parInputs.forEach(inp=>{ pars.push(parseInt(inp.value)||4); });
  if(pars.length<9){showAlert('Need More Holes','A course must have at least 9 holes.');return;}

  // Collect tee boxes
  const teeEls=document.querySelectorAll('#ce-tees .tee-editor-card');
  const teeBoxes=[];
  teeEls.forEach(el=>{
    const color=el.querySelector('.tee-color').value.trim();
    const rating=parseFloat(el.querySelector('.tee-rating').value);
    const slope=parseInt(el.querySelector('.tee-slope').value);
    if(color&&!isNaN(rating)&&!isNaN(slope)) teeBoxes.push({color,rating,slope});
  });
  if(!teeBoxes.length){showAlert('Add a Tee Box','Add at least one tee box with rating and slope.');return;}

  // Build yardages from ceYardages — only include tees that still exist
  const yardages={};
  for(const tb of teeBoxes){
    if(ceYardages[tb.color]) yardages[tb.color]=ceYardages[tb.color];
  }

  const data={name,club,pars,tee_boxes:teeBoxes,yardages};

  if(S.editCourse) await PUT(`/api/courses/${encodeURIComponent(S.editCourse.name)}`,data);
  else await POST('/api/courses',data);

  S.courses=await GET('/api/courses');
  S.viewCourseName=name;
  show('course-detail');
}

/* ================================================================
   STATISTICS — redesigned
   ================================================================ */
let statsTab='overview';

// Shared stats data cached for the lifetime of one "visit" to the stats view.
// Cleared after any mutation that changes stats (round add/delete).
let _statsCache=null;
function clearStatsCache(){_statsCache=null;}

function buildPracticeStats(sessions) {
  if (!sessions || !sessions.length) {
    return `<div class="stat-card" style="text-align:center;padding:28px 20px">
      <img src="/static/golf-ball-96.png" style="width:48px;height:48px;object-fit:contain;opacity:0.35;margin-bottom:10px">
      <div style="font-size:15px;font-weight:600;color:var(--text2)">No Practice Sessions Yet</div>
      <div style="font-size:13px;color:var(--text2);margin-top:6px">Start a session from the home screen.</div>
    </div>`;
  }

  // ── HEATMAP ──────────────────────────────────────────────────────────────
  const sessionByDate = {};
  for (const s of sessions) {
    const date = (s.date || '').substring(0, 10);
    if (!date) continue;
    const drills = s.drills || [];
    const total = drills.length;
    const done = drills.filter(d => d.completed).length;
    sessionByDate[date] = total ? done / total : 0;
  }

  const WEEKS = 18;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  // Align start to Monday
  const todayDow = (today.getDay() + 6) % 7; // 0=Mon
  const startDay = new Date(today);
  startDay.setDate(today.getDate() - todayDow - (WEEKS - 1) * 7);

  let hmCells = '';
  const cur = new Date(startDay);
  for (let col = 0; col < WEEKS; col++) {
    for (let row = 0; row < 7; row++) {
      const dateStr = cur.toISOString().substring(0, 10);
      const isFuture = cur > today;
      const pct = sessionByDate[dateStr];
      let cls = 'hm-future';
      if (!isFuture) {
        if (pct === undefined)   cls = 'hm0';
        else if (pct < 0.5)     cls = 'hm1';
        else if (pct < 0.8)     cls = 'hm2';
        else                    cls = 'hm3';
      }
      const tip = !isFuture ? (pct !== undefined ? `${dateStr} · ${Math.round(pct*100)}% complete` : dateStr) : '';
      hmCells += `<div class="hm-cell ${cls}" title="${tip}"></div>`;
      cur.setDate(cur.getDate() + 1);
    }
  }

  const dowLabels = ['M','T','W','T','F','S','S'].map(l =>
    `<div class="hm-dow">${l}</div>`).join('');

  const _MNAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const dateRangeLabel = `${_MNAMES[today.getMonth()]} ${today.getFullYear()}`;

  // ── PER-DRILL PERFORMANCE ─────────────────────────────────────────────────
  const sortedSessions = [...sessions].sort((a, b) =>
    (a.date || '') < (b.date || '') ? -1 : 1);

  // Collect numeric results per drill name, across sessions.
  // Works regardless of whether resultType is stored (infers from result format).
  const PERF_CATS = new Set(['PUTTING', 'CHIPPING', 'WEDGE MATRIX', 'IRONS', 'WOODS', 'DRIVER']);
  const drillData = {}; // name → { cat, points[], isPct }
  for (const s of sortedSessions) {
    for (const d of (s.drills || [])) {
      if (!d.name || !d.completed) continue;
      if (!PERF_CATS.has(d.category)) continue;
      if (d.resultType === 'check' || d.resultType === 'distance') continue;

      const result = String(d.result || '').trim();
      if (!result) continue;

      let val = null, isPct = false;
      const fracM = result.match(/^(\d+)\/(\d+)$/);
      const pctM  = result.match(/^(\d+)%$/);
      if (fracM) {
        const h = parseInt(fracM[2]);
        if (h > 0) { val = Math.round(parseInt(fracM[1]) / h * 100); isPct = true; }
      } else if (pctM) {
        val = parseInt(pctM[1]); isPct = true;
      } else {
        const n = parseInt(result);
        if (!isNaN(n) && n >= 0) val = n;
      }
      if (val === null) continue;

      if (!drillData[d.name]) drillData[d.name] = { cat: d.category, points: [], isPct: false };
      drillData[d.name].points.push(val);
      if (isPct) drillData[d.name].isPct = true;
    }
  }

  // Build sparkline SVG (last 8 sessions for a drill)
  function sparkline(vals) {
    const recent = vals.slice(-8);
    if (!recent.length) return '';
    const BAR_W = 6, GAP = 2, H = 30;
    const max = Math.max(...recent, 1);
    const bars = recent.map((v, i) => {
      const h = Math.max(2, Math.round(v / max * H));
      return `<rect x="${i*(BAR_W+GAP)}" y="${H-h}" width="${BAR_W}" height="${h}" rx="1" fill="var(--accent)"/>`;
    }).join('');
    return `<svg width="${recent.length*(BAR_W+GAP)-GAP}" height="${H}" style="flex-shrink:0">${bars}</svg>`;
  }

  // Group by category — DRIVER is legacy name for WOODS
  const CAT_ORDER = ['PUTTING', 'CHIPPING', 'WEDGE MATRIX', 'IRONS', 'WOODS', 'DRIVER'];
  const catDrills = {};
  for (const [name, data] of Object.entries(drillData)) {
    if (!data.points.length) continue;
    const key = data.cat === 'DRIVER' ? 'WOODS' : data.cat;
    if (!CAT_ORDER.includes(key)) continue;
    (catDrills[key] = catDrills[key] || []).push({ name, ...data });
  }

  const DISPLAY_ORDER = ['PUTTING', 'CHIPPING', 'WEDGE MATRIX', 'IRONS', 'WOODS'];
  let perfCards = '';
  for (const cat of DISPLAY_ORDER) {
    const drills = catDrills[cat];
    if (!drills) continue;

    let rows = '';
    for (const drill of drills) {
      const pts = drill.points;
      const latest = pts[pts.length - 1];
      const prev   = pts.length > 1 ? pts[pts.length - 2] : null;
      const latestStr = drill.isPct ? `${latest}%` : String(latest);
      let trendIcon = '', trendColor = 'var(--text2)';
      if (prev !== null) {
        if (latest > prev) { trendIcon = '↑'; trendColor = 'var(--green)'; }
        else if (latest < prev) { trendIcon = '↓'; trendColor = 'var(--red)'; }
        else { trendIcon = '→'; }
      }

      // Friendly short name: strip "25 Balls — " prefix for woods
      const displayName = drill.name.replace(/^25 Balls — /, '');

      rows += `<div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:0.5px solid var(--sep)">
        <div style="flex:1;min-width:0">
          <div style="font-size:13px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(displayName)}</div>
          <div style="font-size:11px;color:var(--text2);margin-top:1px">${pts.length} session${pts.length!==1?'s':''}</div>
        </div>
        ${sparkline(pts)}
        <div style="text-align:right;min-width:48px">
          <div style="font-size:16px;font-weight:700">${latestStr}</div>
          ${trendIcon ? `<div style="font-size:12px;font-weight:700;color:${trendColor}">${trendIcon}</div>` : ''}
        </div>
      </div>`;
    }

    const catLabel = cat === 'WEDGE MATRIX' ? 'PITCHING' : cat;
    perfCards += `<div class="stat-card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px">
        <div class="stat-card-title" style="margin-bottom:0">${esc(catLabel)}</div>
        <div class="muted-xs">Latest · Trend</div>
      </div>
      <div class="perf-drill-list">${rows}</div>
    </div>`;
  }

  return `
  <div class="stat-card">
    <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:10px">
      <div class="stat-card-title" style="margin-bottom:0">Practice Activity</div>
      <span style="font-size:11px;font-weight:500;color:var(--text2)">${dateRangeLabel}</span>
    </div>
    <div class="hm-wrap">
      <div class="hm-dow-col">${dowLabels}</div>
      <div class="practice-heatmap">${hmCells}</div>
    </div>
    <div class="hm-legend">
      <div class="hm-legend-cell hm0"></div><span>None</span>
      <div class="hm-legend-cell hm1"></div><span>&lt;50%</span>
      <div class="hm-legend-cell hm2"></div><span>50–79%</span>
      <div class="hm-legend-cell hm3"></div><span>80%+</span>
      <span style="margin-left:auto">${sessions.length} session${sessions.length!==1?'s':''}</span>
    </div>
  </div>
  ${perfCards}`;
}

function svgRing(pct, color, size=80, stroke=7) {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - Math.min(pct,100) / 100);
  return `<div class="stat-ring" style="width:${size}px;height:${size}px">
    <svg width="${size}" height="${size}"><circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="var(--sep)" stroke-width="${stroke}"/>
    <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="${color}" stroke-width="${stroke}" stroke-linecap="round" stroke-dasharray="${circ}" stroke-dashoffset="${offset}"/></svg>
    <div class="stat-ring-val" style="color:${color}">${pct!=null?pct+'%':'—'}</div></div>`;
}

async function renderStats(){
  const v=document.getElementById('v-stats');
  if(!_statsCache){
    v.innerHTML='<div class="page-header" style="text-align:right"><div class="page-title">Statistics</div></div><div class="skeleton-card" style="margin:8px 16px"><div class="skeleton skeleton-num" style="margin:20px auto;width:80px;height:80px"></div><div class="skeleton skeleton-line" style="margin:8px 20px"></div><div class="skeleton skeleton-line-sm" style="margin:4px 20px"></div></div>';
    const [stats,hc,adv,leaks,diffs,best,analytics]=await Promise.all([
      GET('/api/stats'),GET('/api/stats/handicap'),GET('/api/stats/advanced'),
      GET('/api/stats/stroke-leaks'),GET('/api/stats/differentials'),GET('/api/stats/best-round'),
      GET('/api/stats/club-analytics')
    ]);
    _statsCache={stats,hc,adv,leaks,diffs,best,analytics};
  }
  const {stats,hc,adv,leaks,diffs,best,analytics:cachedAnalytics}=_statsCache;
  const idx=hc.handicap_index;

  const tabs=[['overview','Overview'],['perf','Performance'],['clubs','Clubs'],['analysis','Analysis']];
  let tabHtml='<div class="stats-tabs">';
  for(const [k,lbl] of tabs) tabHtml+=`<button class="stats-tab${statsTab===k?' active':''}" onclick="statsTab='${k}';S.editingClub=null;renderStats()">${lbl}</button>`;
  tabHtml+='</div>';

  let body='';

  /* ---- OVERVIEW ---- */
  if(statsTab==='overview'){
    const hcColor = idx!=null ? (idx<15?'var(--green)':idx<25?'var(--accent)':'var(--orange)') : 'var(--text2)';

    // Best round
    let bestHtml='—';
    if(best && best.total_score){
      const bd = best.total_score-(best.par||72);
      bestHtml = `${best.total_score} <span style="font-size:16px;color:${bd>0?'var(--red)':'var(--green)'}">(${bd>0?'+':''}${bd})</span>`;
    }

    body=`
      <!-- Handicap hero -->
      <div class="stat-card">
        <div class="stat-hero">
          <div class="stat-hero-val" style="color:${hcColor}">${idx!=null?idx.toFixed(1):'—'}</div>
          <div class="stat-hero-label">${idx!=null?'Handicap Index':'Not yet established'}</div>
        </div>
      </div>

      <!-- Quick numbers -->
      <div class="stat-mini-grid">
        <div class="stat-mini">
          <div class="stat-mini-val">${stats.total_rounds}</div>
          <div class="stat-mini-label">Total Rounds</div>
        </div>
        <div class="stat-mini">
          <div class="stat-mini-val">${bestHtml}</div>
          <div class="stat-mini-label">Best Round</div>
        </div>
        <div class="stat-mini">
          <div class="stat-mini-val">${stats.avg_score_9||'—'}</div>
          <div class="stat-mini-label">Avg Score (9h)</div>
        </div>
        <div class="stat-mini">
          <div class="stat-mini-val">${stats.total_holes_played||0}</div>
          <div class="stat-mini-label">Holes Played</div>
        </div>
      </div>

      <!-- Differentials -->
      ${diffs&&diffs.length ? `<div class="stat-card">
        <div class="stat-card-title">Score Differentials</div>
        ${diffs.slice(0,8).map((d,i)=>{
          const c = i<3 ? 'var(--green)' : 'var(--text)';
          return `<div class="diff-row">
            <div class="diff-rank">${i+1}</div>
            <div class="diff-info">
              <div class="diff-course">${esc(d.course)}</div>
              <div class="diff-meta">${(d.date||'').substring(0,10)} · ${d.holes}h · Score ${d.score}</div>
            </div>
            <div class="diff-val" style="color:${c}">${d.diff.toFixed(1)}</div>
          </div>`;
        }).join('')}
      </div>` : ''}
    `;
  }

  /* ---- PERFORMANCE ---- */
  else if(statsTab==='perf'){
    // Always fetch training sessions for the practice section
    const trainingSessions = await GET('/api/training');

    if(!adv||!adv.total_holes_tracked){
      body=`<div class="stat-card" style="text-align:center;padding:40px 20px">
        <div style="font-size:40px;margin-bottom:12px"><div class="empty-icon"><img src="${ico('golf-clubs')}" style="width:90px;height:90px;object-fit:contain;margin:1px auto 0;display:block"></div></div>
        <div style="font-size:16px;font-weight:600">No Performance Data</div>
        <div style="font-size:13px;color:var(--text2);margin-top:8px;line-height:1.5">Use "Detailed" entry mode when<br>logging rounds to track these stats.</div>
      </div>
      ${buildPracticeStats(trainingSessions)}`;
    } else {
      const tracked = adv.total_holes_tracked;

      // GIR ring + breakdown
      const girPct = adv.gir_overall;
      const girColor = girPct!=null?(girPct>=30?'var(--green)':girPct>=20?'var(--orange)':'var(--red)'):'var(--text2)';

      // Putting
      const avgP = adv.avg_putts_overall;
      const puttColor = avgP!=null?(avgP<=2?'var(--green)':avgP<=2.5?'var(--accent)':'var(--red)'):'var(--text2)';

      // Scramble
      const scrPct = adv.scramble_rate;
      const scrColor = scrPct!=null?(scrPct>=30?'var(--green)':scrPct>=15?'var(--orange)':'var(--red)'):'var(--text2)';

      body=`
        <!-- GIR -->
        <div class="stat-card">
          <div class="stat-card-title">Greens in Regulation</div>
          <div style="display:flex;align-items:center;gap:20px">
            ${svgRing(girPct, girColor)}
            <div style="flex:1">
              <div class="muted-sm">Overall GIR</div>
              <div style="font-size:11px;color:var(--text2);margin-top:2px">Amateur target: 30–40%</div>
            </div>
          </div>
          <div class="stat-trio">
            <div class="stat-trio-col"><div class="stat-trio-val">${adv.gir_par3!=null?adv.gir_par3+'%':'—'}</div><div class="stat-trio-label">Par 3</div></div>
            <div class="stat-trio-col"><div class="stat-trio-val">${adv.gir_par4!=null?adv.gir_par4+'%':'—'}</div><div class="stat-trio-label">Par 4</div></div>
            <div class="stat-trio-col"><div class="stat-trio-val">${adv.gir_par5!=null?adv.gir_par5+'%':'—'}</div><div class="stat-trio-label">Par 5</div></div>
          </div>
        </div>

        <!-- Putting -->
        <div class="stat-card">
          <div class="stat-card-title">Putting</div>
          <div class="stat-hero">
            <div class="stat-hero-val" style="color:${puttColor};font-size:40px">${avgP!=null?avgP.toFixed(1):'—'}</div>
            <div class="stat-hero-label">Avg Putts per Hole <span style="color:var(--text2)">(Tour: ~1.8)</span></div>
          </div>
          <div class="stat-trio">
            <div class="stat-trio-col"><div class="stat-trio-val" style="color:var(--green)">${adv.one_putt_rate!=null?adv.one_putt_rate+'%':'—'}</div><div class="stat-trio-label">1-Putt</div></div>
            <div class="stat-trio-col"><div class="stat-trio-val">${adv.two_putt_rate!=null?adv.two_putt_rate+'%':'—'}</div><div class="stat-trio-label">2-Putt</div></div>
            <div class="stat-trio-col"><div class="stat-trio-val" style="color:${adv.three_putt_rate!=null&&adv.three_putt_rate>25?'var(--red)':'var(--text)'}">${adv.three_putt_rate!=null?adv.three_putt_rate+'%':'—'}</div><div class="stat-trio-label">3-Putt</div></div>
          </div>
        </div>

        <!-- Scramble + Strokes to Green -->
        <div class="stat-mini-grid">
          <div class="stat-mini">
            ${svgRing(scrPct, scrColor, 64, 6)}
            <div class="stat-mini-label" style="margin-top:6px">Scramble Rate</div>
          </div>
          <div class="stat-mini" style="text-align:center">
            <div class="stat-mini-val" style="font-size:20px">${adv.avg_strokes_to_green_par4!=null?adv.avg_strokes_to_green_par4.toFixed(1):'—'}</div>
            <div class="stat-mini-label">Avg STG (Par 4)</div>
            <div style="font-size:10px;color:var(--text2)">Target: 2.0</div>
          </div>
        </div>


        ${buildPracticeStats(trainingSessions)}
      `;
    }
  }

  /* ---- CLUBS ---- */
  else if(statsTab==='clubs'){
    const analytics=cachedAnalytics;
    const usageMap={};
    const totalShots=analytics.total_shots||0;
    for(const c of (analytics.ranked_clubs||[])) usageMap[c.name]=c;

    // Sort: by usage count when available, putter always last, else by distance
    const putterLast=(a,b)=>{
      const pa=a.name.toLowerCase()==='putter', pb=b.name.toLowerCase()==='putter';
      if(pa) return 1; if(pb) return -1; return 0;
    };
    let sorted=[...S.clubs];
    if(totalShots>0){
      sorted.sort((a,b)=>putterLast(a,b)||((usageMap[b.name]?.count||0)-(usageMap[a.name]?.count||0)));
    } else {
      sorted.sort((a,b)=>putterLast(a,b)||((b.distance||0)-(a.distance||0)));
    }

    const maxUsage=totalShots>0?Math.max(...sorted.map(c=>usageMap[c.name]?.count||0),1):0;
    const maxDist=sorted.length?Math.max(...sorted.map(c=>c.distance||0),1):300;

    let itemsHtml='';
    for(let i=0;i<sorted.length;i++){
      const c=sorted[i];
      const isExp=S.editingClub===c.name;
      const usage=usageMap[c.name];
      const barPct=totalShots>0&&maxUsage>0?Math.round((usage?.count||0)/maxUsage*100):Math.round((c.distance||0)/maxDist*100);
      const usageLbl=usage?`${usage.percentage}% of shots`:'';
      const posClass=sorted.length===1?'is-solo':i===0?'is-first':i===sorted.length-1?'is-last':'';
      itemsHtml+=`<div class="club-item${isExp?' expanded':''}${posClass?' '+posClass:''}">
        <div class="club-item-main" onclick="clubToggle('${esc(c.name)}')">
          <div class="club-item-name">${esc(c.name)}</div>
          <div class="club-item-bar-wrap"><div class="club-item-bar" style="width:${barPct}%"></div></div>
          <div class="club-item-right">
            <div class="club-item-dist">${c.distance} <span style="font-size:11px;font-weight:400;color:var(--text2)">yd</span></div>
            ${usageLbl?`<div class="club-item-usage">${usageLbl}</div>`:''}
          </div>
          <div class="club-item-chevron">›</div>
        </div>
        ${isExp?(()=>{
          const isWedge=!!c.partials||['PW','GW','SW','LW','AW'].includes(c.name)||c.name.toLowerCase().includes('wedge');
          const p=c.partials||{};
          return `<div class="club-item-edit">
          <div class="club-edit-row">
            <div class="club-edit-lbl">Full</div>
            <input class="form-input" id="club-edit-dist" type="number" value="${c.distance}" style="flex:1">
            <span class="muted-sm">yd</span>
          </div>
          ${isWedge?`
          <div class="club-edit-row">
            <div class="club-edit-lbl">¾ swing</div>
            <input class="form-input" id="club-edit-p34" type="number" value="${p['3/4']||''}" placeholder="yd" style="flex:1">
            <span class="muted-sm">yd</span>
          </div>
          <div class="club-edit-row">
            <div class="club-edit-lbl">½ swing</div>
            <input class="form-input" id="club-edit-p12" type="number" value="${p['1/2']||''}" placeholder="yd" style="flex:1">
            <span class="muted-sm">yd</span>
          </div>
          <div class="club-edit-row">
            <div class="club-edit-lbl">¼ swing</div>
            <input class="form-input" id="club-edit-p14" type="number" value="${p['1/4']||''}" placeholder="yd" style="flex:1">
            <span class="muted-sm">yd</span>
          </div>`:''}
          <div class="club-edit-actions">
            <button class="club-edit-save" onclick="clubSave('${esc(c.name)}')"><img src="/static/save-96.png" style="width:15px;height:15px;object-fit:contain"> Save</button>
            <button class="club-edit-delete" onclick="clubDelete('${esc(c.name)}')">Remove</button>
            <button class="club-edit-cancel" onclick="clubToggle(null)">Cancel</button>
          </div>
        </div>`;
        })():''}
      </div>`;
    }

    const CLUB_NAMES=['Driver','3 Wood','5 Wood','Hybrid','3 Iron','4 Iron','5 Iron','6 Iron','7 Iron','8 Iron','9 Iron','PW','GW','SW','LW','Putter'];
    const existing=new Set(sorted.map(c=>c.name));
    const available=CLUB_NAMES.filter(n=>!existing.has(n));
    const isAdding=S.editingClub==='__new__';

    const sortLbl=totalShots>0?'Sorted by usage':'Sorted by distance';
    const bagHtml=sorted.length?`
      <div class="club-section-label">
        <span class="club-section-label-title">My Bag</span>
        <span class="club-section-label-sub">${sortLbl}</span>
      </div>
      <div class="club-items-card">${itemsHtml}</div>`
      :`<div class="empty"><div class="empty-icon"><img src="/static/golf-clubs-96.png" style="width:72px;height:72px;display:block;margin:0 auto"></div><div class="empty-headline">Bag is Empty</div><div class="empty-text">Add your clubs to get distance suggestions while scoring.</div></div>`;

    const addSection=isAdding?`
      <div class="club-section-label"><span class="club-section-label-title">Add Club</span></div>
      <div class="club-items-card">
        <div class="club-item is-solo club-item-edit" style="border-top:none">
          <div class="club-edit-row">
            <div class="club-edit-lbl">Club</div>
            <select class="form-select" id="club-new-name" style="flex:1">
              ${available.length?available.map(n=>`<option>${n}</option>`).join(''):'<option disabled>All clubs added</option>'}
            </select>
          </div>
          <div class="club-edit-row">
            <div class="club-edit-lbl">Distance</div>
            <input class="form-input" id="club-new-dist" type="number" placeholder="Yards" style="flex:1">
            <span class="muted-sm">yd</span>
          </div>
          <div class="club-edit-actions">
            <button class="club-edit-save" onclick="clubAdd()"><img src="/static/save-96.png" style="width:15px;height:15px;object-fit:contain"> Add to Bag</button>
            <button class="club-edit-cancel" onclick="clubToggle(null)">Cancel</button>
          </div>
        </div>
      </div>`
      :(available.length?`<button class="club-add-btn" onclick="clubToggle('__new__')">+ Add Club</button>`:'');

    body=`${bagHtml}${addSection}`;
  }

  /* ---- ANALYSIS ---- */
  else if(statsTab==='analysis'){
    const trainingSessions = await GET('/api/training');

    // Map each leak area → practice category + specific drills
    // LEAK_DRILL_MAP is global (defined at top of script)

    // Build a "last practiced" index: category → days ago (null = never)
    const catLastPracticed = {};
    const today = new Date(); today.setHours(0,0,0,0);
    for (const ts of [...trainingSessions].sort((a,b)=>(b.date||'').localeCompare(a.date||''))) {
      const tsDate = new Date((ts.date||'').substring(0,10));
      const daysAgo = Math.round((today - tsDate) / 86400000);
      for (const d of (ts.drills||[])) {
        const cat = d.category;
        if (cat && !(cat in catLastPracticed)) catLastPracticed[cat] = daysAgo;
      }
    }

    function freshnessTag(cat) {
      if (!(cat in catLastPracticed)) return `<span class="drill-fresh never">Never practiced</span>`;
      const d = catLastPracticed[cat];
      if (d === 0) return `<span class="drill-fresh today">Practiced today</span>`;
      if (d <= 7)  return `<span class="drill-fresh recent">${d}d ago</span>`;
      if (d <= 21) return `<span class="drill-fresh stale">${d}d ago</span>`;
      return `<span class="drill-fresh old">${d}d ago — overdue</span>`;
    }

    if(!adv||!adv.total_holes_tracked){
      body=`<div class="stat-card" style="text-align:center;padding:40px 20px">
        <div style="font-size:40px;margin-bottom:12px"><img src="/static/golfer-96.png" style="width:40px;height:40px"></div>
        <div style="font-size:16px;font-weight:600">No Data Available</div>
        <div style="font-size:13px;color:var(--text2);margin-top:8px;line-height:1.5">Use "Detailed" entry mode when<br>logging rounds to track stats.</div>
      </div>`;
    }
    else if(!leaks||!leaks.length){
      body=`<div class="stat-card" style="text-align:center;padding:32px 20px">
        <div style="margin-bottom:8px"><img src="${ico('golfer')}" style="width:48px;height:48px;object-fit:contain"></div>
        <div style="font-size:20px;font-weight:700;color:var(--green)">Looking Good!</div>
        <div style="font-size:13px;color:var(--text2);margin-top:8px">No significant weaknesses detected.<br>Keep up the consistent play.</div>
      </div>
      <div class="stat-mini-grid">
        <div class="stat-mini">
          <div class="stat-mini-val">${adv.total_holes_tracked}</div>
          <div class="stat-mini-label">Holes Analyzed</div>
        </div>
        <div class="stat-mini">
          <div class="stat-mini-val">${adv.gir_overall!=null?adv.gir_overall+'%':'—'}</div>
          <div class="stat-mini-label">GIR</div>
        </div>
      </div>`;
    }
    else {
      // Collect unique focus areas for the Next Session card (high severity first)
      const focusCats = [];
      const seenCats = new Set();
      for (const l of [...leaks].sort((a,b)=>(a.severity==='high'?0:1)-(b.severity==='high'?0:1))) {
        const map = LEAK_DRILL_MAP[l.area];
        if (map && !seenCats.has(map.cat)) { seenCats.add(map.cat); focusCats.push({ cat: map.cat, drills: map.drills, sev: l.severity||'medium' }); }
      }

      let insightsHtml='';
      for(const l of leaks){
        const sev=l.severity||'medium';
        const sevLabel=sev==='high'?'High Priority':'Medium Priority';
        const sevColor=sev==='high'?'var(--red)':'var(--orange)';
        const map=LEAK_DRILL_MAP[l.area];
        const drillsHtml = map ? map.drills.map(name=>
          `<span class="drill-pill">${esc(name)}</span>`
        ).join('') : '';
        insightsHtml+=`<div class="insight-card">
          <div class="insight-body">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
              <div class="insight-sev" style="color:${sevColor};font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.4px">${sevLabel}</div>
              ${map ? freshnessTag(map.cat) : ''}
            </div>
            <div class="insight-text">${esc(l.message)}</div>
            ${drillsHtml ? `<div style="margin-top:8px">
              <div style="font-size:11px;font-weight:600;color:var(--text2);margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px">Focus Drills</div>
              <div style="display:flex;flex-wrap:wrap;gap:5px">${drillsHtml}</div>
            </div>` : ''}
          </div>
        </div>`;
      }

      // Next Session card — ranked focus cats
      let nextSessionRows = '';
      for (let i = 0; i < focusCats.length; i++) {
        const { cat, drills } = focusCats[i];
        const rank = i === 0 ? '1st' : i === 1 ? '2nd' : '3rd';
        nextSessionRows += `<div style="display:flex;align-items:flex-start;gap:10px;padding:10px 0;${i>0?'border-top:1px solid var(--sep)':''}">
          <div style="width:28px;height:28px;border-radius:50%;background:var(--accent);color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0">${rank}</div>
          <div style="flex:1">
            <div style="font-size:14px;font-weight:600">${cat}</div>
            <div style="font-size:12px;color:var(--text2);margin-top:2px">${drills.slice(0,2).map(d=>esc(d)).join(' · ')}</div>
          </div>
          ${freshnessTag(cat)}
        </div>`;
      }

      body=`
        <div style="padding:12px 16px 4px;font-size:12px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:0.5px">
          ${leaks.length} Area${leaks.length>1?'s':''} to Work On
        </div>
        ${insightsHtml}
        ${focusCats.length ? `<div class="stat-card" style="margin-top:4px">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2px">
            <div class="stat-card-title" style="margin-bottom:0">Next Session Priority</div>
            <button onclick="roundsFilter='practice';show('rounds')" style="background:none;border:none;color:var(--accent);font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;padding:0">History →</button>
          </div>
          ${nextSessionRows}
          <button class="btn btn-primary" style="width:100%;margin-top:12px" onclick="startTraining()">Start Practice Session</button>
        </div>` : ''}
      `;
    }
  }

  v.innerHTML=`
    <div class="page-header" style="text-align:right">
      <div class="page-title">Statistics</div>
    </div>
    ${tabHtml}
    ${body}
  `;
}

function clubToggle(name){
  S.editingClub=S.editingClub===name?null:name;
  renderStats();
}

// Auto-calculate partial swing distances based on full swing
function autoFillPartials(clubName, fullDist) {
  let p34Pct = 0.95, p12Pct = 0.75, p14Pct = 0.50;
  if (clubName.includes('Wedge') || clubName.includes('W') || clubName === 'PW' || clubName === 'GW' || clubName === 'SW' || clubName === 'LW') {
    p34Pct = 0.90; p12Pct = 0.70; p14Pct = 0.45;
  }
  return {
    '3/4': Math.round(fullDist * p34Pct),
    '1/2': Math.round(fullDist * p12Pct),
    '1/4': Math.round(fullDist * p14Pct)
  };
}

async function clubSave(origName){
  const dist=parseInt((document.getElementById('club-edit-dist')||{}).value);
  if(isNaN(dist)||dist<=0){showAlert('Invalid Distance','Enter a valid carry distance in yards.');return;}
  const p34=parseInt((document.getElementById('club-edit-p34')||{}).value);
  const p12=parseInt((document.getElementById('club-edit-p12')||{}).value);
  const p14=parseInt((document.getElementById('club-edit-p14')||{}).value);
  const autoPartials=autoFillPartials(origName, dist);
  const partials={};
  partials['3/4']=(!isNaN(p34)&&p34>0)?p34:autoPartials['3/4'];
  partials['1/2']=(!isNaN(p12)&&p12>0)?p12:autoPartials['1/2'];
  partials['1/4']=(!isNaN(p14)&&p14>0)?p14:autoPartials['1/4'];
  const payload={name:origName,distance:dist,notes:'',partials};
  await PUT(`/api/clubs/${encodeURIComponent(origName)}`,payload);
  S.editingClub=null;
  S.clubs=await GET('/api/clubs');
  renderStats();
}
async function clubDelete(name){
  showConfirm(`Remove ${name}?`, 'It will be removed from your bag.', 'Remove', async () => {
    await DEL(`/api/clubs/${encodeURIComponent(name)}`);
    S.editingClub=null;
    S.clubs=await GET('/api/clubs');
    renderStats();
  });
}
async function clubAdd(){
  const name=(document.getElementById('club-new-name')||{}).value;
  const dist=parseInt((document.getElementById('club-new-dist')||{}).value);
  if(!name||isNaN(dist)||dist<=0){showAlert('Missing Info','Enter a club and carry distance.');return;}
  const partials=autoFillPartials(name, dist);
  await POST('/api/clubs',{name,distance:dist,notes:'',partials});
  S.editingClub=null;
  S.clubs=await GET('/api/clubs');
  renderStats();
}


/* ================================================================
   SCAN SCORECARD FLOW
   ================================================================ */

// Scan state
let _scanOcr = null;         // raw OCR response from /api/courses/scan
let _scanStep = 'upload';    // upload | nine-q | multi-q | review
let _scanReview = null;      // course data object being reviewed/edited
let _scanNineChoice = null;  // 'front'|'back'|'full'
let _scanMultiChoice = null; // 'split'|'combine'
let _scanEditorMode = false; // true = fill course editor instead of showing review form

// tee color options matching teeColorCSS
const SCAN_TEE_COLORS = ['Black','Blue','White','Yellow','Red','Gold','Green','Silver'];

function openScan() {
  _scanEditorMode = false;
  _scanOcr = null;
  _scanStep = 'upload';
  _scanReview = null;
  show('scan');
  renderScan();
}

function openScanForEditor() {
  _scanEditorMode = true;
  _scanOcr = null;
  _scanStep = 'upload';
  _scanReview = null;
  show('scan');
  renderScan();
}

function renderScan() {
  const v = document.getElementById('v-scan');
  if (!v) return;
  const backBtn = _scanEditorMode ? `<button class="back-btn" onclick="show('course-editor')">◀ Add Course</button>` : '';
  v.innerHTML = `<div class="page-header">${backBtn}<div class="page-title">Scan Scorecard</div></div>` +
    _renderScanBody();
  _scanBindEvents();
}

function _renderScanBody() {
  if (_scanStep === 'upload')   return _renderScanUpload();
  if (_scanStep === 'loading')  return _renderScanLoading();
  if (_scanStep === 'nine-q')   return _renderScanNineQ();
  if (_scanStep === 'multi-q')  return _renderScanMultiQ();
  if (_scanStep === 'review')   return _renderScanReview();
  return '';
}

// ── Step 1: Upload ────────────────────────────────────────────────────────────

function _renderScanUpload() {
  const hasFile = !!(_scanOcr === null && document.getElementById('scan-file-hidden')?.files?.length);
  return `
    <div class="hint">Take a photo of the scorecard or upload an image file.</div>

    <div class="scan-upload-zone" id="scan-drop-zone" onclick="document.getElementById('scan-file-hidden').click()">
      <input type="file" id="scan-file-hidden" accept="image/*" style="display:none" onchange="scanFileSelected(this)">
      <div class="scan-upload-icon"><img src="${ico('camera')}" style="width:30px;height:30px;object-fit:contain;margin:1px auto 0;display:block"></div>
      <div class="scan-upload-label">Tap to take photo or choose file</div>
      <div class="scan-upload-sub">JPG, PNG, HEIC — lay card flat in good light</div>
    </div>

    <input type="file" id="scan-camera-input" accept="image/*" capture="environment" style="display:none" onchange="scanFileSelected(this)">

    <div style="padding:12px 16px;display:flex;gap:8px;margin-top:4px">
      <button class="btn btn-primary" style="flex:1;display:flex;align-items:center;justify-content:center;gap:6px" onclick="document.getElementById('scan-camera-input').click()"><img src="/static/camera-w-96.png" class="icon-16"> Take Photo</button>
      <button class="btn btn-primary" style="flex:1;display:flex;align-items:center;justify-content:center;gap:6px" onclick="document.getElementById('scan-file-hidden').click()"><img src="/static/folder-w-96.png" class="icon-16"> Choose File</button>
    </div>

    <div id="scan-preview-container" style="display:none">
      <div class="scan-preview"><img id="scan-preview-img" src="" alt="Preview"></div>
      <div style="padding:12px 16px;display:flex;gap:8px">
        <button class="btn btn-primary" style="flex:1" id="scan-submit-btn" onclick="scanSubmit()">Scan This Card</button>
        <button class="btn" style="flex:0;padding:10px 16px;background:var(--bg)" onclick="scanClearFile()">✕</button>
      </div>
    </div>
  `;
}

function _renderScanLoading() {
  return `
    <div class="scan-spinner">
      <div class="scan-spinner-ring"></div>
      <div style="font-size:14px;color:var(--text2)">Reading scorecard…</div>
      <div style="font-size:12px;color:var(--text3);margin-top:4px">This takes 5–15 seconds</div>
    </div>
  `;
}

// ── Step 3: 9-hole question ───────────────────────────────────────────────────

function _renderScanNineQ() {
  return `
    <div class="card" style="margin-top:8px">
      <div style="font-size:16px;font-weight:600;margin-bottom:6px">9-Hole Card Detected</div>
      <div style="font-size:14px;color:var(--text2)">Which 9 holes does this card cover?</div>
    </div>
    <div class="scan-nine-choice">
      <button class="scan-nine-btn" onclick="scanNineChoice('front')">🔵 Front 9 — Holes 1–9</button>
      <button class="scan-nine-btn" onclick="scanNineChoice('back')">🟢 Back 9 — Holes 10–18</button>
      <button class="scan-nine-btn" onclick="scanNineChoice('full')">⚪ It's actually a full 18-hole card</button>
    </div>
  `;
}

// ── Step 4: Multi-course question ─────────────────────────────────────────────

function _renderScanMultiQ() {
  return `
    <div class="card" style="margin-top:8px">
      <div style="font-size:16px;font-weight:600;margin-bottom:6px">Two Layouts Found</div>
      <div style="font-size:14px;color:var(--text2)">This card appears to show two 9-hole courses. How would you like to save them?</div>
    </div>
    <div class="scan-nine-choice">
      <button class="scan-nine-btn" onclick="scanMultiChoice('combine')"><img src="${ico('golf-course')}" style="width:20px;height:20px;object-fit:contain;vertical-align:middle;margin-right:6px"> One 18-hole course (front + back combined)</button>
      <button class="scan-nine-btn" onclick="scanMultiChoice('split-1')">🔵 Save first layout only</button>
      <button class="scan-nine-btn" onclick="scanMultiChoice('split-2')">🟢 Save second layout only</button>
    </div>
  `;
}

// ── Step 5: Review ────────────────────────────────────────────────────────────

function _renderScanReview() {
  if (!_scanReview) return '<div class="card">No data to review.</div>';
  const d = _scanReview;
  const warnings = _scanOcr?.warnings || [];
  const conf = _scanOcr?.confidence || {};
  const nHoles = (d.pars || []).length || 18;
  const holeNums = Array.from({length: nHoles}, (_, i) => i + 1);

  // Confidence badge
  const o = conf.overall || 0;
  const confClass = o >= 0.7 ? 'scan-conf-high' : o >= 0.4 ? 'scan-conf-med' : 'scan-conf-low';
  const confLabel = o >= 0.7 ? `${Math.round(o*100)}% confidence` : o >= 0.4 ? `${Math.round(o*100)}% — review carefully` : `${Math.round(o*100)}% — many fields need correction`;

  // Warnings banner
  let warnHtml = '';
  if (warnings.length) {
    const items = warnings.map(w => `<div class="scan-warning-item">• ${esc(w)}</div>`).join('');
    warnHtml = `<div class="scan-warning-banner">
      <div class="scan-warning-title">⚠ ${warnings.length} issue${warnings.length > 1 ? 's' : ''} detected</div>
      ${items}
    </div>`;
  }

  // Tee boxes editor
  const tees = d.tee_boxes || [];
  let teesHtml = '';
  tees.forEach((t, i) => {
    const colorOpts = SCAN_TEE_COLORS.map(c =>
      `<option value="${c}" ${(t.color || '') === c ? 'selected' : ''}>${c}</option>`
    ).join('');
    teesHtml += `<div class="scan-tee-card" data-tee-idx="${i}">
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px">
        <div class="form-group" style="flex:1;min-width:80px">
          <div class="form-label">Color</div>
          <select class="form-select scan-tee-color" style="min-height:44px">
            <option value="">— unknown —</option>${colorOpts}
          </select>
        </div>
        <div class="form-group" style="flex:1;min-width:80px">
          <div class="form-label">Label</div>
          <input class="form-input scan-tee-label" value="${esc(t.label || '')}" placeholder="e.g. Championship" style="min-height:44px">
        </div>
        <div class="form-group" style="flex:1;min-width:70px">
          <div class="form-label">Rating</div>
          <input class="form-input scan-tee-rating ${t.rating == null ? 'missing' : ''}" type="number" step="0.1" value="${t.rating != null ? t.rating : ''}" placeholder="—" style="min-height:44px">
        </div>
        <div class="form-group" style="flex:1;min-width:70px">
          <div class="form-label">Slope</div>
          <input class="form-input scan-tee-slope ${t.slope == null ? 'missing' : ''}" type="number" value="${t.slope != null ? t.slope : ''}" placeholder="—" style="min-height:44px">
        </div>
      </div>
    </div>`;
  });
  if (!tees.length) {
    teesHtml = `<div style="font-size:13px;color:var(--text2);padding:8px 0">No tee boxes detected — you can add them manually after saving, or add them in the course editor.</div>`;
  }

  // Hole data table: rows = tee yardages + pars + handicaps
  const pars = d.pars || new Array(nHoles).fill('');
  const hdcps = d.handicaps || new Array(nHoles).fill('');

  const hdrCells = holeNums.map(n => `<th>${n}</th>`).join('');
  let tableRows = '';

  // Par row
  const parCells = holeNums.map((n, i) => {
    const v = pars[i];
    const miss = (v == null || ![3,4,5].includes(v)) ? ' missing' : '';
    return `<td><input class="scan-hole-input scan-par-input${miss}" type="number" min="3" max="6" value="${v != null ? v : ''}" placeholder="—" data-hole="${i}"></td>`;
  }).join('');
  tableRows += `<tr><td>Par</td>${parCells}</tr>`;

  // Handicap row
  const hcpCells = holeNums.map((n, i) => {
    const v = hdcps[i];
    const miss = (v == null) ? ' missing' : '';
    return `<td><input class="scan-hole-input scan-hcp-input${miss}" type="number" min="1" max="18" value="${v != null ? v : ''}" placeholder="—" data-hole="${i}"></td>`;
  }).join('');
  tableRows += `<tr><td>HCP</td>${hcpCells}</tr>`;

  // Yardage rows per tee
  tees.forEach((t, ti) => {
    const yards = t.yardages || [];
    const teeCells = holeNums.map((n, i) => {
      const v = yards[i];
      const miss = (v == null) ? ' missing' : '';
      return `<td><input class="scan-hole-input scan-yard-input${miss}" type="number" value="${v != null ? v : ''}" placeholder="—" data-tee="${ti}" data-hole="${i}"></td>`;
    }).join('');
    const dot = t.color ? `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${teeColorCSS(t.color)};margin-right:4px"></span>` : '';
    tableRows += `<tr><td>${dot}${esc(t.label || t.color || `Tee ${ti+1}`)}</td>${teeCells}</tr>`;
  });

  return `
    <div class="card" style="margin-top:4px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <div class="section-head">Review Extracted Data</div>
        <span class="scan-conf-badge ${confClass}">${confLabel}</span>
      </div>
      <div class="form-group">
        <div class="form-label">Course Name</div>
        <input class="form-input ${!d.course_name ? 'missing' : ''}" id="scan-name" value="${esc(d.course_name || '')}" placeholder="Course name" style="min-height:44px">
      </div>
      <div class="form-group">
        <div class="form-label">Club / Facility</div>
        <input class="form-input" id="scan-club" value="${esc(d.club_name || '')}" placeholder="Club or facility name" style="min-height:44px">
      </div>
    </div>

    ${warnHtml}

    <div class="card">
      <div class="section-head" style="margin-bottom:8px">Tee Boxes</div>
      <div id="scan-tees-container">${teesHtml}</div>
    </div>

    <div class="card">
      <div class="section-head" style="margin-bottom:4px">Hole Data</div>
      <div style="font-size:11px;color:var(--text2);margin-bottom:8px">Orange = unread / needs review. Scroll right to see all holes.</div>
      <div class="scan-hole-scroll">
        <table class="scan-hole-table">
          <thead><tr><th>Row</th>${hdrCells}</tr></thead>
          <tbody id="scan-hole-tbody">${tableRows}</tbody>
        </table>
      </div>
    </div>

    <div style="padding:12px 16px;display:flex;gap:8px">
      <button class="btn btn-primary" style="flex:2;display:flex;align-items:center;justify-content:center;gap:6px" onclick="scanSave()"><img src="/static/save-96.png" class="icon-16"> Save Course</button>
      <button class="btn" style="flex:1;background:var(--bg)" onclick="nav('courses')">Cancel</button>
    </div>

    <div style="padding:0 16px 24px">
      <button class="btn" style="width:100%;background:var(--card);font-size:13px;display:flex;align-items:center;justify-content:center;gap:6px" onclick="scanAddAnotherPhoto()"><img src="${ico('camera')}" style="width:15px;height:15px;object-fit:contain"> Scan another photo (back of card / second 9)</button>
    </div>
  `;
}

// ── Events & binding ──────────────────────────────────────────────────────────

function _scanBindEvents() {
  const zone = document.getElementById('scan-drop-zone');
  if (!zone) return;
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const files = e.dataTransfer?.files;
    if (files?.length) _scanPreviewFile(files[0]);
  });
}

let _scanFile = null;

function scanFileSelected(input) {
  if (!input.files?.length) return;
  _scanPreviewFile(input.files[0]);
}

function _scanPreviewFile(file) {
  _scanFile = file;
  const reader = new FileReader();
  reader.onload = e => {
    const img = document.getElementById('scan-preview-img');
    const container = document.getElementById('scan-preview-container');
    if (img) img.src = e.target.result;
    if (container) container.style.display = '';
  };
  reader.readAsDataURL(file);
}

function scanClearFile() {
  _scanFile = null;
  const container = document.getElementById('scan-preview-container');
  if (container) container.style.display = 'none';
  const inputs = document.querySelectorAll('#scan-file-hidden, #scan-camera-input');
  inputs.forEach(i => i.value = '');
}

async function scanSubmit() {
  if (!_scanFile) { showAlert('No Image Selected','Tap "Take Photo" or "Choose File" first.'); return; }
  _scanStep = 'loading';
  renderScan();

  const fd = new FormData();
  fd.append('image', _scanFile);

  try {
    const res = await fetch('/api/courses/scan', { method: 'POST', body: fd });
    const data = await res.json();

    if (!res.ok) {
      showAlert('Scan Failed', data.tip || data.error || 'Unknown error');
      _scanStep = 'upload';
      renderScan();
      return;
    }

    _scanOcr = data;

    // If merging a second photo into existing review
    if (_scanPrevReview) {
      const prev = _scanPrevReview;
      _scanPrevReview = null;
      const newReview = _scanOcrToReview(data);
      _scanReview = _mergeReviews(prev, newReview);
      _scanOcr.warnings = [...(prev._warnings || []), ...(data.warnings || [])];
      if (_scanEditorMode) {
        _fillEditorFromOcr(_scanReview);
        return;
      }
      _scanStep = 'review';
      renderScan();
      return;
    }

    // Route to correct next step
    if (data.multiple_courses?.length >= 2) {
      _scanStep = 'multi-q';
      renderScan();
    } else if (data.nine_hole_card) {
      _scanStep = 'nine-q';
      renderScan();
    } else if (_scanEditorMode) {
      _fillEditorFromOcr(_scanOcrToReview(data));
    } else {
      _scanReview = _scanOcrToReview(data);
      _scanStep = 'review';
      renderScan();
    }
  } catch (err) {
    showAlert('Network Error','Make sure the app is running and try again.');
    _scanStep = 'upload';
    renderScan();
  }
}

function scanNineChoice(choice) {
  _scanNineChoice = choice;
  const data = _scanOcr;
  const review = (choice === 'full') ? _scanOcrToReview(data) : _scanOcrToReview(data, choice);
  if (_scanEditorMode) {
    _fillEditorFromOcr(review);
    return;
  }
  _scanReview = review;
  _scanStep = 'review';
  renderScan();
}

function scanMultiChoice(choice) {
  _scanMultiChoice = choice;
  const data = _scanOcr;
  let review;
  if (choice === 'combine') {
    const a = data.multiple_courses[0];
    const b = data.multiple_courses[1];
    const merged = {
      course_name: a.course_name || b.course_name,
      club_name: a.club_name || b.club_name,
      pars: [...(a.pars || []), ...(b.pars || [])],
      handicaps: [...(a.handicaps || []), ...(b.handicaps || [])],
      tee_boxes: _mergeTeeBoxes(a.tee_boxes || [], b.tee_boxes || []),
      nine_hole_card: false,
    };
    review = _scanOcrToReview(merged);
  } else if (choice === 'split-1') {
    review = _scanOcrToReview(data.multiple_courses[0]);
  } else {
    review = _scanOcrToReview(data.multiple_courses[1]);
  }
  if (_scanEditorMode) {
    _fillEditorFromOcr(review);
    return;
  }
  _scanReview = review;
  _scanStep = 'review';
  renderScan();
}

function _mergeTeeBoxes(a, b) {
  const merged = a.map(ta => {
    const tb = b.find(t => t.label === ta.label) || {};
    return {
      ...ta,
      yardages: [...(ta.yardages || []), ...(tb.yardages || [])],
    };
  });
  // Add any tees from b not in a
  for (const tb of b) {
    if (!merged.find(t => t.label === tb.label)) {
      merged.push({ ...tb, yardages: [...new Array(a[0]?.yardages?.length || 9).fill(null), ...(tb.yardages || [])] });
    }
  }
  return merged;
}

function _scanOcrToReview(ocrData, nineChoice) {
  // Clone so review edits don't mutate OCR result
  const d = JSON.parse(JSON.stringify(ocrData));
  if (!nineChoice || nineChoice === 'full') return d;

  const offset = nineChoice === 'back' ? 9 : 0;
  const emptyNine = new Array(9).fill(null);

  // Expand pars to 18-hole array
  const pars9 = d.pars || [];
  const pars18 = new Array(18).fill(null);
  for (let i = 0; i < 9 && i < pars9.length; i++) {
    pars18[offset + i] = pars9[i];
  }
  d.pars = pars18;

  // Expand handicaps
  const hcp9 = d.handicaps || [];
  const hcp18 = new Array(18).fill(null);
  for (let i = 0; i < 9 && i < hcp9.length; i++) {
    hcp18[offset + i] = hcp9[i];
  }
  d.handicaps = hcp18;

  // Expand tee yardages
  for (const tee of d.tee_boxes || []) {
    const y9 = tee.yardages || [];
    const y18 = new Array(18).fill(null);
    for (let i = 0; i < 9 && i < y9.length; i++) {
      y18[offset + i] = y9[i];
    }
    tee.yardages = y18;
  }

  d.nine_hole_card = false;
  return d;
}

// ── Scan more photos (merge additional data) ──────────────────────────────────

function scanAddAnotherPhoto() {
  // Store current review data and warnings, reset to upload step
  if (_scanReview) {
    _scanReview._warnings = _scanOcr?.warnings || [];
  }
  _scanPrevReview = _scanReview;
  _scanFile = null;
  _scanStep = 'upload';
  renderScan();
}

let _scanPrevReview = null;

function _mergeReviews(base, incoming) {
  const merged = JSON.parse(JSON.stringify(base));
  // Fill null pars from incoming
  if (incoming.pars?.length) {
    merged.pars = merged.pars || [];
    incoming.pars.forEach((v, i) => { if (v != null && merged.pars[i] == null) merged.pars[i] = v; });
  }
  // Fill null handicaps
  if (incoming.handicaps?.length) {
    merged.handicaps = merged.handicaps || [];
    incoming.handicaps.forEach((v, i) => { if (v != null && merged.handicaps[i] == null) merged.handicaps[i] = v; });
  }
  // Fill null yardages per tee
  for (const inTee of (incoming.tee_boxes || [])) {
    const existing = merged.tee_boxes?.find(t => t.label === inTee.label || t.color === inTee.color);
    if (existing) {
      existing.rating = existing.rating ?? inTee.rating;
      existing.slope = existing.slope ?? inTee.slope;
      if (inTee.yardages?.length) {
        existing.yardages = existing.yardages || [];
        inTee.yardages.forEach((v, i) => { if (v != null && existing.yardages[i] == null) existing.yardages[i] = v; });
      }
    } else if (merged.tee_boxes) {
      merged.tee_boxes.push(inTee);
    }
  }
  // Fill course/club name if missing
  merged.course_name = merged.course_name || incoming.course_name;
  merged.club_name = merged.club_name || incoming.club_name;
  return merged;
}


// ── Fill course editor with OCR data ─────────────────────────────────────────

function _fillEditorFromOcr(data) {
  _scanEditorMode = false;
  S.editCourse = null;
  show('course-editor');

  requestAnimationFrame(() => {
    const nameEl = document.getElementById('ce-name');
    const clubEl = document.getElementById('ce-club');
    if (nameEl && data.course_name) nameEl.value = data.course_name;
    if (clubEl && data.club_name) clubEl.value = data.club_name;

    if (data.pars?.length) {
      cePars = data.pars.map(v => (v != null && v >= 3 && v <= 6) ? v : 4);
      refreshCeParGrid();
    }

    if (data.tee_boxes?.length) {
      const container = document.getElementById('ce-tees');
      if (container) {
        container.innerHTML = '';
        ceYardages = {};
        data.tee_boxes.forEach(t => {
          // Capitalize color so it matches teeColorCSS() map keys (Black/Blue/White/etc.)
          const rawColor = t.color || t.label || 'White';
          const color = rawColor.charAt(0).toUpperCase() + rawColor.slice(1);
          const div = document.createElement('div');
          div.className = 'tee-editor-card';
          div.innerHTML = `<button class="tee-editor-remove" onclick="removeTeeEditor(this)" title="Remove">✕</button>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <div class="form-group" style="flex:1;min-width:70px"><div class="form-label">Color</div><input class="form-input tee-color" value="${esc(color)}" onchange="onTeeColorRenamed(this)"></div>
              <div class="form-group" style="flex:1;min-width:70px"><div class="form-label">Rating</div><input class="form-input tee-rating" value="${t.rating != null ? t.rating : ''}" type="number" step="0.1"></div>
              <div class="form-group" style="flex:1;min-width:70px"><div class="form-label">Slope</div><input class="form-input tee-slope" value="${t.slope != null ? t.slope : ''}" type="number"></div>
            </div>`;
          container.appendChild(div);
          const yards = (t.yardages || []).map(v => v != null ? v : 0);
          while (yards.length < cePars.length) yards.push(0);
          ceYardages[color] = yards;
        });
        const firstColor = data.tee_boxes[0]?.color || data.tee_boxes[0]?.label || 'White';
        ceActiveTee = firstColor.charAt(0).toUpperCase() + firstColor.slice(1);
        refreshCeTeePills();
        refreshCeHoleGrid();
      }
    }
  });
}

// ── Save ──────────────────────────────────────────────────────────────────────

async function scanSave() {
  const name = (document.getElementById('scan-name')?.value || '').trim();
  const club = (document.getElementById('scan-club')?.value || '').trim();
  if (!name) { showAlert('Course Name Required','Enter a name for this course.'); return; }

  // Collect pars
  const parInputs = document.querySelectorAll('.scan-par-input');
  const pars = [];
  parInputs.forEach(inp => {
    const v = parseInt(inp.value);
    pars.push(isNaN(v) ? 4 : v);
  });

  // Collect handicaps
  const hcpInputs = document.querySelectorAll('.scan-hcp-input');
  const handicaps = [];
  hcpInputs.forEach(inp => {
    const v = parseInt(inp.value);
    handicaps.push(isNaN(v) ? null : v);
  });

  // Collect tee boxes + yardages
  const teeCards = document.querySelectorAll('#scan-tees-container .scan-tee-card');
  const teeBoxes = [];
  const yardages = {};

  teeCards.forEach((card, ti) => {
    const color = card.querySelector('.scan-tee-color')?.value || '';
    const label = card.querySelector('.scan-tee-label')?.value?.trim() || '';
    const rating = parseFloat(card.querySelector('.scan-tee-rating')?.value);
    const slope = parseInt(card.querySelector('.scan-tee-slope')?.value);
    if (!color && !label) return;

    const teeKey = color || label;
    if (!isNaN(rating) && !isNaN(slope)) {
      teeBoxes.push({ color, label, rating, slope });
    } else {
      teeBoxes.push({ color, label,
        rating: isNaN(rating) ? null : rating,
        slope: isNaN(slope) ? null : slope });
    }

    // Collect yardages for this tee
    const yardInputs = document.querySelectorAll(`.scan-yard-input[data-tee="${ti}"]`);
    const yards = [];
    yardInputs.forEach(inp => {
      const v = parseInt(inp.value);
      yards.push(isNaN(v) ? 0 : v);
    });
    if (teeKey) yardages[teeKey] = yards;
  });

  if (!teeBoxes.length) { showAlert('Add a Tee Box','Add at least one tee box with rating and slope.'); return; }
  if (pars.length < 9) { showAlert('Need More Holes','A course needs at least 9 holes.'); return; }

  const payload = { name, club, pars, tee_boxes: teeBoxes, yardages };

  try {
    await POST('/api/courses/scan/confirm', payload);
    S.courses = await GET('/api/courses');
    S.viewCourseName = name;
    show('course-detail');
  } catch (err) {
    showAlert('Save Failed','Check all required fields and try again.');
  }
}

/* ================================================================
   THEME-AWARE ICONS
   Returns the correct icon path for the current color scheme.
   Pattern: /static/{name}-96.png (light) or /static/{name}-w-96.png (dark)
   ================================================================ */
function ico(name) {
  return `/static/${name}${DARK_MQ.matches?'-w':''}-96.png`;
}

function updateTabIcons() {
  const t = (sel, name) => { const el=document.querySelector(sel); if(el) el.src=ico(name); };
  t('[data-tab="rounds"] .tab-icon img', 'logbook');
  t('[data-tab="home"] .tab-icon img', 'golfer');
  t('[data-tab="courses"] .tab-icon img', 'golf-course');
}

DARK_MQ.addEventListener('change', () => {
  updateTabIcons();
  if(_currentPage && RENDERERS[_currentPage]) RENDERERS[_currentPage]();
});

/* ================================================================
   MANUAL VIEWER
   ================================================================ */
let _manualSections = null; // [{title, body}]

function _parseSections(raw) {
  // Strip leading HTML h1 block
  raw = raw.replace(/^<h1>[\s\S]*?<\/h1>\s*/m, '');
  // Split on ## headers
  const chunks = raw.split(/^## /m).filter(Boolean);
  return chunks
    .map(chunk => {
      const nl = chunk.indexOf('\n');
      const title = chunk.slice(0, nl).trim();
      const body  = chunk.slice(nl + 1).trim();
      return { title, body };
    })
    .filter(s => s.title !== 'Table of Contents');
}

function _mdToHtml(md) {
  if (typeof marked !== 'undefined') return marked.parse(md);
  return md
    .replace(/^#{4} (.+)$/gm, '<h4>$1</h4>')
    .replace(/^#{3} (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^---$/gm, '<hr>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/\n\n/g, '</p><p>');
}

// Strip leading number "1. " or "1.1 " from section title for display
function _sectionLabel(title) {
  return title.replace(/^\d+(\.\d+)*\.?\s*/, '');
}

async function showManual() {
  const backdrop = document.createElement('div');
  backdrop.className = 'manual-backdrop';
  const sheet = document.createElement('div');
  sheet.className = 'manual-sheet';

  sheet.innerHTML = `
    <div class="manual-drag-handle"></div>
    <div class="manual-header">
      <div style="width:52px"></div>
      <div class="manual-title">Manual</div>
      <button class="manual-done-btn">Done</button>
    </div>
    <div class="manual-sep"></div>
    <div class="manual-panels">
      <div class="manual-panel" id="manual-list-panel">
        <div class="manual-section-list" id="manual-section-list">
          <div style="color:var(--text2);text-align:center;padding:48px 0;font-size:15px">Loading…</div>
        </div>
      </div>
      <div class="manual-panel off-right" id="manual-detail-panel">
        <div class="manual-detail" id="manual-detail-body"></div>
      </div>
    </div>`;

  document.body.appendChild(backdrop);
  document.body.appendChild(sheet);

  const listPanel   = sheet.querySelector('#manual-list-panel');
  const detailPanel = sheet.querySelector('#manual-detail-panel');
  const headerTitle = sheet.querySelector('.manual-title');
  const doneBtn     = sheet.querySelector('.manual-done-btn');

  const goBack = () => {
    listPanel.classList.remove('off-left');
    detailPanel.classList.add('off-right');
    headerTitle.textContent = 'Manual';
    doneBtn.textContent = 'Done';
    doneBtn.removeEventListener('click', goBack);
    doneBtn.addEventListener('click', close);
  };

  const close = () => {
    backdrop.classList.remove('open');
    sheet.classList.remove('open');
    setTimeout(() => { backdrop.remove(); sheet.remove(); }, 380);
  };
  doneBtn.addEventListener('click', close);
  backdrop.addEventListener('click', close);

  requestAnimationFrame(() => { backdrop.classList.add('open'); sheet.classList.add('open'); });

  // Load & parse
  if (!_manualSections) {
    try {
      const res = await fetch('/api/manual');
      _manualSections = _parseSections(await res.text());
    } catch(e) {
      sheet.querySelector('#manual-section-list').innerHTML =
        '<p style="color:var(--red);padding:20px">Could not load manual.</p>';
      return;
    }
  }

  // Build list
  const list = sheet.querySelector('#manual-section-list');
  list.innerHTML = _manualSections.map((s, i) =>
    `<div class="manual-section-row" data-idx="${i}">
      <span class="manual-section-label">${esc(_sectionLabel(s.title))}</span>
      <span class="manual-section-chevron">›</span>
    </div>`
  ).join('<div class="manual-sep"></div>');

  list.querySelectorAll('.manual-section-row').forEach(row => {
    row.addEventListener('click', () => {
      const s = _manualSections[+row.dataset.idx];
      sheet.querySelector('#manual-detail-body').innerHTML =
        `<h2>${esc(_sectionLabel(s.title))}</h2>` + _mdToHtml(s.body);
      detailPanel.classList.remove('off-right');
      listPanel.classList.add('off-left');
      detailPanel.scrollTop = 0;
      headerTitle.textContent = _sectionLabel(s.title);
      doneBtn.textContent = '‹ Back';
      doneBtn.removeEventListener('click', close);
      doneBtn.addEventListener('click', goBack);
    });
  });
}

/* ================================================================
   INIT
   ================================================================ */
async function init(){
  _contentEl=document.getElementById('content');
  _tabbarEl=document.getElementById('tabbar');
  S.clubs=await GET('/api/clubs');
  updateTabIcons();
  nav('home');
}
init();
