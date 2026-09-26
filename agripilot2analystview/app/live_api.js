/* AgriPilot Step 5 browser integration. The simulation dashboard remains independent. */
(() => {
  'use strict';
  const API = window.AGRIPILOT_API_BASE || (location.protocol === 'file:' ? 'http://127.0.0.1:5000' : location.origin);
  const S = { farms: [], farmId: null, context: null, scanUrl: null, sending: false };
  const $ = id => document.getElementById(id);
  const esc = v => String(v == null ? '' : v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const nfmt = (v, digits=2) => Number.isFinite(Number(v)) ? Number(v).toLocaleString(undefined,{maximumFractionDigits:digits}) : 'Unavailable';
  const lang = () => ($('api-lang') && $('api-lang').value) || 'en';
  const selectedFarm = () => S.farms.find(f => Number(f.id) === Number(S.farmId));
  async function api(path, options={}) {
    const response = await fetch(API + path, options);
    const type = response.headers.get('content-type') || '';
    const body = type.includes('json') ? await response.json() : {error:(await response.text()).slice(0,500)};
    if (!response.ok) throw new Error(body.error || body.message || ('API request failed ('+response.status+')'));
    return body;
  }
  const jsonPost = body => ({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  function message(id, text, error=false) { const el=$(id); if(el){el.textContent=text||'';el.classList.toggle('error',!!error);} }
  function stateLabel(text, kind='') { const el=$('api-state');if(el){el.textContent=text;el.className='api-state '+kind;} }
  function setLoading(button, busy, label) { if(!button)return; if(busy){button.dataset.label=button.textContent;button.textContent=label||'Please wait…';}else{button.textContent=button.dataset.label||button.textContent;} button.disabled=busy; }
  function facts(items) { return '<div class="live-grid">'+items.map(x=>'<div class="live-fact"><div class="l">'+esc(x[0])+'</div><div class="n">'+esc(x[1])+'</div></div>').join('')+'</div>'; }
  function fillInputs(m) {
    const form=$('crop-form');if(!form)return;
    const keys=['n','p','k','temperature','humidity','ph','rainfall'];
    let count=0;keys.forEach(k=>{const el=form.elements[k];if(m && m[k]!==null && m[k]!==undefined && m[k]!=='' ){el.value=m[k];count++;}});
    message('crop-prefill-note', count ? 'Prefilled '+count+' available value(s) from this farm’s latest saved measurement. Review before submitting.' : 'No saved measurement is available; enter all values yourself.');
  }
  function renderFarm(ctx) {
    S.context=ctx;
    const f=ctx.farm||{}, user=ctx.user||{}, crop=ctx.active_crop||{}, m=ctx.measurement||{};
    const climate=[['Temperature',m.temperature==null?'Unavailable':nfmt(m.temperature,1)+' °C'],['Humidity',m.humidity==null?'Unavailable':nfmt(m.humidity,1)+'%'],['Recorded rainfall',m.rainfall==null?'Unavailable':nfmt(m.rainfall,1)+' mm'],['Soil moisture',m.soil_moisture==null?'Unavailable':nfmt(m.soil_moisture,1)+'%']];
    const soil=[['Nitrogen (N)',m.n],['Phosphorus (P)',m.p],['Potassium (K)',m.k],['Soil pH',m.ph]].map(x=>[x[0],x[1]==null?'Unavailable':nfmt(x[1])]);
    $('live-farm-content').className='';
    $('live-farm-content').innerHTML='<div class="live-two"><div><h3>Farmer and farm</h3>'+facts([['Farmer',user.name||'Not recorded'],['Farm',f.name||'Unnamed farm'],['Location',[f.location,f.district,f.state].filter(Boolean).join(', ')||'Unavailable'],['Area',f.area_ha==null?'Unavailable':nfmt(f.area_ha)+' ha'],['Soil',f.soil_type||'Unavailable'],['Irrigation',f.irrigation_system||'Unavailable']])+'</div><div><h3>Current crop and saved readings</h3>'+facts([['Crop',crop.crop||'Not recorded'],['Variety',crop.variety||'Unavailable'],['Season',crop.season||'Unavailable'],...soil,...climate,['Measurement saved',m.recorded_at||'No measurement']])+'<div class="live-muted">Weather shown here is from the farm’s latest saved measurement. No live weather-forecast route is exposed by Step 4.</div></div></div><div class="live-actions"><button class="live-btn" id="get-farm-advisory">Get farm advisory</button><span class="live-muted">Uses the saved farm context and Step 2/3 results where available.</span></div>';
    fillInputs(m);
    $('get-farm-advisory').onclick=loadFarmAdvisory;
    const prev=$('live-advisory');prev.hidden=true;prev.innerHTML='';
  }
  async function chooseFarm(id) {
    S.farmId=id?Number(id):null;S.context=null;
    if(!id){message('live-farm-content','No farm records are available. Start the Flask API to initialize its database or add a farm using the Step 4 API.',true);return;}
    message('live-farm-content','Loading farm record…');
    try {const ctx=await api('/api/farms/'+encodeURIComponent(id));renderFarm(ctx);stateLabel('Connected · '+API,'ok');await loadHistory();}
    catch(e){message('live-farm-content',e.message,true);stateLabel('Farm request failed','bad');}
  }
  async function loadFarms() {
    stateLabel('Connecting to '+API+'…');
    const farms=await api('/api/farms');S.farms=Array.isArray(farms)?farms:[];
    const sel=$('api-farm');const wanted=localStorage.getItem('agripilot-api-farm');
    sel.innerHTML=S.farms.length?S.farms.map(f=>'<option value="'+esc(f.id)+'">'+esc(f.name||('Farm '+f.id))+' · '+esc(f.location||f.district||f.state||'Location not recorded')+'</option>').join(''):'<option value="">No saved farms</option>';
    if(S.farms.length){const selected=S.farms.some(f=>String(f.id)===wanted)?wanted:String(S.farms[0].id);sel.value=selected;localStorage.setItem('agripilot-api-farm',selected);await chooseFarm(selected);}
    else {S.farmId=null;stateLabel('Connected · no saved farms','ok');message('live-farm-content','No farm records returned by the API.');}
  }
  function localized(v) {if(v==null)return '';if(typeof v==='string')return v;if(Array.isArray(v))return v.filter(Boolean).join(' · ');if(typeof v==='object')return v[lang()]||v.en||Object.values(v).find(x=>typeof x==='string')||'';return String(v);}
  function listHtml(title, value) {const txt=localized(value);return '<h4>'+esc(title)+'</h4>'+(txt?'<p>'+esc(txt)+'</p>':'<p class="live-muted">Not available in the model response.</p>');}
  function showCropResult(result, advisory) {
    const alts=(result.alternatives||[]).map(x=>'<li>'+esc(x.crop)+' — '+esc(x.confidence_pct==null?nfmt(x.probability*100,1)+'%':nfmt(x.confidence_pct,1)+'%')+'</li>').join('');
    const reasons=(result.reasons||[]).map(x=>'<li><b>'+esc(x.factor||'Reason')+':</b> '+esc(x.detail||x)+'</li>').join('');
    $('crop-result').hidden=false;$('crop-result').innerHTML='<h3>Model recommendation: '+esc(result.recommended_crop||'Unavailable')+'</h3>'+facts([['Model',result.model_used||'Unavailable'],['Confidence',result.confidence_pct==null?'Unavailable':nfmt(result.confidence_pct,1)+'%']])+(alts?'<h4>Alternative predictions</h4><ul class="live-list">'+alts+'</ul>':'')+(reasons?'<h4>Model explanation</h4><ul class="live-list">'+reasons+'</ul>':'')+(advisory?'<h4>Farm advisory</h4><p>'+esc(advisory.summary||'')+'</p><p>'+esc((advisory.irrigation||{}).label||'')+'</p>':'');
  }
  async function submitCrop(e) {
    e.preventDefault();const form=e.currentTarget,button=form.querySelector('button[type=submit]');message('crop-msg','');$('crop-result').hidden=true;
    if(!form.reportValidity())return;
    const vals={};for(const k of ['n','p','k','temperature','humidity','ph','rainfall']){const v=Number(form.elements[k].value);if(!Number.isFinite(v)){message('crop-msg','Enter a valid number for every required input.',true);return;}vals[k]=v;}
    if(vals.ph<0||vals.ph>14||vals.rainfall<0){message('crop-msg','Check the input ranges for pH and rainfall.',true);return;}
    if(S.farmId)vals.farm_id=S.farmId;
    setLoading(button,true,'Running saved model…');message('crop-msg','Sending measured inputs to the crop recommendation API…');
    try {const result=await api('/api/crop-recommend',jsonPost(vals));let adv=null;if(S.farmId){try{adv=await api('/api/advisory',jsonPost({farm_id:S.farmId,language:lang(),run_crop_model:false,persist:false}));}catch(e){message('crop-msg','Prediction received. Advisory unavailable: '+e.message,true);}}
      showCropResult(result,adv);if(!adv)message('crop-msg','Prediction returned by the saved Step 2 model.');else message('crop-msg','Prediction and farm advisory loaded.');if(S.farmId)loadHistory();
    } catch(e){message('crop-msg',e.message,true);} finally{setLoading(button,false);}
  }
  function requestAssistant(prompt){const input=$('chatin');input.value=prompt||'Please explain my latest crop health result and safe next steps.';document.querySelector('.navbtn[data-p="assistant"]').click();window.sendChat(input.value);}
  function diseaseResultHtml(r, advisory, imageUrl) {
    const candidates=(r.top_candidates||[]).map(x=>'<li>'+esc(x.display_name||x.class_name)+' — '+esc(x.confidence_pct==null?nfmt(Number(x.confidence)*100,1)+'%':nfmt(x.confidence_pct,1)+'%')+'</li>').join('');
    const crop=advisory&&advisory.standing_crop?advisory.standing_crop:r.crop;
    const care=advisory&&advisory.actions?advisory.actions.map(a=>a.text).filter(Boolean):[];
    const precaution=localized(r.precautions),symptoms=localized(r.symptoms),prevention=localized(r.prevention);
    const treatment=r.treatment||{};const safeManagement=localized(treatment.organic_biological_management||treatment.general_management||treatment.cultural_management);
    const irrigation=advisory&&advisory.irrigation?advisory.irrigation.label:'';
    const gradcam=r.gradcam_base64||null;
    const explain=gradcam?'<h4>Grad-CAM model explanation</h4><img alt="Grad-CAM overlay from the classifier" src="'+esc(gradcam)+'">':(r.gradcam_path?'<p class="live-muted">Grad-CAM was saved by the backend at '+esc(r.gradcam_path)+'; the API did not return image bytes.</p>':'<p class="live-muted">Grad-CAM was not returned for this request.</p>');
    return '<h3>Leaf analysis result</h3><img class="live-image-preview" alt="Uploaded leaf image" src="'+esc(imageUrl)+'">'+facts([['Crop',r.crop||'Unavailable'],['Diagnosis',r.disease||'Unavailable'],['Confidence',r.confidence_pct==null?'Unavailable':nfmt(r.confidence_pct,1)+'%'],['Severity',r.severity||'Unavailable'],['Healthy classification',r.is_healthy==null?'Unavailable':(r.is_healthy?'Yes':'No')]])+explain+(candidates?'<h4>Other model candidates</h4><ul class="live-list">'+candidates+'</ul>':'')+listHtml('Symptoms',symptoms)+listHtml('Precautions',precaution)+listHtml('General management',safeManagement)+listHtml('Prevention',prevention)+(irrigation?'<h4>Farm irrigation/care context</h4><p>'+esc(irrigation)+'</p>'+care.map(c=>'<p>'+esc(c)+'</p>').join(''):'<p class="live-muted">Farm-specific irrigation/care advisory is unavailable; no measurement context was returned.</p>')+'<div class="live-actions"><button class="live-btn" id="ask-disease-assistant">Ask Assistant about this result</button></div>';
  }
  async function submitScan(e) {
    e.preventDefault();const form=e.currentTarget,button=form.querySelector('button[type=submit]'),file=$('leaf-image').files[0];$('scan-result').hidden=true;message('scan-msg','');
    if(!file){message('scan-msg','Choose a leaf image first.',true);return;}
    if(!/^image\/(jpeg|png|webp)$/.test(file.type)){message('scan-msg','Upload a JPEG, PNG, or WebP image.',true);return;}
    if(file.size>10*1024*1024){message('scan-msg','Image is larger than 10 MB. Choose a smaller image.',true);return;}
    const fd=new FormData();fd.append('image',file,file.name);fd.append('gradcam','1');fd.append('include_gradcam_b64','1');if(S.farmId)fd.append('farm_id',String(S.farmId));
    setLoading(button,true,'Analyzing image…');message('scan-msg','Uploading image to the Step 3 disease classifier…');
    try {const r=await api('/api/disease-predict',{method:'POST',body:fd});let adv=null;if(S.farmId){try{adv=await api('/api/advisory',jsonPost({farm_id:S.farmId,language:lang(),run_crop_model:false,persist:false}));}catch(e){message('scan-msg','Diagnosis returned. Farm advisory unavailable: '+e.message,true);}}
      if(S.scanUrl)URL.revokeObjectURL(S.scanUrl);S.scanUrl=URL.createObjectURL(file);$('scan-result').hidden=false;$('scan-result').innerHTML=diseaseResultHtml(r,adv,S.scanUrl);$('ask-disease-assistant').onclick=()=>requestAssistant('Please explain the '+(r.disease||'leaf diagnosis')+' result for '+(r.crop||'my crop')+' in simple '+lang()+' language. Give only general safe management and prevention guidance.');if(S.farmId)loadHistory();if(!adv)message('scan-msg','Diagnosis returned by the saved Step 3 model.');else message('scan-msg','Diagnosis and farm-context advisory loaded.');
    } catch(e){message('scan-msg',e.message,true);} finally{setLoading(button,false);}
  }
  function fmtDate(x){return x||'Date unavailable';}
  function itemCard(title, line, date, detail='') {return '<div class="live-history-card"><b>'+esc(title)+'</b><div>'+esc(line||'')+'</div>'+(detail?'<div class="live-muted">'+esc(detail)+'</div>':'')+'<div class="live-muted">'+esc(fmtDate(date))+'</div></div>';}
  function parseJson(s){try{return typeof s==='string'?JSON.parse(s):s;}catch(_){return null;}}
  async function loadHistory() {
    if(!S.farmId)return;
    const el=$('history-content');if(el)el.textContent='Loading saved history…';
    try {
      const [crops,diseases,advisories,queries,irrigation]=await Promise.all(['crop-predictions','disease-predictions','advisories','queries','irrigation'].map(x=>api('/api/history/'+x+'?farm_id='+S.farmId+'&limit=10')));
      const blocks=[];
      crops.forEach(x=>blocks.push(itemCard('Crop recommendation',x.recommended_crop+' · confidence '+(x.confidence==null?'Unavailable':nfmt(x.confidence*100,1)+'%'),x.created_at,x.model_name||'')));
      diseases.forEach(x=>blocks.push(itemCard('Leaf diagnosis',(x.crop||'Crop')+' · '+(x.disease||x.class_name||'Unavailable')+' · confidence '+(x.confidence==null?'Unavailable':nfmt(x.confidence*100,1)+'%'),x.created_at,x.image_name||'')));
      advisories.forEach(x=>blocks.push(itemCard('Farm advisory',x.summary||x.title||'Saved advisory',x.created_at,x.language||'')));
      queries.forEach(x=>blocks.push(itemCard('Assistant query',x.question,x.created_at,x.answer||'')));
      irrigation.forEach(x=>blocks.push(itemCard('Irrigation',x.recommendation,x.created_at,x.reason||'')));
      $('history-content').innerHTML=blocks.length?blocks.join(''):'<p class="live-muted">No saved prediction, advisory, or assistant history for this farm yet.</p>';
    } catch(e){if(el){el.textContent=e.message;el.classList.add('error');}}
  }
  function matrixTable(title, matrix, labels) {
    if(!Array.isArray(matrix)||!matrix.length)return '<p class="live-muted">'+esc(title)+': unavailable in saved evaluation artifact.</p>';
    const names=Array.isArray(labels)?labels:matrix.map((_,i)=>String(i));
    return '<h4>'+esc(title)+'</h4><div class="live-table-wrap"><table class="live-table"><thead><tr><th>Actual ↓ / Predicted →</th>'+names.map(n=>'<th>'+esc(n)+'</th>').join('')+'</tr></thead><tbody>'+matrix.map((row,i)=>'<tr><th>'+esc(names[i]||i)+'</th>'+row.map(v=>'<td>'+esc(v)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';
  }
  function metricCards(o) {if(!o)return '<p class="live-muted">Evaluation metrics unavailable in saved artifact.</p>';return facts([['Accuracy',o.accuracy_pct==null?(o.accuracy==null?'Unavailable':nfmt(o.accuracy*100,2)+'%'):nfmt(o.accuracy_pct,2)+'%'],['Precision (macro)',o.precision_macro==null?'Unavailable':nfmt(o.precision_macro*100,2)+'%'],['Recall (macro)',o.recall_macro==null?'Unavailable':nfmt(o.recall_macro*100,2)+'%'],['F1 (macro)',o.f1_macro==null?'Unavailable':nfmt(o.f1_macro*100,2)+'%']]);}
  function renderAnalyst(data,records) {
    const c=data.crop,d=data.disease;let out='<h3>Database records</h3>'+facts([['Farmers',records.users.length],['Farms',records.farms.length],['Crop predictions',records.crop.length],['Disease predictions',records.disease.length],['Advisories',records.advisories.length],['Assistant queries',records.queries.length]]);
    out+='<div class="live-two"><div class="mlcard"><h3>Crop classifier · '+esc(c&&c.best_model||'evaluation unavailable')+'</h3>'+metricCards(c&&c.best_model&&c.comparison?c.comparison[c.best_model]:null);
    if(c&&c.comparison){out+='<h4>Model comparison</h4><div class="live-table-wrap"><table class="live-table"><thead><tr><th>Model</th><th>Accuracy</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead><tbody>'+Object.entries(c.comparison).map(([k,v])=>'<tr><td>'+esc(v.model_name||k)+'</td><td>'+nfmt(v.accuracy*100,2)+'%</td><td>'+nfmt(v.precision_macro*100,2)+'%</td><td>'+nfmt(v.recall_macro*100,2)+'%</td><td>'+nfmt(v.f1_macro*100,2)+'%</td></tr>').join('')+'</tbody></table></div>';const key=c.best_model;out+=matrixTable('Confusion matrix · '+key,c.confusion_matrices&&c.confusion_matrices[key],c.metadata&&c.metadata.classes);const fs=c.feature_importance&&c.feature_importance[key];if(fs&&fs.length)out+='<h4>Feature importance · '+esc(key)+'</h4><ol class="live-list">'+fs.map(x=>'<li>'+esc(x.label||x.feature)+' — '+nfmt(x.importance,4)+'</li>').join('')+'</ol>';}
    out+='</div><div class="mlcard"><h3>Disease classifier</h3>'+metricCards(d&&d.overall);if(d&&d.overall)out+='<p class="live-muted">Held-out samples: '+esc(d.overall.correct_samples)+' / '+esc(d.overall.total_samples)+'</p>';const labels=d&&d.metadata&&d.metadata.classes;out+=matrixTable('Confusion matrix',d&&d.confusion_matrix,labels);if(d&&d.per_class){out+='<h4>Per-class precision / recall / F1</h4><div class="live-table-wrap"><table class="live-table"><thead><tr><th>Class</th><th>Precision</th><th>Recall</th><th>F1</th><th>Support</th></tr></thead><tbody>'+Object.entries(d.per_class).map(([k,v])=>'<tr><td>'+esc(k)+'</td><td>'+nfmt(v.precision*100,1)+'%</td><td>'+nfmt(v.recall*100,1)+'%</td><td>'+nfmt(v.f1_score*100,1)+'%</td><td>'+esc(v.support)+'</td></tr>').join('')+'</tbody></table></div>';}
    out+='</div></div>';
    const dist={};records.disease.forEach(x=>{const k=x.class_name||x.disease||'Unspecified';dist[k]=(dist[k]||0)+1;});const crops={};records.crop.forEach(x=>{const k=x.recommended_crop||'Unspecified';crops[k]=(crops[k]||0)+1;});out+='<div class="live-two"><div class="mlcard"><h3>Saved prediction distributions</h3><h4>Recommended crops</h4>'+(Object.keys(crops).length?'<ul>'+Object.entries(crops).map(([k,v])=>'<li>'+esc(k)+': '+v+'</li>').join('')+'</ul>':'<p class="live-muted">No saved crop predictions.</p>')+'<h4>Disease classes</h4>'+(Object.keys(dist).length?'<ul>'+Object.entries(dist).map(([k,v])=>'<li>'+esc(k)+': '+v+'</li>').join('')+'</ul>':'<p class="live-muted">No saved disease predictions.</p>')+'</div><div class="mlcard"><h3>Registered farms</h3>'+(records.farms.length?'<ul>'+records.farms.map(f=>'<li>'+esc(f.name)+' · '+esc([f.location,f.district,f.state].filter(Boolean).join(', ')||'location unavailable')+'</li>').join('')+'</ul>':'<p class="live-muted">No saved farms.</p>')+'</div></div>';
    $('analyst-content').innerHTML=out;
  }
  async function loadAnalyst() {
    message('analyst-msg','Loading saved evaluations and database records…');
    try {const [data,users,farms,crop,disease,advisories,queries]=await Promise.all([api('/api/model-evaluation'),api('/api/records/users?limit=500'),api('/api/records/farms?limit=500'),api('/api/records/crop_predictions?limit=1000'),api('/api/records/disease_predictions?limit=1000'),api('/api/records/advisories?limit=1000'),api('/api/records/farmer_queries?limit=1000')]);renderAnalyst(data,{users,farms,crop,disease,advisories,queries});message('analyst-msg','Live data loaded from the Flask API and saved evaluation JSON.');}
    catch(e){message('analyst-msg',e.message,true);}
  }
  async function loadFarmAdvisory() {
    if(!S.farmId){message('live-farm-content','Select a saved farm first.',true);return;}
    const btn=$('get-farm-advisory');setLoading(btn,true,'Building advisory…');const box=$('live-advisory');box.hidden=false;box.textContent='Loading advisory from the backend…';
    try {const a=await api('/api/advisory',jsonPost({farm_id:S.farmId,language:lang(),run_crop_model:true,persist:true}));box.innerHTML='<h3>'+esc(a.summary||'Farm advisory')+'</h3>'+facts([['Standing crop',a.standing_crop||'Unavailable'],['Irrigation',a.irrigation&&a.irrigation.label||'Unavailable'],['Crop recommendation',a.crop_recommendation&&a.crop_recommendation.recommended_crop||'Unavailable'],['Model confidence',a.crop_recommendation&&a.crop_recommendation.confidence_pct!=null?nfmt(a.crop_recommendation.confidence_pct,1)+'%':'Unavailable']])+'<h4>Reasons</h4><ul class="live-list">'+(a.reasons||[]).map(x=>'<li><b>'+esc(x.factor||'')+':</b> '+esc(x.detail||'')+'</li>').join('')+'</ul>';await loadHistory();loadAnalyst();}
    catch(e){box.textContent=e.message;box.classList.add('error');}finally{setLoading(btn,false);}
  }
  async function sendAssistant(text) {
    text=String(text||'').trim();if(!text||S.sending)return;
    const log=$('chatlog'),input=$('chatin'),button=$('chatsend');S.sending=true;addBubble('user',text);input.value='';button.disabled=true;const typing=addBubble('bot','Waiting for farm assistant…');
    try {const out=await api('/api/assistant',jsonPost({farm_id:S.farmId||null,language:lang(),question:text,persist:!!S.farmId}));typing.textContent=out.answer||'The assistant returned no answer.';if(Array.isArray(out.sources)&&out.sources.length){const src=document.createElement('div');src.className='live-muted';src.textContent='Sources: '+out.sources.map(x=>x.title||x.source||'knowledge base').join('; ');typing.appendChild(src);}loadHistory();}
    catch(e){typing.textContent='Assistant unavailable: '+e.message;typing.classList.add('error');}
    finally{S.sending=false;button.disabled=false;log.scrollTop=log.scrollHeight;}
  }
  function addBubble(role,text) {const b=document.createElement('div');b.className='bubble '+(role==='bot'?'bot':'user');b.textContent=text;const log=$('chatlog');log.appendChild(b);log.scrollTop=log.scrollHeight;return b;}
  function resetBackendChat(){const log=$('chatlog');log.replaceChildren();const farm=selectedFarm();$('chat-sub').textContent=farm?'Step 4 assistant · '+(farm.name||'selected farm')+' · '+lang():'Step 4 assistant · no farm selected · '+lang();addBubble('bot',farm?'Ask a question about your selected farm. The answer will use saved farm context and the selected response language.':'Connect the backend or select a farm to include farm context.');}
  function addTodayAssistantControl(){const header=document.querySelector('#assistant .chathead');if(!header)return;}
  document.addEventListener('DOMContentLoaded', () => {
    $('api-farm').addEventListener('change',e=>{localStorage.setItem('agripilot-api-farm',e.target.value);chooseFarm(e.target.value);resetBackendChat();});
    $('refresh-live').onclick=()=>loadFarms().catch(e=>{stateLabel('Backend unavailable','bad');message('live-farm-content',e.message,true);});
    $('refresh-history').onclick=loadHistory;$('refresh-analyst').onclick=loadAnalyst;
    $('crop-form').addEventListener('submit',submitCrop);$('scan-form').addEventListener('submit',submitScan);
    document.querySelectorAll('.navbtn').forEach(b=>b.addEventListener('click',()=>{const titles={'crop-tool':'Crop recommendation',scanner:'Crop health scanner',history:'Farm history',ml:'ML insights'};if(titles[b.dataset.p])document.getElementById('tb-title').textContent=titles[b.dataset.p];if(b.dataset.p==='ml')loadAnalyst();if(b.dataset.p==='history')loadHistory();}));
    $('api-lang').addEventListener('change',()=>{const f=selectedFarm();$('chat-sub').textContent='Step 4 assistant · '+(f&&f.name||'no farm selected')+' · '+lang();});
    window.sendChat=sendAssistant;window.resetChat=resetBackendChat;
    loadFarms().catch(e=>{stateLabel('Backend unavailable','bad');message('live-farm-content','Could not load farm data. Start the Flask API at '+API+'. '+e.message,true);$('api-farm').innerHTML='<option value="">API unavailable</option>';});
    loadAnalyst();resetBackendChat();
  });
})();
