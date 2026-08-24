import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from pyproj import Transformer

# 1. Configuracion de pantalla optimizada para monitores (16:9)
st.set_page_config(
    page_title="Monitor CPAU - Habilitaciones CABA", 
    page_icon="📍", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Diseno adaptativo por CSS para pantallas grandes y moviles (9:16)
st.markdown("""
    <style>
    .main .block-container { padding-top: 1.5rem !important; padding-bottom: 1.5rem !important; }
    div[data-testid="stVerticalBlock"] { gap: 0.8rem !important; }
    h1 { color: #1E3A8A; font-family: sans-serif; font-weight: 700; font-size: 1.8rem !important; margin-bottom: 0.2rem !important; }
    
    /* Cuadrantes superiores con tipografia clara y visible */
    div[data-testid="stContainer"] {
        background-color: #F8FAFC !important;
        padding: 12px 16px !important;
        border-radius: 8px !important;
        border: 1px solid #E2E8F0 !important;
        text-align: center;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    div[data-testid="stContainer"] h4 { color: #1E3A8A !important; font-size: 1.6rem !important; margin: 0 !important; }
    div[data-testid="stContainer"] p { color: #475569 !important; font-weight: 600; font-size: 0.85rem !important; margin: 0 !important; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1>📊 Monitor de Habilitaciones Comerciales CPAU (CABA)</h1>", unsafe_allow_html=True)
st.caption("Estructura comercial urbana y distribucion de tramites 2019 - 2024")

# 2. Carga y conversion matematica de coordenadas
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

columna_barrio = "BARRIO"
columna_comuna = "COMUNA"

# 3. Barra Lateral de Filtros
st.sidebar.header("Filtros del Tablero")

anos_ordenados = sorted(df['ano_habilitacion'].unique()) if 'ano_habilitacion' in df.columns else []
anos_seleccionados = st.sidebar.multiselect("Filtrar por Ano:", options=anos_ordenados, default=anos_ordenados)

rubros_disponibles = sorted(df['rubros'].unique()) if 'rubros' in df.columns else []
rubros_seleccionados = st.sidebar.multiselect("Filtrar por Categoria de Rubro:", options=rubros_disponibles, default=rubros_disponibles)

df_filtrado = df.copy()
if anos_seleccionados:
    df_filtrado = df_filtrado[df_filtrado['ano_habilitacion'].isin(anos_seleccionados)]
if rubros_seleccionados:
    df_filtrado = df_filtrado[df_filtrado['rubros'].isin(rubros_seleccionados)]

comunas_seleccionadas = []
if columna_comuna in df_filtrado.columns:
    comunas_disponibles = sorted(df_filtrado[columna_comuna].dropna().unique(), key=lambda x: int(''.join(filter(str.isdigit, str(x))) or 0))
    comunas_seleccionadas = st.sidebar.multiselect("Filtrar por Comuna:", options=comunas_disponibles)
    if comunas_seleccionadas:
        df_filtrado = df_filtrado[df_filtrado[columna_comuna].isin(comunas_seleccionadas)]

if columna_barrio in df_filtrado.columns:
    barrios_disponibles = sorted(df_filtrado[columna_barrio].dropna().unique())
    barrios_seleccionados = st.sidebar.multiselect("Filtrar por Barrio:", options=barrios_disponibles)
    if barrios_seleccionados:
        df_filtrado = df_filtrado[df_filtrado[columna_barrio].isin(barrios_seleccionados)]

# 4. Cuadrantes numericos superiores
metrica_total, metrica_rubros, metrica_zonas = st.columns(3)

with metrica_total:
    with st.container():
        st.write("Habilitaciones Totales")
        st.subheader(f"{len(df_filtrado):,}".replace(",", "."))

with metrica_rubros:
    with st.container():
        st.write("Categorias Activas")
        categorias_activas = df_filtrado['rubros'].nunique() if 'rubros' in df_filtrado.columns else 0
        st.subheader(f"{categorias_activas} de 7")

with metrica_zonas:
    with st.container():
        st.write("Barrios en Pantalla")
        barrios_unicos = df_filtrado[columna_barrio].nunique() if columna_barrio in df_filtrado.columns else 0
        st.subheader(str(barrios_unicos))

st.markdown("<br>", unsafe_allow_html=True)

# 5. CORRECCIÓN CRÍTICA: Se añade el argumento 2 para definir las columnas en paralelo (Formato 16:9 PC)
col_mapa, col_graficos = st.columns(2)

with col_mapa:
    st.markdown("### 📍 Mapa de Distribucion Territorial")
    if 'latitud' in df_filtrado.columns and len(df_filtrado) > 0:
        centro_mapa = [df_filtrado['latitud'].astype(float).mean(), df_filtrado['longitud'].astype(float).mean()] if len(df_filtrado) < 5000 else [-34.6157, -58.4333]
        zoom_inicial = 14 if (columna_barrio in df_filtrado.columns and 'barrios_seleccionados' in locals() and barrios_seleccionados) else (13 if comunas_seleccionadas else 11.8)
        
        m = folium.Map(location=centro_mapa, zoom_start=zoom_inicial, tiles="cartodbpositron")
        
        colores_rubros = {
            "1. Comercio Minorista de Cercania": "blue",
            "2. Gastronomia y Alimentacion": "orange",
            "3. Servicios Profesionales y Oficinas": "purple",
            "4. Salud y Estetiva": "green",
            "5. Esparcimiento, Cultura y Deporte": "pink",
            "6. Industria y Deposito": "red",
            "7. Educacion, ciencia y tecnologia": "cadetblue"
        }
        
        limite_puntos = min(1000, len(df_filtrado))
        df_mapa = df_filtrado.sample(n=limite_puntos, random_state=42) if len(df_filtrado) > 1200 else df_filtrado
        
        for _, fila in df_mapa.iterrows():
            rubro_actual = fila.get('rubros', 'Desconocido')
            color_punto = colores_rubros.get(rubro_actual, "gray")
            
            texto_popup = f"<b>Rubro:</b> {rubro_actual}<br><b>Tramite:</b> {fila.get('descripcion_rubro', 'S/D')}<br><b>Ano:</b> {fila.get('ano_habilitacion', 'S/D')}"
            
            folium.CircleMarker(
                location=[float(fila['latitud']), float(fila['longitud'])],
                radius=4,
                popup=folium.Popup(texto_popup, max_width=250),
                color=color_punto,
                fill=True,
                fill_color=color_punto,
                fill_opacity=0.6,
                weight=1
            ).add_to(m)
        
        st_folium(m, width="100%", height=480, returned_objects=[])
    else:
        st.warning("Selecciona criterios con datos espaciales validos.")

with col_graficos:
    st.markdown("### 📊 Indicadores Estadisticos")
    
    # Grafico A: Evolucion Temporal (Altura de 230px para formato PC)
    if 'ano_habilitacion' in df_filtrado.columns and len(df_filtrado) > 0:
        conteo_anos = df_filtrado['ano_habilitacion'].value_counts().reset_index()
        conteo_anos.columns = ['Ano', 'Cantidad']
        fig_lineas = px.line(conteo_anos.sort_values(by='Ano'), x='Ano', y='Cantidad', markers=True, text='Cantidad',
                             color_discrete_sequence=['#2563EB'], template="plotly_white")
        fig_lineas.update_traces(textposition="top center", line=dict(width=3))
        fig_lineas.update_layout(height=230, margin=dict(l=10, r=10, t=15, b=10), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig_lineas, width='stretch')

    # Grafico B: Distribucion de Rubros (Altura de 230px para formato PC)
    if 'rubros' in df_filtrado.columns and len(df_filtrado) > 0:
        conteo_rubros = df_filtrado['rubros'].value_counts().reset_index()
        conteo_rubros.columns = ['Categoria', 'Cantidad']
        fig_barras = px.bar(conteo_rubros.sort_values(by='Categoria'), x='Cantidad', y='Categoria', orientation='h', text='Cantidad',
                            color='Categoria', color_discrete_sequence=px.colors.qualitative.Prism, template="plotly_white")
        fig_barras.update_traces(textposition="outside")
        fig_barras.update_layout(showlegend=False, height=230, margin=dict(l=10, r=10, t=15, b=10), xaxis_title=None, yaxis_title=None, yaxis={'categoryorder':'category descending'})
        st.plotly_chart(fig_barras, width='stretch')

# 6. Matriz Comparativa Territorial (Fila inferior expansible)
if columna_barrio in df_filtrado.columns and 'rubros' in df_filtrado.columns and len(df_filtrado) > 0:
    st.markdown("---")
    with st.expander("🏢 Ver Matriz y Perfil Comparativo por Barrio (Análisis de Suelo)"):
        df_cruzado = df_filtrado.groupby([columna_barrio, 'rubros']).size().reset_index(name='Cantidad')
        top_barrios = df_filtrado[columna_barrio].value_counts().head(10).index
        df_cruzado_filtrado = df_cruzado[df_cruzado[columna_barrio].isin(top_barrios)]
        
        fig_apilado = px.bar(
            df_cruzado_filtrado, x=columna_barrio, y='Cantidad', color='rubros',
            color_discrete_sequence=px.colors.qualitative.Prism, template="plotly_white"
        )
        fig_apilado.update_layout(barmode='stack', height=350, xaxis={'categoryorder':'total descending'}, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_apilado, width='stretch')
