import { useEffect, useState } from "react";
import { api, descargar } from "../api";
import { Guardadas } from "../componentes/Guardadas";
import { Portada, Vacio } from "../componentes/Marca";
import { FORMATOS, TIPOS, plural } from "../etiquetas";
import type { Analisis, Paquete, PublicacionGuardada, ResultadoOCI, Sistema } from "../tipos";

interface Props {
  analisis: Analisis | null;
  sistema: Sistema | null;
  alActualizar: () => void;
  alCurar: () => void;
}

export function Publicacion({ analisis, sistema, alActualizar, alCurar }: Props) {
  const [paquete, setPaquete] = useState<Paquete | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [guardadas, setGuardadas] = useState<PublicacionGuardada[] | null>(null);
  const meta = analisis?.paquete;

  useEffect(() => {
    if (meta) api.get<Paquete>("/paquete").then(setPaquete).catch(() => setPaquete(null));
  }, [meta?.paquete_id, meta?.curaduria.aprobado, analisis?.resultado_oci]);

  if (!meta) {
    return (
      <>
        <Portada titulo="Publicaciones"
          bajada="Lo que ya está guardado en OCI. Para sumar un paquete nuevo, analiza un lote y cura sus borradores."
          cifras={guardadas ? [
            { valor: guardadas.length, texto: "guardadas en OCI" },
            { valor: guardadas.filter((g) => g.imagen).length, texto: "con imagen" },
            { valor: new Set(guardadas.map((g) => g.autor).filter(Boolean)).size, texto: "personas destacadas" },
          ] : undefined} />
        <Guardadas recarga={0} alCargar={setGuardadas} />
      </>
    );
  }

  const aprobados = (paquete?.activos ?? []).filter((a) => a.estado_curaduria === "aprobado");
  const conImagen = (paquete?.activos ?? []).filter((a) => a.imagen?.estado === "lista").length;
  const redactando = analisis?.redaccion && !analisis.redaccion.terminado;
  const resultado = analisis?.resultado_oci;

  async function guardar() {
    setGuardando(true);
    setError("");
    try {
      await api.post<ResultadoOCI>("/paquete/guardar");
      alActualizar();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <>
      <Portada
        titulo="Guardar el paquete"
        bajada="El paquete viaja completo, con el estado de curaduría de cada borrador y sus imágenes. Cada activo aprobado se puede rastrear hasta el mensaje que lo originó."
        cifras={[
          { valor: aprobados.length, texto: "aprobados" },
          { valor: meta.activos, texto: "en el paquete" },
          { valor: conImagen, texto: "con imagen" },
        ]}
      />

      <div className="publicar">
        <section className="seccion">
          <h2>{plural(aprobados.length, "activo aprobado", "activos aprobados")}</h2>
          {aprobados.length ? (
            <div className="hoja">
              {aprobados.map((a) => (
                <div className="traza" key={a.activo_id}>
                  <span className="paso"><b>{a.activo_id}</b><span className="sec">{FORMATOS[a.formato]}</span></span>
                  <span className="paso">
                    {a.origen.opportunity_id}<span className="sec">{TIPOS[a.origen.type]}, score {a.origen.score.toFixed(2)}</span>
                  </span>
                  <span className="paso">
                    {a.origen.message_id}<span className="sec">#{a.origen.channel || "sin canal"}</span>
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <Vacio titulo="Aún no apruebas ningún borrador"
              acciones={<button className="boton" onClick={alCurar}>Ir a curaduría</button>}>
              El paquete se puede guardar igual: cada activo viaja con su estado de curaduría.
            </Vacio>
          )}
        </section>

        <section className="hoja hoja-cuerpo seccion">
          <h2>Destino</h2>
          <dl className="datos">
            <dt>Servicio</dt>
            <dd>{sistema?.oci_conectado ? "OCI Object Storage (Always Free)" : "Copia local (sin credenciales de OCI)"}</dd>
            <dt>Bucket</dt><dd>{sistema?.bucket ?? "—"}</dd>
            <dt>Ruta</dt><dd>{meta.ruta_objeto}</dd>
            <dt>Paquete</dt><dd>{meta.paquete_id}, estado {meta.status}</dd>
            <dt>Contenido</dt>
            <dd>{aprobados.length} de {meta.activos} aprobados, {plural(conImagen, "con imagen", "con imagen")}</dd>
          </dl>
          {redactando && (
            <p className="nota aviso">
              Todavía se están redactando borradores ({analisis!.redaccion!.listos} de {analisis!.redaccion!.total}).
              Espera a que termine para guardar el paquete completo.
            </p>
          )}
          <button className="boton primario" onClick={guardar} disabled={guardando || !!redactando}>
            {guardando && <span className="cargando" />}
            {sistema?.oci_conectado ? "Guardar en OCI" : "Guardar copia local"}
          </button>
          {error && <p className="nota error" role="alert">{error}</p>}
          {resultado && (
            <>
              <p className={`nota ${resultado.status === "guardado_con_exito" ? "bien" : resultado.error ? "aviso" : "bien"}`}>
                {resultado.status === "guardado_con_exito"
                  ? `Guardado en OCI con ${plural(resultado.imagenes_subidas ?? 0, "imagen", "imágenes")}.`
                  : resultado.error ? "No se pudo subir a OCI; quedó la copia local." : "Guardado en local."}
              </p>
              <pre className="resultado">{JSON.stringify(resultado, null, 2)}</pre>
            </>
          )}
          <button className="boton" onClick={() => descargar("/paquete/json", `${meta.paquete_id}.json`)}>
            Descargar paquete (JSON)
          </button>
        </section>
      </div>
      <Guardadas recarga={resultado ? 1 : 0} />
    </>
  );
}
