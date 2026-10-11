import { useCallback, useEffect, useRef, useState } from "react";
import { api, guardarSesion, sesionGuardada, usarToken } from "./api";
import { plural } from "./etiquetas";
import type { Analisis, Dataset, Sesion, Sistema } from "./tipos";
import { Ingreso } from "./vistas/Ingreso";
import { Comunidad } from "./vistas/Comunidad";
import { Clasificacion } from "./vistas/Clasificacion";
import { Curaduria } from "./vistas/Curaduria";
import { Publicacion } from "./vistas/Publicacion";
import { Resumen } from "./vistas/Resumen";
import { Usuarios } from "./componentes/Usuarios";
import { DestinoPortada, RedConversaciones, Simbolo } from "./componentes/Marca";

export type Vista = "resumen" | "comunidad" | "clasificacion" | "curaduria" | "publicacion";
// Las cuatro etapas del flujo; el Resumen queda fuera del flujo y es la portada al ingresar
const VISTAS: Exclude<Vista, "resumen">[] = ["comunidad", "clasificacion", "curaduria", "publicacion"];

function vistaDeLaUrl(): Vista {
  const h = location.hash.slice(1) as Vista;
  return h === "resumen" || (VISTAS as Vista[]).includes(h) ? h : "resumen";
}

export default function App() {
  const [sesion, setSesion] = useState<Sesion | null>(sesionGuardada());
  const salir = useCallback(() => {
    api.post("/logout").catch(() => {});
    guardarSesion(null);
    setSesion(null);
  }, []);
  usarToken(sesion?.token ?? "", () => { guardarSesion(null); setSesion(null); });

  if (!sesion) {
    return <Ingreso alIngresar={(s) => { guardarSesion(s); usarToken(s.token, salir); setSesion(s); }} />;
  }
  return <Consola sesion={sesion} alSalir={salir} />;
}

