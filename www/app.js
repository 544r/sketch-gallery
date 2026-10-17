(async function () {
  const nc = '?t=' + Date.now();
  const [data, cfg] = await Promise.all([
    fetch('/data.json' + nc).then(r => r.json()),
    fetch('/settings.json' + nc).then(r => r.json()).catch(() => ({}))]);
  const $ = id => document.getElementById(id);
  const S = Object.assign({ title: '写生画廊', subtitle: '', columns: 4, gap: 16, frame: 'none', captions: false, filter: true, interval: 5 }, cfg);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  document.title = S.title; $('t').textContent = S.title; $('st').textContent = S.subtitle;
  const authors = [...new Set(data.map(d => d.author).filter(Boolean))];
  $('meta').textContent = `${data.length} 幅${authors.length ? ' · ' + authors.length + ' 位作者' : ''}`;
  const g = $('grid');
  g.className = 'grid frame-' + S.frame + (S.captions ? ' caps' : '');
  document.documentElement.style.setProperty('--cols', S.columns);
  document.documentElement.style.setProperty('--gap', S.gap + 'px');

  let who = '全部', view = [], cur = 0, playing = false, timer = null, front = 'ia';
  if (S.filter && authors.length > 1) {
    $('f').innerHTML = ['全部', ...authors].map(a => `<button data-v="${esc(a)}">${esc(a)}</button>`).join('');
    $('f').querySelectorAll('button').forEach(b => b.onclick = () => { who = b.dataset.v; render(); });
  } else $('f').style.display = 'none';

  function render() {
    $('f').querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.v === who));
    view = data.filter(d => who === '全部' || d.author === who);
    g.innerHTML = view.map((d, i) => `<figure class="tile" data-i="${i}" style="--d:${Math.min(i, 16) * 40}ms">
      <img loading="lazy" src="/thumb/${d.id}.jpg" width="${d.w}" height="${d.h}" alt="${esc(d.title)}">
      <figcaption><b>${esc(d.title)}</b><span>${esc(d.author)}</span></figcaption></figure>`).join('');
    g.querySelectorAll('.tile').forEach(t => t.onclick = () => open(+t.dataset.i));
  }

  // ---------- viewer ----------
  const lb = $('lb');
  function paint(animate = true) {
    const d = view[cur];
    const next = front === 'ia' ? 'ib' : 'ia';
    const el = $(next), old = $(front);
    el.onload = () => {
      el.classList.remove('kb'); void el.offsetWidth;
      if (playing) el.classList.add('kb');
      el.classList.add('show'); old.classList.remove('show');
      front = next;
    };
    el.src = `/img/${d.id}.jpg`;
    $('cap-t').textContent = d.title || '';
    $('cap-a').textContent = d.author || '';
    $('cap-i').textContent = `${cur + 1} / ${view.length}`;
    const n = view[(cur + 1) % view.length]; if (n) new Image().src = `/img/${n.id}.jpg`;
    if (playing) restartBar();
  }
  function open(i) {
    if (!view.length) return;
    cur = i; lb.classList.add('on'); document.body.style.overflow = 'hidden'; paint(); poke();
  }
  function close() {
    stop(); lb.classList.remove('on'); document.body.style.overflow = '';
    $('ia').classList.remove('show'); $('ib').classList.remove('show');
    if (document.fullscreenElement) document.exitFullscreen();
  }
  function step(k) { cur = (cur + k + view.length) % view.length; paint(); }
  function random() {
    if (!view.length) return;
    let i = Math.floor(Math.random() * view.length);
    if (view.length > 1 && lb.classList.contains('on') && i === cur) i = (cur + 1 + Math.floor(Math.random() * (view.length - 1))) % view.length;
    lb.classList.contains('on') ? (cur = i, paint()) : open(i);
  }
  function restartBar() {
    const b = $('bar'); b.style.transition = 'none'; b.style.width = '0'; void b.offsetWidth;
    b.style.transition = `width ${S.interval}s linear`; b.style.width = '100%';
    clearTimeout(timer); timer = setTimeout(() => step(1), S.interval * 1000);
  }
  function play() {
    playing = true; lb.classList.add('playing'); restartBar();
    $(front).classList.add('kb');
  }
  function stop() {
    playing = false; lb.classList.remove('playing'); clearTimeout(timer);
    const b = $('bar'); b.style.transition = 'none'; b.style.width = '0';
  }
  function toggle() { playing ? stop() : play(); }
  function full() {
    if (document.fullscreenElement) document.exitFullscreen(); else lb.requestFullscreen && lb.requestFullscreen().catch(() => {});
  }

  // idle: hide controls while playing
  let idle;
  function poke() { lb.classList.remove('idle'); clearTimeout(idle); idle = setTimeout(() => { if (playing) lb.classList.add('idle'); }, 2500); }
  lb.addEventListener('mousemove', poke);

  $('rand').onclick = random;
  $('play').onclick = () => { open(Math.floor(Math.random() * view.length)); play(); };
  $('lb-rand').onclick = random;
  $('lb-prev').onclick = () => step(-1);
  $('lb-next').onclick = () => step(1);
  $('lb-play').onclick = toggle;
  $('lb-full').onclick = full;
  $('lb-close').onclick = close;
  $('stage').addEventListener('click', e => { if (e.target.id === 'stage') close(); });
  document.addEventListener('keydown', e => {
    if (!lb.classList.contains('on')) return;
    poke();
    const k = e.key;
    if (k === 'ArrowLeft') step(-1);
    else if (k === 'ArrowRight') step(1);
    else if (k === 'Escape') close();
    else if (k === ' ') { e.preventDefault(); toggle(); }
    else if (k === 'r' || k === 'R') random();
    else if (k === 'f' || k === 'F') full();
  });
  // sticky toolbar shadow
  const tb = $('toolbar');
  addEventListener('scroll', () => tb.classList.toggle('stuck', tb.getBoundingClientRect().top <= 0), { passive: true });

  render();
})();
