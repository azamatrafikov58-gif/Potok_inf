import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

STATUSES = ["Заявка", "Съёмка", "В работе", "Текст готов", "Монтаж", "Проверка", "Утверждено", "В эфире"]
RULES = {
    "Заявка": ["Администратор-продюсер", "Шеф-редактор"],
    "Съёмка": ["Телеоператор", "Водитель", "Администратор-продюсер"],
    "В работе": ["Журналист"],
    "Текст готов": ["Редактор", "Шеф-редактор"],
    "Монтаж": ["Монтажёр"],
    "Проверка": ["Режиссёр монтажа", "Шеф-редактор"],
    "Утверждено": ["Выпускающий режиссёр", "Шеф-редактор"],
    "В эфире": ["Выпускающий режиссёр"]
}

CARDS = [
    {"id": 1, "title": "Открытие нового моста через реку", "status": "Заявка", "loc": "Южный обход, 14 км",
     "crew": "Оператор: Смирнов, Водитель: Козлов", "tc": "00:00 - Общий план",
     "text": "В городе открыли движение по новому мостовому переходу.", "s3": "s3://rf-news/bridge.mp4",
     "audit": ["[10:00] Система: Карточка создана"]},
    {"id": 2, "title": "Запуск IT-кластера в технопарке", "status": "В работе", "loc": "ул. Инноваций, 1",
     "crew": "Оператор: Иванов, Водитель: Петров", "tc": "00:15 - Синхрон спикера",
     "text": "Резидентами кластера стали тридцать российских компаний.", "s3": "s3://rf-news/it.mp4",
     "audit": ["[10:15] Продюсер: Переведено в работу"]},
    {"id": 3, "title": "Итоги дорожного ремонта за неделю", "status": "Утверждено", "loc": "Администрация",
     "crew": "Оператор: Сидоров, Водитель: Орлов", "tc": "00:05 - Проезд техники",
     "text": "Более двадцати километров дорог обновили за неделю.", "s3": "s3://rf-news/road.mp4",
     "audit": ["[11:00] Шеф-редактор: Утверждено в эфир"]}
]

HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Фабрика Новостей</title>
<style>
body{font-family:sans-serif;background:#0f172a;color:#fff;margin:0}
header{background:#1e293b;padding:12px 20px;display:flex;justify-content:space-between}
.bar{background:#1e293b;padding:10px 20px;display:flex;gap:8px;border-top:1px solid #334155}
input,select,textarea{background:#0f172a;color:#fff;border:1px solid #475569;padding:6px;border-radius:5px}
button{background:#2563eb;color:#fff;border:none;padding:6px 12px;border-radius:5px;cursor:pointer}
.board{display:flex;gap:10px;padding:15px;overflow-x:auto}
.col{min-width:210px;background:#1e293b;padding:10px;border-radius:8px;border:1px solid #334155}
.card{background:#0f172a;padding:10px;margin-top:8px;border-radius:6px;border:1px solid #334155;cursor:pointer}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);justify-content:center;align-items:center}
.box{background:#1e293b;padding:20px;border-radius:10px;width:750px;max-width:95vw}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
input,textarea{width:100%;box-sizing:border-box;margin-top:4px}
#prm{display:none;position:fixed;inset:0;background:#000;color:#fff;padding:40px;font-size:40px}
</style></head><body>
<header><b>Фабрика Новостей</b><div>Роль: <select id="role" onchange="draw()">
<option>Администратор-продюсер</option><option>Водитель</option><option>Телеоператор</option>
<option>Журналист</option><option>Редактор</option><option>Шеф-редактор</option>
<option>Монтажёр</option><option>Режиссёр монтажа</option><option>Выпускающий режиссёр</option>
</select></div></header>
<div class="bar"><input id="nt" placeholder="Тема заявки..." style="width:240px"><input id="nl" placeholder="Адрес..." style="width:180px">
<button onclick="add()">+ Заявка</button><button onclick="nt.value='Срочно: Запуск скоростного трамвая';nl.value='Депо №2'" style="background:#334155">ТАСС/РИА</button></div>
<div class="board" id="board"></div>
<div class="modal" id="m"><div class="box">
<div style="display:flex;justify-content:space-between"><b id="mh"></b><div>
<button onclick="step(-1)" style="background:#334155">← Назад</button> <button onclick="step(1)" style="background:#10b981;color:#000">Дальше →</button> <button onclick="m.style.display='none'" style="background:#dc2626">✕</button>
</div></div><small id="hint" style="color:#60a5fa"></small>
<div class="grid"><div>
Заголовок<input id="ft">Адрес<input id="fl">Экипаж<input id="fc">S3 Файл<input id="fm">
<div style="margin-top:8px"><button onclick="xml()" style="background:#334155">Экспорт XML</button> <button onclick="prm.innerText=ft.value+'\\n\\n'+ftx.value;prm.style.display='block'" style="background:#334155">Суфлёр</button></div>
</div><div>
Таймкоды<textarea id="ftc" rows="3"></textarea>Текст<textarea id="ftx" rows="6"></textarea>
</div></div><br><button onclick="save()">Сохранить</button>
<h4>Журнал аудита </h4><div id="au" style="font-size:12px;background:#0f172a;padding:8px;max-height:90px;overflow-y:auto"></div>
</div></div>
<div id="prm" onclick="this.style.display='none'"></div>
<script>
const ST=["Заявка","Съёмка","В работе","Текст готов","Монтаж","Проверка","Утверждено","В эфире"];
const RL={"Заявка":["Администратор-продюсер","Шеф-редактор"],"Съёмка":["Телеоператор","Водитель","Администратор-продюсер"],"В работе":["Журналист"],"Текст готов":["Редактор","Шеф-редактор"],"Монтаж":["Монтажёр"],"Проверка":["Режиссёр монтажа","Шеф-редактор"],"Утверждено":["Выпускающий режиссёр","Шеф-редактор"],"В эфире":["Выпускающий режиссёр"]};
let cards=[],cid=null;
async function load(){cards=await(await fetch('/api')).json();draw();}
function draw(){
  board.innerHTML='';
  ST.forEach(s=>{
    let col=document.createElement('div');col.className='col';
    if((RL[s]||[]).includes(role.value))col.style.borderColor='#3b82f6';
    col.innerHTML='<b>'+s+'</b>';
    cards.filter(c=>c.status===s).forEach(c=>{
      let d=document.createElement('div');d.className='card';
      d.innerHTML='<b>#'+c.id+' '+c.title+'</b><br><small style=color:#94a3b8>'+c.loc+'</small>';
      d.onclick=()=>op(c.id);col.appendChild(d);
    });board.appendChild(col);
  });
}
async function post(act,data){
  let r=await fetch('/api',{method:'POST',body:JSON.stringify({act,role:role.value,...data})});
  let res=await r.json();if(res.err)return alert(res.err);cards=res.cards;draw();if(cid)op(cid);
}
function add(){if(nt.value){post('add',{title:nt.value,loc:nl.value||'Выезд'});nt.value='';}}
function op(id){
  cid=id;let c=cards.find(x=>x.id===id);if(!c)return;
  mh.innerText='#'+c.id+' • '+c.status;hint.innerText='Ответственные: '+(RL[c.status]||[]).join(', ');
  ft.value=c.title;fl.value=c.loc;fc.value=c.crew;fm.value=c.s3;ftc.value=c.tc;ftx.value=c.text;
  au.innerHTML=c.audit.map(x=>'<div>'+x+'</div>').join('');m.style.display='flex';
}
function save(){post('save',{id:cid,title:ft.value,loc:fl.value,crew:fc.value,s3:fm.value,tc:ftc.value,text:ftx.value});}
function step(dir){post('step',{id:cid,dir});}
function xml(){
  let a=document.createElement('a');
  a.href='data:text/xml;charset=utf-8,'+encodeURIComponent('<xmeml><title>'+ft.value+'</title><file>'+fm.value+'</file></xmeml>');
  a.download='story_'+cid+'.xml';a.click();post('audit',{id:cid,msg:'Экспорт XML (NLE)'});
}
load();
</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(CARDS).encode("utf-8"))
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        act, role = data.get("act"), data.get("role")
        now = datetime.now().strftime("%H:%M:%S")
        err = None

        if act == "add":
            if role not in ["Администратор-продюсер", "Шеф-редактор"]:
                err = "Создавать заявки может только Продюсер или Шеф-редактор"
            else:
                CARDS.append({
                    "id": len(CARDS) + 1, "title": data["title"], "status": "Заявка",
                    "loc": data["loc"], "crew": "Не назначен", "tc": "", "text": "",
                    "s3": "s3://rf-news/new.mp4", "audit": [f"[{now}] {role}: Создана заявка"]
                })
        elif act == "save":
            c = next(x for x in CARDS if x["id"] == data["id"])
            c.update({"title": data["title"], "loc": data["loc"], "crew": data["crew"],
                      "s3": data["s3"], "tc": data["tc"], "text": data["text"]})
            c["audit"].insert(0, f"[{now}] {role}: Сохранены изменения")
        elif act == "step":
            c = next(x for x in CARDS if x["id"] == data["id"])
            if role not in RULES.get(c["status"], []):
                err = f"Нужна роль: {', '.join(RULES[c['status']])}"
            else:
                idx = STATUSES.index(c["status"]) + data["dir"]
                if 0 <= idx < len(STATUSES):
                    old = c["status"]
                    c["status"] = STATUSES[idx]
                    c["audit"].insert(0, f"[{now}] {role}: {old} -> {c['status']}")
        elif act == "audit":
            c = next(x for x in CARDS if x["id"] == data["id"])
            c["audit"].insert(0, f"[{now}] {role}: {data['msg']}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"err": err, "cards": CARDS}).encode("utf-8"))

if __name__ == "__main__":
    print("Сервер запущен: http://127.0.0.1:8090")
    HTTPServer(("127.0.0.1", 8090), Handler).serve_forever()
