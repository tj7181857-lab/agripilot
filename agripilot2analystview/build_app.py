"""
Builds the AgriPilot farmer app: one self-contained HTML file, no webfonts, no
external requests, works from a cached copy on a 2G connection.  Season data is
inlined from outputs/demo_farm.json so the app opens instantly offline.
"""
import json, os, datetime

OUT = os.path.join(os.path.dirname(__file__), "app", "index_mr_lowbandwidth.html")
data = json.load(open(os.path.join(os.path.dirname(__file__), "outputs", "demo_farm.json")))
summary = json.load(open(os.path.join(os.path.dirname(__file__), "outputs", "summary.json")))

KEEP = ("day", "rain", "etc", "irrigation", "dr", "dr_hat", "raw", "taw", "ks", "n", "spray")
trace = [{k: v for k, v in row.items() if k in KEEP} for row in data["trace"]]
audit = [{"day": a["day"], "status": a["status"],
          "args": {"kind": a["args"]["kind"], "message": a["args"]["message"],
                   "confidence": round(float(a["args"].get("confidence", 0.8)), 2)}}
         for a in data["audit"] if a["day"] <= 96][-45:]
payload = json.dumps({"trace": trace, "audit": audit, "farm": data["farm"],
                      "agent": data["agent"], "baseline": data["baseline"],
                      "summary": {k: v for k, v in summary.items() if isinstance(v, (int, float))}},
                     ensure_ascii=False, separators=(",", ":"))

