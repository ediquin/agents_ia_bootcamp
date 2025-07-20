import os
from dotenv import load_dotenv # <-- AÑADE ESTA LÍNEA
load_dotenv() # <-- Y ESTA LÍNEA
from crewai import Agent, Task, Crew
# from crewai_tools import ScrapeWebsiteTool # <-- COMENTADO PORQUE LA HERRAMIENTA NO EXISTE

# NOTA: Debes asegurarte de tener la API Key como una variable de entorno.
# No la pegues directamente en el código.
os.environ["OPENAI_API_KEY"] = "DUMMY_KEY_FOR_CREWAI" # CrewAI lo requiere, aunque usaremos Gemini.
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY') # Asegúrate que tu API key está aquí.

from langchain_google_genai import ChatGoogleGenerativeAI

# Configura el LLM que usarán todos los agentes
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    verbose=True,
    temperature=0.5,
    google_api_key=os.environ.get("GOOGLE_API_KEY")
)

# Herramienta para que el primer agente pueda raspar la web
# Es más simple y robusta que nuestro código Selenium original para este framework
# scraper = ScrapeWebsiteTool() # <-- COMENTADO PORQUE LA HERRAMIENTA NO EXISTE

# ---------------------------------
# 1. DEFINICIÓN DE NUESTROS AGENTES
# ---------------------------------

class AgentesDeContenido:
    def analista_web(self):
        return Agent(
            role='Analista Experto de Contenido Web',
            goal='Extraer el contenido principal y esencial de una página web, eliminando todo el ruido (menús, footers, anuncios).',
            backstory='Eres un analista de contenido con años de experiencia en identificar las partes más valiosas de un sitio web para su posterior análisis y reconstrucción.',
            # tools=[scraper],  # <-- Elimina o comenta esta línea
            llm=llm,
            verbose=True
        )

    def especialista_seo(self):
        return Agent(
            role='Especialista en SEO y Copywriting',
            goal='Reescribir y optimizar un texto dado para una palabra clave específica, mejorando su legibilidad, atractivo y posicionamiento en buscadores.',
            backstory='Eres un gurú del SEO que sabe cómo transformar un contenido simple en una pieza que enamora tanto a Google como a los usuarios. Conoces todas las técnicas de copywriting para maximizar el engagement.',
            llm=llm,
            verbose=True
        )

    def codificador_html(self):
        return Agent(
            role='Desarrollador Frontend Senior con especialidad en Bootstrap',
            goal='Tomar una serie de elementos de contenido (títulos, párrafos, imágenes) y convertirlos en un archivo HTML limpio, moderno y responsivo usando Bootstrap 5.',
            backstory='Eres un desarrollador frontend que convierte ideas y contenidos en páginas web funcionales y estéticamente agradables. Tu código es siempre limpio y sigue las mejores prácticas.',
            llm=llm,
            verbose=True
        )

# ---------------------------------
# 2. DEFINICIÓN DE LAS TAREAS
# ---------------------------------

class TareasDeContenido:
    def analisis_de_contenido(self, agent, texto):
        return Task(
            description=(
                'Recibe el siguiente texto extraído de una página web. '
                'Si puedes, organiza y resume el contenido de forma clara y estructurada. '
                'Si no puedes optimizar o el texto es muy corto o irrelevante, simplemente devuelve el texto tal cual lo recibiste, sin cambios.\n\n'
                f'TEXTO:\n{texto}'
            ),
            expected_output='Un texto limpio y legible que resuma u organice el contenido recibido, pero si no es posible, devuelve exactamente el mismo texto recibido.',
            agent=agent,
            async_execution=False
        )

    def optimizacion_seo(self, agent, keyword):
        return Task(
            description=f'Toma el contenido extraído de la tarea anterior y optimízalo para la palabra clave: "{keyword}". Incorpora la palabra clave de forma natural en títulos y párrafos. Mejora la redacción para que sea más atractiva.',
            expected_output='El contenido de texto reescrito y optimizado para SEO.',
            agent=agent,
            async_execution=False
        )

    def generacion_html(self, agent):
        return Task(
            description='Convierte el texto optimizado para SEO en un archivo HTML completo. Utiliza Bootstrap 5 para el diseño. La página debe ser responsiva e incluir un contenedor principal (`<div class="container">`). Las imágenes deben tener la clase `img-fluid`. El resultado final debe ser el código HTML completo en un solo bloque.',
            expected_output='Un único bloque de código que contenga el HTML completo, desde `<!DOCTYPE html>` hasta `</html>`.',
            agent=agent,
            async_execution=False
        )