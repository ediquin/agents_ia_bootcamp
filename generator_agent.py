import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timezone
import uuid
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==============================================================================
# SECCIÓN 1: CONFIGURACIÓN Y HERRAMIENTAS OPTIMIZADAS
# ==============================================================================
GOOGLE_API_KEY = 'Paste the API key Here'

try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"Error al configurar la API de Google. Verifica tu API Key. Error: {e}")
    model = None

def minify_html(html_string: str) -> str:
    if not isinstance(html_string, str): 
        return ''
    minified = re.sub(r'[\n\t\r]', '', html_string)
    minified = re.sub(r'>\s+<', '><', minified)
    minified = re.sub(r'\s+', ' ', minified)
    return minified.strip()

def clean_and_extract_content(soup):
    """
    Extrae y limpia el contenido más relevante de la página
    Elimina elementos no deseados y optimiza para la API
    """
    # Elementos a eliminar completamente
    unwanted_selectors = [
        'script', 'style', 'nav', 'header', 'footer', 
        '.navigation', '.nav', '.menu', '.sidebar', 
        '.cookie', '.popup', '.modal', '.advertisement', 
        '.ad', '.social', '.share', '.comment', '.breadcrumb',
        '[id*="cookie"]', '[class*="cookie"]', '[id*="ad"]', 
        '[class*="ad"]', '.hidden', '[style*="display:none"]',
        '.footer', '.header', '#footer', '#header'
    ]
    
    # Remover elementos no deseados
    for selector in unwanted_selectors:
        for element in soup.select(selector):
            element.decompose()
    
    # Priorizar contenido principal
    main_content_selectors = [
        'main', 'article', '[role="main"]', 
        '#content', '#main', '#main-content', 
        '.content', '.main-content', '.page-content',
        '.post-content', '.entry-content', '.article-content'
    ]
    
    main_content = None
    for selector in main_content_selectors:
        candidates = soup.select(selector)
        if candidates:
            # Elegir el candidato con más contenido de texto
            best_candidate = max(candidates, key=lambda x: len(x.get_text().strip()))
            if len(best_candidate.get_text().strip()) > 200:  # Mínimo 200 caracteres
                main_content = best_candidate
                break
    
    # Si no encontramos contenido principal, usar el body pero limpiado
    if not main_content:
        main_content = soup.body or soup
    
    # Limpiar atributos innecesarios para reducir tamaño
    for tag in main_content.find_all(True):
        # Mantener solo atributos esenciales
        essential_attrs = ['href', 'src', 'alt', 'title', 'class', 'id']
        attrs_to_remove = [attr for attr in tag.attrs if attr not in essential_attrs]
        for attr in attrs_to_remove:
            del tag[attr]
        
        # Simplificar clases (mantener solo las primeras 2)
        if 'class' in tag.attrs and isinstance(tag['class'], list):
            tag['class'] = tag['class'][:2]
    
    return main_content

def estimate_token_count(text):
    """Estimación básica de tokens (aproximadamente 4 caracteres por token)"""
    return len(text) // 4

def truncate_content_smart(html_content, max_chars=20000):
    """
    Trunca el contenido de manera inteligente manteniendo la estructura HTML
    """
    if len(html_content) <= max_chars:
        return html_content
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Priorizar elementos por importancia
    priority_elements = []
    
    # 1. Títulos (más importantes)
    for tag in soup.find_all(['h1', 'h2', 'h3']):
        priority_elements.append(('title', tag, len(str(tag))))
    
    # 2. Párrafos con contenido sustancial
    for tag in soup.find_all('p'):
        text_length = len(tag.get_text().strip())
        if text_length > 50:  # Solo párrafos con contenido significativo
            priority_elements.append(('paragraph', tag, len(str(tag))))
    
    # 3. Listas
    for tag in soup.find_all(['ul', 'ol']):
        priority_elements.append(('list', tag, len(str(tag))))
    
    # 4. Imágenes relevantes
    for tag in soup.find_all('img'):
        if tag.get('alt') or tag.get('title'):
            priority_elements.append(('image', tag, len(str(tag))))
    
    # Ordenar por tipo de prioridad y tamaño
    type_priority = {'title': 1, 'paragraph': 2, 'list': 3, 'image': 4}
    priority_elements.sort(key=lambda x: (type_priority.get(x[0], 5), -x[2]))
    
    # Construir HTML optimizado
    selected_html = []
    current_length = 0
    
    for elem_type, element, elem_length in priority_elements:
        if current_length + elem_length <= max_chars:
            selected_html.append(str(element))
            current_length += elem_length
        else:
            break
    
    return '<div>' + ''.join(selected_html) + '</div>'