HTML = """<!doctype html>
<html lang="mr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>AgriPilot &mdash; शेत सल्ला</title>
<style>
:root{
  --ink:#16241d; --ink-soft:#4a5b51; --paper:#f3f2ea; --card:#ffffff;
  --water:#1d6b86; --leaf:#3f7a37; --soil:#8a5a3b; --alert:#bf4520;
  --rule:#d8d7c9; --shadow:0 1px 0 var(--rule);
}
:root:not([data-theme=light]){}
@media (prefers-color-scheme:dark){
 :root:not([data-theme=light]){--ink:#e9ece3;--ink-soft:#9dab9c;--paper:#101511;--card:#19211b;--rule:#2c352d;--water:#5fb6d1;--leaf:#7cc06e;--soil:#c08f68;--alert:#f08055;}
}
:root[data-theme=dark]{--ink:#e9ece3;--ink-soft:#9dab9c;--paper:#101511;--card:#19211b;--rule:#2c352d;--water:#5fb6d1;--leaf:#7cc06e;--soil:#c08f68;--alert:#f08055;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
 font-family:"Noto Sans Devanagari","Nirmala UI",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
 font-size:17px;line-height:1.5;-webkit-text-size-adjust:100%}
.wrap{max-width:430px;margin:0 auto;padding:0 14px 90px}
header{padding:16px 0 10px;border-bottom:2px solid var(--ink)}
.brand{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.brand b{font-size:20px;letter-spacing:-.01em}
.brand span{font-size:13px;color:var(--ink-soft)}
.meta{font-size:13px;color:var(--ink-soft);margin-top:4px}

/* hero: the day's action, the one loud thing in the whole design */
.today{margin:14px 0 0;background:var(--card);border:2px solid var(--ink);border-radius:2px}
.today .band{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--rule)}
.today .band .day{font-variant-numeric:tabular-nums;font-size:13px;color:var(--ink-soft)}
.today .verb{padding:14px;display:flex;gap:14px;align-items:flex-start}
.today .glyph{font-size:40px;line-height:1}
.today h1{margin:0;font-size:26px;line-height:1.15;letter-spacing:-.02em}
.today p{margin:8px 0 0;font-size:16px}
.confi{display:inline-block;margin-top:10px;font-size:12px;padding:3px 8px;border:1px solid var(--rule);border-radius:99px;color:var(--ink-soft)}
.acts{display:flex;border-top:1px solid var(--rule)}
.acts button{flex:1;border:0;padding:15px 8px;font:inherit;font-size:16px;background:transparent;color:var(--ink);cursor:pointer}
.acts button+button{border-left:1px solid var(--rule)}
.acts button.yes{background:var(--leaf);color:#fff;font-weight:600}
.acts button:focus-visible{outline:3px solid var(--water);outline-offset:-3px}
.done{padding:12px 14px;font-size:15px;color:var(--leaf);display:none}

h2{font-size:14px;font-weight:600;margin:26px 0 8px;color:var(--ink-soft)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--rule);border:1px solid var(--rule)}
.cell{background:var(--card);padding:10px 12px}
.cell .n{font-size:22px;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.cell .l{font-size:12px;color:var(--ink-soft)}
.cell .d{font-size:12px;color:var(--leaf)}
.cell .d.bad{color:var(--alert)}

.moist{background:var(--card);border:1px solid var(--rule);padding:12px}
.bar{height:26px;background:linear-gradient(90deg,var(--water),#9cc9d6);position:relative;border:1px solid var(--rule)}
.bar i{position:absolute;top:-6px;bottom:-6px;width:3px;background:var(--ink)}
.bar u{position:absolute;top:0;bottom:0;right:0;background:var(--paper);opacity:.85}
.scale{display:flex;justify-content:space-between;font-size:11px;color:var(--ink-soft);margin-top:4px}

svg{display:block;width:100%;height:auto}
.chartbox{background:var(--card);border:1px solid var(--rule);padding:10px 8px 4px;overflow-x:auto}
.legend{display:flex;gap:14px;font-size:12px;color:var(--ink-soft);padding:6px 4px 0;flex-wrap:wrap}
.legend b{display:inline-block;width:10px;height:10px;margin-right:4px;vertical-align:-1px}

.log{border:1px solid var(--rule);background:var(--card)}
.row{padding:10px 12px;border-bottom:1px solid var(--rule);display:flex;gap:10px;font-size:14px}
.row:last-child{border-bottom:0}
.row .g{font-size:18px}
.row .t{flex:1}
.row .s{font-size:11px;color:var(--ink-soft);white-space:nowrap}
.row.rej .t{opacity:.55;text-decoration:line-through}

.sms{font-family:ui-monospace,"Cascadia Mono",Menlo,monospace;font-size:13px;background:var(--card);
 border:1px dashed var(--soil);padding:10px 12px;white-space:pre-wrap;word-break:break-word}
.tabs{display:flex;gap:0;margin:26px 0 0;border-bottom:2px solid var(--ink)}
.tabs button{flex:1;background:transparent;border:0;padding:11px 6px;font:inherit;font-size:15px;color:var(--ink-soft);cursor:pointer}
.tabs button[aria-selected=true]{color:var(--ink);font-weight:600;box-shadow:inset 0 -3px 0 var(--leaf)}
.pane{display:none}.pane.on{display:block}
footer{margin-top:28px;font-size:12px;color:var(--ink-soft);border-top:1px solid var(--rule);padding-top:12px}
.kb{font-size:11px;color:var(--ink-soft);text-align:right;padding-top:6px}
@media (prefers-reduced-motion:no-preference){.today{transition:border-color .2s}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="brand"><b>AgriPilot</b><span id="fmeta"></span></div>
  <div class="meta" id="fsub"></div>
</header>

<div class="today" id="today"></div>

<div class="tabs" role="tablist">
  <button role="tab" aria-selected="true" data-p="p1">आज</button>
  <button role="tab" aria-selected="false" data-p="p2">हंगाम</button>
  <button role="tab" aria-selected="false" data-p="p3">नोंदी</button>
</div>

<div class="pane on" id="p1">
  <h2>जमिनीतील ओलावा</h2>
  <div class="moist">
    <div class="bar"><u id="dep"></u><i id="mark"></i></div>
    <div class="scale"><span>भरलेले</span><span id="rawlbl">ताण सुरू</span><span>कोरडे</span></div>
    <p style="margin:10px 0 0;font-size:14px" id="mtxt"></p>
  </div>
  <h2>पुढील ७ दिवस</h2>
  <div class="chartbox"><svg id="plan" viewBox="0 0 360 120" role="img" aria-label="सात दिवसांचा आराखडा"></svg></div>
  <h2>SMS आवृत्ती (१६० अक्षरे)</h2>
  <div class="sms" id="sms"></div>
</div>

<div class="pane" id="p2">
  <h2>आजपर्यंत — तुमच्या नेहमीच्या पद्धतीशी तुलना</h2>
  <div class="grid" id="kpi"></div>
  <h2>पाणी आणि ताण</h2>
  <div class="chartbox"><svg id="season" viewBox="0 0 360 170" role="img" aria-label="हंगामातील पाणी"></svg>
    <div class="legend"><span><b style="background:var(--water)"></b>सिंचन</span>
      <span><b style="background:#9cc9d6"></b>पाऊस</span>
      <span><b style="background:var(--soil)"></b>ओलावा घट</span>
      <span><b style="background:var(--alert)"></b>ताण मर्यादा</span></div></div>
  <h2>निविष्ठा वापर</h2>
  <div class="chartbox"><svg id="inputs" viewBox="0 0 360 130" role="img" aria-label="निविष्ठा तुलना"></svg></div>
</div>

<div class="pane" id="p3">
  <h2>सल्ल्यांची नोंद</h2>
  <div class="log" id="log"></div>
  <div class="kb" id="weight"></div>
</div>

<footer>
  AgriPilot हे सल्ला देणारे साधन आहे. अंतिम निर्णय शेतकऱ्याचा.<br>
  <span id="src"></span>
</footer>
</div>

<script id="d" type="application/json">__PAYLOAD__</script>
<script>
const D=JSON.parse(document.getElementById('d').textContent);
const T=D.trace, A=D.audit, F=D.farm;
const CROP={onion:'कांदा',grape:'द्राक्ष',tomato:'टोमॅटो',wheat:'गहू',soybean:'सोयाबीन',cotton:'कापूस'};
const today=Math.min(96,T.length-8);            // demo "current day" of the season
const t=T[today];

document.getElementById('fmeta').textContent=F.id+' · '+F.village;
document.getElementById('fsub').textContent=CROP[F.crop]+' · '+F.area_ha+' हेक्टर · ठिबक · लागवडीनंतर '+today+' दिवस';

/* ---------- hero: today's single most important action ---------- */
const todayCalls=A.filter(a=>a.day===today);
const pick=todayCalls.find(a=>['irrigate','skip_irrigation'].includes(a.args.kind))||todayCalls[0]
 ||{args:{kind:'skip_irrigation',message:'आज विशेष काही नाही.',confidence:.8},status:'executed'};
const GL={irrigate:'💧',skip_irrigation:'🚫',fertilise:'🌱',defer_fertiliser:'⏸',spray:'🐛',no_spray:'✅'};
const VERB={irrigate:'पाणी द्या',skip_irrigation:'आज पाणी नको',fertilise:'खत द्या',
 defer_fertiliser:'खत थांबवा',spray:'फवारणी करा',no_spray:'फवारणी नको'};
const conf=Math.round((pick.args.confidence||.8)*100);
document.getElementById('today').innerHTML=
 '<div class="band"><span class="day">दिवस '+today+'</span><span class="day" style="margin-left:auto">'
 +(t.rain>0?('पाऊस '+t.rain+' मिमी'):'कोरडे')+' · ET '+t.etc+' मिमी</span></div>'
 +'<div class="verb"><div class="glyph">'+(GL[pick.args.kind]||'🌾')+'</div><div>'
 +'<h1>'+(VERB[pick.args.kind]||'सल्ला')+'</h1><p>'+pick.args.message+'</p>'
 +'<span class="confi">खात्री '+conf+'%</span></div></div>'
 +'<div class="acts"><button class="yes" id="ok">केले</button><button id="no">नाही करणार</button></div>'
 +'<div class="done" id="done"></div>';
function answer(txt){document.querySelector('.acts').style.display='none';
 const d=document.getElementById('done');d.style.display='block';d.textContent=txt;}
document.getElementById('ok').onclick=()=>answer('✓ नोंद झाली. उद्या पुन्हा तपासले जाईल.');
document.getElementById('no').onclick=()=>answer('नोंद झाली. कारण विचारून पुढील सल्ले बदलले जातील.');

/* ---------- soil moisture gauge ---------- */
const depl=Math.min(100,100*t.dr/t.taw), rawp=100*t.raw/t.taw;
document.getElementById('dep').style.width=depl+'%';
document.getElementById('mark').style.left=rawp+'%';
document.getElementById('mtxt').textContent=
 'मुळांच्या भागात '+Math.round(t.taw-t.dr)+' मिमी पाणी शिल्लक ('+Math.round(100-depl)+'%). '
 +'ताण सुरू होण्याची मर्यादा '+Math.round(t.raw)+' मिमी घट. सेन्सर अंदाज '+t.dr_hat+' मिमी.';

/* ---------- 7-day plan ---------- */
(function(){const s=document.getElementById('plan'),W=360,H=120,n=7;const days=T.slice(today,today+n);
 const mx=Math.max(12,...days.map(d=>Math.max(d.rain,d.irrigation)));let h='';
 days.forEach((d,i)=>{const x=14+i*48;
  const hr=d.rain/mx*62, hi=d.irrigation/mx*62;
  h+='<rect x="'+x+'" y="'+(86-hr)+'" width="16" height="'+hr+'" fill="#9cc9d6"/>';
  h+='<rect x="'+(x+18)+'" y="'+(86-hi)+'" width="16" height="'+hi+'" fill="var(--water)"/>';
  h+='<text x="'+(x+17)+'" y="100" font-size="10" text-anchor="middle" fill="var(--ink-soft)">दि '+(today+i)+'</text>';
  if(d.irrigation>0)h+='<text x="'+(x+17)+'" y="112" font-size="10" text-anchor="middle" fill="var(--water)">'+Math.round(d.irrigation)+'</text>';});
 h+='<line x1="8" y1="86" x2="352" y2="86" stroke="var(--rule)"/>';
 s.innerHTML=h;})();

/* ---------- SMS preview ---------- */
document.getElementById('sms').textContent=(GL[pick.args.kind]||'')+' '+pick.args.message.slice(0,150);

/* ---------- KPI cells ---------- */
const a=D.agent,b=D.baseline;
const pct=(x,y)=>Math.round((x/y-1)*100);
const cells=[['उत्पादन',a.yield_t_ha.toFixed(1)+' टन/हे',pct(a.yield_t_ha,b.yield_t_ha)],
 ['सिंचन',Math.round(a.irrigation_mm)+' मिमी',-pct(a.irrigation_mm,b.irrigation_mm)],
 ['नत्र',Math.round(a.n_applied)+' किलो/हे',-pct(a.n_applied,b.n_applied)],
 ['रासायनिक फवारण्या',a.chem_sprays+' (+ '+a.bio_sprays+' जैविक)',-pct(a.chem_sprays,b.chem_sprays)],
 ['पाणी उत्पादकता',a.water_productivity_kg_m3.toFixed(2)+' किलो/घमी',pct(a.water_productivity_kg_m3,b.water_productivity_kg_m3)],
 ['निव्वळ नफा','₹'+Math.round(a.gross_margin).toLocaleString('en-IN'),pct(a.gross_margin,b.gross_margin)]];
document.getElementById('kpi').innerHTML=cells.map(c=>
 '<div class="cell"><div class="n">'+c[1]+'</div><div class="l">'+c[0]+'</div>'
 +'<div class="d'+(c[2]<0?' bad':'')+'">'+(c[2]>0?'+':'')+c[2]+'% नेहमीच्या पद्धतीपेक्षा</div></div>').join('');

/* ---------- season chart ---------- */
(function(){const s=document.getElementById('season'),W=360,H=170,L=30,R=6,Tp=8,B=22;
 const n=T.length,x=i=>L+(W-L-R)*i/(n-1);
 const mxw=Math.max(...T.map(d=>Math.max(d.rain,d.irrigation,d.dr)));
 const y=v=>Tp+(H-Tp-B)*(1-v/mxw);let h='';
 h+='<line x1="'+L+'" y1="'+(H-B)+'" x2="'+(W-R)+'" y2="'+(H-B)+'" stroke="var(--rule)"/>';
 T.forEach((d,i)=>{if(d.rain>0)h+='<rect x="'+(x(i)-1)+'" y="'+y(d.rain)+'" width="2" height="'+(H-B-y(d.rain))+'" fill="#9cc9d6"/>';});
 T.forEach((d,i)=>{if(d.irrigation>0)h+='<rect x="'+(x(i)-1)+'" y="'+y(d.irrigation)+'" width="2" height="'+(H-B-y(d.irrigation))+'" fill="var(--water)"/>';});
 h+='<path d="'+T.map((d,i)=>(i?'L':'M')+x(i).toFixed(1)+' '+y(d.dr).toFixed(1)).join(' ')+'" fill="none" stroke="var(--soil)" stroke-width="1.6"/>';
 h+='<path d="'+T.map((d,i)=>(i?'L':'M')+x(i).toFixed(1)+' '+y(d.raw).toFixed(1)).join(' ')+'" fill="none" stroke="var(--alert)" stroke-dasharray="3 3"/>';
 h+='<line x1="'+x(today)+'" y1="'+Tp+'" x2="'+x(today)+'" y2="'+(H-B)+'" stroke="var(--ink)" stroke-width="1"/>';
 h+='<text x="'+(x(today)+3)+'" y="'+(Tp+9)+'" font-size="9" fill="var(--ink-soft)">आज</text>';
 [0,50,100,150].filter(v=>v<n).forEach(v=>h+='<text x="'+x(v)+'" y="'+(H-8)+'" font-size="9" text-anchor="middle" fill="var(--ink-soft)">दि '+v+'</text>');
 h+='<text x="4" y="'+(Tp+8)+'" font-size="9" fill="var(--ink-soft)">'+Math.round(mxw)+' मिमी</text>';
 s.innerHTML=h;})();

/* ---------- inputs comparison ---------- */
(function(){const s=document.getElementById('inputs'),W=360,H=130;
 const rows=[['पाणी (मिमी)',a.irrigation_mm,b.irrigation_mm],['नत्र (किलो)',a.n_applied,b.n_applied],
  ['फवारण्या',a.chem_sprays+a.bio_sprays,b.chem_sprays],['नत्र वाहून (किलो)',a.n_leached,b.n_leached]];
 let h='';rows.forEach((r,i)=>{const yy=16+i*30,mx=Math.max(r[1],r[2])||1;
  h+='<text x="0" y="'+(yy-3)+'" font-size="10" fill="var(--ink-soft)">'+r[0]+'</text>';
  h+='<rect x="120" y="'+(yy-11)+'" width="'+(210*r[2]/mx)+'" height="9" fill="var(--rule)"/>';
  h+='<rect x="120" y="'+(yy-1)+'" width="'+(210*r[1]/mx)+'" height="9" fill="var(--leaf)"/>';
  h+='<text x="336" y="'+(yy+7)+'" font-size="9" text-anchor="end" fill="var(--ink-soft)">'+Math.round(r[1])+' / '+Math.round(r[2])+'</text>';});
 h+='<text x="120" y="126" font-size="9" fill="var(--ink-soft)">हिरवा = AgriPilot, करडा = नेहमीची पद्धत</text>';
 s.innerHTML=h;})();

/* ---------- advisory log ---------- */
document.getElementById('log').innerHTML=A.slice(-40).reverse().map(c=>
 '<div class="row'+(c.status==='rejected'?' rej':'')+'"><span class="g">'+(GL[c.args.kind]||'🌾')+'</span>'
 +'<span class="t">'+c.args.message+'</span><span class="s">दि '+c.day+'<br>'+(c.status==='executed'?'केले':'नाकारले')+'</span></div>').join('');
document.getElementById('weight').textContent='पान '+(new Blob([document.documentElement.outerHTML]).size/1024).toFixed(0)+' KB · बाह्य विनंती नाही · ऑफलाइन चालते';
document.getElementById('src').textContent='हंगाम सिम्युलेशन · '+A.length+' सल्ले · स्वीकृती '+Math.round(a.adoption_rate*100)+'%';

/* ---------- tabs ---------- */
document.querySelectorAll('.tabs button').forEach(btn=>btn.onclick=()=>{
 document.querySelectorAll('.tabs button').forEach(b=>b.setAttribute('aria-selected',b===btn));
 document.querySelectorAll('.pane').forEach(p=>p.classList.toggle('on',p.id===btn.dataset.p));});
</script>
</body></html>"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(HTML.replace("__PAYLOAD__", payload))
print("wrote", OUT, round(os.path.getsize(OUT) / 1024, 1), "KB")
