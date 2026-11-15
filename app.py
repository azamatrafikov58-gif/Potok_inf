# app.py — «Фабрика новостей», MVP по ТЗ
# поднял на голом http.server чтобы не тащить зависимости на старте.
# когда переедем на нормальный фреймворк + БД — заменить CARDS на ORM.
# TODO: вынести HTML в шаблоны (сейчас это боль, знаю)

import json, re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# порядок из ТЗ п.3.1 — не переставлять, от него завязаны step(±1)
STATUSES = ["Заявка", "В работе", "Текст готов", "Съёмка",
            "Монтаж", "Проверка", "Утверждено", "В эфире"]

# матрица "кто может двигать карточку из этого статуса"
RULES = {
    "Заявка":      ["Журналист", "Администратор-продюсер", "Шеф-редактор"],
    "В работе":    ["Журналист", "Администратор-продюсер", "Шеф-редактор"],
    "Текст готов": ["Редактор", "Шеф-редактор"],
    "Съёмка":      ["Телеоператор", "Администратор-продюсер"],
    "Монтаж":      ["Монтажёр", "Режиссёр монтажа"],
    "Проверка":    ["Режиссёр монтажа", "Шеф-редактор", "Редактор"],
    "Утверждено":  ["Выпускающий режиссёр", "Шеф-редактор"],
    "В эфире":     ["Выпускающий режиссёр"],
}

ROLES = ["Журналист", "Телеоператор", "Монтажёр", "Редактор", "Шеф-редактор",
         "Выпускающий режиссёр", "Администратор-продюсер", "Режиссёр монтажа"]

CREATORS = ["Журналист", "Администратор-продюсер", "Шеф-редактор"]

# заглушка вместо AD/LDAP (п.4 ТЗ), пока захардкожено
USERS = ["Иванов", "Смирнов", "Сидоров", "Козлов", "Петров", "Орлов",
         "Журналист", "Редактор", "Шеф-редактор", "Монтажёр",
         "Режиссёр монтажа", "Выпускающий режиссёр", "Администратор-продюсер"]

NOTIFS = []  # уведомления, живут в памяти — для демо хватит

def nnow():
    return datetime.now().strftime("%d.%m %H:%M")

def notify(txt):
    # туповато режем до 30 последних, потом прикрутим нормальную пагинацию
    NOTIFS.insert(0, {"ts": nnow(), "text": txt, "read": False})
    del NOTIFS[30:]

# --- демо-данные, чтобы UI не пустовал при первом старте ---
CARDS = [
    {"id": 1, "title": "Открытие нового моста через реку", "status": "Заявка",
     "author": "Иванов", "deadline": "2026-11-18", "loc": "Южный обход, 14 км",
     "crew": "Оператор: Смирнов",
     "operator": "Смирнов", "journalist": "Иванов", "driver": "Козлов",
     "tc": "00:00 - Общий план",
     "text": "В городе открыли движение по новому мостовому переходу.",
     "text_versions": [{"ts": "10:00", "author": "Иванов",
                        "text": "В городе открыли движение по новому мостовому переходу."}],
     "s3": "s3://rf-news/bridge.mp4",
     "media": [{"name": "bridge_raw.mp4", "type": "video", "size": "3.4 ГБ"}],
     "comments": [], "audit": ["[10:00] Система: Карточка создана"],
     "duration": 120, "in_rundown": False, "rundown_pos": 0},

    {"id": 2, "title": "Запуск IT-кластера в технопарке", "status": "В работе",
     "author": "Петров", "deadline": "2026-11-14", "loc": "ул. Инноваций, 1",
     "crew": "Оператор: Иванов",
     "operator": "Иванов", "journalist": "Петров", "driver": "Орлов",
     "tc": "00:15 - Синхрон спикера",
     "text": "Резидентами кластера стали тридцать российских компаний.",
     "text_versions": [{"ts": "10:15", "author": "Петров",
                        "text": "Резидентами кластера стали тридцать российских компаний."}],
     "s3": "s3://rf-news/it.mp4", "media": [],
     "comments": [{"ts": "10:20", "author": "Смирнов",
                   "text": "@Петров нужны кадры со дрона"}],
     "audit": ["[10:15] Продюсер: Переведено в работу"],
     "duration": 90, "in_rundown": False, "rundown_pos": 0},

    {"id": 3, "title": "Итоги дорожного ремонта за неделю", "status": "Утверждено",
     "author": "Сидоров", "deadline": "2026-11-12", "loc": "Администрация",
     "crew": "Оператор: Сидоров",
     "operator": "Сидоров", "journalist": "Сидоров", "driver": "Орлов",
     "tc": "00:05 - Проезд техники",
     "text": "Более двадцати километров дорог обновили за неделю.",
     "text_versions": [{"ts": "11:00", "author": "Сидоров",
                        "text": "Более двадцати километров дорог обновили за неделю."}],
     "s3": "s3://rf-news/road.mp4",
     "media": [{"name": "road_edit_v2.mp4", "type": "video", "size": "1.1 ГБ"}],
     "comments": [], "audit": ["[11:00] Шеф-редактор: Утверждено в эфир"],
     "duration": 150, "in_rundown": True, "rundown_pos": 1},
]


