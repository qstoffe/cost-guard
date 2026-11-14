// Independent population expectation from canonical publications, never DOM rows.
module.exports = function expectedMiniRows(view) {
  const running = new Map(), finished = new Map();
  const ordered = (a,b) => (a.at ?? -Infinity)-(b.at ?? -Infinity) ||
    a.id.localeCompare(b.id) || a.event.localeCompare(b.event);
  const entry = (card,prompt,active) => ({
    id:card.session_id,event:prompt.event_id,running:active,
    verified:!!(prompt.in_progress && !prompt.execution_unverified),
    play:!!(active && prompt.in_progress && !prompt.execution_unverified &&
      !prompt.aborted && !prompt.has_error && !prompt.completed_successfully),
    at:active ? prompt.at_ms : prompt.completed_at_ms,
    clock:(active ? prompt.display?.clock : prompt.display?.finished_clock) || '—',
    help:(active ? prompt.display?.mini_start_date_time : prompt.display?.mini_finished_date_time) ||
      (active ? 'Unknown start time' : 'Unknown finish time')
  });
  for(const card of view.active_cards || []) for(const {prompt} of card.rows || []) {
    if(prompt.is_compaction || !card.focal_id || prompt.event_id!==card.focal_id) continue;
    const active=!!(prompt.in_progress || prompt.execution_unverified), value=entry(card,prompt,active);
    const pool=active ? running : finished, old=pool.get(value.id);
    const preferred=old && active && value.verified!==old.verified ?
      value.verified : !old || ordered(value,old)>0;
    if(preferred) pool.set(value.id,value);
  }
  for(const card of [...(view.history_cards || []),...(view.recent_finished_cards || [])]) {
    if(!card.rows?.[0]) continue;
    const value=entry(card,card.rows[0].prompt,false), old=finished.get(value.id);
    if(!old || ordered(value,old)>=0) finished.set(value.id,value);
  }
  const fillers=[...finished.values()].filter(value=>!running.has(value.id)).sort(ordered);
  const slots=Math.max(0,5-running.size);
  return [...running.values(),...(slots ? fillers.slice(-slots) : [])].sort(ordered);
};
