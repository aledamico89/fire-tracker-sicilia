// Pagina evento: particelle del vento, fumo simulato, satellite reale prima/dopo. Si aggancia ai dati del replay (evento 'ev-ready').
addEventListener('ev-ready', ({detail: E}) => {
  const {map, wx, hot} = E, $ = id => document.getElementById(id), R = Math.PI / 180;
  const hourIdx = () => Math.max(0, Math.min(wx.points[0].ws.length - 1, Math.floor((E.now() - wx.t0) / wx.step)));

  // ---- campo di vento ERA5 (griglia 0,5°) con interpolazione bilineare; u,v = verso cui soffia, km/h
  const lats = [...new Set(wx.points.map(p => p.lat))].sort((a, b) => a - b), lons = [...new Set(wx.points.map(p => p.lon))].sort((a, b) => a - b);
  const G = {}; wx.points.forEach(p => G[p.lat + ',' + p.lon] = p);
  function wind(lon, lat, i) {
    const fa = Math.max(0, Math.min(lats.length - 1.001, (lat - lats[0]) / .5)), fb = Math.max(0, Math.min(lons.length - 1.001, (lon - lons[0]) / .5));
    const a = Math.floor(fa), b = Math.floor(fb), da = fa - a, db = fb - b; let u = 0, v = 0;
    for (const [x, y, w] of [[0, 0, (1 - da) * (1 - db)], [1, 0, da * (1 - db)], [0, 1, (1 - da) * db], [1, 1, da * db]]) {
      const p = G[lats[a + x] + ',' + lons[b + y]]; if (!p) continue;
      u -= p.ws[i] * Math.sin(p.wd[i] * R) * w; v -= p.ws[i] * Math.cos(p.wd[i] * R) * w;
    }
    return [u, v];
  }

  // ---- due tele sopra la mappa: scie del vento (sfumano) e fumo (ridisegnato a ogni fotogramma)
  const mk = z => { const c = document.createElement('canvas'); c.style.cssText = `position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:${z}`; map.getContainer().appendChild(c); return c; };
  const cw = mk(2), cs = mk(3), gw = cw.getContext('2d'), gs = cs.getContext('2d');
  let W = 0, H = 0;
  const size = () => { const r = devicePixelRatio || 1; W = cw.clientWidth; H = cw.clientHeight; for (const [c, g] of [[cw, gw], [cs, gs]]) { c.width = W * r; c.height = H * r; g.setTransform(r, 0, 0, r, 0, 0); } };
  size(); new ResizeObserver(size).observe(cw);
  const mobile = matchMedia('(max-width:700px)').matches, N = mobile ? 600 : 1400;
  const seed = () => { const b = map.getBounds(); return {lon: b.getWest() + Math.random() * (b.getEast() - b.getWest()), lat: b.getSouth() + Math.random() * (b.getNorth() - b.getSouth()), age: Math.random() * 90}; };
  let parts = [], smoke = [], moving = false;
  map.on('movestart', () => { moving = true; gw.clearRect(0, 0, W, H); });
  map.on('moveend', () => { moving = false; parts = parts.map(seed); });

  // focolai attivi (ultime 6 h di tempo simulato), aggiornati due volte al secondo
  let active = [], lastAct = 0;
  const refresh = ts => { if (ts - lastAct < 500) return; lastAct = ts; const t = E.now(); active = hot.filter(p => p[2] <= t && t - p[2] < 21600); };

  let last = 0;
  function frame(ts) {
    const dt = Math.min(.05, (ts - last) / 1000 || 0); last = ts;
    const i = hourIdx(), z = map.getZoom(), deg = 360 / (512 * 2 ** z);   // gradi per pixel
    // vento
    gw.globalCompositeOperation = 'destination-in'; gw.fillStyle = 'rgba(0,0,0,.93)'; gw.fillRect(0, 0, W, H); gw.globalCompositeOperation = 'source-over';
    if ($('lWind').checked && !moving) {
      while (parts.length < N) parts.push(seed());
      gw.strokeStyle = 'rgba(225,238,255,.7)'; gw.lineWidth = 1.2; gw.beginPath();
      const s = dt * 1.4 * deg;   // ~1,4 px/s per km/h
      for (const p of parts) {
        const a = p.px || map.project([p.lon, p.lat]), [u, v] = wind(p.lon, p.lat, i);
        p.lon += u * s / Math.cos(p.lat * R); p.lat += v * s; p.age++;
        const b = map.project([p.lon, p.lat]); p.px = b;
        if (p.age > 110 || b.x < 0 || b.y < 0 || b.x > W || b.y > H) { Object.assign(p, seed(), {px: null, age: 0}); continue; }
        gw.moveTo(a.x, a.y); gw.lineTo(b.x, b.y);
      }
      gw.stroke();
    }
    // fumo: ogni focolaio emette in proporzione alla potenza (FRP), il pennacchio segue il vento reale
    gs.clearRect(0, 0, W, H);
    if ($('lSmoke').checked) {
      refresh(ts);
      for (const h of active) if (smoke.length < (mobile ? 1200 : 3000) && Math.random() < Math.min(1, h[3] / 60) * dt * 6)
        smoke.push({lon: h[0], lat: h[1], age: 0, life: 6 + Math.random() * 6, k: Math.min(1, .3 + h[3] / 300)});
      const s = dt * 1.1 * deg;
      smoke = smoke.filter(p => (p.age += dt) < p.life);
      for (const p of smoke) {
        const [u, v] = wind(p.lon, p.lat, i), j = 1 + p.age * .6;
        p.lon += (u + (Math.random() - .5) * 8 * j) * s / Math.cos(p.lat * R); p.lat += (v + (Math.random() - .5) * 8 * j) * s;
        const q = map.project([p.lon, p.lat]), r = (3 + p.age * 4) * Math.max(.6, 2 ** (z - 9)) * .6, f = 1 - p.age / p.life;
        if (q.x < -50 || q.y < -50 || q.x > W + 50 || q.y > H + 50) continue;
        const gr = gs.createRadialGradient(q.x, q.y, 0, q.x, q.y, r);
        gr.addColorStop(0, `rgba(150,145,140,${.38 * f * p.k})`); gr.addColorStop(1, 'rgba(120,115,110,0)');
        gs.fillStyle = gr; gs.fillRect(q.x - r, q.y - r, 2 * r, 2 * r);
      }
    } else smoke = [];
    requestAnimationFrame(frame);
  }
  map.setLayoutProperty('wind', 'visibility', 'none');   // le frecce lasciano il posto alle particelle
  requestAnimationFrame(frame);

  // ---- satellite reale prima/dopo: solo il riquadro inquadrato, letto dai file Sentinel-2 (COG) su AWS
  const UTM = '+proj=utm +zone=33 +datum=WGS84 +units=m +no_defs', SPLIT = Date.UTC(2023, 6, 24) / 1000;
  let key = null, timer = null, busy = false;
  const lbl = t => { $('s2lbl').textContent = t; };
  const hide = () => { if (map.getLayer('s2')) map.setLayoutProperty('s2', 'visibility', 'none'); };
  async function s2() {
    if (!$('lS2').checked) { hide(); lbl(''); key = null; return; }
    if (map.getZoom() < 10.5) { hide(); key = null; lbl('Avvicinati (zoom di zona) per vedere le immagini reali.'); return; }
    if (busy) return;
    const pre = E.now() < SPLIT, c = map.getCenter(), b = map.getBounds();
    const half = .12, box = [Math.max(b.getWest(), c.lng - half), Math.max(b.getSouth(), c.lat - half * .8), Math.min(b.getEast(), c.lng + half), Math.min(b.getNorth(), c.lat + half * .8)];
    const k = (pre ? 'pre' : 'post') + box.map(v => v.toFixed(2)).join();
    if (k === key) return; key = k; busy = true; lbl('Cerco l\'immagine Sentinel-2…');
    try {
      const r = await fetch('https://earth-search.aws.element84.com/v1/search', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
        collections: ['sentinel-2-l2a'], intersects: {type: 'Point', coordinates: [c.lng, c.lat]}, query: {'eo:cloud_cover': {lt: 10}}, limit: 20,
        datetime: pre ? '2023-06-20T00:00:00Z/2023-07-21T23:59:59Z' : '2023-07-28T00:00:00Z/2023-08-31T23:59:59Z',
        sortby: [{field: 'properties.datetime', direction: pre ? 'desc' : 'asc'}]})});
      const it = (await r.json()).features.find(f => f.assets.visual);
      if (!it) { lbl('Nessuna immagine limpida in quel periodo.'); return; }
      const u = [[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]].map(p => proj4('EPSG:4326', UTM, p));
      const x0 = Math.min(...u.map(p => p[0])), x1 = Math.max(...u.map(p => p[0])), y0 = Math.min(...u.map(p => p[1])), y1 = Math.max(...u.map(p => p[1]));
      const sc = Math.min(1, 1400 / (Math.max(x1 - x0, y1 - y0) / 10)), Wd = Math.round((x1 - x0) / 10 * sc), Hd = Math.round((y1 - y0) / 10 * sc);
      lbl('Scarico il riquadro…');
      const ras = await (await GeoTIFF.fromUrl(it.assets.visual.href)).readRasters({bbox: [x0, y0, x1, y1], width: Wd, height: Hd, interleave: true});
      const cv = document.createElement('canvas'); cv.width = Wd; cv.height = Hd; const g = cv.getContext('2d'), im = g.createImageData(Wd, Hd);
      for (let i = 0, j = 0; i < ras.length; i += 3, j += 4) { im.data[j] = ras[i]; im.data[j + 1] = ras[i + 1]; im.data[j + 2] = ras[i + 2]; im.data[j + 3] = ras[i] + ras[i + 1] + ras[i + 2] ? 255 : 0; }
      g.putImageData(im, 0, 0);
      const corners = [[x0, y1], [x1, y1], [x1, y0], [x0, y0]].map(p => proj4(UTM, 'EPSG:4326', p));
      const src = {url: cv.toDataURL('image/jpeg', .85), coordinates: corners};
      if (map.getSource('s2')) map.getSource('s2').updateImage(src);
      else { map.addSource('s2', {type: 'image', ...src}); map.addLayer({id: 's2', type: 'raster', source: 's2', paint: {'raster-fade-duration': 300}}, 'shade'); }
      map.setLayoutProperty('s2', 'visibility', 'visible');
      lbl(`Sentinel-2, ${pre ? 'prima' : 'dopo'} gli incendi: ${it.properties.datetime.slice(0, 10).split('-').reverse().join('/')} (10 m)`);
    } catch (e) { lbl('Immagine non disponibile: ' + e.message); key = null; }
    finally { busy = false; }
  }
  const later = () => { clearTimeout(timer); timer = setTimeout(s2, 600); };
  map.on('moveend', later); $('lS2').onchange = later;
  let phase = E.now() < SPLIT; setInterval(() => { const p = E.now() < SPLIT; if (p !== phase) { phase = p; later(); } }, 1000);
});