# ---------------- фронт ----------------
# css/js держу инлайном чтобы не настраивать статику. да, знаю что так некрасиво.
HTML = r"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Фабрика Новостей</title>
<style>
:root{--bg:#0f172a;--panel:#1e293b;--border:#334155;--accent:#2563eb;--muted:#94a3b8}
*{box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:var(--bg);color:#fff;margin:0}
header{background:var(--panel);padding:10px 20px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--border);flex-wrap:wrap;gap:8px}
header b{font-size:16px}
.tabs{display:flex;gap:4px;background:var(--panel);padding:0 20px;border-bottom:1px solid var(--border);overflow-x:auto}
.tab{padding:10px 16px;cursor:pointer;color:var(--muted);border-bottom:2px solid transparent;white-space:nowrap}
.tab.active{color:#fff;border-bottom-color:var(--accent)}
.bar{background:var(--panel);padding:10px 20px;display:flex;gap:8px;align-items:center;border-bottom:1px solid var(--border);flex-wrap:wrap}
input,select,textarea{background:var(--bg);color:#fff;border:1px solid #475569;padding:6px;border-radius:5px;font-family:inherit;font-size:13px}
button{background:var(--accent);color:#fff;border:none;padding:6px 12px;border-radius:5px;cursor:pointer;font-family:inherit;font-size:13px}
button.sec{background:var(--border)}
button.danger{background:#dc2626}
button.ok{background:#10b981;color:#000}
button:disabled{opacity:.4;cursor:not-allowed}
.view{display:none;padding:15px}
.view.active{display:block}
.board{display:flex;gap:10px;overflow-x:auto;min-height:calc(100vh - 240px)}
.col{min-width:220px;background:var(--panel);padding:10px;border-radius:8px;border:2px solid var(--border);display:flex;flex-direction:column;gap:8px}
.col.act{border-color:var(--accent)}
.col h3{margin:0 0 4px 0;font-size:13px;display:flex;justify-content:space-between;gap:6px}
.col h3 span{background:var(--bg);padding:1px 7px;border-radius:10px;font-size:11px}
.card{background:var(--bg);padding:9px;border-radius:6px;border:1px solid var(--border);cursor:pointer;font-size:12px}
.card.act{border-left:3px solid var(--accent)}
.card.overdue{border-left:3px solid #dc2626}
.card .meta{color:var(--muted);font-size:11px;margin-top:4px;display:flex;justify-content:space-between;gap:4px}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);justify-content:center;align-items:flex-start;z-index:10;overflow-y:auto;padding:20px}
.modal.show{display:flex}
.box{background:var(--panel);padding:20px;border-radius:10px;width:960px;max-width:100%}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
@media (max-width:700px){.grid2,.grid3{grid-template-columns:1fr}}
label{display:block;margin-top:8px;font-size:12px;color:var(--muted)}
input,textarea{width:100%}
.modal-tabs{display:flex;gap:4px;margin-top:14px;border-bottom:1px solid var(--border);flex-wrap:wrap}
.mtab{padding:6px 12px;cursor:pointer;color:var(--muted);border-bottom:2px solid transparent;font-size:13px}
.mtab.active{color:#fff;border-bottom-color:var(--accent)}
.mview{display:none;padding:10px 0}
.mview.active{display:block}
#prm{display:none;position:fixed;inset:0;background:#000;color:#fff;padding:40px;font-size:44px;z-index:20;line-height:1.3;overflow-y:auto}
#prm.show{display:block}
.bell{position:relative;cursor:pointer;font-size:20px;user-select:none}
.bell .badge{position:absolute;top:-4px;right:-10px;background:#dc2626;border-radius:10px;font-size:10px;padding:1px 6px;color:#fff}
.notif-panel{display:none;position:absolute;top:52px;right:20px;background:var(--panel);border:1px solid var(--border);border-radius:8px;width:340px;max-height:60vh;overflow-y:auto;z-index:100;padding:10px;box-shadow:0 4px 20px rgba(0,0,0,.5)}
.notif-panel.show{display:block}
.notif{font-size:12px;padding:6px;border-bottom:1px solid var(--border);color:#cbd5e1}
.notif.unread{color:#fff;font-weight:500}
.notif:last-child{border-bottom:none}
.comment{background:var(--bg);padding:8px;border-radius:6px;margin-top:6px;font-size:13px}
.comment .who{color:#60a5fa;font-size:12px;margin-bottom:3px}
.mention{color:#f59e0b;font-weight:bold}
.ver{background:var(--bg);padding:8px;border-radius:6px;margin-top:6px;font-size:12px;border-left:3px solid var(--accent)}
.rundown{display:flex;flex-direction:column;gap:8px;max-width:820px}
.rundown-item{background:var(--panel);padding:10px 12px;border-radius:8px;display:flex;gap:10px;align-items:center;border:1px solid var(--border)}
.rundown-item .num{background:var(--accent);border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-weight:bold;flex-shrink:0}
.rundown-item .body{flex:1;font-size:13px}
.analytics{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.panel{background:var(--panel);padding:15px;border-radius:10px;border:1px solid var(--border)}
.bar-row{display:flex;align-items:center;gap:8px;margin:6px 0;font-size:13px}
.bar-row .lbl{width:140px;color:var(--muted);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar-row .bar{height:16px;background:var(--accent);border-radius:4px;min-width:2px}
.bar-row .val{color:var(--muted);font-size:12px}
.calendar{display:grid;grid-template-columns:repeat(7,1fr);gap:4px}
.cal-head{background:var(--panel);padding:8px;text-align:center;font-size:12px;color:var(--muted);border-radius:4px}
.cal-day{background:var(--panel);padding:6px;border-radius:6px;min-height:88px;font-size:11px;border:1px solid var(--border)}
.cal-day.today{border-color:var(--accent);background:#1a2740}
.cal-day .day-num{color:var(--muted);font-size:11px;margin-bottom:4px}
.cal-day .ev{background:var(--bg);padding:2px 5px;border-radius:3px;margin-top:2px;font-size:10px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-left:2px solid var(--accent)}
.stat-card{background:var(--panel);padding:15px;border-radius:10px;text-align:center;border:1px solid var(--border)}
.stat-card .num{font-size:30px;font-weight:bold;color:var(--accent)}
.stat-card .lbl{color:var(--muted);font-size:12px;margin-top:4px}
h4{margin:8px 0 10px}
</style></head><body>

<header>
  <b>🎬 Фабрика Новостей</b>
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <div class="bell" onclick="toggleNotif(event)">🔔<span class="badge" id="notif-badge"></span></div>
    <label style="margin:0">Пользователь: <input id="user" value="Иванов" style="width:110px" onchange="syncUser()"></label>
    <label style="margin:0">Роль: <select id="role" onchange="syncUser()"></select></label>
  </div>
</header>

<nav class="tabs">
  <div class="tab active" data-tab="kanban">Канбан</div>
  <div class="tab" data-tab="calendar">Календарь</div>
  <div class="tab" data-tab="rundown">Выпуск (Rundown)</div>
  <div class="tab" data-tab="analytics">Аналитика</div>
</nav>

<div class="bar">
  <input id="f-author" placeholder="Автор..." oninput="render()" style="width:130px">
  <select id="f-deadline" onchange="render()">
    <option value="">Все дедлайны</option>
    <option value="overdue">Просрочено</option>
    <option value="today">Сегодня</option>
    <option value="week">На неделе</option>
  </select>
  <select id="f-status" onchange="render()"></select>
  <label style="margin:0;display:flex;align-items:center;gap:4px;font-size:12px;color:#cbd5e1">
    <input type="checkbox" id="f-mine" onchange="render()" style="width:auto"> Только мои задачи
  </label>
  <div style="flex:1"></div>
  <input id="nt" placeholder="Тема заявки..." style="width:220px">
  <input id="nl" placeholder="Адрес..." style="width:140px">
  <input id="nd" type="date" style="width:140px">
  <button onclick="addCard()">+ Заявка</button>
</div>

<div class="view active" id="v-kanban"><div class="board" id="board"></div></div>
<div class="view" id="v-calendar"><div class="calendar" id="calendar"></div></div>
<div class="view" id="v-rundown"><div id="rundown"></div></div>
<div class="view" id="v-analytics"><div id="analytics"></div></div>

<div class="modal" id="m"><div class="box">
  <div style="display:flex;justify-content:space-between;align-items:start;gap:10px;flex-wrap:wrap">
    <div><b id="mh"></b><br><small style="color:#60a5fa" id="mhint"></small></div>
    <div style="display:flex;gap:6px">
      <button class="sec" onclick="step(-1)">← Назад</button>
      <button class="ok" onclick="step(1)">Дальше →</button>
      <button class="danger" onclick="$('m').classList.remove('show')">✕</button>
    </div>
  </div>
  <div class="grid3" style="margin-top:10px">
    <div><label>Заголовок</label><input id="ft"></div>
    <div><label>Автор</label><input id="fa"></div>
    <div><label>Дедлайн</label><input id="fd" type="date"></div>
    <div><label>Адрес</label><input id="fl"></div>
    <div><label>Хронометраж (сек)</label><input id="fdur" type="number" min="10"></div>
    <div><label>S3 файл</label><input id="fm"></div>
    <div><label>Оператор</label><input id="fop"></div>
    <div><label>Журналист</label><input id="fjr"></div>
  </div>
  <label>Таймкоды</label><textarea id="ftc" rows="2"></textarea>
  <label>Текст</label><textarea id="ftx" rows="5"></textarea>
  <div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap">
    <button class="sec" onclick="exportXML()">Экспорт XML (NLE)</button>
    <button class="sec" onclick="sufler()">Суфлёр</button>
    <button class="ok" onclick="saveCard()">💾 Сохранить</button>
  </div>
  <div class="modal-tabs">
    <div class="mtab active" data-mt="versions">Версии</div>
    <div class="mtab" data-mt="media">Медиа</div>
    <div class="mtab" data-mt="comments">Комментарии</div>
    <div class="mtab" data-mt="audit">Аудит</div>
  </div>
  <div class="mview active" id="mv-versions"></div>
  <div class="mview" id="mv-media"></div>
  <div class="mview" id="mv-comments"></div>
  <div class="mview" id="mv-audit"></div>
</div></div>

<div id="prm" onclick="this.classList.remove('show')"></div>
<div class="notif-panel" id="np"></div>

<script>
// мелкие хелперы, чтобы не повторять $('x') по 10 раз
const $ = id => document.getElementById(id);
const esc = s => (s||'').toString().replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const todayStr = () => new Date().toISOString().slice(0,10);
const weekStr  = () => new Date(Date.now()+7*864e5).toISOString().slice(0,10);

let ST=[], RL={}, ROLES=[], USERS=[], CARDS=[], NOTIFS=[];
let curTab='kanban', curCard=null, curRole='', curUser='';

async function load(){
  const d = await (await fetch('/api')).json();
  applyPayload(d);
  ST = d.statuses; RL = d.rules; ROLES = d.roles; USERS = d.users;
  // селекты ролей/статусов — один раз при старте
  $('role').innerHTML = ROLES.map(r=>`<option>${r}</option>`).join('');
  $('f-status').innerHTML = '<option value="">Все статусы</option>' + ST.map(s=>`<option>${s}</option>`).join('');
  curRole = $('role').value; curUser = $('user').value;
  render();
}

function applyPayload(d){
  CARDS = d.cards; NOTIFS = d.notifications;
  updateBadge(); renderNotifs();
  // если карточка открыта — перерисовываем её же, чтобы не терять контекст
  if (curCard && CARDS.find(c=>c.id===curCard)) openCard(curCard);
}

function updateBadge(){
  const un = NOTIFS.filter(n=>!n.read).length;
  $('notif-badge').textContent = un ? un : '';
}

function renderNotifs(){
  $('np').innerHTML = NOTIFS.length
    ? NOTIFS.slice(0,15).map(n=>`<div class="notif ${n.read?'':'unread'}">[${n.ts}] ${esc(n.text)}</div>`).join('')
    : '<div class="notif">Нет уведомлений</div>';
}

async function toggleNotif(e){
  e.stopPropagation();
  const np = $('np');
  if (np.classList.contains('show')) np.classList.remove('show');
  else {
    np.classList.add('show');
    if (NOTIFS.some(n=>!n.read)) await post('notif_read');
  }
}

function syncUser(){ curRole = $('role').value; curUser = $('user').value; render(); }

// универсальный POST, чтобы не плодить обёртки
async function post(act, extra={}){
  const body = {act, role: curRole, user: curUser, ...extra};
  const r = await fetch('/api', {method:'POST', body: JSON.stringify(body)});
  const d = await r.json();
  if (d.err) alert(d.err);
  applyPayload(d);
}

function render(){
  if (curTab==='kanban') renderKanban();
  else if (curTab==='calendar') renderCalendar();
  else if (curTab==='rundown') renderRundown();
  else if (curTab==='analytics') renderAnalytics();
}

// фильтры — общие для канбана и календаря
function filtered(){
  const a = $('f-author').value.toLowerCase();
  const dl = $('f-deadline').value;
  const st = $('f-status').value;
  const mine = $('f-mine').checked;
  const t = todayStr(), w = weekStr();
  return CARDS.filter(c=>{
    if (a && !(c.author||'').toLowerCase().includes(a)) return false;
    if (st && c.status!==st) return false;
    if (dl==='overdue' && !(c.deadline && c.deadline < t && c.status!=='В эфире')) return false;
    if (dl==='today' && c.deadline!==t) return false;
    if (dl==='week' && !(c.deadline && c.deadline>=t && c.deadline<=w)) return false;
    if (mine && !(RL[c.status]||[]).includes(curRole)) return false;
    return true;
  });
}

function renderKanban(){
  const board = $('board'); board.innerHTML='';
  const t = todayStr();
  ST.forEach(s=>{
    const col = document.createElement('div');
    col.className = 'col' + ((RL[s]||[]).includes(curRole) ? ' act' : '');
    const list = filtered().filter(c=>c.status===s);
    col.innerHTML = `<h3>${s}<span>${list.length}</span></h3>`;
    list.forEach(c=>{
      const overdue = c.deadline && c.deadline < t && c.status!=='В эфире';
      const d = document.createElement('div');
      d.className = 'card'
        + ((RL[c.status]||[]).includes(curRole) ? ' act' : '')
        + (overdue ? ' overdue' : '');
      d.innerHTML = `<b>#${c.id} ${esc(c.title)}</b>
        <div class="meta"><span>👤 ${esc(c.author||'—')}</span><span>${c.deadline||''}</span></div>
        <div class="meta"><span>📍 ${esc(c.loc||'')}</span><span>⏱ ${fmtDur(c.duration)}</span></div>`;
      d.onclick = ()=>openCard(c.id);
      col.appendChild(d);
    });
    board.appendChild(col);
  });
}

function renderCalendar(){
  // рисуем текущий месяц, листать пока не просили — не стали делать
  const now = new Date();
  const y = now.getFullYear(), m = now.getMonth();
  const first = new Date(y, m, 1);
  const dim = new Date(y, m+1, 0).getDate();
  const start = (first.getDay()+6)%7; // неделя с Пн
  const cal = $('calendar'); cal.innerHTML='';
  ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].forEach(d=>{
    const h = document.createElement('div'); h.className='cal-head'; h.textContent=d;
    cal.appendChild(h);
  });
  for (let i=0;i<start;i++) cal.appendChild(document.createElement('div'));
  const t = todayStr();
  const cards = filtered();
  for (let d=1; d<=dim; d++){
    const ds = `${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    const cell = document.createElement('div');
    cell.className = 'cal-day' + (ds===t ? ' today' : '');
    cell.innerHTML = `<div class="day-num">${d}</div>`;
    cards.filter(c=>c.deadline===ds).forEach(c=>{
      const ev = document.createElement('div');
      ev.className='ev';
      ev.textContent = `#${c.id} ${c.title}`;
      ev.title = `${c.title} (${c.status})`;
      ev.onclick = ()=>openCard(c.id);
      cell.appendChild(ev);
    });
    cal.appendChild(cell);
  }
}

function fmtDur(sec){
  sec = Math.round(sec||0);
  const m = Math.floor(sec/60), s = sec%60;
  return `${m}:${String(s).padStart(2,'0')}`;
}

function renderRundown(){
  const items = CARDS.filter(c=>c.in_rundown).sort((a,b)=>a.rundown_pos-b.rundown_pos);
  const total = items.reduce((s,c)=>s+(c.duration||0),0);
  const target = 1800; // 30 минут — стандартный слот, потом вынести в настройки
  const diff = total - target;
  const avail = CARDS.filter(c=>!c.in_rundown && ['Утверждено','В эфире'].includes(c.status));
  $('rundown').innerHTML = `
    <div class="analytics" style="margin-bottom:15px">
      <div class="stat-card"><div class="num">${fmtDur(total)}</div><div class="lbl">Хронометраж выпуска</div></div>
      <div class="stat-card"><div class="num">${fmtDur(target)}</div><div class="lbl">Целевой хронометраж</div></div>
      <div class="stat-card"><div class="num" style="color:${diff>0?'#dc2626':'#10b981'}">${diff>0?'+':''}${fmtDur(Math.abs(diff))}</div><div class="lbl">${diff>0?'Перебор':'Запас'}</div></div>
      <div class="stat-card"><div class="num">${items.length}</div><div class="lbl">Сюжетов в выпуске</div></div>
    </div>
    <div class="rundown">
      ${items.length ? items.map((c,i)=>`
        <div class="rundown-item">
          <div class="num">${i+1}</div>
          <div class="body"><b>#${c.id} ${esc(c.title)}</b><br>
            <small style="color:#94a3b8">${esc(c.status)} • ${fmtDur(c.duration)}</small></div>
          <button class="sec" onclick="rundownMove(${c.id},-1)" ${i===0?'disabled':''}>↑</button>
          <button class="sec" onclick="rundownMove(${c.id},1)" ${i===items.length-1?'disabled':''}>↓</button>
          <button class="danger" onclick="rundownRemove(${c.id})">✕</button>
        </div>`).join('') : '<div style="color:#94a3b8">В выпуске пока нет сюжетов. Добавьте из списка ниже.</div>'}
    </div>
    <h4>Доступно к добавлению</h4>
    <div class="rundown">
      ${avail.length ? avail.map(c=>`
        <div class="rundown-item">
          <div class="body"><b>#${c.id} ${esc(c.title)}</b> <small style="color:#94a3b8">• ${fmtDur(c.duration)}</small></div>
          <button onclick="rundownAdd(${c.id})">+ В выпуск</button>
        </div>`).join('') : '<div style="color:#94a3b8">Нет утверждённых сюжетов</div>'}
    </div>
    <div style="margin-top:15px;display:flex;gap:8px;flex-wrap:wrap">
      <button class="sec" onclick="exportRundown('mos')">📤 Экспорт MOS</button>
      <button class="sec" onclick="exportRundown('xml')">📤 Экспорт XML</button>
    </div>`;
}

function rundownAdd(id){ post('rundown_add',{id}); }
function rundownRemove(id){ post('rundown_remove',{id}); }
function rundownMove(id,dir){ post('rundown_move',{id,dir}); }

function renderAnalytics(){
  const t = todayStr();
  const total = CARDS.length;
  const inProg = CARDS.filter(c=>!['Утверждено','В эфире'].includes(c.status)).length;
  const inAir = CARDS.filter(c=>c.status==='В эфире').length;
  const overdue = CARDS.filter(c=>c.deadline && c.deadline<t && c.status!=='В эфире').length;
  const withDeadline = CARDS.filter(c=>c.deadline).length;
  const onTime = CARDS.filter(c=>c.deadline && c.deadline>=t).length;
  const byS = {}; ST.forEach(s=>byS[s]=CARDS.filter(c=>c.status===s).length);
  const maxS = Math.max(1,...Object.values(byS));
  const byA = {}; CARDS.forEach(c=>byA[c.author||'—']=(byA[c.author||'—']||0)+1);
  const maxA = Math.max(1,...Object.values(byA));
  $('analytics').innerHTML = `
    <div class="analytics">
      <div class="stat-card"><div class="num">${total}</div><div class="lbl">Всего сюжетов</div></div>
      <div class="stat-card"><div class="num">${inProg}</div><div class="lbl">В производстве</div></div>
      <div class="stat-card"><div class="num">${inAir}</div><div class="lbl">В эфире</div></div>
      <div class="stat-card"><div class="num" style="color:${overdue?'#dc2626':'#10b981'}">${overdue}</div><div class="lbl">Просрочено</div></div>
      <div class="stat-card"><div class="num">${withDeadline?Math.round(onTime/withDeadline*100):0}%</div><div class="lbl">Соблюдение дедлайнов</div></div>
    </div>
    <div class="analytics" style="margin-top:15px">
      <div class="panel"><h4>По статусам</h4>
        ${Object.entries(byS).map(([s,n])=>`<div class="bar-row"><div class="lbl">${s}</div><div class="bar" style="width:${n/maxS*220}px"></div><div class="val">${n}</div></div>`).join('')}
      </div>
      <div class="panel"><h4>По авторам</h4>
        ${Object.entries(byA).map(([a,n])=>`<div class="bar-row"><div class="lbl">${esc(a)}</div><div class="bar" style="width:${n/maxA*220}px;background:#10b981"></div><div class="val">${n}</div></div>`).join('')}
      </div>
    </div>`;
}

function addCard(){
  if (!$('nt').value) return;
  post('add', {title: $('nt').value, loc: $('nl').value || 'Выезд', deadline: $('nd').value});
  $('nt').value=''; $('nl').value='';
}

function openCard(id){
  curCard = id;
  const c = CARDS.find(x=>x.id===id); if (!c) return;
  $('mh').textContent = `#${c.id} • ${c.status}`;
  $('mhint').textContent = 'Ответственные: ' + (RL[c.status]||[]).join(', ');
  $('ft').value=c.title||''; $('fa').value=c.author||''; $('fd').value=c.deadline||'';
  $('fl').value=c.loc||''; $('fdur').value=c.duration||60; $('fm').value=c.s3||'';
  $('fop').value=c.operator||''; $('fjr').value=c.journalist||''
  $('ftc').value=c.tc||''; $('ftx').value=c.text||'';
  renderVersions(c); renderMedia(c); renderComments(c); renderAudit(c);
  $('m').classList.add('show');
}

function renderVersions(c){
  const vs = c.text_versions||[];
  $('mv-versions').innerHTML = vs.length ? vs.map((v,i)=>`
    <div class="ver">
      <div><b>${v.ts}</b> • ${esc(v.author)} ${i===0?'<span style="color:#10b981">← текущая</span>':''}</div>
      <div style="margin-top:4px">${esc(v.text)}</div>
      ${i>0?`<button class="sec" style="margin-top:6px" onclick="rollback(${c.id},${i})">↩ Откатить</button>`:''}
    </div>`).join('') : '<div style="color:#94a3b8">Нет версий текста</div>';
}

function renderMedia(c){
  const ms = c.media||[];
  // TODO: сейчас это имитация загрузки, реальный upload — потом (см. п.3.2 ТЗ)
  $('mv-media').innerHTML = `
    <div style="display:flex;gap:6px;margin-bottom:10px">
      <input id="mname" placeholder="Имя файла (например, bridge_raw.mp4)" style="flex:1">
      <button onclick="addMedia()">+ Загрузить</button>
    </div>
    ${ms.length ? ms.map(m=>`<div class="ver"><b>${esc(m.name)}</b> <small style="color:#94a3b8">${esc(m.type)} • ${esc(m.size)}</small></div>`).join('') : '<div style="color:#94a3b8">Нет файлов</div>'}`;
}

function renderComments(c){
  const cs = c.comments||[];
  $('mv-comments').innerHTML = `
    <textarea id="cmtx" rows="2" placeholder="Комментарий… используйте @Иванов для упоминания"></textarea>
    <button onclick="addComment()" style="margin-top:6px">Отправить</button>
    <div style="margin-top:12px">
      ${cs.length ? cs.map(cm=>`
        <div class="comment">
          <div class="who">${esc(cm.author)} • ${cm.ts}</div>
          <div>${formatMentions(cm.text)}</div>
        </div>`).join('') : '<div style="color:#94a3b8">Комментариев нет</div>'}
    </div>`;
}

function formatMentions(t){
  // ловим @User и подсвечиваем — подсветка чисто визуальная, нотифает бэк
  return esc(t).replace(/@([А-Яа-яA-Za-z0-9_]+)/g,'<span class="mention">@$1</span>');
}

function renderAudit(c){
  $('mv-audit').innerHTML = (c.audit||[]).map(a=>`<div class="ver">${esc(a)}</div>`).join('');
}

function saveCard(){
  post('save', {
    id: curCard, title: $('ft').value, author: $('fa').value, deadline: $('fd').value,
    loc: $('fl').value, duration: parseInt($('fdur').value)||60, s3: $('fm').value,
    operator: $('fop').value, journalist: $('fjr').value, driver: $('fdr').value,
    crew: composeCrew($('fop').value, $('fjr').value, $('fdr').value),
    tc: $('ftc').value, text: $('ftx').value
  });
}

function composeCrew(op, jr, dr){
  const p=[]; if (op) p.push('Оператор: '+op); if (jr) p.push('Журналист: '+jr);
  return p.join(', ');
}

function step(dir){ post('step',{id: curCard, dir}); }
function addComment(){
  const t = $('cmtx').value.trim(); if (!t) return;
  post('comment',{id: curCard, text: t});
}
function addMedia(){
  const n = $('mname').value.trim(); if (!n) return;
  const ext = n.split('.').pop().toLowerCase();
  const type = ['mp4','mov','avi','mkv'].includes(ext) ? 'video'
             : ['mp3','wav','aac'].includes(ext) ? 'audio'
             : ['jpg','png','jpeg'].includes(ext) ? 'image' : 'file';
  post('media_add',{id: curCard, name: n, type, size: '—'});
}
function rollback(id, idx){
  const c = CARDS.find(x=>x.id===id); if (!c) return;
  const v = c.text_versions[idx];
  if (!v || !confirm('Откатить текст к версии ' + v.ts + '?')) return;
  $('ftx').value = v.text;
  saveCard();
}

function sufler(){
  // простой полноэкранный суфлёр, крутить скорость не просили
  $('prm').textContent = $('ft').value + '\\n\\n' + $('ftx').value;
  $('prm').classList.add('show');
}

function download(name, content){
  const a = document.createElement('a');
  a.href = 'data:application/xml;charset=utf-8,' + encodeURIComponent(content);
  a.download = name; a.click();
}

function exportXML(){
  // минимальный xmeml-стаб — Premiere/Resolve съедят как болванку
  const c = CARDS.find(x=>x.id===curCard); if (!c) return;
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\\n<xmeml version="4">\\n  <sequence>\\n    <name>#${c.id} ${c.title}</name>\\n    <duration>${c.duration||0}</duration>\\n    <file id="file-1">\\n      <pathurl>${c.s3}</pathurl>\\n    </file>\\n  </sequence>\\n</xmeml>`;
  download(`story_${c.id}.xml`, xml);
  post('audit',{id: curCard, msg: 'Экспорт XML (NLE)'});
}

function exportRundown(fmt){
  // MOS делаем "по-минимуму" — реальные ID надо согласовывать с вещательной
  const items = CARDS.filter(c=>c.in_rundown).sort((a,b)=>a.rundown_pos-b.rundown_pos);
  let xml;
  if (fmt==='mos'){
    xml = `<?xml version="1.0" encoding="UTF-8"?>\\n<mos>\\n  <mosID>RF_NEWS_RUNDOWN</mosID>\\n  <storyList>\\n`;
    items.forEach((c,i)=>{ xml += `    <story id="${i+1}" slug="${c.title}" duration="${c.duration||0}" status="${c.status}">\\n      <mosID>story_${c.id}</mosID>\\n      <file>${c.s3}</file>\\n    </story>\\n`; });
    xml += `  </storyList>\\n</mos>`;
    download('rundown.mos.xml', xml);
  } else {
    xml = `<?xml version="1.0" encoding="UTF-8"?>\\n<rundown>\\n`;
    items.forEach((c,i)=>{ xml += `  <item pos="${i+1}" id="${c.id}">\\n    <title>${c.title}</title>\\n    <duration>${c.duration||0}</duration>\\n    <file>${c.s3}</file>\\n    <status>${c.status}</status>\\n  </item>\\n`; });
    xml += `</rundown>`;
    download('rundown.xml', xml);
  }
}

// переключение табов (сделал делегированием, чтобы не плодить onclick)
document.querySelectorAll('.tab').forEach(t=>{
  t.onclick = ()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
    document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));
    t.classList.add('active');
    $('v-'+t.dataset.tab).classList.add('active');
    curTab = t.dataset.tab; render();
  };
});
document.querySelectorAll('.mtab').forEach(t=>{
  t.onclick = ()=>{
    document.querySelectorAll('.mtab').forEach(x=>x.classList.remove('active'));
    document.querySelectorAll('.mview').forEach(x=>x.classList.remove('active'));
    t.classList.add('active');
    $('mv-'+t.dataset.mt).classList.add('active');
  };
});
document.addEventListener('click', e=>{
  if (!e.target.closest('.notif-panel') && !e.target.closest('.bell')) $('np').classList.remove('show');
});

load();
</script></body></html>"""


# ---------------- бэк ----------------
class Handler(BaseHTTPRequestHandler):

    def _payload(self):
        # единая точка — что отдаём в JS, то и в ответе на POST
        return {
            "cards": CARDS, "notifications": NOTIFS,
            "statuses": STATUSES, "rules": RULES,
            "roles": ROLES, "users": USERS,
        }

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        if self.path == "/api":
            self._json(self._payload())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        act = data.get("act")
        role = data.get("role")
        user = data.get("user") or role or "—"
        err = None

        # без try/except вокруг всего — предпочитаю точечные проверки,
        # StopIteration ловлю в конце: единственный сценарий с next()
        try:
            if act == "add":
                if role not in CREATORS:
                    err = f"Создавать заявки могут: {', '.join(CREATORS)}"
                else:
                    new_id = max((c["id"] for c in CARDS), default=0) + 1
                    CARDS.append({
                        "id": new_id, "title": data["title"], "status": "Заявка",
                        "author": user, "deadline": data.get("deadline", ""),
                        "loc": data.get("loc", ""), "crew": "", "operator": "",
                        "journalist": "", "driver": "", "tc": "", "text": "",
                        "text_versions": [], "s3": "s3://rf-news/new.mp4",
                        "media": [], "comments": [],
                        "audit": [f"[{nnow()}] {user}: Создана заявка"],
                        "duration": 60, "in_rundown": False, "rundown_pos": 0,
                    })
                    notify(f"#{new_id} Новая заявка: {data['title']} ({user})")

            elif act == "save":
                c = next(x for x in CARDS if x["id"] == data["id"])
                old_text = c.get("text", "")
                for k in ["title","loc","crew","operator","journalist","driver",
                          "deadline","s3","tc","duration","author"]:
                    if k in data: c[k] = data[k]
                new_text = data.get("text")
                if new_text is not None and new_text != old_text:
                    # новую версию пишем только если текст реально поменялся
                    c["text_versions"].insert(0, {"ts": nnow(), "author": user, "text": new_text})
                c["audit"].insert(0, f"[{nnow()}] {user}: Сохранены изменения")

            elif act == "step":
                c = next(x for x in CARDS if x["id"] == data["id"])
                if role not in RULES.get(c["status"], []):
                    err = f"Нужна роль: {', '.join(RULES[c['status']])}"
                else:
                    idx = STATUSES.index(c["status"]) + data["dir"]
                    if 0 <= idx < len(STATUSES):
                        old = c["status"]
                        c["status"] = STATUSES[idx]
                        c["audit"].insert(0, f"[{nnow()}] {user}: {old} → {c['status']}")
                        notify(f"#{c['id']} {old} → {c['status']}: {c['title']}")

            elif act == "comment":
                c = next(x for x in CARDS if x["id"] == data["id"])
                txt = data["text"]
                c["comments"].insert(0, {"ts": nnow(), "author": user, "text": txt})
                c["audit"].insert(0, f"[{nnow()}] {user}: Комментарий")
                # тут по-хорошему искать по id пользователя, но у нас строки
                for m in re.findall(r"@([А-Яа-яA-Za-z0-9_]+)", txt):
                    notify(f"#{c['id']} {user} упомянул @{m}")

            elif act == "media_add":
                c = next(x for x in CARDS if x["id"] == data["id"])
                c["media"].append({"name": data["name"],
                                   "type": data.get("type", "file"),
                                   "size": data.get("size", "—")})
                c["audit"].insert(0, f"[{nnow()}] {user}: Загружен файл {data['name']}")

            elif act == "rundown_add":
                c = next(x for x in CARDS if x["id"] == data["id"])
                if c["status"] not in ("Утверждено", "В эфире"):
                    err = "В выпуск можно добавлять только утверждённые сюжеты"
                else:
                    c["in_rundown"] = True
                    pos = max((x["rundown_pos"] for x in CARDS if x["in_rundown"]), default=0)
                    c["rundown_pos"] = pos + 1
                    c["audit"].insert(0, f"[{nnow()}] {user}: Добавлено в выпуск")

            elif act == "rundown_remove":
                c = next(x for x in CARDS if x["id"] == data["id"])
                c["in_rundown"] = False
                c["rundown_pos"] = 0
                c["audit"].insert(0, f"[{nnow()}] {user}: Убрано из выпуска")

            elif act == "rundown_move":
                # не самое эффективное (пересобираем весь список), но зато надёжно
                c = next(x for x in CARDS if x["id"] == data["id"])
                items = sorted([x for x in CARDS if x["in_rundown"]], key=lambda x: x["rundown_pos"])
                i = items.index(c); j = i + data["dir"]
                if 0 <= j < len(items):
                    items[i], items[j] = items[j], items[i]
                    for k, it in enumerate(items, 1):
                        it["rundown_pos"] = k

            elif act == "audit":
                c = next(x for x in CARDS if x["id"] == data["id"])
                c["audit"].insert(0, f"[{nnow()}] {user}: {data['msg']}")

            elif act == "notif_read":
                for n in NOTIFS: n["read"] = True

            # else: молча игнорируем — фронт сам не должен такое слать

        except StopIteration:
            err = "Карточка не найдена"

        self._json({"err": err, **self._payload()})


if __name__ == "__main__":
    print("Сервер запущен: http://127.0.0.1:8090")
    HTTPServer(("127.0.0.1", 8090), Handler).serve_forever()