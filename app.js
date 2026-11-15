const $ = id => document.getElementById(id);
const labels = ['PTS','REB','AST','STL','BLK'];
function safe(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function date(value) { const d = new Date(value); return value && !isNaN(d) ? d.toLocaleString() : 'Waiting for a successful poll'; }
async function refresh() {
  try {
    const response = await fetch('/api/status', {cache:'no-store'});
    if (!response.ok) throw Error('HTTP ' + response.status);
    const data = await response.json();
    const age = data.updated_at ? (Date.now() - Date.parse(data.updated_at)) / 60000 : Infinity;
    $('status').textContent = data.status === 'waiting' ? 'Waiting for first poll' : age > 10 ? 'Stale · check scheduler' : data.status === 'degraded' ? 'Partial data · check logs' : 'Monitoring active';
    $('games').textContent = data.active_games ?? 0;
    $('tracked').textContent = (data.players || []).length;
    $('checked').textContent = date(data.last_successful_check);
    $('leaderboard').innerHTML = (data.players || []).length ? data.players.map(p => `<article class="card player"><div><div class="name">${safe(p.name)}</div><div class="muted">${safe(p.team)} · ${safe(p.game)} · ${safe(p.status)}</div></div><div class="stats">${(p.values || []).map((v,i)=>`<div class="stat ${v >= 5 ? 'hit' : ''}"><b>${safe(v)}</b><small>${labels[i]}</small></div>`).join('')}</div><div class="progress">${safe(p.reached)}/5 at 5+<small>${p.distance === 0 ? '5×5 achieved' : `${safe(p.distance)} total stats away · ${p.minimum < 2 ? 'below 5×2 entry' : '5×2 eligible'}`}</small></div></article>`).join('') : '<div class="card empty">No live player box scores. The leaderboard fills when games are in progress.</div>';
    $('alerts').innerHTML = (data.recent_alerts || []).length ? data.recent_alerts.map(a=>`<div class="alert"><span><b>${safe(a.name)}</b> · ${safe(a.stage)} <span class="muted">${safe(a.team)}</span></span><time class="muted">${safe(date(a.at))}</time></div>`).join('') : '<div class="empty">No alerts recorded by this dashboard yet.</div>';
  } catch(error) { $('status').textContent = 'Dashboard data unavailable'; }
}
refresh(); setInterval(refresh, 30000);
