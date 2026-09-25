/* AgriPilot Step 5 browser integration. The simulation dashboard remains independent. */
(() => {
  'use strict';
  const API = window.AGRIPILOT_API_BASE || (location.protocol === 'file:' ? 'http://127.0.0.1:5000' : location.origin);
  const S = { farms: [], farmId: null, context: null, scanUrl: null, sending: false, supportedDiseaseCrops: [] };
  const $ = id => document.getElementById(id);
  const t = value => window.AgriPilotI18n ? window.AgriPilotI18n.t(value) : value;
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
  function message(id, text, error=false) { const el=$(id);if(el){el.textContent=t(text||'');el.classList.toggle('error',!!error);} }
  function stateLabel(text, kind='') { const el=$('api-state');if(el){el.textContent=t(text);el.className='api-state '+kind;} }
  function setLoading(button, busy, label) { if(!button)return; if(busy){button.dataset.label=button.textContent;button.textContent=t(label||'Please wait…');}else{button.textContent=button.dataset.label||button.textContent;} button.disabled=busy; }
  function facts(items) { return '<div class="live-grid">'+items.map(x=>'<div class="live-fact"><div class="l">'+esc(t(x[0]))+'</div><div class="n">'+esc(t(x[1]))+'</div></div>').join('')+'</div>'; }
  function fillInputs(m) {
    const form=$('crop-form');if(!form)return;
    const soilSource=m&&m.source==='soil_test_report_farmer_entered';
    const keys=soilSource?['n','p','k','ph']:[];
    let count=0;keys.forEach(k=>{const el=form.elements[k];if(m && m[k]!==null && m[k]!==undefined && m[k]!==''){el.value=m[k];count++;}});
    message('crop-prefill-note', count ? 'Loaded '+count+' previously saved, farmer-confirmed soil value(s). Please review and confirm them again.' : 'No previously saved, farmer-confirmed soil report values. Fields are left blank.');
  }
  function updateSoilReportFields() {
    const choice=document.querySelector('#crop-form input[name="soil_report"]:checked');
    const confirmed=!!choice&&choice.value==='yes';
    const workflow=$('crop-model-fields');workflow.hidden=!confirmed;
    workflow.querySelectorAll('input').forEach(input=>{input.disabled=!confirmed;});
    const fields=$('soil-report-fields');fields.hidden=!confirmed;
    fields.querySelectorAll('input').forEach(input=>{input.disabled=!confirmed;input.required=confirmed&&(['n','p','k','ph'].includes(input.name)||input.name==='soil_confirm');});
    $('soil-report-note').hidden=!(choice&&choice.value==='no');
    if(choice&&choice.value==='no'){fields.querySelectorAll('input').forEach(input=>{input.value='';});['temperature','humidity','rainfall'].forEach(key=>{workflow.querySelector('[name="'+key+'"]').value='';});}
  }
  function renderFarm(ctx) {
    S.context=ctx;
    const f=ctx.farm||{}, user=ctx.user||{}, crop=ctx.active_crop||{}, m=ctx.measurement||{};
    const title=document.getElementById('tb-title');if(title)title.textContent=t('My Farm');
    const crumb=document.getElementById('tb-crumb');if(crumb)crumb.textContent=[f.name,[f.location,f.district,f.state].filter(Boolean).join(', ')].filter(Boolean).join(' · ');
    const pill=document.getElementById('tb-pill');if(pill)pill.textContent='Farm ID '+f.id;
    const currentUser=window.AGRIPILOT_CURRENT_USER;
    const controls=$('farm-selection-controls');if(controls)controls.hidden=!!(currentUser&&currentUser.role==='farmer'&&S.farms.length<=1);
    const climate=[['Temperature',m.temperature==null?'Unavailable':nfmt(m.temperature,1)+' °C'],['Humidity',m.humidity==null?'Unavailable':nfmt(m.humidity,1)+'%'],['Recorded rainfall',m.rainfall==null?'Unavailable':nfmt(m.rainfall,1)+' mm'],['Soil moisture',m.soil_moisture==null?'Unavailable':nfmt(m.soil_moisture,1)+'%']];
    const soil=[['Nitrogen (N)',m.n],['Phosphorus (P)',m.p],['Potassium (K)',m.k],['Soil pH',m.ph]].map(x=>[x[0],x[1]==null?'Unavailable':nfmt(x[1])]);
    $('live-farm-content').className='';
    $('live-farm-content').innerHTML='<div class="live-two"><div><h3>'+esc(t('Farm profile'))+'</h3>'+facts([['Farm',f.name||'Unnamed farm'],['Owner',user.name||'Not recorded'],['Location',[f.location,f.district,f.state].filter(Boolean).join(', ')||'Unavailable'],['Area',f.area_ha==null?'Unavailable':nfmt(f.area_ha)+' ha'],['Soil',f.soil_type||'Unavailable'],['Irrigation',f.irrigation_system||'Unavailable']])+'</div><div><h3>'+esc(t('Current crop and saved readings'))+'</h3>'+facts([['Crop',crop.crop||'Not recorded'],['Variety',crop.variety||'Unavailable'],['Season',crop.season||'Unavailable'],...soil,...climate,['Measurement saved',m.recorded_at||'No measurement']])+'<div class="live-muted">'+esc(t('The values above are stored farm measurements, not live weather.'))+'</div><section class="farm-weather"><div class="live-head"><h3>'+esc(t('Live weather'))+'</h3><button type="button" class="live-btn secondary" id="refresh-farm-weather">'+esc(t('Refresh'))+'</button></div><div id="farm-weather-data" class="live-muted" aria-live="polite">'+esc(t('Loading live weather…'))+'</div></section></div></div><details class="farm-edit"><summary>'+esc(t('Edit farm profile'))+'</summary><form id="farm-profile-form" class="live-form"><label>'+esc(t('Farm name'))+'<input name="name" maxlength="160" required value="'+esc(f.name||'')+'"></label><label>'+esc(t('Location'))+'<input name="location" maxlength="160" value="'+esc(f.location||'')+'"></label><label>'+esc(t('District'))+'<input name="district" maxlength="100" value="'+esc(f.district||'')+'"></label><label>'+esc(t('State'))+'<input name="state" maxlength="100" value="'+esc(f.state||'')+'"></label><label>'+esc(t('Area (hectares)'))+'<input name="area_ha" type="number" min="0" step="any" value="'+esc(f.area_ha==null?'':f.area_ha)+'"></label><label>'+esc(t('Soil type'))+'<input name="soil_type" maxlength="100" value="'+esc(f.soil_type||'')+'"></label><label>'+esc(t('Irrigation system'))+'<input name="irrigation_system" maxlength="100" value="'+esc(f.irrigation_system||'')+'"></label><label>'+esc(t('Current crop'))+'<input name="crop" maxlength="100" value="'+esc(crop.crop||'')+'"></label><label>'+esc(t('Variety'))+'<input name="variety" maxlength="100" value="'+esc(crop.variety||'')+'"></label><label>'+esc(t('Season'))+'<input name="season" maxlength="100" value="'+esc(crop.season||'')+'"></label><label>'+esc(t('Sowing date'))+'<input name="sowing_date" type="date" value="'+esc(crop.sowing_date||'')+'"></label><div class="live-actions"><button class="live-btn" type="submit">'+esc(t('Save farm profile'))+'</button></div></form><div id="farm-profile-msg" class="live-msg" aria-live="polite"></div></details><div class="live-actions"><button class="live-btn" id="get-farm-advisory">'+esc(t('Get farm advisory'))+'</button><span class="live-muted">'+esc(t('Uses this farm’s saved context and model results.'))+'</span></div>';
    fillInputs(m);
    $('farm-profile-form').addEventListener('submit',saveFarmProfile);
    $('refresh-farm-weather').addEventListener('click',()=>loadFarmWeather(f.id));
    loadFarmWeather(f.id);
    $('get-farm-advisory').onclick=loadFarmAdvisory;
    const prev=$('live-advisory');prev.hidden=true;prev.innerHTML='';
  }
  async function saveFarmProfile(e) {
    e.preventDefault();const form=e.currentTarget;const msg=$('farm-profile-msg');
    if(!form.reportValidity()||!S.farmId)return;
    const body=Object.fromEntries(new FormData(form).entries());
    body.area_ha=body.area_ha===''?null:Number(body.area_ha);
    try {await api('/api/farms/'+encodeURIComponent(S.farmId),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});message('farm-profile-msg','Farm profile saved.');await chooseFarm(S.farmId);}
    catch(err){message('farm-profile-msg',err.message,true);}
  }
  async function chooseFarm(id) {
    S.farmId=id?Number(id):null;S.context=null;
    if(!id){message('live-farm-content','No farm records are available. Start the Flask API to initialize its database or add a farm using the Step 4 API.',true);return;}
    message('live-farm-content','Loading farm record…');
    try {const ctx=await api('/api/farms/'+encodeURIComponent(id));renderFarm(ctx);stateLabel('Connected · '+API,'ok');await loadHistory();}
    catch(e){message('live-farm-content',e.message,true);stateLabel('Farm request failed','bad');}
  }
  async function loadFarmWeather(id) {
    const box=$('farm-weather-data');if(!box)return;
    box.classList.remove('error');box.textContent=t('Loading live weather…');
    try {
      const result=await api('/api/farms/'+encodeURIComponent(id)+'/weather');
      if(!result.available){box.textContent=t(result.message||'Weather data is currently unavailable.');return;}
      const c=result.current||{},d=result.daily||{},place=result.location||{};
      const current=[['Temperature',c.temperature_2m==null?null:nfmt(c.temperature_2m,1)+' °C'],['Relative humidity',c.relative_humidity_2m==null?null:nfmt(c.relative_humidity_2m,0)+'%'],['Recent precipitation',c.precipitation==null?null:nfmt(c.precipitation,1)+' mm']].filter(x=>x[1]!=null);
      const days=(d.time||[]).map((date,i)=>date+': '+(d.temperature_2m_min&&d.temperature_2m_max?nfmt(d.temperature_2m_min[i],0)+'–'+nfmt(d.temperature_2m_max[i],0)+' °C':t('temperature unavailable'))+'; '+t('precipitation')+' '+(d.precipitation_sum?nfmt(d.precipitation_sum[i],1)+' mm':t('unavailable'))).join(' · ');
      box.innerHTML='<div class="live-muted">'+esc(t('Source:'))+' '+esc(result.source)+' · '+esc([place.name,place.district,place.state].filter(Boolean).join(', '))+' · '+esc(c.time||t('time unavailable'))+' ('+esc(result.timezone||t('timezone unavailable'))+')</div>'+facts(current)+ (days?'<div class="live-muted">'+esc(t('Daily forecast:'))+' '+esc(days)+'</div>':'');
    } catch(e){box.textContent=t('Weather data is currently unavailable.');box.classList.add('error');}
  }
  async function loadDiseaseModelInfo() {
    const coverage=$('scan-coverage');
    try {
      const info=await api('/api/disease-model-info');
      S.supportedDiseaseCrops=Array.isArray(info.supported_crops)?info.supported_crops:[];
      $('supported-disease-crops').replaceChildren(...S.supportedDiseaseCrops.map(crop=>new Option(crop,crop)));
      coverage.textContent=S.supportedDiseaseCrops.length?t('Supported crops in the saved model:')+' '+S.supportedDiseaseCrops.join(', ')+'. '+t('Other crops are rejected.'):t('Crop coverage is unavailable from the model metadata.');
    } catch(e){coverage.textContent=t('Could not load disease model crop coverage:')+' '+e.message;}
  }
  async function loadFarms() {
    stateLabel('Connecting to '+API+'…');
    const farms=await api('/api/farms');S.farms=Array.isArray(farms)?farms:[];
    const sel=$('api-farm');const wanted=localStorage.getItem('agripilot-api-farm');
    const user=window.AGRIPILOT_CURRENT_USER;const controls=$('farm-selection-controls');if(controls)controls.hidden=!!(user&&user.role==='farmer'&&S.farms.length<=1);
    sel.innerHTML=S.farms.length?S.farms.map(f=>'<option value="'+esc(f.id)+'">'+esc(f.name||('Farm '+f.id))+' · '+esc(f.location||f.district||f.state||'Location not recorded')+'</option>').join(''):'<option value="">No saved farms</option>';
    if(S.farms.length){const selected=S.farms.some(f=>String(f.id)===wanted)?wanted:String(S.farms[0].id);sel.value=selected;localStorage.setItem('agripilot-api-farm',selected);await chooseFarm(selected);}
    else {S.farmId=null;stateLabel('Connected · no saved farms','ok');message('live-farm-content','No farm records returned by the API.');}
  }
  function localized(v) {if(v==null)return '';if(typeof v==='string')return v;if(Array.isArray(v))return v.filter(Boolean).join(' · ');if(typeof v==='object')return v[lang()]||v.en||Object.values(v).find(x=>typeof x==='string')||'';return String(v);}
  function listHtml(title, value) {const txt=localized(value);return '<h4>'+esc(t(title))+'</h4>'+(txt?'<p>'+esc(txt)+'</p>':'<p class="live-muted">'+esc(t('Not available in the model response.'))+'</p>');}
  function showCropResult(result, advisory) {
    const alts=(result.alternatives||[]).map(x=>'<li>'+esc(x.crop)+' — '+esc(x.confidence_pct==null?nfmt(x.probability*100,1)+'%':nfmt(x.confidence_pct,1)+'%')+'</li>').join('');
    const reasons=(result.reasons||[]).map(x=>'<li><b>'+esc(x.factor||'Reason')+':</b> '+esc(x.detail||x)+'</li>').join('');
    $('crop-result').hidden=false;$('crop-result').innerHTML='<h3>Model recommendation: '+esc(result.recommended_crop||'Unavailable')+'</h3>'+facts([['Model',result.model_used||'Unavailable'],['Confidence',result.confidence_pct==null?'Unavailable':nfmt(result.confidence_pct,1)+'%']])+(alts?'<h4>Alternative predictions</h4><ul class="live-list">'+alts+'</ul>':'')+(reasons?'<h4>Model explanation</h4><ul class="live-list">'+reasons+'</ul>':'')+(advisory?'<h4>Farm advisory</h4><p>'+esc(advisory.summary||'')+'</p><p>'+esc((advisory.irrigation||{}).label||'')+'</p>':'');
  }
  async function submitCrop(e) {
    e.preventDefault();const form=e.currentTarget,button=form.querySelector('button[type=submit]');message('crop-msg','');$('crop-result').hidden=true;
    const soilReport=form.querySelector('input[name="soil_report"]:checked');
    if(!soilReport){message('crop-msg','Please say whether you have a soil test report.',true);return;}
    if(soilReport.value!=='yes'){message('crop-msg','Precise soil-based crop recommendation requires soil information from a soil test report.',true);return;}
    if(!form.elements.soil_confirm.checked){message('crop-msg','Please review and confirm all N, P, K, and pH values against your real soil test report.',true);return;}
    if(!['n','p','k','ph'].every(k=>String(form.elements[k].value||'').trim()!=='')){message('crop-msg','Enter Nitrogen, Phosphorus, Potassium, and pH exactly as shown on your real soil report.',true);return;}
    if(!String(form.elements.temperature.value||'').trim()||!String(form.elements.humidity.value||'').trim()){message('crop-msg','Load current temperature and humidity from live weather before continuing.',true);return;}
    if(!String(form.elements.rainfall.value||'').trim()){message('crop-msg','Rainfall data required by the trained model could not be reliably matched to the model\'s training period. A verified recommendation cannot be produced without this value.',true);return;}
    if(!form.reportValidity())return;
    const vals={};for(const k of ['n','p','k','temperature','humidity','ph','rainfall']){const v=Number(form.elements[k].value);if(!Number.isFinite(v)){message('crop-msg','Enter a valid number for every required input.',true);return;}vals[k]=v;}
    vals.soil_data_confirmed=true;
    vals.soil_report_filename=$('soil-report-filename').value;
    if(vals.ph<0||vals.ph>14||vals.rainfall<0){message('crop-msg','Check the input ranges for pH and rainfall.',true);return;}
    if(S.farmId)vals.farm_id=S.farmId;
    setLoading(button,true,'Running saved model…');message('crop-msg','Sending measured inputs to the crop recommendation API…');
    try {const result=await api('/api/crop-recommend',jsonPost(vals));let adv=null;if(S.farmId){try{adv=await api('/api/advisory',jsonPost({farm_id:S.farmId,language:lang(),run_crop_model:false,persist:false}));}catch(e){message('crop-msg','Prediction received. Advisory unavailable: '+e.message,true);}}
      showCropResult(result,adv);if(!adv)message('crop-msg','Prediction returned by the saved Step 2 model.');else message('crop-msg','Prediction and farm advisory loaded.');if(S.farmId)loadHistory();
    } catch(e){message('crop-msg',e.message,true);} finally{setLoading(button,false);}
  }
  async function extractSoilReport(){
    const file=$('soil-report-file').files[0];if(!file){message('soil-extract-msg','Choose a PDF, JPG, JPEG, or PNG report first.',true);return;}
    const fd=new FormData();fd.append('report',file);message('soil-extract-msg','Trying local text/OCR extraction…');
    try{const result=await api('/api/soil-report/extract',{method:'POST',body:fd});$('soil-report-filename').value=result.filename||file.name;for(const key of ['n','p','k','ph'])if(result.values&&result.values[key]!=null)document.querySelector('#crop-form [name="'+key+'"]').value=result.values[key];const note=result.status==='manual_entry_required'?'Automatic reading of this report is not available in this installation. Please enter the values exactly as shown on your soil test report.':(result.message||'Review extracted fields.');message('soil-extract-msg',note+(result.method?' Method: '+result.method+'.':''));}
    catch(e){message('soil-extract-msg',e.message,true);}
  }
  async function useCropWeather(){
    if(!S.farmId){message('crop-weather-note','Select your farm before loading weather.',true);return;}
    message('crop-weather-note','Loading location-matched live weather…');
    try{const result=await api('/api/farms/'+encodeURIComponent(S.farmId)+'/weather');if(!result.available)throw Error(result.message||'Weather is unavailable.');const current=result.current||{};let count=0;if(current.temperature_2m!=null&&current.temperature_2m!==''&&Number.isFinite(Number(current.temperature_2m))){$('crop-form').elements.temperature.value=current.temperature_2m;count++;}if(current.relative_humidity_2m!=null&&current.relative_humidity_2m!==''&&Number.isFinite(Number(current.relative_humidity_2m))){$('crop-form').elements.humidity.value=current.relative_humidity_2m;count++;}const precip=current.precipitation==null?'unavailable':current.precipitation+' mm';message('crop-weather-note','Filled '+count+' current measurement(s) from '+(result.source||'live weather')+'. Recent precipitation: '+precip+' at '+(current.time||'unknown time')+'. The training rainfall reporting period is undocumented, so it was not substituted.');}
    catch(e){message('crop-weather-note','Live weather unavailable: '+e.message+' Enter measured weather values; no defaults are supplied.',true);}
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
    const explain=gradcam?'<h4>'+esc(t('Grad-CAM model explanation'))+'</h4><img alt="Grad-CAM overlay from the classifier" src="'+esc(gradcam)+'">':(r.gradcam_path?'<p class="live-muted">'+esc(t('Grad-CAM was saved by the backend at'))+' '+esc(r.gradcam_path)+'; '+esc(t('the API did not return image bytes.'))+'</p>':'<p class="live-muted">'+esc(t('Grad-CAM was not returned for this request.'))+'</p>');
    return '<h3>'+esc(t('Leaf analysis result'))+'</h3><img class="live-image-preview" alt="Uploaded leaf image" src="'+esc(imageUrl)+'">'+facts([['Crop',r.crop||'Unavailable'],['Diagnosis',r.disease||'Unavailable'],['Confidence',r.confidence_pct==null?'Unavailable':nfmt(r.confidence_pct,1)+'%'],['Severity',r.severity||'Unavailable'],['Healthy classification',r.is_healthy==null?'Unavailable':(r.is_healthy?'Yes':'No')]])+explain+(candidates?'<h4>'+esc(t('Other model candidates'))+'</h4><ul class="live-list">'+candidates+'</ul>':'')+listHtml('Symptoms',symptoms)+listHtml('Precautions',precaution)+listHtml('General management',safeManagement)+listHtml('Prevention',prevention)+(irrigation?'<h4>'+esc(t('Farm irrigation/care context'))+'</h4><p>'+esc(irrigation)+'</p>'+care.map(c=>'<p>'+esc(c)+'</p>').join(''):'<p class="live-muted">'+esc(t('Farm-specific irrigation/care advisory is unavailable; no measurement context was returned.'))+'</p>')+'<div class="live-actions"><button class="live-btn" id="ask-disease-assistant">'+esc(t('Ask Assistant about this result'))+'</button></div>';
  }
  async function submitScan(e) {
    e.preventDefault();const form=e.currentTarget,button=form.querySelector('button[type=submit]'),file=$('leaf-image').files[0];$('scan-result').hidden=true;message('scan-msg','');
    const selectedCrop=$('scan-crop').value.trim();
    if(!selectedCrop){message('scan-msg','Select or enter the crop shown in the image.',true);return;}
    if(!file){message('scan-msg','Choose a leaf image first.',true);return;}
    if(!/^image\/(jpeg|png|webp)$/.test(file.type)){message('scan-msg','Upload a JPEG, PNG, or WebP image.',true);return;}
    if(file.size>10*1024*1024){message('scan-msg','Image is larger than 10 MB. Choose a smaller image.',true);return;}
    const fd=new FormData();fd.append('crop',selectedCrop);fd.append('image',file,file.name);fd.append('gradcam','1');fd.append('include_gradcam_b64','1');if(S.farmId)fd.append('farm_id',String(S.farmId));
    setLoading(button,true,'Analyzing image…');message('scan-msg','Uploading image to the Step 3 disease classifier…');
    try {const r=await api('/api/disease-predict',{method:'POST',body:fd});let adv=null;if(S.farmId){try{adv=await api('/api/advisory',jsonPost({farm_id:S.farmId,language:lang(),run_crop_model:false,persist:false}));}catch(e){message('scan-msg','Diagnosis returned. Farm advisory unavailable: '+e.message,true);}}
      if(S.scanUrl)URL.revokeObjectURL(S.scanUrl);S.scanUrl=URL.createObjectURL(file);$('scan-result').hidden=false;$('scan-result').innerHTML=diseaseResultHtml(r,adv,S.scanUrl);$('ask-disease-assistant').onclick=()=>requestAssistant('Please explain the '+(r.disease||'leaf diagnosis')+' result for '+(r.crop||'my crop')+' in simple '+lang()+' language. Give only general safe management and prevention guidance.');if(S.farmId)loadHistory();if(!adv)message('scan-msg','Diagnosis returned by the saved Step 3 model.');else message('scan-msg','Diagnosis and farm-context advisory loaded.');
    } catch(e){message('scan-msg',e.message,true);} finally{setLoading(button,false);}
  }
  function fmtDate(x){return x||'Date unavailable';}
  function itemCard(title, line, date, detail='') {return '<div class="live-history-card"><b>'+esc(t(title))+'</b><div>'+esc(line||'')+'</div>'+(detail?'<div class="live-muted">'+esc(detail)+'</div>':'')+'<div class="live-muted">'+esc(fmtDate(date))+'</div></div>';}
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
      $('history-content').innerHTML=blocks.length?blocks.join(''):'<p class="live-muted">'+esc(t('No saved prediction, advisory, or assistant history for this farm yet.'))+'</p>';
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
    $('crop-form').addEventListener('submit',submitCrop);document.querySelectorAll('#crop-form input[name="soil_report"]').forEach(input=>{input.checked=false;input.addEventListener('change',updateSoilReportFields);});updateSoilReportFields();$('scan-form').addEventListener('submit',submitScan);
    $('soil-report-file').addEventListener('change',event=>{$('soil-report-filename').value=event.target.value.split(/[\\/]/).pop()||'';});
    $('extract-soil-report').addEventListener('click',extractSoilReport);
    $('use-crop-weather').addEventListener('click',useCropWeather);
    document.querySelectorAll('.navbtn').forEach(b=>b.addEventListener('click',()=>{const titles={'crop-tool':'Crop recommendation',scanner:'Crop health scanner',history:'Farm history',ml:'ML insights'};if(titles[b.dataset.p])document.getElementById('tb-title').textContent=titles[b.dataset.p];if(b.dataset.p==='ml')loadAnalyst();if(b.dataset.p==='history')loadHistory();}));
    $('api-lang').addEventListener('change',()=>{const f=selectedFarm();$('chat-sub').textContent='Step 4 assistant · '+(f&&f.name||'no farm selected')+' · '+lang();});loadDiseaseModelInfo();
    document.addEventListener('agripilot-languagechange',()=>{
      const f=selectedFarm();
      $('chat-sub').textContent=t(f?'Step 4 assistant · '+(f.name||'selected farm')+' · '+lang():'Step 4 assistant · no farm selected · '+lang());
      const active=document.querySelector('.navbtn.on');
      const titleMap={today:'My Farm',advisories:'Advisory log',season:'Season data',compare:'Pilot results',ml:'ML insights','crop-tool':'Crop recommendation',scanner:'Crop health scanner',history:'Farm history',assistant:'Assistant'};
      if(active&&titleMap[active.dataset.p])$('tb-title').textContent=t(titleMap[active.dataset.p]);
      if(S.context&&active&&active.dataset.p==='today'){
        const form=$('farm-profile-form');const values=form?Object.fromEntries(new FormData(form).entries()):null;
        renderFarm(S.context);
        if(values){const replacement=$('farm-profile-form');for(const [key,value] of Object.entries(values)){if(replacement.elements[key])replacement.elements[key].value=value;}}
      }
      if(active&&active.dataset.p==='history')loadHistory();
      loadDiseaseModelInfo();
    });
    window.sendChat=sendAssistant;window.resetChat=resetBackendChat;
    loadFarms().catch(e=>{stateLabel('Backend unavailable','bad');message('live-farm-content','Could not load farm data. Start the Flask API at '+API+'. '+e.message,true);$('api-farm').innerHTML='<option value="">API unavailable</option>';});
    api('/api/auth/session').then(({user})=>{if(user&&user.role==='analyst')loadAnalyst();}).catch(()=>{});resetBackendChat();
  });
})();
