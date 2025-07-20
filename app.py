import streamlit as st
from agentes_crew import AgentesDeContenido, TareasDeContenido
from crewai import Crew

import requests
from bs4 import BeautifulSoup

def extraer_contenido_requests(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        partes = []
        # Títulos principales
        for tag in soup.select("h1, h2, h3"):
            txt = tag.get_text(strip=True)
            if txt:
                partes.append(txt)
        # Productos y descripciones
        for card in soup.select(".caption"):
            txt = card.get_text(separator=" ", strip=True)
            if txt:
                partes.append(txt)
        # Precios
        for price in soup.select(".price"):
            txt = price.get_text(strip=True)
            if txt:
                partes.append(f"Precio: {txt}")
        texto = "\n".join(partes)
        return texto[:8000]
    except Exception as e:
        return f"Error al extraer contenido: {e}"

st.set_page_config(page_icon="🚀", layout="centered")

st.title("🚀 Agente de Migración y Optimización Web")

st.markdown("""
Bienvenido. Esta aplicación utiliza un equipo de agentes de IA para migrar, optimizar para SEO y rediseñar cualquier página web.
1.  **Introduce la URL** de la página que quieres migrar.
2.  **Define tu palabra clave** para la optimización SEO.
3.  **Lanza los agentes** y observa la magia.

⚠️ *Esta demo funciona mejor con páginas simples y públicas. Si el texto extraído no es útil, edítalo antes de procesar.*
""")

# --- Inputs del Usuario ---
url = st.text_input("🔗 URL de la página a migrar", placeholder="https://ejemplo.com/articulo")
keyword = st.text_input("🎯 Palabra Clave para SEO", placeholder="mejores zapatillas para correr")

texto_extraido = ""
if url:
    texto_extraido = extraer_contenido_requests(url)
    if texto_extraido.startswith("Error"):
        st.error(texto_extraido)
        texto_extraido = ""

texto_editable = st.text_area("Texto extraído (puedes editarlo antes de procesar)", value=texto_extraido, height=300, key="texto_editable")

if st.button("Procesar con IA"):
    if not url or not keyword:
        st.error("Por favor, introduce la URL y la palabra clave.")
    elif not texto_editable.strip():
        st.error("No hay texto extraído para procesar.")
    else:
        texto_final = texto_editable[:8000]  # Limita a 8000 caracteres
        # --- Inicialización de Agentes y Tareas ---
        agentes = AgentesDeContenido()
        tareas = TareasDeContenido()

        analista = agentes.analista_web()
        seo_specialist = agentes.especialista_seo()
        html_coder = agentes.codificador_html()

        tarea_analisis = tareas.analisis_de_contenido(analista, texto_final)
        tarea_seo = tareas.optimizacion_seo(seo_specialist, keyword)
        tarea_html = tareas.generacion_html(html_coder)

        equipo_de_contenido = Crew(
            agents=[analista, seo_specialist, html_coder],
            tasks=[tarea_analisis, tarea_seo, tarea_html],
            verbose=True
        )

        with st.spinner("🤖 Los agentes están trabajando... Esto puede tardar unos minutos..."):
            try:
                resultado_final = equipo_de_contenido.kickoff()
                # Si el resultado es vacío, fallback
                if not resultado_final or not resultado_final.strip():
                    raise ValueError("Resultado vacío")
            except Exception as e:
                # Fallback: muestra el body optimizado hasta donde se pudo
                body_optimizado = texto_editable.strip() or "(Sin contenido procesado)"
                resultado_final = f"""
                <!DOCTYPE html>
                <html lang='es'>
                <head>
                    <meta charset='UTF-8'>
                    <title>Página incompleta</title>
                    <link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css' rel='stylesheet'>
                </head>
                <body>
                    <div class='container mt-5'>
                        <h2>Contenido optimizado hasta donde fue posible</h2>
                        <pre>{body_optimizado}</pre>
                    </div>
                </body>
                </html>
                """
                st.warning("El procesamiento con IA falló. Se muestra el contenido extraído hasta donde fue posible.")

            st.success("¡Trabajo completado! 🎉")
            st.balloons()
            
            # --- Mostrar Resultados ---
            st.subheader("📄 Página HTML Generada y SEO Optimizada")
            st.code(resultado_final, language='html')

            st.download_button(
                label="📥 Descargar página HTML optimizada",
                data=resultado_final,
                file_name="pagina_migrada_seo.html",
                mime="text/html"
            )
            
            st.subheader("👀 Vista Previa de la Página SEO Optimizada")
            st.markdown(f'<iframe srcdoc="{resultado_final.replace("`", "")}" width="100%" height="600px"></iframe>', unsafe_allow_html=True)