function Consola({ sesion, alSalir }: { sesion: Sesion; alSalir: () => void }) {
  const [vista, setVista] = useState<Vista>(vistaDeLaUrl());
  const [sistema, setSistema] = useState<Sistema | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [analisis, setAnalisis] = useState<Analisis | null>(null);
  const [usuarios, setUsuarios] = useState(false);
  const [destino, setDestino] = useState<HTMLDivElement | null>(null);
  // "Flujo de curaduría" vuelve a la última etapa visitada
  const ultimaEtapa = useRef<Exclude<Vista, "resumen">>("comunidad");
  useEffect(() => { if (vista !== "resumen") ultimaEtapa.current = vista; }, [vista]);
  const temporizador = useRef<number>();

  // Cada etapa tiene su #ancla: los botones atrás/adelante del navegador y los enlaces directos funcionan
  const ir = (v: Vista) => {
    if (location.hash !== `#${v}`) location.hash = v;
    else setVista(v);
  };
  useEffect(() => {
    const alCambiar = () => {
      setVista(vistaDeLaUrl());
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", alCambiar);
    return () => window.removeEventListener("hashchange", alCambiar);
  }, []);

  useEffect(() => {
    api.get<Sistema>("/sistema").then(setSistema).catch(() => {});
    api.get<Dataset>("/dataset").then(setDataset).catch(() => {});
  }, []);

  const actualizar = useCallback(async () => {
    try {
      setAnalisis(await api.get<Analisis>("/analisis"));
    } catch {
      /* el siguiente ciclo lo reintenta */
    }
  }, []);

  // Mientras el motor trabaja en segundo plano, el estado se consulta seguido; en reposo, no.
  useEffect(() => {
    window.clearTimeout(temporizador.current);
    const fase = analisis?.fase;
    const imagenesPendientes = analisis?.imagenes && !analisis.imagenes.terminado;
    const espera = fase === "clasificando" ? 900 : fase === "redactando" || imagenesPendientes ? 2500 : 0;
    if (!analisis) actualizar();
    else if (espera) temporizador.current = window.setTimeout(actualizar, espera);
    return () => window.clearTimeout(temporizador.current);
  }, [analisis, actualizar]);

  // Al terminar un análisis, el lote se vuelve a pedir para saber qué mensajes ya quedaron analizados en la base
  useEffect(() => {
    if (analisis?.fase === "listo") api.get<Dataset>("/dataset").then(setDataset).catch(() => {});
  }, [analisis?.fase]);

  const etapas = calcularEtapas(dataset, analisis);

  return (
    <div className="consola">
      <header className="masthead">
        <RedConversaciones className="masthead-red" />
        <div className="marco masthead-interior">
          <div className="barra">
            <span className="marca"><span className="marca-icono"><Simbolo tam={26} /></span>
              CommunityLab <span className="ai">AI</span></span>
            <span className="espacio" />
            <span className="usuario">
              <span className="usuario-nombre">{sesion.usuario}</span>
              {sesion.rol === "ADMIN" && (
                <button className="boton fantasma chico" onClick={() => setUsuarios(true)}>Usuarios</button>
              )}
              <button className="boton fantasma chico" onClick={alSalir}>Salir</button>
            </span>
          </div>

          <nav className="pestanas" aria-label="Secciones">
            <button aria-current={vista === "resumen" ? "page" : undefined} onClick={() => ir("resumen")}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></svg>
              Resumen
            </button>
            <button aria-current={vista !== "resumen" ? "page" : undefined}
              onClick={() => ir(vista === "resumen" ? ultimaEtapa.current : vista)}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="2.5" /><circle cx="19" cy="12" r="2.5" /><path d="M7.5 12h9" /><path d="M12 7v10" /></svg>
              Flujo<span className="solo-ancho"> de curaduría</span>
            </button>
          </nav>

          {vista !== "resumen" && <nav className="flujo" aria-label="Etapas del flujo">
            {VISTAS.map((v) => (
              <button key={v} className={`etapa ${vista === v ? "activa" : ""} ${etapas[v].trabajando ? "trabajando" : ""}`}
                aria-current={vista === v ? "page" : undefined} onClick={() => ir(v)}>
                <span className="pista"><i style={{ width: `${etapas[v].avance * 100}%` }} /></span>
                <span className="nombre">{etapas[v].nombre}</span>
                <span className="cuenta num">{etapas[v].cuenta}</span>
              </button>
            ))}
          </nav>}
          <div ref={setDestino} />
        </div>
      </header>

      <DestinoPortada.Provider value={destino}>
        <main className="marco pagina">
          {vista === "resumen" && <Resumen alAnalizar={() => ir("comunidad")} />}
          {vista === "comunidad" && (
            <Comunidad dataset={dataset} analisis={analisis} sistema={sistema}
              alCambiarDataset={setDataset} alAnalizar={() => ir("clasificacion")} />
          )}
          {vista === "clasificacion" && (
            <Clasificacion dataset={dataset} analisis={analisis} sistema={sistema}
              alActualizar={actualizar} alCurar={() => ir("curaduria")} alElegirFuente={() => ir("comunidad")} />
          )}
          {vista === "curaduria" && (
            <Curaduria analisis={analisis} alActualizar={actualizar} alAnalizar={() => ir("clasificacion")}
              alPublicar={() => ir("publicacion")} />
          )}
          {vista === "publicacion" && (
            <Publicacion analisis={analisis} sistema={sistema} alActualizar={actualizar} alCurar={() => ir("curaduria")} />
          )}
        </main>
      </DestinoPortada.Provider>

      <footer className="pie-marca">
        <div className="marco pie-interior">
          <span className="marca"><Simbolo tam={22} /> CommunityLab <span className="ai">AI</span></span>
          <span className="pie-lema">Personas + Conversaciones + Oportunidades</span>
          <span className="tenue">Hackathon ONE G10, NoCountry</span>
        </div>
      </footer>
      {usuarios && <Usuarios alCerrar={() => setUsuarios(false)} />}
    </div>
  );
}

interface Etapa { nombre: string; cuenta: string; avance: number; trabajando?: boolean }

function calcularEtapas(dataset: Dataset | null, a: Analisis | null): Record<Exclude<Vista, "resumen">, Etapa> {
  const total = dataset?.total ?? 0;
  const comunidad: Etapa = { nombre: "Comunidad", cuenta: dataset ? plural(total, "mensaje", "mensajes") : "cargando…",
    avance: total ? 1 : 0 };

  let clasificacion: Etapa = { nombre: "Clasificación", cuenta: "sin analizar", avance: 0 };
  if (a?.fase === "error") clasificacion = { ...clasificacion, cuenta: "se detuvo con un error" };
  else if (a?.fase === "clasificando")
    clasificacion = { ...clasificacion, cuenta: `clasificando ${a.mensajes.length} de ${a.total}`,
      avance: a.mensajes.length / Math.max(a.total, 1), trabajando: true };
  else if (a?.resumen)
    clasificacion = { ...clasificacion, avance: 1,
      cuenta: plural(a.resumen.oportunidades_detectadas, "oportunidad", "oportunidades") };

  let curaduria: Etapa = { nombre: "Curaduría", cuenta: "sin borradores", avance: 0 };
  if (a?.paquete && a.redaccion) {
    const { aprobado, descartado } = a.paquete.curaduria;
    if (!a.redaccion.terminado)
      curaduria = { ...curaduria, cuenta: `redactando ${a.redaccion.listos} de ${a.redaccion.total}`,
        avance: a.redaccion.listos / Math.max(a.redaccion.total, 1), trabajando: true };
    else if (a.paquete.activos)
      curaduria = { ...curaduria, cuenta: `${aprobado} de ${a.paquete.activos} aprobados`,
        avance: (aprobado + descartado) / a.paquete.activos };
  }

  const r = a?.resultado_oci;
  const publicacion: Etapa = {
    nombre: "Publicación",
    cuenta: !r ? (a?.paquete ? "sin guardar" : "—") : r.status === "guardado_con_exito" ? "guardado en OCI" : "copia local",
    avance: r ? 1 : 0,
  };
  return { comunidad, clasificacion, curaduria, publicacion };
}
