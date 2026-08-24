import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Configuración visual de la ventana del Navegador
st.set_page_config(
    page_title="Monitor CPAU - Habilitaciones CABA", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo personalizado para mejorar la tipografía y la visualización de datos
st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { color: #1E3A8A; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 700; }
    h3 { color: #2C3E50; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 500; }
    .stMetric { background-color: #F8FAFC; padding: 15px; border-radius: 10px; border: 1px solid #E2E8F0; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Monitor de Habilitaciones Comerciales CPAU (CABA)")
st.caption("Análisis interactivo de dinámicas comerciales del tejido urbano | Período 2019 - 2024")
st.markdown("---")

# 2. Carga optimizada de la base de datos limpia desde el entorno online
@st.cache_data
def cargar_datos_limpios():
    # Al estar online, buscamos el archivo directamente por su nombre en el repositorio
    ruta_csv = "HA_19-24_PROCESADO.csv" 
    data = pd.read_csv(ruta_csv, sep=';', encoding='utf-8-sig', dtype=str)
    
    if 'ano_habilitacion' in data.columns:
        data['ano_habilitacion'] = data['ano_habilitacion'].astype(str).str.replace('.0', '', regex=False)
        data = data[data['ano_habilitacion'] != '<NA>']
        data = data[data['ano_habilitacion'].str.strip() != '']
    return data

df = cargar_datos_limpios()

# 3. Panel de Filtros Interactivos en la Barra Lateral (Sidebar)
st.sidebar.header("Filtros del Tablero")
st.sidebar.markdown("Modifica las selecciones para actualizar los gráficos en tiempo real.")

# Filtro A: Selección de Período Temporal (Años)
if 'ano_habilitacion' in df.columns:
    anos_ordenados = sorted(df['ano_habilitacion'].unique())
    anos_seleccionados = st.sidebar.multiselect(
        "Seleccionar Años:", 
        options=anos_ordenados, 
        default=anos_ordenados
    )
else:
    anos_seleccionados = []

# Filtro B: Selección de la Nueva Clasificación de Rubros
if 'rubros' in df.columns:
    rubros_disponibles = sorted(df['rubros'].unique())
    rubros_seleccionados = st.sidebar.multiselect(
        "Seleccionar Categorías de Rubro:", 
        options=rubros_disponibles, 
        default=rubros_disponibles
    )
else:
    rubros_seleccionados = []

# Aplicación estricta de filtros cruzados sobre los datos
df_filtrado = df.copy()
if anos_seleccionados:
    df_filtrado = df_filtrado[df_filtrado['ano_habilitacion'].isin(anos_seleccionados)]
if rubros_seleccionados:
    df_filtrado = df_filtrado[df_filtrado['rubros'].isin(rubros_seleccionados)]

# 4. Bloque Superior de Métricas Clave (KPIs)
metrica_total, metrica_rubros, metrica_barrios = st.columns(3)

with metrica_total:
    st.metric(
        label="Total Trámites Registrados", 
        value=f"{len(df_filtrado):,}".replace(",", ".")
    )
with metrica_rubros:
    categorias_activas = df_filtrado['rubros'].nunique() if 'rubros' in df_filtrado.columns else 0
    st.metric(
        label="Categorías en Pantalla", 
        value=f"{categorias_activas} de 7"
    )
with metrica_barrios:
    columna_barrio = next((col for col in df_filtrado.columns if 'barrio' in col.lower() or 'comuna' in col.lower()), None)
    barrios_unicos = df_filtrado[columna_barrio].nunique() if columna_barrio else "N/A"
    st.metric(
        label="Zonas Urbanas Cubiertas", 
        value=barrios_unicos
    )

st.markdown("<br>", unsafe_allow_html=True)

# 5. Fila de Gráficos Principales (Distribución Temporal y de Actividades)
col_izq, col_der = st.columns(2)

with col_izq:
    st.subheader("📈 Evolución de Habilitaciones por Año")
    if 'ano_habilitacion' in df_filtrado.columns and len(df_filtrado) > 0:
        conteo_anos = df_filtrado['ano_habilitacion'].value_counts().reset_index()
        conteo_anos.columns = ['Año', 'Cantidad']
        conteo_anos = conteo_anos.sort_values(by='Año')
        
        # Gráfico dinámico de líneas y puntos de Plotly
        fig_lineas = px.line(
            conteo_anos, x='Año', y='Cantidad', 
            markers=True, text='Cantidad',
            color_discrete_sequence=['#2563EB'], 
            template="plotly_white"
        )
        fig_lineas.update_traces(textposition="top center", line=dict(width=3))
        st.plotly_chart(fig_lineas, use_container_width=True)
    else:
        st.info("No hay datos temporales disponibles para el criterio seleccionado.")

with col_der:
    st.subheader("📊 Distribución Estricta por Rubro")
    if 'rubros' in df_filtrado.columns and len(df_filtrado) > 0:
        conteo_rubros = df_filtrado['rubros'].value_counts().reset_index()
        conteo_rubros.columns = ['Categoría', 'Cantidad']
        conteo_rubros = conteo_rubros.sort_values(by='Categoría') # Respeta el orden jerárquico del 1 al 8
        
        # Gráfico de barras horizontales
        fig_barras = px.bar(
            conteo_rubros, x='Cantidad', y='Categoría', 
            orientation='h', text='Cantidad',
            color='Categoría', 
            color_discrete_sequence=px.colors.qualitative.Prism,
            template="plotly_white"
        )
        fig_barras.update_traces(textposition="outside")
        fig_barras.update_layout(showlegend=False, yaxis={'categoryorder':'descending'})
        st.plotly_chart(fig_barras, use_container_width=True)
    else:
        st.info("Selecciona al menos una categoría de rubro en la barra lateral.")

st.markdown("---")

# 6. Bloque Inferior: Relación Espacial (Rubros por Barrio / Comuna)
st.subheader("🏢 Distribución Temática Territorial")

if columna_barrio and 'rubros' in df_filtrado.columns and len(df_filtrado) > 0:
    # Agrupación cruzada de datos para contabilizar rubros por zona
    df_cruzado = df_filtrado.groupby([columna_barrio, 'rubros']).size().reset_index(name='Cantidad')
    
    # Filtrar los 15 principales barrios con más movimiento comercial para evitar sobrecargar el gráfico
    top_barrios = df_filtrado[columna_barrio].value_counts().head(15).index
    df_cruzado_filtrado = df_cruzado[df_cruzado[columna_barrio].isin(top_barrios)]
    
    # Gráfico de barras apiladas interactivo
    fig_apilado = px.bar(
        df_cruzado_filtrado, 
        x=columna_barrio, 
        y='Cantidad', 
        color='rubros',
        title=f"Estructura Comercial en las Principales Zonas de CABA (Top 15 por volumen)",
        labels={columna_barrio: 'Barrio / Comuna', 'Cantidad': 'Número de Trámites', 'rubros': 'Categorías del Rubro'},
        color_discrete_sequence=px.colors.qualitative.Prism,
        template="plotly_white"
    )
    fig_apilado.update_layout(barmode='stack', xaxis={'categoryorder':'total descending'})
    st.plotly_chart(fig_apilado, use_container_width=True)
else:
    st.info("La columna que detalla los barrios o comunas no pudo identificarse en los datos actuales.")

# 7. Tabla exploradora de datos crudos (Preview)
if st.checkbox("🔍 Mostrar explorador de base de datos completa (Primeras 500 filas)"):
    st.dataframe(df_filtrado.head(500), use_container_width=True)
