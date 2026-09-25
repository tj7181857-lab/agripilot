"""
Builds the professional English AgriPilot dashboard: one self-contained HTML
file with a farmer-facing simple view, a full analyst dashboard, and an
AI assistant grounded in this season's actual data (via the claude.use
"sample" runtime capability, with a rule-based offline fallback when that
capability isn't granted).
"""
import json, os

BASE = os.path.dirname(__file__)
farms = json.load(open(os.path.join(BASE, "outputs", "demo_farms_en.json")))
summary = json.load(open(os.path.join(BASE, "outputs", "summary.json")))

CROP_LABEL = {"onion": "Onion", "tomato": "Tomato", "grape": "Grape",
              "soybean": "Soybean", "wheat": "Wheat", "cotton": "Cotton"}
for f in farms:
    f["crop_label"] = CROP_LABEL[f["crop"]]
    f["audit"] = f["audit"][-70:]   # cap advisory-log history for page weight

summary_numeric = {k: v for k, v in summary.items() if isinstance(v, (int, float))}
by_crop = summary.get("by_crop", {})
means = summary.get("means", {})

ml_path = os.path.join(BASE, "outputs", "ml_summary.json")
ml = json.load(open(ml_path)) if os.path.exists(ml_path) else None

payload = json.dumps({
    "farms": farms,
    "pilot": {"headline": summary_numeric, "by_crop": by_crop, "means": means,
              "n_farms": summary.get("n_farms"), "n_farm_seasons": summary.get("n_farm_seasons")},
    "ml": ml,
}, ensure_ascii=False, separators=(",", ":"))

print("payload size:", round(len(payload) / 1024, 1), "KB")

HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>AgriPilot &mdash; Farm Decision Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --paper:#f4f6ee; --card:#ffffff; --ink:#202b1c; --ink-soft:#5c6b55; --ink-faint:#8b9682;
  --line:#dde3d0; --line-strong:#c7d0b8;
  --leaf:#2f7a3d; --leaf-deep:#1f5c2b; --leaf-tint:#e6f1e2;
  --water:#1c6e8c; --water-tint:#e2eff3;
  --soil:#9a5b2e; --soil-tint:#f4e9dd;
  --gold:#b9852a; --gold-tint:#f8eed9;
  --alert:#b3401f; --alert-tint:#fbe8e1;
  --radius:10px; --radius-sm:6px;
  --sidebar-w:236px;
}
@media (prefers-color-scheme:dark){
 :root:not([data-theme=light]){
  --paper:#12160f; --card:#1a2016; --ink:#e9ede2; --ink-soft:#a7b39c; --ink-faint:#71806a;
  --line:#2b3325; --line-strong:#394331;
  --leaf:#5fbf6d; --leaf-deep:#7fd68b; --leaf-tint:#1d2a1c;
  --water:#5cb8d6; --water-tint:#152730;
  --soil:#d19a63; --soil-tint:#2a2118;
  --gold:#dcae52; --gold-tint:#2c2413;
  --alert:#e5765a; --alert-tint:#2e1912;
 }
}
:root[data-theme=dark]{
 --paper:#12160f; --card:#1a2016; --ink:#e9ede2; --ink-soft:#a7b39c; --ink-faint:#71806a;
 --line:#2b3325; --line-strong:#394331;
 --leaf:#5fbf6d; --leaf-deep:#7fd68b; --leaf-tint:#1d2a1c;
 --water:#5cb8d6; --water-tint:#152730;
 --soil:#d19a63; --soil-tint:#2a2118;
 --gold:#dcae52; --gold-tint:#2c2413;
 --alert:#e5765a; --alert-tint:#2e1912;
}
*{box-sizing:border-box}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
html,body{height:100%}
body{margin:0;background:var(--paper);color:var(--ink);
 font-family:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
 font-size:15.5px;line-height:1.5;-webkit-text-size-adjust:100%;
 padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
.num{font-variant-numeric:tabular-nums}
.mono{font-family:"IBM Plex Mono",ui-monospace,monospace}
button{font-family:inherit}
a{color:var(--water)}
:focus-visible{outline:2px solid var(--water);outline-offset:2px}

/* ---------------- shell ---------------- */
.shell{display:flex;min-height:100%}
.sidebar{width:var(--sidebar-w);flex:none;border-right:1px solid var(--line);
 padding:18px 14px;display:flex;flex-direction:column;gap:18px;position:sticky;top:0;
 height:100vh;overflow-y:auto}
.brand{display:flex;align-items:center;gap:9px;padding:2px 6px 6px}
.brand .mark{width:30px;height:30px;border-radius:7px;background:var(--leaf);color:#fff;
 display:flex;align-items:center;justify-content:center;font-size:16px;flex:none}
.brand b{font-size:16px;letter-spacing:-.01em}
.brand span{display:block;font-size:10.5px;color:var(--ink-faint);letter-spacing:.03em}

.farmswitch{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:10px}
.farmswitch .lbl{font-size:11px;color:var(--ink-faint);margin-bottom:6px}
.farmlist{display:flex;flex-direction:column;gap:3px}
.farmbtn{display:flex;align-items:center;gap:9px;width:100%;text-align:left;background:transparent;
 border:1px solid transparent;border-radius:var(--radius-sm);padding:7px 8px;cursor:pointer;color:var(--ink)}
.farmbtn:hover{background:var(--paper)}
.farmbtn.on{background:var(--leaf-tint);border-color:var(--leaf);color:var(--leaf-deep);font-weight:600}
.farmbtn .dot{width:8px;height:8px;border-radius:50%;background:var(--soil);flex:none}
.farmbtn.on .dot{background:var(--leaf)}
.farmbtn .fb-name{font-size:13.5px;display:block;line-height:1.25}
.farmbtn .fb-sub{font-size:11px;color:var(--ink-faint)}
.farmbtn.on .fb-sub{color:var(--leaf-deep);opacity:.75}

nav.mainnav{display:flex;flex-direction:column;gap:2px}
.navbtn{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:var(--radius-sm);
 background:transparent;border:0;color:var(--ink-soft);font-size:14px;cursor:pointer;text-align:left}
.navbtn:hover{background:var(--card);color:var(--ink)}
.navbtn.on{background:var(--card);color:var(--ink);font-weight:600;box-shadow:inset 2px 0 0 var(--leaf)}
.navbtn .ic{width:18px;text-align:center;font-size:15px}

.sidefoot{margin-top:auto;padding-top:10px;border-top:1px solid var(--line)}
.modeswitch{display:flex;background:var(--card);border:1px solid var(--line);border-radius:99px;padding:3px}
.modeswitch button{flex:1;border:0;background:transparent;padding:6px 4px;font-size:12px;border-radius:99px;
 color:var(--ink-faint);cursor:pointer}
.modeswitch button.on{background:var(--leaf);color:#fff}
.sidefoot .hint{font-size:10.5px;color:var(--ink-faint);margin-top:8px;line-height:1.4}

.main{flex:1;min-width:0}
.topbar{display:flex;align-items:center;gap:12px;padding:14px 26px;border-bottom:1px solid var(--line);
 position:sticky;top:0;background:color-mix(in srgb, var(--paper) 92%, transparent);backdrop-filter:blur(6px);z-index:5}
.topbar h1{font-size:18px;margin:0;letter-spacing:-.01em;font-weight:600}
.topbar .crumb{font-size:12.5px;color:var(--ink-faint)}
.topbar .spacer{flex:1}
.pill{font-size:11.5px;padding:4px 10px;border-radius:99px;border:1px solid var(--line);color:var(--ink-soft)}
.menubtn{display:none;border:1px solid var(--line);background:var(--card);border-radius:var(--radius-sm);
 width:34px;height:34px;font-size:16px;cursor:pointer;color:var(--ink)}

.content{padding:22px 26px 90px;max-width:1180px}
.pane{display:none}
.pane.on{display:block}
h2.sec{font-size:12.5px;font-weight:600;color:var(--ink-faint);text-transform:none;letter-spacing:.01em;
 margin:30px 0 10px}
h2.sec:first-child{margin-top:0}
.helptext{font-size:13px;color:var(--ink-soft);margin:-4px 0 14px;max-width:62ch}

/* ---------------- today hero ---------------- */
.hero{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
.hero .top{display:flex;justify-content:space-between;align-items:center;padding:11px 18px;
 border-bottom:1px solid var(--line);font-size:12.5px;color:var(--ink-faint)}
.hero .top .wx{display:flex;gap:14px}
.hero .body{display:flex;gap:18px;padding:22px 18px 18px;align-items:flex-start}
.hero .glyph{font-size:42px;line-height:1;flex:none;width:56px;text-align:center}
.hero h1{margin:0;font-size:25px;letter-spacing:-.015em;font-weight:700}
.hero p{margin:9px 0 0;font-size:15px;color:var(--ink);max-width:56ch}
.confi{display:inline-flex;align-items:center;gap:6px;margin-top:12px;font-size:11.5px;
 padding:4px 10px;border-radius:99px;background:var(--paper);border:1px solid var(--line);color:var(--ink-soft)}
.confi i{width:6px;height:6px;border-radius:50%;background:var(--leaf)}
.hero .acts{display:flex;border-top:1px solid var(--line)}
.hero .acts button{flex:1;border:0;padding:14px 8px;font-size:14.5px;background:transparent;
 color:var(--ink);cursor:pointer;font-weight:500}
.hero .acts button+button{border-left:1px solid var(--line)}
.hero .acts button.yes{background:var(--leaf);color:#fff}
.hero .acts button.yes:hover{background:var(--leaf-deep)}
.hero .acts button.no:hover{background:var(--alert-tint);color:var(--alert)}
.hero .done{padding:13px 18px;font-size:14px;color:var(--leaf-deep);display:none;background:var(--leaf-tint)}

.queue{display:flex;flex-direction:column;gap:8px;margin-top:10px}
.qrow{display:flex;gap:10px;align-items:center;background:var(--card);border:1px solid var(--line);
 border-radius:var(--radius-sm);padding:10px 12px;font-size:13.5px}
.qrow .g{font-size:16px}
.qrow .t{flex:1;color:var(--ink)}
.qrow .s{font-size:11px;color:var(--ink-faint)}

/* ---------------- kpi + grids ---------------- */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);
 border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
.kpi{background:var(--card);padding:14px 16px}
.kpi .n{font-size:23px;font-weight:600;letter-spacing:-.015em}
.kpi .l{font-size:12px;color:var(--ink-faint);margin-top:2px}
.kpi .d{font-size:11.5px;margin-top:7px;display:inline-flex;align-items:center;gap:4px}
.kpi .d.good{color:var(--leaf-deep)}
.kpi .d.bad{color:var(--alert)}

.grid2{display:grid;grid-template-columns:1.3fr 1fr;gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:16px 18px}
.card h3{margin:0 0 3px;font-size:14px;font-weight:600}
.card .sub{font-size:12px;color:var(--ink-faint);margin-bottom:12px}

.moist .bar{height:28px;border-radius:5px;position:relative;overflow:hidden;
 background:linear-gradient(90deg,var(--water),color-mix(in srgb, var(--water) 30%, var(--water-tint)))}
.moist .bar u{position:absolute;inset:0 0 0 auto;background:var(--paper);opacity:.9}
.moist .bar i{position:absolute;top:-5px;bottom:-5px;width:2px;background:var(--alert)}
.moist .scale{display:flex;justify-content:space-between;font-size:11px;color:var(--ink-faint);margin-top:6px}
.moist .readout{margin-top:12px;font-size:13px;color:var(--ink-soft)}
.moist .readout b{color:var(--ink);font-weight:600}

.chartbox{overflow-x:auto}
svg{display:block;width:100%;height:auto}
.legend{display:flex;gap:16px;font-size:11.5px;color:var(--ink-soft);padding-top:8px;flex-wrap:wrap}
.legend span{display:inline-flex;align-items:center;gap:5px}
.legend b{display:inline-block;width:10px;height:10px;border-radius:2px}

.log{border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;background:var(--card)}
.logfilter{display:flex;gap:8px;margin-bottom:10px}
.logfilter button{border:1px solid var(--line);background:var(--card);border-radius:99px;
 padding:6px 13px;font-size:12.5px;color:var(--ink-soft);cursor:pointer}
.logfilter button.on{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.row{padding:12px 16px;border-bottom:1px solid var(--line);display:flex;gap:12px;font-size:14px;align-items:flex-start}
.row:last-child{border-bottom:0}
.row .g{font-size:18px;flex:none}
.row .t{flex:1;color:var(--ink)}
.row .s{font-size:11px;color:var(--ink-faint);white-space:nowrap;text-align:right}
.row.rej{background:color-mix(in srgb, var(--alert-tint) 55%, var(--card))}
.row.rej .t{color:var(--ink-soft)}
.tag{display:inline-block;font-size:10px;padding:1px 7px;border-radius:99px;margin-top:3px}
.tag.ok{background:var(--leaf-tint);color:var(--leaf-deep)}
.tag.rej{background:var(--alert-tint);color:var(--alert)}

/* ---------------- compare (pilot-wide) ---------------- */
.pilotbanner{display:flex;gap:0;border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;
 background:var(--card);margin-bottom:18px}
.pilotbanner .seg{flex:1;padding:15px 16px;border-left:1px solid var(--line)}
.pilotbanner .seg:first-child{border-left:0}
.pilotbanner .seg .n{font-size:21px;font-weight:600}
.pilotbanner .seg .l{font-size:11.5px;color:var(--ink-faint);margin-top:2px}
.croprow{display:grid;grid-template-columns:110px 1fr 1fr 1fr 1fr;gap:10px;align-items:center;
 padding:10px 4px;border-bottom:1px solid var(--line);font-size:13px}
.croprow.head{color:var(--ink-faint);font-size:11px}
.croprow .cname{font-weight:600}
.hbarwrap{background:var(--line);border-radius:3px;height:7px;overflow:hidden}
.hbar{height:100%;background:var(--leaf)}
.hbar.neg{background:var(--alert)}

/* ---------------- assistant ---------------- */
.chatwrap{display:flex;flex-direction:column;height:calc(100vh - 150px);max-height:760px;
 border:1px solid var(--line);border-radius:var(--radius);background:var(--card);overflow:hidden}
.chathead{padding:12px 16px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:9px}
.chathead .av{width:26px;height:26px;border-radius:7px;background:var(--leaf);color:#fff;display:flex;
 align-items:center;justify-content:center;font-size:13px;flex:none}
.chathead b{font-size:13.5px}
.chathead .sub{font-size:11.5px;color:var(--ink-faint)}
.chatlog{flex:1;overflow-y:auto;padding:16px}
.bubble{max-width:80%;padding:10px 13px;border-radius:11px;font-size:14px;line-height:1.5;margin-bottom:10px;
 white-space:pre-wrap}
.bubble.user{margin-left:auto;background:var(--leaf);color:#fff;border-bottom-right-radius:3px}
.bubble.bot{background:var(--paper);border:1px solid var(--line);border-bottom-left-radius:3px}
.bubble.sys{background:transparent;color:var(--ink-faint);font-size:12px;text-align:center;max-width:100%;
 margin:6px auto}
.chips{display:flex;gap:7px;flex-wrap:wrap;padding:0 16px 12px}
.chip{border:1px solid var(--line);background:var(--card);border-radius:99px;padding:7px 12px;
 font-size:12.5px;color:var(--ink-soft);cursor:pointer}
.chip:hover{border-color:var(--leaf);color:var(--leaf-deep)}
.chatinput{display:flex;gap:8px;padding:12px 14px;border-top:1px solid var(--line)}
.chatinput input{flex:1;border:1px solid var(--line);border-radius:99px;padding:10px 15px;font-size:14px;
 background:var(--paper);color:var(--ink);font-family:inherit}
.chatinput input:focus{outline:2px solid var(--leaf);outline-offset:1px}
.chatinput button{border:0;background:var(--leaf);color:#fff;border-radius:99px;width:40px;height:40px;
 font-size:16px;cursor:pointer;flex:none}
.chatinput button:disabled{opacity:.5;cursor:default}
.typing{display:inline-flex;gap:3px}
.typing i{width:5px;height:5px;border-radius:50%;background:var(--ink-faint);animation:blink 1.1s infinite}
.typing i:nth-child(2){animation-delay:.15s}.typing i:nth-child(3){animation-delay:.3s}
@keyframes blink{0%,60%,100%{opacity:.25}30%{opacity:1}}

.mlgrid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.mlcard{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:16px 18px}
.mlcard h3{margin:0 0 2px;font-size:14.5px;font-weight:600;display:flex;align-items:center;gap:8px}
.mltag{font-size:10px;padding:2px 8px;border-radius:99px;font-weight:600;letter-spacing:.02em}
.mltag.sup{background:var(--water-tint);color:var(--water)}
.mltag.uns{background:var(--gold-tint);color:var(--gold)}
.mltag.ano{background:var(--alert-tint);color:var(--alert)}
.mltag.rl{background:var(--leaf-tint);color:var(--leaf-deep)}
.mlcard .sub{font-size:12px;color:var(--ink-faint);margin:2px 0 12px}
.mlstat{display:flex;gap:18px;margin-bottom:12px}
.mlstat .n{font-size:24px;font-weight:600;letter-spacing:-.01em}
.mlstat .l{font-size:11px;color:var(--ink-faint)}
.mlbar-row{display:flex;align-items:center;gap:8px;font-size:12px;margin:5px 0}
.mlbar-row .fname{width:120px;flex:none;color:var(--ink-soft);text-align:right;font-size:11.5px}
.mlbar-track{flex:1;height:8px;background:var(--line);border-radius:3px;overflow:hidden}
.mlbar-fill{height:100%;background:var(--water)}
.mlbar-val{width:46px;flex:none;font-size:11px;color:var(--ink-faint);font-variant-numeric:tabular-nums}
.clusterlegend{display:flex;flex-wrap:wrap;gap:10px;font-size:11.5px;color:var(--ink-soft);margin-top:8px}
.clusterlegend span{display:inline-flex;align-items:center;gap:5px}
.clusterlegend b{width:9px;height:9px;border-radius:50%;display:inline-block}
.mlnote{font-size:12px;color:var(--ink-faint);margin-top:10px;line-height:1.5}

footer.note{margin-top:30px;font-size:12px;color:var(--ink-faint);border-top:1px solid var(--line);
 padding-top:12px;max-width:70ch}

/* ---------------- farmer-simple mode ---------------- */
body[data-mode="farmer"] .analyst-only{display:none !important}
body[data-mode="farmer"] .navbtn[data-p="season"],
body[data-mode="farmer"] .navbtn[data-p="compare"],
body[data-mode="farmer"] .navbtn[data-p="ml"]{display:none}
body[data-mode="farmer"] .hero h1{font-size:29px}
body[data-mode="farmer"] .hero p{font-size:16.5px}

/* ---------------- responsive ---------------- */
@media (max-width:920px){
 .grid2{grid-template-columns:1fr}
 .kpis{grid-template-columns:repeat(2,1fr)}
}
@media (max-width:760px){
 .sidebar{position:fixed;left:0;top:0;bottom:0;z-index:20;transform:translateX(-100%);
  transition:transform .2s ease;box-shadow:0 0 0 100vw rgba(0,0,0,0);width:78vw;max-width:300px}
 .sidebar.open{transform:translateX(0);box-shadow:0 0 40px rgba(0,0,0,.25)}
 .menubtn{display:block}
 .content{padding:16px 16px 90px}
 .topbar{padding:12px 14px}
 .pilotbanner{flex-wrap:wrap}
 .pilotbanner .seg{flex:1 1 50%;border-left:0;border-top:1px solid var(--line)}
 .pilotbanner .seg:nth-child(-n+2){border-top:0}
 .croprow{grid-template-columns:80px 1fr 1fr;row-gap:4px}
 .croprow .c4,.croprow .c5{display:none}
}
.scrim{display:none;position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:15}
.scrim.on{display:block}
</style>
</head>
<body data-mode="farmer">
<div class="scrim" id="scrim"></div>
<div class="shell">

<aside class="sidebar" id="sidebar">
  <div class="brand"><div class="mark">A</div><div><b>AgriPilot</b><span>Farm decision assistant</span></div></div>

  <div class="farmswitch">
    <div class="lbl">Viewing farm</div>
    <div class="farmlist" id="farmlist"></div>
  </div>

  <nav class="mainnav">
    <button class="navbtn" data-p="today"><span class="ic">&#9679;</span>Today</button>
    <button class="navbtn" data-p="advisories"><span class="ic">&#9776;</span>Advisory log</button>
    <button class="navbtn" data-p="season"><span class="ic">&#9707;</span>Season data</button>
    <button class="navbtn" data-p="compare"><span class="ic">&#8862;</span>Pilot results</button>
    <button class="navbtn" data-p="ml"><span class="ic">&#10022;</span>ML insights</button>
    <button class="navbtn" data-p="assistant"><span class="ic">&#9673;</span>Assistant</button>
  </nav>

  <div class="sidefoot">
    <div class="modeswitch">
      <button id="mode-farmer" class="on">Farmer view</button>
      <button id="mode-analyst">Analyst view</button>
    </div>
    <div class="hint" id="modehint"></div>
  </div>
</aside>

<div class="main">
  <div class="topbar">
    <button class="menubtn" id="menubtn" aria-label="Menu">&#9776;</button>
    <div>
      <h1 id="tb-title">Today</h1>
      <div class="crumb" id="tb-crumb"></div>
    </div>
    <div class="spacer"></div>
    <span class="pill" id="tb-pill"></span>
  </div>

  <div class="content">

    <div class="pane on" id="today">
      <div class="hero" id="hero"></div>
      <div id="queue-wrap" style="display:none">
        <h2 class="sec">Also today</h2>
        <div class="queue" id="queue"></div>
      </div>
      <div class="analyst-only">
        <h2 class="sec">This season vs. this farm's usual practice</h2>
        <div class="kpis" id="kpis"></div>
      </div>
    </div>

    <div class="pane" id="advisories">
      <h2 class="sec">Every recommendation this season</h2>
      <p class="helptext">What the agent suggested, when, and whether it was accepted. Declined items fall back to the farm's usual habit for that day.</p>
      <div class="logfilter">
        <button class="on" data-f="all">All</button>
        <button data-f="executed">Accepted</button>
        <button data-f="rejected">Declined</button>
      </div>
      <div class="log" id="log"></div>
    </div>

    <div class="pane" id="season">
      <h2 class="sec">Root-zone water balance</h2>
      <p class="helptext">Rainfall and irrigation refill the soil; the dashed line is the stress threshold &mdash; the crop is safe as long as the solid depletion line stays under it.</p>
      <div class="card chartbox"><svg id="chart-season" viewBox="0 0 760 220" role="img" aria-label="Season water balance"></svg>
        <div class="legend">
          <span><b style="background:var(--water)"></b>Irrigation</span>
          <span><b style="background:#9cc9d6"></b>Rainfall</span>
          <span><b style="background:var(--soil)"></b>Root-zone depletion</span>
          <span><b style="background:var(--alert)"></b>Stress threshold</span>
        </div>
      </div>

      <h2 class="sec">Input use vs. usual practice</h2>
      <div class="card chartbox"><svg id="chart-inputs" viewBox="0 0 760 170" role="img" aria-label="Input comparison"></svg></div>

      <h2 class="sec">Canopy health &amp; pest pressure</h2>
      <p class="helptext">NDVI (satellite greenness) tracks crop vigor; pest pressure is the agent's running estimate, corrected by scouting reports where available.</p>
      <div class="card chartbox"><svg id="chart-pest" viewBox="0 0 760 170" role="img" aria-label="NDVI and pest pressure"></svg>
        <div class="legend">
          <span><b style="background:var(--leaf)"></b>NDVI</span>
          <span><b style="background:var(--gold)"></b>Pest pressure</span>
        </div>
      </div>
    </div>

    <div class="pane" id="compare">
      <h2 class="sec">Pilot-wide results</h2>
      <p class="helptext" id="pilot-scope"></p>
      <div class="pilotbanner" id="pilotbanner"></div>

      <h2 class="sec">By crop &mdash; AgriPilot vs. farmer practice</h2>
      <div class="card">
        <div class="croprow head"><span>Crop</span><span>Yield change</span><span>Water saved</span><span>Nitrogen cut</span><span>Margin gained</span></div>
        <div id="croptable"></div>
      </div>

      <h2 class="sec">Across two growing years</h2>
      <div class="card" id="yearcards" style="display:flex;gap:14px"></div>
    </div>

    <div class="pane" id="ml">
      <h2 class="sec">Machine learning applied to the pilot dataset</h2>
      <p class="helptext">Four models trained on the 240 AgriPilot farm-seasons from the pilot run, each answering a different kind of question the simulation and rule-based agent can't answer on their own.</p>

      <div class="mlgrid">
        <div class="mlcard">
          <h3><span class="mltag sup">Supervised · regression</span></h3>
          <div class="sub">Gradient-boosted trees predicting realised yield as a fraction of each crop's attainable potential, from practice and context alone.</div>
          <div class="mlstat" id="ml-reg-stats"></div>
          <div id="ml-reg-features"></div>
          <div class="mlnote" id="ml-reg-note"></div>
        </div>

        <div class="mlcard">
          <h3><span class="mltag sup">Supervised · classification</span></h3>
          <div class="sub">Predicts, before the season starts, whether a farm is headed for above-median water stress &mdash; from soil, crop and farmer context only.</div>
          <div class="mlstat" id="ml-clf-stats"></div>
          <div id="ml-clf-features"></div>
          <div class="mlnote" id="ml-clf-note"></div>
        </div>

        <div class="mlcard">
          <h3><span class="mltag uns">Unsupervised · clustering</span></h3>
          <div class="sub">K-means groups farms into management archetypes from water, nitrogen, spray and margin patterns &mdash; no labels given.</div>
          <div class="chartbox"><svg id="chart-clusters" viewBox="0 0 340 220" role="img" aria-label="Farm archetype clusters"></svg></div>
          <div class="clusterlegend" id="cluster-legend"></div>
          <div class="mlnote" id="ml-cluster-note"></div>
        </div>

        <div class="mlcard">
          <h3><span class="mltag ano">Anomaly detection</span></h3>
          <div class="sub">Isolation Forest flags sensor-days whose rain/irrigation/depletion relationship doesn't fit the rest of that farm's season.</div>
          <div class="mlstat" id="ml-ano-stats"></div>
          <div id="ml-ano-list"></div>
          <div class="mlnote">Flagged days are candidates for down-weighting in the state estimator and a technician probe check &mdash; not necessarily errors, just statistically unusual.</div>
        </div>
      </div>

      <h2 class="sec">Reinforcement learning: does the analytic agent actually beat a learned policy?</h2>
      <div class="mlcard">
        <div class="sub" id="ml-rl-setup"></div>
        <div class="chartbox"><svg id="chart-rl-training" viewBox="0 0 700 140" role="img" aria-label="Q-learning training curve"></svg></div>
        <div class="croprow head" style="grid-template-columns:1fr 1fr 1fr 1fr"><span>Policy</span><span>Yield (t/ha)</span><span>Water (mm)</span><span>Water productivity</span></div>
        <div id="ml-rl-table"></div>
        <div class="mlnote" id="ml-rl-note"></div>
      </div>
    </div>

    <div class="pane" id="assistant">
      <div class="chatwrap">
        <div class="chathead">
          <div class="av">A</div>
          <div><b>Farm assistant</b><div class="sub" id="chat-sub">Answers using this farm's live season data</div></div>
        </div>
        <div class="chatlog" id="chatlog"></div>
        <div class="chips" id="chips"></div>
        <div class="chatinput">
          <input id="chatin" type="text" placeholder="Ask about irrigation, costs, pests&hellip;" autocomplete="off">
          <button id="chatsend" aria-label="Send">&#8593;</button>
        </div>
      </div>
    </div>

    <footer class="note">AgriPilot is a decision-support tool built on simulated seasons calibrated to FAO-56/FAO-33 agronomic models. It supports a farmer's judgement; it does not replace it. The assistant answers from this season's actual simulated data and general agronomy &mdash; verify field-critical decisions locally.</footer>
  </div>
</div>
</div>

<script id="d" type="application/json">__PAYLOAD__</script>
<script>
const DATA = JSON.parse(document.getElementById('d').textContent);
const FARMS = DATA.farms, PILOT = DATA.pilot;
const GL = {irrigate:'&#128167;', skip_irrigation:'&#128683;', fertilise:'&#127793;',
 defer_fertiliser:'&#9208;', spray:'&#128029;', no_spray:'&#9989;'};
const VERB = {irrigate:'Irrigate today', skip_irrigation:'No irrigation needed',
 fertilise:'Apply fertiliser', defer_fertiliser:'Hold the fertiliser',
 spray:'Spray for pests', no_spray:'No spray needed'};
const SHORT = {irrigate:'Irrigation', skip_irrigation:'Irrigation', fertilise:'Fertiliser',
 defer_fertiliser:'Fertiliser', spray:'Pest control', no_spray:'Pest control'};

let state = {farm:0, pane:'today', mode:'farmer', logFilter:'all'};
const CURDAY = {};   // per-farm "today" pointer
FARMS.forEach((f,i)=> CURDAY[i] = Math.min(f.trace.length-9, Math.max(20, f.trace.length-55)));

function farm(){ return FARMS[state.farm]; }
function today(){ const f=farm(); return f.trace[CURDAY[state.farm]]; }
function fmt(n,d=0){ return Number(n).toLocaleString('en-IN',{maximumFractionDigits:d,minimumFractionDigits:d}); }
function pct(x,y){ return Math.round((x/y-1)*100); }

/* ---------------- sidebar: farm list ---------------- */
function renderFarmList(){
  document.getElementById('farmlist').innerHTML = FARMS.map((f,i)=>
   '<button class="farmbtn'+(i===state.farm?' on':'')+'" data-i="'+i+'">'
   +'<span class="dot"></span><span><span class="fb-name">'+f.name+'</span>'
   +'<span class="fb-sub">'+f.crop_label+' &middot; '+f.village+'</span></span></button>').join('');
  document.querySelectorAll('.farmbtn').forEach(b=>b.onclick=()=>{
    state.farm = +b.dataset.i; renderAll();
  });
}

/* ---------------- today ---------------- */
function heroHtml(){
  const f=farm(), t=today();
  const dayCalls = f.audit.filter(a=>a.day===CURDAY[state.farm]);
  const primary = dayCalls.find(a=>['irrigate','skip_irrigation'].includes(a.args.kind)) || dayCalls[0]
    || {args:{kind:'skip_irrigation', message:'Nothing needs attention today. Conditions are within the normal range.', confidence:.8}, status:'executed'};
  const rest = dayCalls.filter(a=>a!==primary);
  const conf = Math.round((primary.args.confidence||.8)*100);
  const wx = (t.rain>0 ? ('Rain '+t.rain+' mm') : 'No rain') + ' &middot; crop water use '+t.etc+' mm';
  let html = '<div class="top"><span>Day '+CURDAY[state.farm]+' after planting</span><span class="wx">'+wx+'</span></div>'
   +'<div class="body"><div class="glyph">'+GL[primary.args.kind]+'</div><div>'
   +'<h1>'+(VERB[primary.args.kind]||'Recommendation')+'</h1>'
   +'<p>'+primary.args.message+'</p>'
   +'<span class="confi"><i></i>Confidence '+conf+'%</span></div></div>'
   +'<div class="acts"><button class="yes" id="heroYes">Mark as done</button><button class="no" id="heroNo">Skip this</button></div>'
   +'<div class="done" id="heroDone"></div>';
  document.getElementById('hero').innerHTML = html;
  document.getElementById('heroYes').onclick=()=>{
    document.querySelector('#hero .acts').style.display='none';
    const d=document.getElementById('heroDone'); d.style.display='block';
    d.textContent='Logged as done. The agent will check the result tomorrow.';
  };
  document.getElementById('heroNo').onclick=()=>{
    document.querySelector('#hero .acts').style.display='none';
    const d=document.getElementById('heroDone'); d.style.display='block';
    d.textContent="Logged as skipped. Future recommendations will account for this.";
  };
  const qwrap=document.getElementById('queue-wrap'), q=document.getElementById('queue');
  if(rest.length){
    qwrap.style.display='block';
    q.innerHTML = rest.map(a=>'<div class="qrow"><span class="g">'+(GL[a.args.kind]||'&#127806;')+'</span>'
     +'<span class="t">'+a.args.message+'</span><span class="s">'+Math.round((a.args.confidence||.8)*100)+'% confidence</span></div>').join('');
  } else { qwrap.style.display='none'; }
}

function kpiHtml(){
  const f=farm(), a=f.agent, b=f.baseline;
  const rows=[
   ['Yield', fmt(a.yield_t_ha,1)+' t/ha', pct(a.yield_t_ha,b.yield_t_ha)],
   ['Irrigation water', fmt(a.irrigation_mm)+' mm', -pct(a.irrigation_mm,b.irrigation_mm)],
   ['Nitrogen applied', fmt(a.n_applied)+' kg/ha', -pct(a.n_applied,b.n_applied)],
   ['Net margin', '&#8377;'+fmt(a.gross_margin), pct(a.gross_margin,b.gross_margin)],
  ];
  document.getElementById('kpis').innerHTML = rows.map(r=>
   '<div class="kpi"><div class="n">'+r[1]+'</div><div class="l">'+r[0]+'</div>'
   +'<div class="d '+(r[2]>=0?'good':'bad')+'">'+(r[2]>0?'&#9650; +':r[2]<0?'&#9660; ':'')+Math.abs(r[2])+'% vs. usual practice</div></div>').join('');
}

/* ---------------- advisory log ---------------- */
function logHtml(){
  const f=farm();
  let items = f.audit.slice().reverse();
  if(state.logFilter!=='all') items = items.filter(a=>a.status===state.logFilter);
  document.getElementById('log').innerHTML = items.map(a=>
   '<div class="row'+(a.status==='rejected'?' rej':'')+'"><span class="g">'+(GL[a.args.kind]||'&#127806;')+'</span>'
   +'<span class="t">'+a.args.message+'<br><span class="tag '+(a.status==='executed'?'ok':'rej')+'">'
   +(a.status==='executed'?'Accepted':'Declined')+'</span></span>'
   +'<span class="s">Day '+a.day+'</span></div>').join('') || '<div class="row"><span class="t">No matching entries.</span></div>';
}
document.querySelectorAll('.logfilter button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.logfilter button').forEach(x=>x.classList.toggle('on',x===b));
  state.logFilter=b.dataset.f; logHtml();
});

/* ---------------- season charts ---------------- */
function svgLine(pts){ return pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' '); }

function chartSeason(){
  const f=farm(), T=f.trace, W=760,H=220,L=40,R=10,Tp=10,B=26;
  const n=T.length, x=i=>L+(W-L-R)*i/(n-1);
  const mx=Math.max(...T.map(d=>Math.max(d.rain,d.irrigation,d.dr,d.raw)))*1.05;
  const y=v=>Tp+(H-Tp-B)*(1-v/mx);
  let h='';
  h+='<line x1="'+L+'" y1="'+(H-B)+'" x2="'+(W-R)+'" y2="'+(H-B)+'" stroke="var(--line-strong)"/>';
  [0,0.5,1].forEach(f2=>{const yy=y(mx*f2);h+='<line x1="'+L+'" y1="'+yy+'" x2="'+(W-R)+'" y2="'+yy+'" stroke="var(--line)" stroke-dasharray="2 3"/>'
   +'<text x="6" y="'+(yy+3)+'" font-size="9.5" fill="var(--ink-faint)">'+Math.round(mx*f2)+'</text>';});
  T.forEach((d,i)=>{ if(d.rain>0) h+='<rect x="'+(x(i)-1.1)+'" y="'+y(d.rain)+'" width="2.2" height="'+(H-B-y(d.rain))+'" fill="#9cc9d6"/>'; });
  T.forEach((d,i)=>{ if(d.irrigation>0) h+='<rect x="'+(x(i)-1.1)+'" y="'+y(d.irrigation)+'" width="2.2" height="'+(H-B-y(d.irrigation))+'" fill="var(--water)"/>'; });
  h+='<path d="'+svgLine(T.map((d,i)=>[x(i),y(d.raw)]))+'" fill="none" stroke="var(--alert)" stroke-width="1.4" stroke-dasharray="4 3"/>';
  h+='<path d="'+svgLine(T.map((d,i)=>[x(i),y(d.dr)]))+'" fill="none" stroke="var(--soil)" stroke-width="1.8"/>';
  const cd=CURDAY[state.farm];
  h+='<line x1="'+x(cd)+'" y1="'+Tp+'" x2="'+x(cd)+'" y2="'+(H-B)+'" stroke="var(--ink)" stroke-width="1"/>';
  h+='<text x="'+(x(cd)+4)+'" y="'+(Tp+10)+'" font-size="10" fill="var(--ink-soft)">today</text>';
  [0,30,60,90,120,150].filter(v=>v<n).forEach(v=>h+='<text x="'+x(v)+'" y="'+(H-8)+'" font-size="10" text-anchor="middle" fill="var(--ink-faint)">day '+v+'</text>');
  h+='<text x="'+L+'" y="'+(H-4)+'" font-size="9.5" fill="var(--ink-faint)"></text>';
  document.getElementById('chart-season').innerHTML=h;
}

function chartInputs(){
  const f=farm(), a=f.agent, b=f.baseline, W=760,H=170;
  const rows=[['Irrigation (mm)',a.irrigation_mm,b.irrigation_mm],
   ['Nitrogen (kg/ha)',a.n_applied,b.n_applied],
   ['Chemical sprays',a.chem_sprays,b.chem_sprays],
   ['Nitrogen leached (kg/ha)',a.n_leached,b.n_leached]];
  let h='';
  rows.forEach((r,i)=>{ const yy=22+i*38, mx=Math.max(r[1],r[2])||1, bw=W-260;
   h+='<text x="0" y="'+(yy-14)+'" font-size="11.5" fill="var(--ink-soft)">'+r[0]+'</text>';
   h+='<rect x="200" y="'+(yy-12)+'" width="'+(bw*r[2]/mx)+'" height="11" fill="var(--line-strong)" rx="2"/>';
   h+='<text x="'+(210+bw*r[2]/mx)+'" y="'+(yy-3)+'" font-size="10" fill="var(--ink-faint)">'+fmt(r[2],1)+' usual</text>';
   h+='<rect x="200" y="'+(yy+3)+'" width="'+(bw*r[1]/mx)+'" height="11" fill="var(--leaf)" rx="2"/>';
   h+='<text x="'+(210+bw*r[1]/mx)+'" y="'+(yy+12)+'" font-size="10" fill="var(--leaf-deep)">'+fmt(r[1],1)+' AgriPilot</text>';
  });
  document.getElementById('chart-inputs').innerHTML=h;
}

function chartPest(){
  const f=farm(), T=f.trace, W=760,H=170,L=10,R=10,Tp=14,B=26;
  const n=T.length, x=i=>L+(W-L-R)*i/(n-1);
  const yN=v=>Tp+(H-Tp-B)*(1-v);
  const mxP=Math.max(1,...T.map(d=>d.pest));
  const yP=v=>Tp+(H-Tp-B)*(1-v/mxP);
  let h='';
  h+='<line x1="'+L+'" y1="'+(H-B)+'" x2="'+(W-R)+'" y2="'+(H-B)+'" stroke="var(--line-strong)"/>';
  h+='<path d="'+svgLine(T.map((d,i)=>[x(i),yP(d.pest)]))+'" fill="none" stroke="var(--gold)" stroke-width="1.6" opacity=".85"/>';
  h+='<path d="'+svgLine(T.map((d,i)=>[x(i),yN(d.ndvi)]))+'" fill="none" stroke="var(--leaf)" stroke-width="2"/>';
  T.forEach((d,i)=>{ if(d.spray) h+='<circle cx="'+x(i)+'" cy="'+(H-B+7)+'" r="2.4" fill="'+(d.spray==='chemical'?'var(--alert)':'var(--leaf)')+'"/>'; });
  [0,30,60,90,120,150].filter(v=>v<n).forEach(v=>h+='<text x="'+x(v)+'" y="'+(H-8)+'" font-size="10" text-anchor="middle" fill="var(--ink-faint)">day '+v+'</text>');
  document.getElementById('chart-pest').innerHTML=h;
}

/* ---------------- pilot-wide compare ---------------- */
function renderCompare(){
  const P=PILOT.headline;
  document.getElementById('pilot-scope').textContent =
   'Across the full '+PILOT.n_farms+'-farm, two-year pilot ('+PILOT.n_farm_seasons+' simulated farm-seasons), every policy ran on identical weather so the comparison is paired.';
  const segs=[
   [fmt(P.water_saving_pct,0)+'%','Water saved vs. usual practice'],
   [fmt(P.nitrogen_reduction_pct,0)+'%','Nitrogen reduction'],
   [fmt(P.chem_spray_reduction_pct,0)+'%','Fewer chemical sprays'],
   ['&#8377;'+fmt(P.gross_margin_gain_inr_per_ha,0),'Extra margin per hectare'],
   [fmt(P.mean_adoption_rate*100,0)+'%','Recommendations accepted'],
  ];
  document.getElementById('pilotbanner').innerHTML = segs.map(s=>
   '<div class="seg"><div class="n">'+s[0]+'</div><div class="l">'+s[1]+'</div></div>').join('');

  const crops = PILOT.by_crop;
  const maxMargin = Math.max(...Object.values(crops).map(c=>Math.abs(c.margin_gain_inr)));
  document.getElementById('croptable').innerHTML = Object.entries(crops).map(([c,v])=>{
    const bar=(val,cap)=>{const w=Math.min(100,Math.abs(val)/cap*100); return '<div class="hbarwrap"><div class="hbar'+(val<0?' neg':'')+'" style="width:'+w+'%"></div></div>';};
    return '<div class="croprow"><span class="cname">'+(CROP_LABELS[c]||c)+'</span>'
     +'<span class="c2">'+(v.yield_gain_pct>=0?'+':'')+fmt(v.yield_gain_pct,1)+'%'+bar(v.yield_gain_pct,15)+'</span>'
     +'<span class="c3">'+fmt(v.water_saving_pct,1)+'%'+bar(v.water_saving_pct,50)+'</span>'
     +'<span class="c4">'+fmt(v.n_reduction_pct,1)+'%'+bar(v.n_reduction_pct,60)+'</span>'
     +'<span class="c5">&#8377;'+fmt(v.margin_gain_inr,0)+bar(v.margin_gain_inr,maxMargin)+'</span></div>';
  }).join('');

  const P2=PILOT;
  document.getElementById('yearcards').innerHTML = '';
}
const CROP_LABELS={onion:'Onion',grape:'Grape',tomato:'Tomato',soybean:'Soybean',wheat:'Wheat',cotton:'Cotton'};

/* ---------------- assistant ---------------- */
let sampleFn=null, sampleTried=false, chatHistory=[];
async function ensureSample(){
  if(sampleTried) return sampleFn;
  sampleTried=true;
  try{
    if(window.claude && window.claude.use){
      sampleFn = await window.claude.use('sample');
    }
  }catch(e){ sampleFn=null; }
  return sampleFn;
}
function farmContext(){
  const f=farm(), a=f.agent, b=f.baseline, t=today();
  const recent = f.audit.filter(x=>x.day<=CURDAY[state.farm]).slice(-8)
   .map(x=>'day '+x.day+': ['+x.status+'] '+x.args.message).join('\n');
  return [
   'You are the AgriPilot farm assistant, embedded in a decision-support dashboard for smallholder farmers in Maharashtra, India.',
   'Answer only using the data below plus general, safe agronomic knowledge. Be concise (2-5 sentences unless asked for detail). Plain language, no jargon unless you define it. Currency is INR (rupees). Do not invent numbers not derivable from the data.',
   '--- Current farm ---',
   'Farmer: '+f.name+', '+f.village+'. Crop: '+f.crop_label+' on '+f.area_ha+' ha, '+f.soil+' soil, '+f.system+' irrigation.',
   'Day '+CURDAY[state.farm]+' of the season. Today: rain '+t.rain+' mm, crop water use '+t.etc+' mm, root-zone depletion '+t.dr+'/'+t.taw+' mm, stress threshold '+t.raw+' mm.',
   '--- Season so far (AgriPilot agent vs. this farmer\'s usual practice) ---',
   'Yield: '+a.yield_t_ha.toFixed(1)+' t/ha vs '+b.yield_t_ha.toFixed(1)+' t/ha usual.',
   'Irrigation applied: '+Math.round(a.irrigation_mm)+' mm vs '+Math.round(b.irrigation_mm)+' mm usual.',
   'Nitrogen applied: '+Math.round(a.n_applied)+' kg/ha vs '+Math.round(b.n_applied)+' kg/ha usual.',
   'Chemical sprays: '+a.chem_sprays+' (+'+a.bio_sprays+' biological) vs '+b.chem_sprays+' usual.',
   'Net margin: Rs '+Math.round(a.gross_margin)+'/ha vs Rs '+Math.round(b.gross_margin)+'/ha usual.',
   'Recommendation acceptance rate: '+Math.round(a.adoption_rate*100)+'%.',
   '--- Recent recommendations ---', recent,
   '--- Pilot-wide results (60 farms, 2 years, for context if asked) ---',
   JSON.stringify(PILOT.headline),
  ].join('\n');
}
function addBubble(role,text){
  const log=document.getElementById('chatlog');
  const b=document.createElement('div'); b.className='bubble '+role; b.textContent=text;
  log.appendChild(b); log.scrollTop=log.scrollHeight; return b;
}
function offlineAnswer(q){
  const ql=q.toLowerCase(), f=farm(), a=f.agent, b=f.baseline;
  if(/water|irrigat/.test(ql)) return "This season AgriPilot applied "+Math.round(a.irrigation_mm)+" mm of water on "+f.name+"'s farm, against "+Math.round(b.irrigation_mm)+" mm under the usual routine \u2014 a "+Math.round((1-a.irrigation_mm/b.irrigation_mm)*100)+"% reduction, because irrigation is only recommended when the forecast and soil sensors together show real risk of stress.";
  if(/nitrogen|fertil/.test(ql)) return "Nitrogen use is "+Math.round(a.n_applied)+" kg/ha here versus "+Math.round(b.n_applied)+" kg/ha usually \u2014 the agent matches applications to what the crop can actually take up in the next two weeks, and holds off before heavy rain to avoid washing it away.";
  if(/pest|spray|insect/.test(ql)) return "The agent has used "+a.chem_sprays+" chemical sprays and "+a.bio_sprays+" biological treatments this season, against "+b.chem_sprays+" chemical sprays under calendar spraying \u2014 spraying only when expected crop-loss avoided outweighs the cost and the environmental impact.";
  if(/margin|profit|cost|money|rupee|income/.test(ql)) return "Net margin this season is roughly Rs "+Math.round(a.gross_margin).toLocaleString('en-IN')+"/ha, against Rs "+Math.round(b.gross_margin).toLocaleString('en-IN')+"/ha under the farm's usual practice.";
  if(/yield|produc/.test(ql)) return "Projected yield is "+a.yield_t_ha.toFixed(1)+" t/ha this season, versus "+b.yield_t_ha.toFixed(1)+" t/ha under the usual routine.";
  if(/ndvi/.test(ql)) return "NDVI is a satellite greenness index \u2014 healthy, actively growing canopy reflects more near-infrared light, so a higher NDVI generally means a healthier stand. AgriPilot uses it to cross-check the soil and weather picture, especially when it corroborates a pest or stress signal.";
  if(/trust|adopt|accept/.test(ql)) return "You've accepted "+Math.round(a.adoption_rate*100)+"% of this farm's recommendations so far. The agent adapts \u2014 recommendations you decline are logged and shape future suggestions.";
  return "I can answer from this farm's season data \u2014 try asking about water use, nitrogen, pest control, margin, or yield. (Running in offline mode: connect an AI session for open-ended questions.)";
}
async function sendChat(text){
  if(!text.trim()) return;
  addBubble('user', text);
  chatHistory.push({role:'user', content:text});
  const input=document.getElementById('chatin'); input.value=''; 
  const sendBtn=document.getElementById('chatsend'); sendBtn.disabled=true;
  const typing=addBubble('bot',''); typing.innerHTML='<span class="typing"><i></i><i></i><i></i></span>';
  const fn = await ensureSample();
  if(fn){
    try{
      const res = await fn([{role:'user', content: farmContext()+'\n\n--- Conversation so far ---\n'
        +chatHistory.slice(0,-1).map(m=>m.role+': '+m.content).join('\n')+'\nuser: '+text}],
        {onText:({text:t})=>{ typing.textContent=t; document.getElementById('chatlog').scrollTop=1e9; }});
      typing.textContent = res.text;
      chatHistory.push({role:'assistant', content:res.text});
    }catch(e){
      typing.textContent = offlineAnswer(text);
    }
  } else {
    await new Promise(r=>setTimeout(r,400));
    typing.textContent = offlineAnswer(text);
  }
  sendBtn.disabled=false;
}
function renderChips(){
  const chips=['How much water have we saved?','Why hold the fertiliser?','Is the pest risk high right now?','How does this compare to last year?'];
  document.getElementById('chips').innerHTML = chips.map(c=>'<button class="chip">'+c+'</button>').join('');
  document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>sendChat(c.textContent));
}
function resetChat(){
  const f=farm();
  document.getElementById('chatlog').innerHTML='';
  document.getElementById('chat-sub').textContent = 'Grounded in '+f.name+"'s "+f.crop_label.toLowerCase()+' season \u2014 '+f.village;
  addBubble('sys','Assistant reset for '+f.name+"'s farm.");
  addBubble('bot','Hello! I can answer questions about '+f.name+"'s "+f.crop_label.toLowerCase()+' season \u2014 irrigation, fertiliser, pest control, costs, or how this compares to the usual practice. What would you like to know?');
  chatHistory=[];
  renderChips();
}
document.getElementById('chatsend').onclick=()=>sendChat(document.getElementById('chatin').value);
document.getElementById('chatin').addEventListener('keydown',e=>{ if(e.key==='Enter') sendChat(e.target.value); });

/* ---------------- nav / mode / farm switching ---------------- */
const TITLES={today:'Today', advisories:'Advisory log', season:'Season data', compare:'Pilot results', ml:'ML insights', assistant:'Assistant'};
function renderAll(){
  renderFarmList();
  const f=farm();
  document.getElementById('tb-crumb').textContent = f.name+' \u00b7 '+f.village+' \u00b7 '+f.crop_label+' \u00b7 '+f.area_ha+' ha \u00b7 '+f.system+' irrigation';
  document.getElementById('tb-pill').textContent = 'Day '+CURDAY[state.farm]+' of season';
  document.getElementById('tb-title').textContent = TITLES[state.pane];
  heroHtml(); kpiHtml(); logHtml();
  chartSeason(); chartInputs(); chartPest();
  renderCompare();
  renderMl();
  resetChat();
}
/* ---------------- ML insights ---------------- */
const CLUSTER_COLORS=['var(--leaf)','var(--water)','var(--gold)','var(--alert)','var(--soil)','var(--ink-soft)'];
function renderMl(){
  const ML = DATA.ml;
  if(!ML){ document.getElementById('ml').innerHTML='<p class="helptext">ML summary not available in this build.</p>'; return; }

  const reg = ML.supervised.yield_regressor;
  document.getElementById('ml-reg-stats').innerHTML =
   '<div><div class="n">'+reg.cv_r2_mean.toFixed(2)+'</div><div class="l">Cross-val R&sup2;</div></div>'
   +'<div><div class="n">&plusmn;'+(reg.cv_mae_efficiency*100).toFixed(1)+'%</div><div class="l">Mean error (yield efficiency)</div></div>';
  document.getElementById('ml-reg-features').innerHTML = reg.top_features.slice(0,6).map(f=>{
    const w = Math.max(4, Math.round(100*f.importance/reg.top_features[0].importance));
    return '<div class="mlbar-row"><span class="fname">'+f.feature.replace(/_/g,' ')+'</span>'
     +'<span class="mlbar-track"><span class="mlbar-fill" style="width:'+w+'%"></span></span>'
     +'<span class="mlbar-val">'+f.importance.toFixed(3)+'</span></div>';
  }).join('');
  document.getElementById('ml-reg-note').textContent = 'GroupKFold cross-validation by farm ('+reg.cv_folds+' folds), '
   +reg.n_samples+' seasons, '+reg.n_features+' features. Baseline (predict the mean) error: '
   +(reg.baseline_mae_efficiency*100).toFixed(1)+'%.';

  const clf = ML.supervised.stress_classifier;
  document.getElementById('ml-clf-stats').innerHTML =
   '<div><div class="n">'+(clf.cv_accuracy_mean*100).toFixed(0)+'%</div><div class="l">Accuracy</div></div>'
   +'<div><div class="n">'+(clf.cv_auc_mean?clf.cv_auc_mean.toFixed(2):'&mdash;')+'</div><div class="l">ROC-AUC</div></div>'
   +'<div><div class="n">'+(clf.cv_f1_mean*100).toFixed(0)+'%</div><div class="l">F1 score</div></div>';
  document.getElementById('ml-clf-features').innerHTML = clf.top_features.slice(0,5).map(f=>{
    const w = Math.max(4, Math.round(100*f.importance/clf.top_features[0].importance));
    return '<div class="mlbar-row"><span class="fname">'+f.feature.replace(/_/g,' ')+'</span>'
     +'<span class="mlbar-track"><span class="mlbar-fill" style="width:'+w+'%;background:var(--gold)"></span></span>'
     +'<span class="mlbar-val">'+f.importance.toFixed(3)+'</span></div>';
  }).join('');
  document.getElementById('ml-clf-note').textContent = 'Baseline (always predict the majority class): '
   +(clf.baseline_accuracy*100).toFixed(0)+'% accuracy. Only pre-season-known features used ('+clf.n_features+').';

  const uns = ML.unsupervised, clusters = ML.unsupervised_clusters;
  const W=340,H=220,pad=20;
  const allX=clusters.flatMap(c=>c.points.map(p=>p.x)), allY=clusters.flatMap(c=>c.points.map(p=>p.y));
  const mnX=Math.min(...allX),mxX=Math.max(...allX),mnY=Math.min(...allY),mxY=Math.max(...allY);
  const sx=x=>pad+(W-2*pad)*(x-mnX)/(mxX-mnX||1), sy=y=>H-pad-(H-2*pad)*(y-mnY)/(mxY-mnY||1);
  let svg='';
  clusters.forEach((c,ci)=>{ c.points.forEach(p=>{
    svg+='<circle cx="'+sx(p.x).toFixed(1)+'" cy="'+sy(p.y).toFixed(1)+'" r="4" fill="'+CLUSTER_COLORS[ci%CLUSTER_COLORS.length]+'" opacity="0.82"><title>'+p.farm_id+' ('+p.crop+')</title></circle>';
  });});
  document.getElementById('chart-clusters').innerHTML = svg;
  document.getElementById('cluster-legend').innerHTML = clusters.map((c,ci)=>
   '<span><b style="background:'+CLUSTER_COLORS[ci%CLUSTER_COLORS.length]+'"></b>'+c.label+' ('+c.n_farms+')</span>').join('');
  document.getElementById('ml-cluster-note').textContent = 'k='+uns.chosen_k+' (silhouette '+uns.silhouette.toFixed(2)
   +'; silhouette-optimal k was '+uns.silhouette_optimal_k+', but '+uns.chosen_k+' gives more actionable segments at a small cost in fit). '
   +'PCA explains '+Math.round((uns.pca_explained_variance[0]+uns.pca_explained_variance[1])*100)+'% of variance in 2D.';

  const ano = ML.anomaly;
  document.getElementById('ml-ano-stats').innerHTML =
   '<div><div class="n">'+ano.total_flagged+'</div><div class="l">Days flagged</div></div>'
   +'<div><div class="n">'+((ano.total_flagged/ano.total_days_scored)*100).toFixed(1)+'%</div><div class="l">Of all sensor-days</div></div>';
  document.getElementById('ml-ano-list').innerHTML = Object.entries(ML.anomaly_by_farm).map(([fid,v])=>{
    const pct = Math.round(100*v.n_flagged/v.n_days);
    return '<div class="mlbar-row"><span class="fname">'+fid+' ('+v.crop+')</span>'
     +'<span class="mlbar-track"><span class="mlbar-fill" style="width:'+Math.max(4,pct*4)+'%;background:var(--alert)"></span></span>'
     +'<span class="mlbar-val">'+v.n_flagged+'/'+v.n_days+'</span></div>';
  }).join('');

  const rl = ML.reinforcement;
  document.getElementById('ml-rl-setup').textContent = 'Tabular Q-learning, state = (soil-depletion decile ' +
   '× days-since-irrigation × growth stage), '+rl.setup.train_episodes+' training episodes on simulated '
   +rl.setup.crop+' seasons, evaluated on '+rl.setup.eval_episodes+' held-out seasons never seen in training.';
  (function(){ const s2=document.getElementById('chart-rl-training'),W2=700,H2=140,L=36,R=10,Tp=10,B=22;
    const curve=rl.training_curve_sample, n=curve.length, mx=Math.max(...curve,1)*1.1;
    const x=i=>L+(W2-L-R)*i/(n-1), y=v=>Tp+(H2-Tp-B)*(1-v/mx);
    let h='<line x1="'+L+'" y1="'+(H2-B)+'" x2="'+(W2-R)+'" y2="'+(H2-B)+'" stroke="var(--line-strong)"/>';
    h+='<path d="'+curve.map((v,i)=>(i?'L':'M')+x(i).toFixed(1)+' '+y(v).toFixed(1)).join(' ')+'" fill="none" stroke="var(--leaf)" stroke-width="2"/>';
    h+='<text x="4" y="'+(Tp+8)+'" font-size="10" fill="var(--ink-faint)">'+Math.round(mx)+' t/ha</text>';
    h+='<text x="'+L+'" y="'+(H2-6)+'" font-size="10" fill="var(--ink-faint)">episode 0</text>';
    h+='<text x="'+(W2-R)+'" y="'+(H2-6)+'" font-size="10" text-anchor="end" fill="var(--ink-faint)">episode '+(rl.setup.train_episodes)+'</text>';
    s2.innerHTML=h; })();
  const rows=[['Q-learning (learned, no forecast)',rl.q_learning_agent],
   ['AgriPilot analytic agent (forecast-aware)',rl.agripilot_analytic_agent],
   ['Farmer practice (baseline)',rl.farmer_practice_baseline]];
  document.getElementById('ml-rl-table').innerHTML = rows.map(r=>
   '<div class="croprow" style="grid-template-columns:1fr 1fr 1fr 1fr"><span>'+r[0]+'</span>'
   +'<span>'+r[1].mean_yield_t_ha.toFixed(2)+'</span><span>'+Math.round(r[1].mean_water_mm)+'</span>'
   +'<span>'+r[1].water_productivity.toFixed(2)+' kg/m&sup3;</span></div>').join('');
  document.getElementById('ml-rl-note').textContent = rl.note;
}

document.querySelectorAll('.navbtn').forEach(b=>b.onclick=()=>{
  state.pane=b.dataset.p;
  document.querySelectorAll('.navbtn').forEach(x=>x.classList.toggle('on',x===b));
  document.querySelectorAll('.pane').forEach(p=>p.classList.toggle('on',p.id===state.pane));
  document.getElementById('tb-title').textContent = TITLES[state.pane];
  document.getElementById('sidebar').classList.remove('open'); document.getElementById('scrim').classList.remove('on');
});
document.querySelector('.navbtn[data-p="today"]').classList.add('on');

function setMode(m){
  state.mode=m; document.body.dataset.mode=m;
  document.getElementById('mode-farmer').classList.toggle('on', m==='farmer');
  document.getElementById('mode-analyst').classList.toggle('on', m==='analyst');
  document.getElementById('modehint').textContent = m==='farmer'
   ? 'Simple view: today\u2019s action and a plain summary.'
   : 'Full dashboard: charts, logs and pilot-wide results.';
  if(m==='farmer' && ['season','compare','ml'].includes(state.pane)){
    document.querySelector('.navbtn[data-p="today"]').click();
  }
}
document.getElementById('mode-farmer').onclick=()=>setMode('farmer');
document.getElementById('mode-analyst').onclick=()=>setMode('analyst');
setMode('farmer');

document.getElementById('menubtn').onclick=()=>{ document.getElementById('sidebar').classList.add('open'); document.getElementById('scrim').classList.add('on'); };
document.getElementById('scrim').onclick=()=>{ document.getElementById('sidebar').classList.remove('open'); document.getElementById('scrim').classList.remove('on'); };

renderAll();
</script>
</body></html>"""

# Step 5 integration: retain the simulation dashboard and attach the API-backed panels.
def _step5_inject_once(old, new):
    global HTML
    if HTML.count(old) != 1:
        raise RuntimeError("Step 5 template marker changed: " + old[:80])
    HTML = HTML.replace(old, new, 1)

_step5_inject_once('<link rel="preconnect" href="https://fonts.googleapis.com">',
                   '<link rel="stylesheet" href="live_api.css">\n<link rel="preconnect" href="https://fonts.googleapis.com">')
_step5_inject_once('    <button class="navbtn" data-p="assistant"><span class="ic">&#9673;</span>Assistant</button>',
                   '    <button class="navbtn" data-p="crop-tool"><span class="ic">&#127793;</span>Crop recommendation</button>\n'
                   '    <button class="navbtn" data-p="scanner"><span class="ic">&#128247;</span>Leaf scanner</button>\n'
                   '    <button class="navbtn" data-p="history"><span class="ic">&#9776;</span>Farm history</button>\n'
                   '    <button class="navbtn" data-p="assistant"><span class="ic">&#9673;</span>Assistant</button>')
_step5_inject_once('      <div id="queue-wrap" style="display:none">', r'''      <div class="live-panel" id="live-farm-panel"><div class="live-head"><div><h2>Connected farm records</h2><div class="live-muted">Farmer and measurements loaded from the Flask database</div></div><span class="api-state" id="api-state">Connecting to local AgriPilot API…</span></div><div class="live-actions"><label for="api-farm" class="live-muted">Database farm</label><select id="api-farm" class="live-select" aria-label="Select database farm"><option value="">Loading farms…</option></select><button class="live-btn secondary" id="refresh-live">Refresh</button></div><div id="live-farm-content" class="live-msg" aria-live="polite">Loading saved farm data…</div><div id="live-advisory" class="live-result" hidden></div></div>
      <div id="queue-wrap" style="display:none">''')
_step5_inject_once('    <div class="pane" id="assistant">', r'''    <div class="pane" id="crop-tool">
      <h2 class="sec">Crop recommendation</h2><p class="helptext">Enter measured soil and weather values. The saved Step 2 model will return the recommendation and confidence.</p>
      <div class="live-panel"><div class="live-head"><h2>Farm inputs</h2><span class="live-muted" id="crop-prefill-note">Select a database farm to prefill its latest measurement</span></div>
        <form id="crop-form" class="live-form">
          <label>Nitrogen (N)<input name="n" type="number" step="any" required></label><label>Phosphorus (P)<input name="p" type="number" step="any" required></label><label>Potassium (K)<input name="k" type="number" step="any" required></label><label>Temperature °C<input name="temperature" type="number" step="any" required></label><label>Humidity %<input name="humidity" type="number" step="any" required></label><label>Soil pH<input name="ph" type="number" step="any" min="0" max="14" required></label><label>Rainfall mm<input name="rainfall" type="number" step="any" min="0" required></label>
          <div class="live-actions"><button class="live-btn" type="submit">Get model recommendation</button></div>
        </form><div id="crop-msg" class="live-msg" aria-live="polite"></div><div id="crop-result" class="live-result" hidden></div>
      </div>
    </div>
    <div class="pane" id="scanner">
      <h2 class="sec">Crop health scanner</h2><p class="helptext">Upload a clear leaf image for the saved Step 3 classifier. Results and the Grad-CAM overlay come from the model response.</p>
      <div class="live-panel"><form id="scan-form" class="live-form"><label>Leaf image (JPG, PNG, WebP; up to 10 MB)<input id="leaf-image" name="image" type="file" accept="image/jpeg,image/png,image/webp" required></label><div class="live-actions"><button class="live-btn" type="submit">Analyze leaf</button></div></form><div id="scan-msg" class="live-msg" aria-live="polite"></div><div id="scan-result" class="live-result" hidden></div></div>
    </div>
    <div class="pane" id="history">
      <h2 class="sec">Saved farm history</h2><p class="helptext">Records below are fetched from the selected farm’s database history endpoints.</p>
      <div class="live-panel"><div class="live-head"><h2 id="history-title">Recent predictions and advisories</h2><button class="live-btn secondary" id="refresh-history">Refresh history</button></div><div id="history-content" class="live-msg" aria-live="polite">Select a database farm to load history.</div></div>
    </div>
    <div class="pane" id="assistant">
      <div class="chatlang"><label class="live-muted" for="api-lang">Response language&nbsp;</label><select id="api-lang"><option value="en">English</option><option value="hi">हिन्दी</option><option value="mr">मराठी</option></select></div>''')
_step5_inject_once('        <div class="mlnote" id="ml-rl-note"></div>\n      </div>\n    </div>', r'''        <div class="mlnote" id="ml-rl-note"></div>
        <section class="live-panel" id="live-analyst">
          <div class="live-head"><div><h2>Live database and model evaluation</h2><div class="live-muted">Counts and metrics loaded from saved API records and evaluation artifacts</div></div><button class="live-btn secondary" id="refresh-analyst">Refresh analyst data</button></div>
          <div id="analyst-msg" class="live-msg" aria-live="polite">Loading saved model evaluations and records…</div><div id="analyst-content"></div>
        </section>
      </div>
    </div>''')
_step5_inject_once('</body></html>', '<script src="live_api.js" defer></script>\n</body></html>')

os.makedirs(os.path.join(BASE, "app"), exist_ok=True)
out_path = os.path.join(BASE, "app", "index.html")
open(out_path, "w", encoding="utf-8").write(HTML.replace("__PAYLOAD__", payload))
print("wrote", out_path, round(os.path.getsize(out_path) / 1024, 1), "KB")
