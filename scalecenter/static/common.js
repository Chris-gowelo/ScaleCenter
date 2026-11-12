const FIELDS=["Web Development","Web Design","Networking","Cybersecurity","EEE","EIE","Plumbing","Computer Science","Cloud Computing","AI & Data","Mobile Apps","Electrical Work","Other"];
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const $=s=>document.querySelector(s);
async function api(path,method="GET",body){
  const r=await fetch("/api"+path,{method,headers:{"Content-Type":"application/json",Authorization:localStorage.token||""},body:body?JSON.stringify(body):undefined});
  const d=await r.json().catch(()=>({}));
  if(!r.ok){if(r.status===401&&localStorage.token){localStorage.clear();location.reload()}throw new Error(d.detail||"Something went wrong")}
  return d;
}
const opts=(sel,all)=>(all?`<option value="">${all}</option>`:"")+FIELDS.map(f=>`<option ${f===sel?"selected":""}>${f}</option>`).join("");
