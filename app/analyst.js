(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = value => typeof value === 'number' ? (Math.abs(value) <= 1 ? (value*100).toFixed(2)+'%' : value.toLocaleString()) : (value == null ? 'Not available' : String(value));
  async function get(path){const r=await fetch(path,{credentials:'same-origin'});const v=await r.json();if(!r.ok)throw Error(v.error||('HTTP '+r.status));return v;}
  function chart(id,data){const values=Object.entries(data||{});if(!values.length){$(id).innerHTML='<p class="muted">No recorded data.</p>';return;}const max=Math.max(...values.map(x=>Number(x[1])||0),1);$(id).innerHTML='<div class="bars">'+values.sort((a,b)=>b[1]-a[1]).map(([k,v])=>'<div class="barrow"><span>'+esc(k)+'</span><div class="bar"><i style="width:'+((Number(v)||0)/max*100)+'%"></i></div><b>'+esc(v)+'</b></div>').join('')+'</div>';}
  function modelBlock(id,artifact,kind){
    if(!artifact){$(id).innerHTML='<p class="notice">Saved '+kind+' evaluation artifact is not available.</p>';return;}
    const meta=artifact.metadata||{}, overall=artifact.overall||{}, values=Object.entries(overall).filter(([,v])=>typeof v==='number'&&Number.isFinite(v));
    let out='<div class="json-grid">'+values.map(([k,v])=>'<div class="metric"><b>'+esc(k.replaceAll('_',' '))+'</b><span>'+esc(fmt(v))+'</span></div>').join('')+'</div>';
    const comparison=artifact.comparison||{};
    if(Object.keys(comparison).length){out+='<h3>Saved model comparison</h3><div class="scroll"><table class="table"><thead><tr><th>Model</th><th>Saved evaluation values</th></tr></thead><tbody>'+Object.entries(comparison).map(([name,row])=>'<tr><td>'+esc(row.model_name||name)+'</td><td>'+esc(JSON.stringify(row))+'</td></tr>').join('')+'</tbody></table></div>';}
    if(meta.classes)out+='<h3>Dataset classes ('+esc(meta.num_classes||meta.classes.length)+')</h3><p>'+esc(meta.classes.join(', '))+'</p>';
    if(kind==='disease classifier'&&meta.classes){const crops=[...new Set(meta.classes.map(c=>String(c).split('___')[0]))];out+='<h3>Supported crops from saved class mapping</h3><p>'+esc(crops.join(', '))+'</p>';}
    if(meta.features)out+='<h3>Features</h3><p>'+esc(meta.features.join(', '))+'</p>';
    if(meta.supported_crops)out+='<h3>Supported crops</h3><p>'+esc(meta.supported_crops.join(', '))+'</p>';
    if(artifact.per_class)out+='<h3>Per-class evaluation</h3><pre>'+esc(JSON.stringify(artifact.per_class,null,2))+'</pre>';
    if(artifact.confusion_matrix)out+='<h3>Saved confusion matrix</h3><pre>'+esc(JSON.stringify(artifact.confusion_matrix))+'</pre>';
    if(artifact.confusion_matrices)out+='<h3>Saved confusion matrices by model</h3><pre>'+esc(JSON.stringify(artifact.confusion_matrices,null,2))+'</pre>';
    if(artifact.feature_importance)out+='<h3>Saved feature importance</h3><pre>'+esc(JSON.stringify(artifact.feature_importance,null,2))+'</pre>';
    if(artifact.top_features)out+='<h3>Saved feature importance</h3><pre>'+esc(JSON.stringify(artifact.top_features,null,2))+'</pre>';
    out+='<p class="muted">Artifact information: '+esc(JSON.stringify(meta))+'</p>';
    $(id).innerHTML=out;
  }
  async function load(){try{
    const [session,overview,artifacts]=await Promise.all([get('/api/auth/session'),get('/api/analyst/overview'),get('/api/model-evaluation')]);
    if(!session.user||session.user.role!=='analyst'){location.assign('/analyst/login');return;}
    $('analyst-name').textContent=session.user.name||session.user.username||'Analyst';
    $('overview').innerHTML=Object.entries(overview.counts||{}).map(([k,v])=>'<div class="card"><span>'+esc(k.replaceAll('_',' '))+'</span><strong>'+esc(v)+'</strong></div>').join('');
    chart('states',overview.farms_by_state);chart('districts',overview.farms_by_district);chart('current-crops',overview.current_crops);chart('crops',overview.recommendations_by_crop);chart('diseases',overview.disease_by_class);chart('disease-crops',overview.disease_by_crop);
    modelBlock('crop-model',artifacts.crop,'crop recommendation');modelBlock('disease-model',artifacts.disease,'disease classifier');
    const rows=overview.recent_activity||[];$('activity').innerHTML=rows.length?'<div class="scroll"><table class="table"><thead><tr><th>Activity</th><th>Recorded value</th><th>Time</th></tr></thead><tbody>'+rows.map(x=>'<tr><td>'+esc(x.type)+'</td><td>'+esc(x.label||'Not available')+'</td><td>'+esc(x.created_at||'Not available')+'</td></tr>').join('')+'</tbody></table></div>':'<p class="muted">No recorded activity.</p>';
    $('status').textContent='Live aggregates loaded from SQLite. Model figures read from saved Step 2 and Step 3 evaluation artifacts.';
  }catch(e){$('status').textContent='Could not load analyst data: '+e.message;}}
  $('logout').addEventListener('click',async()=>{await fetch('/api/auth/logout',{method:'POST',credentials:'same-origin'});location.assign('/analyst/login');});
  load();
})();
