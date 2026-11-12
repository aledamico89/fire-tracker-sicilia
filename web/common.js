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
    document.body.append(nav); (document.querySelector('#side') || document.body).append(foot);
  });
})();

window.FT = {
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
  enhance(map, {dem = null, hill = true, buildings = true} = {}) {
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
      try { map.setSky({'sky-color':'#0f1a2a', 'horizon-color':'#3b4859', 'fog-color':'#2a3340', 'sky-horizon-blend':.7, 'horizon-fog-blend':.6, 'fog-ground-blend':.5,
        'atmosphere-blend':['interpolate', ['linear'], ['zoom'], 0, 1, 10, 0]}); } catch (_) {}
    };
    map.loaded() ? go() : map.once('load', go);
  }
};
