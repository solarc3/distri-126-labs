"""Frontend de estadísticas de CivicMesh (Seccion 5.4).

Sirve una pagina que muestra el estado por topic x canal, la brecha
percepcion-realidad, la convergencia entre peers y el estado de la vista.
Lee las metricas desde ``metrics/`` en cada request para reflejar corridas
en vivo (por ejemplo, el experimento de caida de peers).

Uso:
    python scripts/frontend.py --metrics <dir de metricas> [--port 8080]
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from civicmesh.frontend import construir_resumen
from civicmesh.metrics import MetricaError, leer_metricas

PAGINA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>CivicMesh - Metricas</title>
<style>
  body{font-family:system-ui,Segoe UI,Arial,sans-serif;background:#0f172a;
  color:#e2e8f0;margin:2rem}
  h1{color:#38bdf8}
  h2{color:#94a3b8;border-bottom:1px solid #334155;padding-bottom:.3rem}
  table{border-collapse:collapse;margin:.6rem 0;width:100%;max-width:700px}
  th,td{border:1px solid #334155;padding:.3rem .6rem;font-size:.9rem;text-align:left}
  th{background:#1e293b}
  .ok{color:#34d399}
  .mal{color:#f87171}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));
  gap:1rem}
  canvas,svg{width:100%;height:80px}
</style>
</head>
<body>
<h1>CivicMesh &mdash; Metricas en vivo</h1>
<p id="meta"></p>
<div id="contenido">Cargando...</div>
<script>
const fmt=x=>{
  if(typeof x==="string")return x;
  if(x==null)return "-";
  return Number(x).toFixed(1);
};
function spark(vals,w=330,h=80){
  if(!vals.length)return"<i>sin datos</i>";
  const xs=vals.map(v=>v[0]),min=Math.min(...xs),max=Math.max(...xs);
  const pts=vals.map((v,i)=>{
    const y=v[1], ys=vals.map(q=>q[1]);
    const lo=Math.min(...ys),hi=Math.max(...ys);
    const px=i*(w/(Math.max(vals.length-1,1)));
    const py=h-(hi===lo?h/2:(y-lo)/(hi-lo)*(h-8)+4);
    return px+","+py;
  }).join(" ");
  return '<svg width="'+w+'" height="'+h+'"><polyline points="'+pts+
    '" fill="none" stroke="#38bdf8" stroke-width="2"/></svg>';
}
function tabla(titulo,filas){
  if(!filas.length)return "";
  let h="<h3>"+titulo+"</h3><table><tr>"+
    Object.keys(filas[0]).map(k=>"<th>"+k+"</th>").join("")+"</tr>";
  for(const f of filas){
    h+="<tr>"+Object.values(f).map(v=>"<td>"+fmt(v)+"</td>").join("")+"</tr>";
  }
  return h+"</table>";
}
async function actualizar(){
  const r=await fetch("/api/resumen");
  const d=await r.json();
  if(d.error)return document.getElementById("contenido").innerHTML=d.error;
  document.getElementById("meta").textContent=
    "Registros: "+d.total_registros+" | Peers: "+Object.keys(d.vista).length;
  let html="";
  const m={objetivo:"objetivo",subjetivo:"subjetivo"};
  for(const topic of Object.keys(d.topicos)){
    const t=d.topicos[topic];
    let estado="";
    for(const canal of ["objetivo","subjetivo"]){
      if(!t[canal])continue;
      const up=t[canal].ultimo_por_peer;
      const filas=Object.keys(up).map(p=>({peer:p,valor:up[p]}));
      estado+=tabla("Canal "+canal+" (por peer)",filas);
      const c=t[canal].convergencia;
      estado+="<p>Convergencia: "+(c.convergido
        ?'<b class="ok">SI</b>':'<b class="mal">NO</b>')+
        " &mdash; dispersion final "+fmt(c.dispersion_final)+
        (c.ts_convergencia!=null?" &mdash; t="+fmt(c.ts_convergencia):"")+"</p>";
      estado+=spark(c.serie.map(s=>[s[0],s[1]]));
    }
    const brecha=t.brecha.map(b=>({ts:b[0],peer:b[1],gap:b[2]}));
    html+='<div class="grid"><div><h2>'+topic+'</h2>'+estado+
      tabla("Brecha perceptiva-realidad",brecha)+"</div></div>";
  }
  const vista=Object.keys(d.vista).map(p=>{
    const v=d.vista[p];return {peer:p,vivos:v.vivos,sospechosos:v.sospechosos,
      muertos:v.muertos,total:v.total};
  });
  html+=tabla("Estado de la vista por peer",vista);
  document.getElementById("contenido").innerHTML=html;
}
actualizar();
setInterval(actualizar,2000);
</script>
</body>
</html>
"""


def _crear_handler(metrica_ruta: Path, eps: float, bucket: float) -> type:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _formato: str, *args: object) -> None:
            return

        def _json(self, data: object) -> None:
            cuerpo = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self) -> None:
            if self.path == "/api/resumen":
                try:
                    metricas = leer_metricas(metrica_ruta)
                    resumen = construir_resumen(metricas, eps=eps, bucket=bucket)
                except MetricaError as error:
                    self._json({"error": str(error)})
                    return
                self._json(resumen)
                return
            cuerpo = PAGINA.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

    return Handler


def _main(args: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Frontend de metricas de CivicMesh")
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--eps", type=float, default=2.0)
    parser.add_argument("--bucket", type=float, default=0.1)
    parsed = parser.parse_args(args)

    if not parsed.metrics.exists():
        parser.error(f"no existe el directorio de metricas: {parsed.metrics}")

    servidor = ThreadingHTTPServer(
        (parsed.host, parsed.port),
        _crear_handler(parsed.metrics, parsed.eps, parsed.bucket),
    )
    print(f"Frontend en http://{parsed.host}:{parsed.port} (metrics={parsed.metrics})")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
