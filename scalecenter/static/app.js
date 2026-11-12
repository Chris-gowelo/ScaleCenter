let U=null;const app=$("#app");
const NAV=[["feed","Opportunities"],["people","Find talent"],["inbox","Messages"],["profile","My profile"]];
function nav(v){$("#nav").innerHTML=U?NAV.map(n=>`<button class="${n[0]===v?"on":""}" onclick="go('${n[0]}')">${n[1]}</button>`).join("")+(U.is_admin?'<a href="admin.html">Admin</a>':"")+'<button onclick="localStorage.clear();location.reload()">Log out</button>':""}
function go(v,a){nav(v);({feed,people,inbox,profile,chat})[v](a)}
function authView(reg){
  app.innerHTML=`<h1>Where tech skills meet the people who hire them.</h1><p class="mute">Web, networking, cybersecurity, EEE, EIE, cloud, plumbing and more. Show your skills, post a job, or fund the next team.</p>
  <div class="card"><h2>${reg?"Create your account":"Log in"}</h2><div id="e" class="err"></div>
  ${reg?'<label>Full name or company<input id="n"></label>':""}<label>Email<input id="em" type="email"></label><label>Password<input id="pw" type="password"></label>
  ${reg?'<label>I want to<select id="role"><option value="talent">Get hired (talent)</option><option value="employer">Hire people (employer / company / CEO)</option><option value="investor">Invest and offer jobs (investor)</option></select></label>':""}
  <button class="b" id="go">${reg?"Create account":"Log in"}</button> <button class="b alt" onclick="authView(${!reg})">${reg?"I have an account":"Create an account"}</button></div>`;
  $("#go").onclick=async()=>{try{const d=await api(reg?"/register":"/login","POST",{name:reg?$("#n").value:"",email:$("#em").value,password:$("#pw").value,role:reg?$("#role").value:"talent"});localStorage.token=d.token;boot()}catch(x){$("#e").textContent=x.message}}
}
const postCard=p=>`<div class="card ${p.kind}"><span class="tag">${p.kind==="job"?"Job offer":"Skill post"}</span><span class="tag">${esc(p.field)}</span>
<h3>${esc(p.title)}</h3><p>${esc(p.body)}</p><p class="mute">${esc(p.author)} (${p.role}) · ${p.created.slice(0,10)}</p>
${p.uid===U.id||U.is_admin?`<button class="b del sm" onclick="delPost(${p.id})">Delete</button>`:`<button class="b sm" onclick="go('chat',${p.uid})">${p.kind==="job"?"Apply":"Hire this person"}</button>`}</div>`;
async function delPost(id){if(confirm("Delete this post?")){await api("/posts/"+id,"DELETE");feed()}}
async function feed(){
  const kind=U.role==="talent"?"job":"";
  app.innerHTML=`<h2>Opportunities</h2><div class="card"><div class="row"><input id="q" placeholder="Search"><select id="f">${opts("","All fields")}</select><select id="k"><option value="">Jobs and skills</option><option value="job">Jobs</option><option value="skill">Skills</option></select></div>
  <details><summary><b>${U.role==="talent"?"Post your skills":"Post a job"}</b></summary><br><input id="t" placeholder="Title"><textarea id="b" rows="3" placeholder="Details"></textarea><select id="pf">${opts()}</select><button class="b" id="pb">Publish</button> <span id="pe" class="err"></span></details></div><div id="list"></div>`;
  const load=async()=>{const p=await api(`/posts?kind=${$("#k").value}&field=${encodeURIComponent($("#f").value)}&q=${encodeURIComponent($("#q").value)}`);$("#list").innerHTML=p.map(postCard).join("")||'<p class="mute">No posts yet. Be the first to publish one.</p>'};
  ["q","f","k"].forEach(i=>$("#"+i).oninput=load);
  $("#pb").onclick=async()=>{try{await api("/posts","POST",{kind:U.role==="talent"?"skill":"job",title:$("#t").value,body:$("#b").value,field:$("#pf").value});feed()}catch(x){$("#pe").textContent=x.message}};
  load();
}
async function people(){
  app.innerHTML=`<h2>Find talent and partners</h2><input id="q" placeholder="Search by name, skill or field"><div id="list"></div>`;
  const load=async()=>{const p=await api("/people?q="+encodeURIComponent($("#q").value));$("#list").innerHTML=p.filter(x=>x.id!==U.id).map(x=>`<div class="card"><span class="tag">${x.role}</span>${x.field?`<span class="tag">${esc(x.field)}</span>`:""}<h3>${esc(x.name)}</h3><p>${esc(x.bio)}</p><p class="mute">Skills: ${esc(x.skills)||"not added yet"}</p><button class="b sm" onclick="go('chat',${x.id})">Message</button></div>`).join("")||'<p class="mute">No one matches that search.</p>'};
  $("#q").oninput=load;load();
}
async function inbox(){
  const t=await api("/threads");app.innerHTML="<h2>Messages</h2>"+(t.map(x=>`<div class="card"><b>${esc(x.name)}</b> <span class="tag">${x.role}</span><p class="mute">${esc(x.last)}</p><button class="b sm" onclick="go('chat',${x.id})">Open</button></div>`).join("")||'<p class="mute">No conversations yet. Message someone from Opportunities or Find talent.</p>');
}
async function chat(id){
  const d=await api("/messages/"+id);if(!d.with)return inbox();
  app.innerHTML=`<h2>Chat with ${esc(d.with.name)}</h2><div class="card"><div class="msgs">${d.messages.map(m=>`<div class="m ${m.frm===U.id?"me":""}">${esc(m.body)}</div>`).join("")||'<p class="mute">Say hello and describe the job or your skills.</p>'}</div>
  <textarea id="mb" rows="2" placeholder="Write a message"></textarea><button class="b" id="sb">Send</button></div>`;
  $(".msgs").scrollTop=1e9;$("#sb").onclick=async()=>{if($("#mb").value.trim()){await api("/messages","POST",{to:id,body:$("#mb").value});chat(id)}};
}
function profile(){
  app.innerHTML=`<h2>My profile</h2><div class="card"><span class="tag">${U.role}</span><label>Name<input id="n" value="${esc(U.name)}"></label><label>Main field<select id="f">${opts(U.field,"Choose")}</select></label>
  <label>Skills (comma separated)<input id="s" value="${esc(U.skills)}"></label><label>About you<textarea id="b" rows="4">${esc(U.bio)}</textarea></label><button class="b" id="sv">Save changes</button> <span id="ok" class="mute"></span></div>`;
  $("#sv").onclick=async()=>{await api("/me","PUT",{name:$("#n").value,field:$("#f").value,skills:$("#s").value,bio:$("#b").value});U=await api("/me");$("#ok").textContent="Saved"};
}
async function boot(){if(!localStorage.token){nav();return authView(false)}try{U=await api("/me");go("feed")}catch{authView(false)}}
boot();
