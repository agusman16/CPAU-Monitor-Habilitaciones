import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from pyproj import Transformer

# 1. Configuración de la interfaz del navegador
st.set_page_config(
    page_title="Monitor CPAU - Habilitaciones CABA", 
    page_icon="📍", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos estéticos del monitor
st.markdown("""
    <style>
    .main .block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; }
    h1 { color: #1E3A8A; font-family: 'Helvetica Neue', Arial, sans-serif; font-weight: 700; }
    h3 { color: #2C3E50; font-family: 'Helvetica Neue', Arial, sans-serif; margin-top: 1rem; }
    .stMetric { background-color: #F8FAFC; padding: 15px; border-radius: 10px; border: 1px solid #E2E8F0; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Monitor de Habilitaciones Comerciales CPAU (CABA)")
st.caption("Análisis geoespacial interactivo de dinámicas comerciales urbanas | Período 2019 - 2024")
st.markdown("---")

# 2. Carga y conversión matemática de coordenadas (De metros POSGAR a Grados WGS84)
@st.cache_data
def cargar_y_proyectar_datos():
    ruta_csv = "HA_19-24_PROCESADO.csv"
    data = pd.read_csv(ruta_csv, sep=';', encoding='utf-8-sig', dtype=str)
    
    # Limpieza básica de la columna temporal de años
    if 'ano_habilitacion' in data.columns:
        data['ano_habilitacion'] = data['ano_habilitacion'].astype(str).str.replace('.0', '', regex=False)
        data = data[data['ano_habilitacion'] != '<NA>']
        data = data[data['ano_habilitacion'].str.strip() != '']
        
    # Conversión geométrica en tiempo real para el entorno web
    if 'X_5347' in data.columns and 'Y_5347' in data.columns:
        # Convertir textos limpios a números decimales de punto flotante
        data['X_num'] = pd.to_numeric(data['X_5347'], errors='coerce')
        data['Y_num'] = pd.to_numeric(data['Y_5347'], errors='coerce')
        
        # Eliminar filas con coordenadas rotas para que no falle la biblioteca de mapas
        data = data.dropna(subset=['X_num', 'Y_num'])
        
        # Configurar el transformador: De EPSG:5347 (CABA metros) a EPSG:4326 (Internet Lat/Lon)
        transformer = Transformer.from_crs("EPSG:5347", "EPSG:4326", always_xy=True)
        
        # Ejecutar la proyección matemática en bloque sobre toda la base de datos
        lon, lat = transformer.transform(data['X_num'].values, data['Y_num'].values)
        data['longitud'] = lon
        data['latitud'] = lat
        
    return data

df = cargar_y_proyectar_datos()

# 3. Barra Lateral de Filtros Cruzados Dinámicos
st.sidebar.header("Filtros Territoriales")
st.sidebar.markdown("Modifica los criterios para actualizar los mapas y estadísticas de forma instantánea.")

if 'ano_habilitacion' in df.columns:
    anos_ordenados = sorted(df['ano_habilitacion'].unique())
    anos_seleccionados = st.sidebar.multiselect("Filtrar Período (Años):", options=anos_ordenados, default=anos_ordenados)
else:
    anos_seleccionados = []

if 'rubros' in df.columns:
    rubros_disponibles = sorted(df['rubros'].unique())
    rubros_seleccionados = st.sidebar.multiselect("Filtrar Categorías de Rubro:", options=rubros_disponibles, default=rubros_disponibles)
else:
    rubros_seleccionados = []

# Aplicación estricta de filtros sobre el DataFrame
df_filtrado = df.copy()
if anos_seleccionados:
    df_filtrado = df_filtrado[df_filtrado['ano_habilitacion'].isin(anos_seleccionados)]
if rubros_seleccionados:
    df_filtrado = df_filtrado[df_filtrado['rubros'].isin(rubros_seleccionados)]

# 4. Sección de Indicadores Rápidos (KPIs)
metrica_total, metrica_rubros, metrica_zonas = st.columns(3)
with metrica_total:
    st.metric(label="Trámites en la Zona Seleccionada", value=f"{len(df_filtrado):,}".replace(",", "."))
with metrica_rubros:
    categorias_activas = df_filtrado['rubros'].nunique() if 'rubros' in df_filtrado.columns else 0
    st.metric(label="Categorías Comerciales Activas", value=f"{categorias_activas} de 7")
with metrica_zonas:
    columna_barrio = next((col for col in df_filtrado.columns if 'barrio' in col.lower() or 'comuna' in col.lower()), None)
    barrios_unicos = df_filtrado[columna_barrio].nunique() if columna_barrio else 0
    st.metric(label="Barrios bajo Análisis", value=barrios_unicos)

st.markdown("<br>", unsafe_allow_html=True)

# 5. NUEVA SECCIÓN PRINCIPAL: MAPA INTERACTIVO DE DISTRIBUCIÓN URBANA
st.subheader("📍 Distribución Cartográfica en Tiempo Real (CABA)")
st.caption("Pasa el cursor sobre los puntos para visualizar la descripción del rubro y la fecha de habilitación oficial.")

if 'latitud' in df_filtrado.columns and len(df_filtrado) > 0:
    # Definir centro geográfico inicial coordinado sobre el centro geográfico de CABA (Caballito)
    centro_caba = [-34.6157, -58.4333]
    
    # Crear el lienzo del mapa interactivo usando Folium
    m = folium.Map(location=centro_caba, zoom_start=12, tiles="cartodbpositron")
    
    # Paleta de colores lógicos para identificar los rubros principales visualmente en el mapa
    colores_rubros = {
        "1. Comercio Minorista de Cercanía": "blue",
        "2. Gastronomía y Alimentación": "orange",
        "3. Servicios Profesionales y Oficinas": "purple",
        "4. Salud y Estética": "green",
        "5. Esparcimiento, Cultura y Deporte": "pink",
        "6. Industria y Depósito": "red",
        "7. Educación, ciencia y tecnología": "cadetblue"
    }
    
    # Para evitar ralentizar el navegador con más de 20.000 puntos simultáneos, 
    # mapeamos de forma detallada una muestra significativa de hasta 1.200 puntos por consulta filtrada
    limite_puntos = min(1200, len(df_filtrado))
    df_mapa = df_filtrado.sample(n=limite_puntos, random_state=42) if len(df_filtrado) > 1200 else df_filtrado
    
    # Renderizar cada punto comercial en la cuadrícula del mapa
    for _, fila in df_mapa.iterrows():
        rubro_actual = fila.get('rubros', 'Desconocido')
        color_punto = colores_rubros.get(rubro_actual, "gray")
        
        # Construcción del cuadro de descripción emergente (Popup)
        texto_popup = f"""
        <strong>Categoría:</strong> {rubro_actual}<br>
        <strong>Trámite:</strong> {fila.get('descripcion_rubro', 'Sin descripción')}<br>
        <strong>Año:</strong> {fila.get('ano_habilitacion', 'S/D')}
        """
        
        folium.CircleMarker(
            location=[float(fila['latitud']), float(fila['longitud'])],
            radius=4,
            popup=folium.Popup(texto_popup, max_width=300),
            color=color_punto,
            fill=True,
            fill_color=color_punto,
            fill_opacity=0.6,
            weight=1
        ).add_to(m)
    
    # Dibujar e incrustar el mapa interactivo en la página web de Streamlit
    st_folium(m, width="100%", height=500, returned_objects=[])
else:
    st.warning("No se encontraron coordenadas válidas para dibujar el mapa cartográfico.")

st.markdown("---")

# 6. Gráficos Estadísticos Inferiores (Evolución Temporal y de Actividades)
col_izq, col_der = st.columns(2)

with col_izq:
    st.subheader("📈 Evolución de Habilitaciones por Año")
    if 'ano_habilitacion' in df_filtrado.columns and len(df_filtrado) > 0:
        conteo_anos = df_filtrado['ano_habilitacion'].value_counts().reset_index()
        conteo_anos.columns = ['Año', 'Cantidad']
        conteo_anos = conteo_anos.sort_values(by='Año')
        
        fig_lineas = px.line(conteo_anos, x='Año', y='Cantidad', markers=True, text='Cantidad',
                             color_discrete_sequence=['#2563EB'], template="plotly_white")
        fig_lineas.update_traces(textposition="top center", line=dict(width=3))
        st.plotly_chart(fig_lineas, width='stretch')

with col_der:
    st.subheader("📊 Distribución de Estructuras Comerciales")
    if 'rubros' in df_filtrado.columns and len(df_filtrado) > 0:
        conteo_rubros = df_filtrado['rubros'].value_counts().reset_index()
        conteo_rubros.columns = ['Categoría', 'Cantidad']
        conteo_rubros = conteo_rubros.sort_values(by='Categoría')
        
        fig_barras = px.bar(conteo_rubros, x='Cantidad', y='Categoría', orientation='h', text='Cantidad',
                            color='Categoría', color_discrete_sequence=px.colors.qualitative.Prism, template="plotly_white")
        fig_barras.update_traces(textposition="outside")
        fig_barras.update_layout(showlegend=False, yaxis={'categoryorder':'category descending'})
        st.plotly_chart(fig_barras, width='stretch')

# 7. Relación Temática Territorial (Rubros por Barrio)
if columna_barrio and 'rubros' in df_filtrado.columns and len(df_filtrado) > 0:
    st.markdown("---")
    st.subheader("🏢 Comparativa de Perfiles Comerciales por Barrio")
    df_cruzado = df_filtrado.groupby([columna_barrio, 'rubros']).size().reset_index(name='Cantidad')
    top_barrios = df_filtrado[columna_barrio].value_counts().head(15).index
    df_cruzado_filtrado = df_cruzado[df_cruzado[columna_barrio].isin(top_barrios)]
    
    fig_apilado = px.bar(
        df_cruzado_filtrado, x=columna_barrio, y='Cantidad', color='rubros',
        labels={columna_barrio: 'Barrio / Comuna', 'Cantidad': 'Número de Trámites', 'rubros': 'Categorías'},
        color_discrete_sequence=px.colors.qualitative.Prism, template="plotly_white"
    )
    fig_apilado.update_layout(barmode='stack', xaxis={'categoryorder':'total descending'})
    st.plotly_chart(fig_apilado, width='stretch')

# 8. Tabla exploradora de datos crudos (Preview)
if st.checkbox("🔍 Mostrar explorador de base de datos completa (Primeras 500 filas)"):
    st.dataframe(df_filtrado.head(500), width='stretch')
