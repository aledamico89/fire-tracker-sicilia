// Elementi condivisi: menu delle sezioni, crediti, mappa di base (Esri), rilievo ombreggiato, cielo, edifici 3D
(() => {
  const P = [['./', 'Evento 2023'], ['storico.html', 'Storico'], ['rischio.html', 'Rischio'], ['catasto.html', "Dopo l'incendio"]];
  const here = location.pathname.split('/').pop() || 'index.html';
  document.addEventListener('DOMContentLoaded', () => {
    const nav = document.createElement('nav'); nav.className = 'ft-nav'; nav.setAttribute('aria-label', 'Sezioni');
    nav.innerHTML = P.map(([h, t]) => `<a href="${h}"${h == here || (h == './' && here == 'index.html') ? ' class="on" aria-current="page"' : ''}>${t}</a>`).join('');
    const foot = document.createElement('div'); foot.className = 'ft-foot';
    foot.innerHTML = `© 2026 <a href="https://alessiodamico.com" target="_blank" rel="noopener">Alessio D'Amico</a> · ideazione e design · ` +
      `<a href="https://alessiodamico.com" target="_blank" rel="noopener">alessiodamico.com</a><br>Codice open source <a href="https://github.com/aledamico89/fire-tracker-sicilia" target="_blank" rel="noopener">MIT</a> · dati © delle rispettive fonti`;
    document.body.append(nav); setTimeout(() => document.body.classList.add('ft-ready'), 1500);
    // telefono: il pannello dati diventa una scheda dal basso (nella pagina evento è l'analisi; il pannello livelli resta in alto)
    const ana = document.querySelector('#ana'), side = document.querySelector('#side'), sheet = ana || side, card = document.querySelector('#card'), bar = document.querySelector('#bar');
    (sheet || document.body).append(foot);
    if (ana && side) side.classList.add('ft-sheet-top');
    const fit = () => document.body.style.setProperty('--ft-bottom', bar && matchMedia('(max-width:700px)').matches ? Math.round(innerHeight - bar.getBoundingClientRect().top + 6) + 'px' : '0px');
    fit(); addEventListener('resize', fit);
    if (sheet) { sheet.classList.add('ft-sheet'); if (ana) sheet.style.setProperty('--ft-peek', '120px');
      const h = document.createElement('button'); h.className = 'ft-handle'; h.setAttribute('aria-label', 'Apri o chiudi il pannello dati');
      sheet.prepend(h); FT.drag(h, sheet, open => sheet.classList.toggle('open', open)); }
    if (card) { const x = document.createElement('button'); x.className = 'ft-close'; x.textContent = '× Torna alla mappa';
      const close = () => { typeof window.hide == 'function' ? window.hide() : card.style.display = 'none'; }; x.onclick = close; card.prepend(x);
      const ch = document.createElement('div'); ch.className = 'ft-handle'; card.prepend(ch); FT.drag(ch, card, open => open || close(), true);
      new MutationObserver(() => { if (card.style.display == 'block') sheet?.classList.remove('open'); }).observe(card, {attributes:true, attributeFilter:['style']}); }
  });
})();