def get_layout_instruction(component: dict) -> tuple[str, bool]:
    props = component.get('layout_properties', {})
    distribution = props.get('distribution')
    if distribution == ["50%", "50%"]: 
        return "En su CMS, agregue una sección de **dos columnas iguales (50/50)**.", True
    if distribution == ["33%", "33%", "33%"]: 
        return "En su CMS, agregue una sección de **tres columnas iguales (33/33/33)**.", True
    if distribution == ["33%", "67%"]: 
        return "En su CMS, agregue una sección de **dos columnas (33/66)**.", True
    if distribution == ["67%", "33%"]: 
        return "En su CMS, agregue una sección de **dos columnas (66/33)**.", True
    if distribution == ["25%", "25%", "25%", "25%"]: 
        return "En su CMS, agregue una sección de **cuatro columnas iguales (25/25/25/25)**.", True
    return ("**Layout Complejo Detectado:**\nPara preservar la estructura original, cree una **sección de ancho completo** y pegue el siguiente bloque de código HTML en un único widget.", False)

def build_html_for_component(component: dict) -> str:
    component_type = component.get('component_type')
    content = component.get('content', {})
    layout_props = component.get('layout_properties', {})
    html = ""
    
    # Manejar cuando content es un string en lugar de un objeto
    if isinstance(content, str):
        content_text = content
        content = {'text': content_text}
    elif not isinstance(content, dict):
        content = {}
    
    if component_type == "Heading": 
        # Priorizar level de layout_properties, luego de content, luego default
        level = layout_props.get('level') or content.get('level', 2)
        text = content.get('text', '')
        html = f"<h{level}>{text}</h{level}>"
    elif component_type == "TextBlock": 
        heading = content.get('heading', '')
        paragraph = content.get('paragraph', '')
        html = f"<h2>{heading}</h2><p>{paragraph}</p>"
    elif component_type == "Paragraph": 
        text = content.get('text', '')
        html = f"<p>{text}</p>"
    elif component_type == "Image": 
        src = content.get('src', '') or layout_props.get('src', '')
        alt = content.get('alt', '') or layout_props.get('alt', '')
        html = f'<img src="{src}" alt="{alt}" style="width: 100%;">'
    elif component_type == "Button": 
        url = content.get('url', '') or layout_props.get('url', '')
        text = content.get('text', '')
        html = f'<a class="btn btn-primary" href="{url}" role="link">{text}</a>'
    elif component_type == "BulletedList":
        items = content.get('items', [])
        if isinstance(items, str):
            items = [items]
        list_items = "".join([f"<li>{item}</li>" for item in items])
        html = f"<ul>{list_items}</ul>"
    elif component_type == "CustomHTML":
        html = content.get('html_code', component.get('original_html_snippet', ''))
    else:
        print(f"⚠️  Advertencia: Tipo de componente desconocido '{component_type}'. Usando contenido como texto.")
        text = content.get('text', str(content) if content else '')
        html = f"<div>{text}</div>"
    
    return minify_html(html)

