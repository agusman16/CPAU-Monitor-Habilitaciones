import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from pyproj import Transformer

# 1. Configuración nativa de la interfaz web
st.set_page_config(
    page_title="Monitor CPAU - Habilitaciones CABA", 
    page_icon="📍", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Monitor de Habilitaciones Comerciales CPAU (CABA)")
st.caption("Análisis geoespacial interactivo de dinámicas comerciales urbanas | Período 2019 - 2024")
st.markdown("---")

# 2. Carga y conversión de coordenadas por lote
@st.cache_data
def cargar_y_proyectar_datos():
    ruta_csv = "HA_19-24_PROCESADO.csv"
    data = pd.read_csv(ruta_csv, sep=';', encoding='utf-8-sig', dtype=str)
    
    if 'ano_habilitacion' in data.columns:
        data['ano_habilitacion'] = data['ano_habilitacion'].astype(str).str.replace('.0', '', regex=False)
        data = data[data['ano_habilitacion'] != '<NA>']
        data = data[data['ano_habilitacion'].str.strip() != '']
        
    if 'X_5347' in data.columns and 'Y_5347' in data.columns:
        data['X_num'] = pd.to_numeric(data['X_5347'], errors='coerce')
        data['Y_num'] = pd.to_numeric(data['Y_5347'], errors='coerce')
        data = data.dropna(subset=['X_num', 'Y_num'])
        
        transformer = Transformer.from_crs("EPSG:5347", "EPSG:4326", always_xy=True)
        lon, lat = transformer.transform(data['X_num'].values, data['Y_num'].values)
        data['longitud'] = lon
        data['latitud'] = lat
        
    return data

df = cargar_y_proyectar_datos()

# Búsqueda automatizada de columnas geográficas en tu CSV
columna_barrio = next((c for c in df.columns if 'barrio' in c.lower()), None)
columna_comuna = next((c for c in df.columns if 'comuna' in c.lower()), None)

# 3. Estructuración jerárquica de filtros en la Barra Lateral
st.sidebar.header("Filtros Temporales y Temáticos")

if 'ano_habilitacion' in df.columns:
    anos_ordenados = sorted(df['ano_habilitacion'].unique())
    anos_seleccionados = st.sidebar.multiselect("Filtrar por Año:", options=anos_ordenados, default=anos_ordenados)
else:
    anos_seleccionados = []

if 'rubros' in df.columns:
    rubros_disponibles = sorted(df['rubros'].unique())
    rubros_seleccionados = st.sidebar.multiselect("Filtrar por Categoría de Rubro:", options=rubros_disponibles, default=rubros_disponibles)
else:
    rubros_seleccionados = []

st.sidebar.markdown("---")
st.sidebar.header("Filtros Territoriales")

# Aplicar filtros temáticos base
df_filtrado = df.copy()
if anos_seleccionados:
    df_filtrado = df_filtrado[df_filtrado['ano_habilitacion'].isin(anos_seleccionados)]
if rubros_seleccionados:
    df_filtrado = df_filtrado[df_filtrado['rubros'].isin(rubros_seleccionados)]

# Filtro en cascada para Comunas
comunas_seleccionadas = []
if columna_comuna:
    comunas_disponibles = sorted(df_filtrado[columna_comuna].dropna().unique(), key=lambda x: int(''.join(filter(str.isdigit, str(x))) or 0))
    comunas_seleccionadas = st.sidebar.multiselect("Filtrar por Comuna:", options=comunas_disponibles)
    if comunas_seleccionadas:
        df_filtrado = df_filtrado[df_filtrado[columna_comuna].isin(comunas_seleccionadas)]

# Filtro en cascada para Barrios (reacciona a la comuna seleccionada)
if columna_barrio:
    barrios_disponibles = sorted(df_filtrado[columna_barrio].dropna().unique())
    barrios_seleccionados = st.sidebar.multiselect("Filtrar por Barrio:", options=barrios_disponibles)
    if barrios_seleccionados:
        df_filtrado = df_filtrado[df_filtrado[columna_barrio].isin(barrios_seleccionados)]

# 4. Cuadrantes superiores rediseñados en contenedores nativos estables
st.markdown("### 📈 Indicadores Generales de Selección")
metrica_total, metrica_rubros, metrica_zonas = st.columns(3)

# El uso de contenedores y texto nativo evita bloqueos por contraste e inyección CSS
with metrica_total:
    with st.container(border=True):
        st.markdown("**Habilitaciones Totales**")
        st.subheader(f"{len(df_filtrado):,}".replace(",", "."))

with metrica_rubros:
    with st.container(border=True):
        st.markdown("**Categorías Activas**")
        categorias_activas = df_filtrado['rubros'].nunique() if 'rubros' in df_filtrado.columns else 0
        st.subheader(f"{categorias_activas} de 7")

with metrica_zonas:
    with st.container(border=True):
        st.markdown("**Barrios en Pantalla**")
        barrios_unicos = df_filtrado[columna_barrio].nunique() if columna_barrio else 0
        st.subheader(str(barrios_unicos))

st.markdown("<br>", unsafe_allow_html=True)

# 5. MAPA INTERACTIVO DE DISTRIBUCIÓN URBANA FOILUM
st.subheader("📍 Distribución Cartográfica en Tiempo Real (CABA)")
st.caption("Usa las herramientas de zoom para explorar las habilitaciones otorgadas calle por calle.")

if 'latitud' in df_filtrado.columns and len(df_filtrado) > 0:
    centro_mapa = [df_filtrado['latitud'].astype(float).mean(), df_filtrado['longitud'].astype(float).mean()] if len(df_filtrado) < 5000 else [-34.6157, -58.4333]
    zoom_inicial = 14 if (columna_barrio and barrios_seleccionados) else (13 if comunas_seleccionadas else 12)
    
    m = folium.Map(location=centro_mapa, zoom_start=zoom_inicial, tiles="cartodbpositron")
    
    colores_rubros = {
        "1. Comercio Minorista de Cercanía": "blue",
        "2. Gastronomía y Alimentación": "orange",
        "3. Servicios Profesionales y Oficinas": "purple",
        "4. Salud y Estética": "green",
        "5. Esparcimiento, Cultura y Deporte": "pink",
        "6. Industria y Depósito": "red",
        "7. Educación, ciencia y tecnología": "cadetblue"
    }
    
    limite_puntos = min(1200, len(df_filtrado))
    df_mapa = df_filtrado.sample(n=limite_puntos, random_state=42) if len(df_filtrado) > 1200 else df_filtrado
    
    for _, fila in df_mapa.iterrows():
        rubro_actual = fila.get('rubros', 'Desconocido')
        color_punto = colores_rubros.get(rubro_actual, "gray")
        
        texto_popup = f"""
        <b>Categoría:</b> {rubro_actual}<br>
        <b>Trámite:</b> {fila.get('descripcion_rubro', 'Sin descripción')}<br>
        <b>Barrio:</b> {fila.get(columna_barrio, 'S/D')}<br>
        <b>Año:</b> {fila.get('ano_habilitacion', 'S/D')}
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
    
    st_folium(m, width="100%", height=500, returned_objects=[])
else:
    st.warning("Selecciona criterios con datos espaciales válidos en los filtros laterales.")

st.markdown("---")

# 6. Gráficos Estadísticos Inferiores
col_izq, col_der = st.columns(2)

with col_izq:
    st.subheader("📈 Evolución de Habilitaciones por Año")
    if 'ano_habilitacion' in df_filtrado.columns and len(df_filtrado) > 0:
        conteo_anos = df_filtrado['ano_habilitacion'].value_counts().reset_index()
        conteo_anos.columns = ['Año', 'Cantidad']
        fig_lineas = px.line(conteo_anos.sort_values(by='Año'), x='Año', y='Cantidad', markers=True, text='Cantidad',
                             color_discrete_sequence=['#2563EB'], template="plotly_white")
        fig_lineas.update_traces(textposition="top center", line=dict(width=3))
        st.plotly_chart(fig_lineas, width='stretch')

with col_der:
    st.subheader("📊 Distribución de Estructuras Comerciales")
    if 'rubros' in df_filtrado.columns and len(df_filtrado) > 0:
        conteo_rubros = df_filtrado['rubros'].value_counts().reset_index()
        conteo_rubros.columns = ['Categoría', 'Cantidad']
        fig_barras = px.bar(conteo_rubros.sort_values(by='Categoría'), x='Cantidad', y='Categoría', orientation='h', text='Cantidad',
                            color='Categoría', color_discrete_sequence=px.colors.qualitative.Prism, template="plotly_white")
        fig_barras.update_traces(textposition="outside")
        fig_barras.update_layout(showlegend=False, yaxis={'categoryorder':'category descending'})
        st.plotly_chart(fig_barras, width='stretch')

# 7. Relación Temática Territorial
if columna_barrio and 'rubros' in df_filtrado.columns and len(df_filtrado) > 0:
    st.markdown("---")
    st.subheader("🏢 Comparativa de Perfiles Comerciales por Barrio")
    df_cruzado = df_filtrado.groupby([columna_barrio, 'rubros']).size().reset_index(name='Cantidad')
    top_barrios = df_filtrado[columna_barrio].value_counts().head(15).index
    df_cruzado_filtrado = df_cruzado[df_cruzado[columna_barrio].isin(top_barrios)]
    
    fig_apilado = px.bar(
        df_cruzado_filtrado, x=columna_barrio, y='Cantidad', color='rubros',
        labels={columna_barrio: 'Barrio', 'Cantidad': 'Número de Trámites', 'rubros': 'Categorías'},
        color_discrete_sequence=px.colors.qualitative.Prism, template="plotly_white"
    )
    fig_apilado.update_layout(barmode='stack', xaxis={'categoryorder':'total descending'})
    st.plotly_chart(fig_apilado, width='stretch')