window.FT = {
  // trascinamento verticale di una scheda: segue il dito, al rilascio decide aperta/chiusa; un tocco alterna
  drag(h, el, done, dismissOnly = false) {
    let y0 = null, h0 = 0, moved = false;
    h.addEventListener('pointerdown', e => { y0 = e.clientY; h0 = el.getBoundingClientRect().height; moved = false; h.setPointerCapture(e.pointerId); });
    h.addEventListener('pointermove', e => { if (y0 == null) return; const d = e.clientY - y0; if (Math.abs(d) > 6) moved = true;
      if (moved) { el.style.transition = 'none'; el.style.setProperty('max-height', Math.max(60, Math.min(innerHeight * .85, h0 - d)) + 'px', 'important'); } });
    const up = e => { if (y0 == null) return; const d = e.clientY - y0; y0 = null; el.style.removeProperty('max-height'); el.style.transition = '';
      if (!moved) { if (!dismissOnly) done(!el.classList.contains('open')); return; }
      done(dismissOnly ? d < 80 : (h0 - d) > innerHeight * .35); };
    h.addEventListener('pointerup', up); h.addEventListener('pointercancel', up);
  },
  sat: {type:'raster', tileSize:256, maxzoom:19, tiles:['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
    attribution:'Immagini © Esri, Maxar, Earthstar Geographics · <a href="https://alessiodamico.com" target="_blank">Alessio D\'Amico</a>'},
  // ricerca comune: campo con suggerimenti sotto il titolo del pannello; pick(i) apre la scheda
  search(map, names, G, pick) {
    const box = document.createElement('div'); box.className = 'ft-search';
    box.innerHTML = '<input list="ft-com" placeholder="Cerca un comune…" aria-label="Cerca un comune"><datalist id="ft-com"></datalist>';
    box.querySelector('datalist').innerHTML = names.map(n => `<option value="${String(n).replace(/[&<>"]/g, '')}">`).join('');
    document.querySelector('#side h1').after(box);
    const inp = box.querySelector('input'), norm = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim();
    const go = () => { const q = norm(inp.value); if (!q) return; let i = names.findIndex(n => norm(n) == q); if (i < 0) i = names.findIndex(n => norm(n).startsWith(q)); if (i < 0) return;
      inp.value = names[i]; inp.blur(); pick(i);
      const c = G.features[i].geometry.coordinates.flat(G.features[i].geometry.type == 'Polygon' ? 1 : 2);
      map.fitBounds([[Math.min(...c.map(p => p[0])), Math.min(...c.map(p => p[1]))], [Math.max(...c.map(p => p[0])), Math.max(...c.map(p => p[1]))]], {padding:{left:380, right:380, top:80, bottom:80}, maxZoom:11.5}); };
    inp.addEventListener('change', go); inp.addEventListener('keydown', e => e.key == 'Enter' && go());
  },
  // dem: nome di una sorgente raster-dem già presente nella pagina (evita di scaricare due volte il rilievo)
  enhance(map, {dem = null, hill = true, buildings = true, flat = false} = {}) {
    if (flat) { hill = buildings = false; map.touchZoomRotate.disableRotation(); }
    // telefono: lo zoom su un'area lascia spazio alla scheda in basso
    const fb = map.fitBounds.bind(map), mq = matchMedia('(max-width:700px)');
    map.fitBounds = (b, o = {}) => fb(b, mq.matches ? {...o, padding:{top:60, bottom:Math.round(innerHeight * .6), left:24, right:24}} : o);
    const go = () => {
      const below = map.getStyle().layers[1]?.id;
      if (!dem) { dem = 'ft-dem'; map.addSource(dem, {type:'raster-dem', encoding:'terrarium', tileSize:256, maxzoom:14, tiles:['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png']}); }
      if (hill) map.addLayer({id:'ft-hill', type:'hillshade', source:dem, paint:{'hillshade-exaggeration':.4, 'hillshade-shadow-color':'#000', 'hillshade-highlight-color':'#fff', 'hillshade-accent-color':'#222'}}, below);
      if (buildings) {
        map.addSource('ft-omt', {type:'vector', url:'https://tiles.openfreemap.org/planet', attribution:'© OpenMapTiles © OpenStreetMap'});
        map.addLayer({id:'ft-bld', type:'fill-extrusion', source:'ft-omt', 'source-layer':'building', minzoom:14, paint:{'fill-extrusion-color':'#cfc8bc',
          'fill-extrusion-height':['coalesce', ['get', 'render_height'], 6], 'fill-extrusion-base':['coalesce', ['get', 'render_min_height'], 0],
          'fill-extrusion-opacity':['interpolate', ['linear'], ['zoom'], 14, 0, 15, .8]}});
      }
      if (!flat) try { map.setSky({'sky-color':'#0f1a2a', 'horizon-color':'#3b4859', 'fog-color':'#2a3340', 'sky-horizon-blend':.7, 'horizon-fog-blend':.6, 'fog-ground-blend':.5,
        'atmosphere-blend':['interpolate', ['linear'], ['zoom'], 0, 1, 10, 0]}); } catch (_) {}
    };
    map.loaded() ? go() : map.once('load', go);
  }
};