# ==============================================================================
# SECCIÓN 2: AGENTE MAPEADOR OPTIMIZADO (v3.0)
# ==============================================================================
def run_mapping_agent(url: str) -> dict | None:
    if not model:
        print("El modelo de IA no está configurado.")
        return None
        
    print(f"🤖 Agente Mapeador (v3.0 Optimizado): Iniciando análisis -> {url}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-images")  # No cargar imágenes para ser más rápido
    chrome_options.add_argument("--disable-javascript")  # Opcional: deshabilitar JS si no es necesario
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    service = Service()
    driver = None
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.get(url)
        
        # Esperar menos tiempo para ser más eficiente
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(2)

        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        
        print("🔍 Optimizador v3.0: Extrayendo y limpiando contenido relevante...")
        
        # Usar la nueva función de limpieza
        main_content_soup = clean_and_extract_content(soup)
        
        if not main_content_soup:
            print("Error: No se pudo extraer contenido de la página")
            return None
        
        # Convertir a string y optimizar para la API
        html_to_analyze = str(main_content_soup)
        
        # Truncar de manera inteligente si es muy largo
        original_length = len(html_to_analyze)
        html_to_analyze = truncate_content_smart(html_to_analyze, max_chars=15000)
        
        if len(html_to_analyze) < original_length:
            print(f"📏 Contenido truncado de {original_length} a {len(html_to_analyze)} caracteres")
        
        estimated_tokens = estimate_token_count(html_to_analyze)
        print(f"📊 Tokens estimados: {estimated_tokens}")
        
        if estimated_tokens > 8000:
            print("⚠️  Advertencia: El contenido podría ser muy largo para la API gratuita")
        
        # Prompt optimizado y más específico
        master_prompt = f"""
Eres un experto analista de contenido web. Analiza SOLO el contenido principal de esta página web y extrae los elementos más importantes para SEO y experiencia de usuario.

ENFÓCATE EN:
1. Títulos principales (H1, H2, H3)
2. Párrafos con contenido relevante y valioso
3. Listas importantes
4. Imágenes con alt text significativo
5. Botones/enlaces de acción

IGNORA:
- Navegación y menús
- Footers y headers
- Contenido duplicado o boilerplate
- Elementos decorativos

ESTRUCTURA JSON OBLIGATORIA - SIGUE EXACTAMENTE ESTE FORMATO:

Para Heading:
{{
    "id": "h1_1",
    "component_type": "Heading",
    "content": {{
        "text": "Texto del título",
        "level": 1
    }},
    "layout_properties": {{}}
}}

Para Paragraph:
{{
    "id": "p_1",
    "component_type": "Paragraph",
    "content": {{
        "text": "Texto del párrafo"
    }},
    "layout_properties": {{}}
}}

Para Button:
{{
    "id": "btn_1",
    "component_type": "Button",
    "content": {{
        "text": "Texto del botón",
        "url": "https://example.com"
    }},
    "layout_properties": {{}}
}}

Para Image:
{{
    "id": "img_1",
    "component_type": "Image",
    "content": {{
        "src": "url_de_imagen",
        "alt": "texto_alternativo"
    }},
    "layout_properties": {{}}
}}

ESQUEMA FINAL:
{{
    "schema_version": "1.1",
    "source_url": "{url}",
    "analysis_timestamp": "{datetime.now(timezone.utc).isoformat()}",
    "main_content_blueprint": [
        // Array de componentes siguiendo los formatos de arriba
    ]
}}

HTML A ANALIZAR:
{html_to_analyze}

IMPORTANTE: El campo "content" SIEMPRE debe ser un objeto {{}}, NUNCA un string directo.
Responde ÚNICAMENTE con el JSON válido."""
        
        generation_config = genai.GenerationConfig(
            max_output_tokens=8192,
            temperature=0.1,
            top_p=0.8
        )
        
        print("🤖 Enviando contenido optimizado a Gemini...")
        response_llm = model.generate_content(master_prompt, generation_config=generation_config)

        if not response_llm or not response_llm.text:
            print("Error: El modelo no devolvió respuesta")
            return None

        json_text = response_llm.text.strip()
        
        # Limpiar la respuesta
        if '```json' in json_text:
            json_text = json_text.split('```json', 1)[1].rsplit('```', 1)[0]
        json_text = json_text.strip()

        try:
            blueprint = json.loads(json_text)
            
            # Validar que el blueprint tenga contenido
            if not blueprint.get('main_content_blueprint'):
                print("⚠️  Advertencia: Blueprint vacío o sin contenido principal")
                return None
                
            print(f"✅ Blueprint generado con {len(blueprint['main_content_blueprint'])} componentes")
            return blueprint
            
        except json.JSONDecodeError as e:
            print(f"Error JSON: {e}")
            print("Respuesta recibida (primeros 500 chars):")
            print(response_llm.text[:500])
            return None
            
    except Exception as e:
        print(f"Error durante el análisis: {e}")
        return None
    finally:
        if driver:
            driver.quit()

# ==============================================================================
# SECCIÓN 3: AGENTE CONSTRUCTOR CORREGIDO (v2.4)
# ==============================================================================
def run_generator_agent(blueprint: dict) -> str:
    print("✍️ Agente Constructor (v2.4): Iniciando la generación de la guía...")
    
    # Detector universal de contenido CORREGIDO
    component_list = None
    if blueprint and 'main_content_blueprint' in blueprint:
        component_list = blueprint['main_content_blueprint']
    elif blueprint and 'content' in blueprint and isinstance(blueprint['content'], list):
        print("⚠️  Adaptando: La IA usó la clave 'content'")
        component_list = blueprint['content']
    elif blueprint and 'components' in blueprint and isinstance(blueprint['components'], list):
        print("⚠️  Adaptando: La IA usó la clave 'components'")
        component_list = blueprint['components']
    
    if not component_list or not isinstance(component_list, list):
        return "Error: Blueprint no válido o sin componentes reconocibles."

    guide_parts = [
        "### Guía de Migración de Contenido (Generada por Agente v3.0)\n",
        f"**Componentes detectados:** {len(component_list)}\n"
    ]
    
    # USAR component_list en lugar de blueprint['main_content_blueprint'] ✅
    for i, component in enumerate(component_list):
        if not isinstance(component, dict):
            continue
            
        guide_parts.append(f"---\n\n### Paso {i+1}: Procesar Sección ({component.get('component_type')})")
        
        component_type = component.get('component_type')
        content = component.get('content', {})

        if component_type == "ColumnsContainer":
            instruction, is_simple_layout = get_layout_instruction(component)
            guide_parts.append(instruction)

            if isinstance(content, dict): 
                columns = content.get('columns', {})
            elif isinstance(content, list):
                print("⚠️  Advertencia: 'content' de ColumnsContainer es una lista. Procesando como una sola columna.")
                columns = {"column_1": content} 
            else: 
                columns = {}
            
            if is_simple_layout and columns:
                for col_name, col_widgets in columns.items():
                    if not isinstance(col_widgets, list):
                        continue
                        
                    col_number = col_name.split('_')[-1]
                    guide_parts.append(f"\n#### Contenido para la COLUMNA {col_number}")
                    
                    text_widget_html = ""
                    for widget in col_widgets:
                        if not isinstance(widget, dict):
                            continue
                            
                        if widget.get('component_type') in ["Heading", "Paragraph", "BulletedList", "FeatureCard", "TextBlock"]:
                            text_widget_html += build_html_for_component(widget)
                        else:
                            if text_widget_html:
                                guide_parts.append(f"**Widget: Contenido de Texto**\n```html\n{minify_html(text_widget_html)}\n```")
                                text_widget_html = ""
                            guide_parts.append(f"**Widget: {widget.get('component_type')}**\n```html\n{build_html_for_component(widget)}\n```")
                    
                    if text_widget_html:
                        guide_parts.append(f"**Widget: Contenido de Texto**\n```html\n{minify_html(text_widget_html)}\n```")
            else:
                complex_html = component.get('original_html_snippet', '<div>Contenido complejo detectado</div>')
                guide_parts.append(f"```html\n{minify_html(complex_html)}\n```")
        else:
            guide_parts.append("En su CMS, agregue una **sección de ancho completo**.")
            guide_parts.append(f"**Widget: {component_type}**\n```html\n{build_html_for_component(component)}\n```")

    print("✅ Agente Constructor: Guía completada.")
    return "\n".join(guide_parts)

# ==============================================================================
# SECCIÓN 4: ORQUESTADOR PRINCIPAL
# ==============================================================================
def main():
    print("🚀 Orquestador v3.0: Iniciando pipeline optimizado...")
    target_url = "https://www.legacychryslerjeepdodgeram.net/car-dealership-serving/pendleton-or/"
    
    json_blueprint = run_mapping_agent(target_url)
    
    if json_blueprint:
        print("\n" + "="*60)
        print(" Blueprint JSON Optimizado ".center(60))
        print("="*60)
        print(json.dumps(json_blueprint, indent=2)[:2000] + "..." if len(str(json_blueprint)) > 2000 else json.dumps(json_blueprint, indent=2))
        
        migration_guide = run_generator_agent(json_blueprint)
        
        print("\n" + "="*60)
        print(" Guía de Migración Final ".center(60))
        print("="*60)
        print(migration_guide)
    else:
        print("\n❌ El proceso no pudo completarse debido a un error en la fase de análisis.")
    
    print("\n✅ Orquestador: Proceso finalizado.")

if __name__ == "__main__":
    main()
