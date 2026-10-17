
import streamlit as st
import folium
import requests
import pandas as pd
import os
import html
import json
from branca.element import MacroElement
from jinja2 import Template

from datetime import datetime, timezone
from streamlit_folium import st_folium

# La clave se configura en PowerShell, no se escribe en el archivo.
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "").strip()

CAPAS_METEOROLOGICAS = {
    "☁️ Nubes": "clouds_new",
    "🌧️ Precipitación": "precipitation_new",
    "🌡️ Temperatura": "temp_new",
    "💨 Viento": "wind_new",
    "🌐 Presión atmosférica": "pressure_new",
}

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================

st.set_page_config(
    page_title="SistemaGeo | Clima y Mapas",
    page_icon="🌎",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background-color: #f1f5f9;
}
h1, h2, h3 {
    color: #17324d;
}
div[data-testid="stMetric"] {
    background-color: white;
    border-radius: 12px;
    padding: 15px;
    border: 1px solid #dce5ed;
}
</style>
""", unsafe_allow_html=True)

st.title("🌎 SistemaGeo")
st.write(
    "Sistema de información geográfica y "
    "monitoreo meteorológico."
)

# =====================================================
# BUSCAR CIUDADES
# =====================================================

@st.cache_data(ttl=3600)
def buscar_lugar(nombre):

    url = "https://geocoding-api.open-meteo.com/v1/search"

    params = {
        "name": nombre,
        "count": 10,
        "language": "es",
        "format": "json"
    }

    respuesta = requests.get(
        url,
        params=params,
        timeout=20
    )

    respuesta.raise_for_status()

    return respuesta.json().get("results", [])


# =====================================================
# CONSULTAR CLIMA Y PRONÓSTICO
# =====================================================

@st.cache_data(ttl=300)
def obtener_clima(latitud, longitud):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitud,
        "longitude": longitud,

        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "precipitation",
            "rain",
            "cloud_cover",
            "wind_speed_10m",
            "wind_direction_10m",
            "weather_code"
        ],

        "hourly": [
            "temperature_2m",
            "precipitation_probability",
            "cloud_cover",
            "wind_speed_10m"
        ],

        "forecast_days": 2,
        "timezone": "auto"
    }

    respuesta = requests.get(
        url,
        params=params,
        timeout=20
    )

    respuesta.raise_for_status()

    return respuesta.json()


# =====================================================
# OBTENER RADAR DE LLUVIA
# =====================================================

@st.cache_data(ttl=300)
def obtener_frames_radar():
    """Obtiene las imágenes recientes disponibles del radar RainViewer."""
    respuesta = requests.get(
        "https://api.rainviewer.com/public/weather-maps.json",
        timeout=20
    )
    respuesta.raise_for_status()
    datos = respuesta.json()
    host = datos.get("host", "")
    frames = datos.get("radar", {}).get("past", [])
    return [
        {
            "url": host + frame["path"] + "/256/{z}/{x}/{y}/2/1_1.png",
            "fecha": datetime.fromtimestamp(
                frame["time"], timezone.utc
            ).strftime("%d/%m/%Y %H:%M UTC")
        }
        for frame in frames if host and frame.get("path") and frame.get("time")
    ]


class RadarAnimado(MacroElement):
    """Control Leaflet para reproducir los mosaicos del radar en secuencia."""

    _template = Template(r"""
    {% macro script(this, kwargs) %}
    (function() {
        var map = {{ this._parent.get_name() }};
        var frames = {{ this.frames_json | safe }};
        if (!frames.length) return;
        var indice = frames.length - 1;
        var intervalo = null;
        var capa = null;
        var slider, boton, etiqueta;

        function mostrar(i) {
            indice = i;
            if (capa) map.removeLayer(capa);
            capa = L.tileLayer(frames[i].url, {
                attribution: 'Radar: RainViewer',
                opacity: 0.7,
                maxNativeZoom: 7,
                maxZoom: 18
            }).addTo(map);
            if (slider) slider.value = i;
            if (etiqueta) etiqueta.textContent = frames[i].fecha;
        }

        function pausar() {
            if (intervalo !== null) {
                clearInterval(intervalo);
                intervalo = null;
            }
            if (boton) boton.textContent = '▶ Reproducir';
        }

        var Control = L.Control.extend({
            options: {position: 'bottomleft'},
            onAdd: function() {
                var panel = L.DomUtil.create('div');
                panel.style.cssText = 'background:white;padding:10px;border-radius:8px;box-shadow:0 1px 8px #777;font:13px sans-serif;min-width:230px;';
                var titulo = L.DomUtil.create('div', '', panel);
                titulo.textContent = '🌧️ Radar de lluvia animado';
                titulo.style.cssText = 'font-weight:bold;margin-bottom:6px;';
                boton = L.DomUtil.create('button', '', panel);
                boton.textContent = '▶ Reproducir';
                boton.type = 'button';
                boton.style.cssText = 'cursor:pointer;margin-right:8px;padding:5px;';
                slider = L.DomUtil.create('input', '', panel);
                slider.type = 'range';
                slider.min = 0;
                slider.max = frames.length - 1;
                slider.value = indice;
                slider.style.width = '115px';
                etiqueta = L.DomUtil.create('div', '', panel);
                etiqueta.style.marginTop = '5px';
                etiqueta.textContent = frames[indice].fecha;
                L.DomEvent.disableClickPropagation(panel);
                L.DomEvent.disableScrollPropagation(panel);
                L.DomEvent.on(boton, 'click', function() {
                    if (intervalo !== null) { pausar(); return; }
                    boton.textContent = '⏸ Pausar';
                    intervalo = setInterval(function() {
                        mostrar((indice + 1) % frames.length);
                    }, 900);
                });
                L.DomEvent.on(slider, 'input', function() {
                    pausar();
                    mostrar(Number(slider.value));
                });
                return panel;
            }
        });
        map.addControl(new Control());
        mostrar(indice);
        map.on('unload', pausar);
    })();
    {% endmacro %}
    """)

    def __init__(self, frames):
        super().__init__()
        self._name = "RadarAnimado"
        self.frames_json = json.dumps(frames, ensure_ascii=False).replace("<", "\\u003c")


# =====================================================
# DESCRIPCIÓN DEL CLIMA
# =====================================================

def descripcion_clima(codigo):

    if codigo == 0:
        return "☀️ Despejado"

    elif codigo in [1, 2, 3]:
        return "⛅ Parcialmente nublado"

    elif codigo in [45, 48]:
        return "🌫️ Niebla"

    elif codigo in [51, 53, 55, 56, 57]:
        return "🌦️ Llovizna"

    elif codigo in [61, 63, 65, 66, 67, 80, 81, 82]:
        return "🌧️ Lluvia"

    elif codigo in [71, 73, 75, 77, 85, 86]:
        return "❄️ Nieve"

    elif codigo in [95, 96, 99]:
        return "⛈️ Tormenta"

    return "Condición no disponible"


# =====================================================
# BARRA LATERAL
# =====================================================

with st.sidebar:

    st.header("⚙️ Panel meteorológico")

    ciudad = st.text_input(
        "🔎 Buscar ubicación",
        value="Toluca",
        placeholder="Ejemplo: Madrid"
    )

    st.subheader("🛰️ Capas meteorológicas")
    capa_seleccionada = st.selectbox(
        "Selecciona la capa del mapa",
        ["Ninguna"] + list(CAPAS_METEOROLOGICAS.keys()),
        index=1
    )
    if not OPENWEATHER_API_KEY:
        st.warning("Falta configurar OPENWEATHER_API_KEY para mostrar las capas.")

    mostrar_radar = st.checkbox(
        "🌧️ Mostrar radar de lluvia",
        value=True
    )

    mostrar_marcador = st.checkbox(
        "📍 Mostrar marcador",
        value=True
    )

    zoom = st.slider(
        "Nivel de zoom",
        min_value=3,
        max_value=15,
        value=9
    )

    if st.button("🔄 Actualizar clima"):
        obtener_clima.clear()
        obtener_frames_radar.clear()
        st.rerun()

    st.divider()

    st.caption(
        "Datos meteorológicos: Open-Meteo"
    )

    st.caption(
        "Mapa: OpenStreetMap"
    )

    st.caption(
        "Radar de lluvia: RainViewer"
    )
    st.caption("Capas meteorológicas: OpenWeatherMap")


# =====================================================
# INTERFAZ PRINCIPAL
# =====================================================

if ciudad.strip():

    try:

        lugares = buscar_lugar(ciudad.strip())

        if not lugares:
            st.warning(
                "No se encontraron lugares con ese nombre."
            )
            st.stop()

        opciones = {
            (
                f"{lugar['name']}, "
                f"{lugar.get('admin1', '')}, "
                f"{lugar.get('country', '')} "
                f"({lugar['id']})"
            ): lugar
            for lugar in lugares
        }

        seleccion = st.selectbox(
            "Selecciona la ubicación:",
            list(opciones.keys()),
            format_func=lambda x: x.rsplit(" (", 1)[0]
        )

        lugar = opciones[seleccion]

        lat = lugar["latitude"]
        lon = lugar["longitude"]

        datos = obtener_clima(lat, lon)

        clima = datos["current"]

        st.subheader(
            f"📍 {lugar['name']}, "
            f"{lugar.get('country', '')}"
        )

        st.write(
            descripcion_clima(clima["weather_code"])
        )

        # =============================================
        # MÉTRICAS PRINCIPALES
        # =============================================

        m1, m2, m3, m4 = st.columns(4)

        m1.metric(
            "🌡️ Temperatura",
            f"{clima['temperature_2m']} °C"
        )

        m2.metric(
            "💧 Humedad",
            f"{clima['relative_humidity_2m']} %"
        )

        m3.metric(
            "☁️ Nubosidad",
            f"{clima['cloud_cover']} %"
        )

        m4.metric(
            "🌬️ Viento",
            f"{clima['wind_speed_10m']} km/h"
        )

        st.divider()

        # =============================================
        # MAPA METEOROLÓGICO
        # =============================================

        columna_mapa, columna_datos = st.columns(
            [2.3, 1]
        )

        with columna_mapa:

            st.subheader("🗺️ Mapa meteorológico")

            mapa = folium.Map(
                location=[lat, lon],
                zoom_start=zoom,
                tiles="OpenStreetMap",
                control_scale=True
            )

            # Capas meteorológicas de OpenWeatherMap
            if capa_seleccionada != "Ninguna" and OPENWEATHER_API_KEY:
                identificador = CAPAS_METEOROLOGICAS[capa_seleccionada]
                url_capa = (
                    "https://tile.openweathermap.org/map/"
                    f"{identificador}/{{z}}/{{x}}/{{y}}.png"
                    f"?appid={OPENWEATHER_API_KEY}"
                )
                folium.TileLayer(
                    tiles=url_capa,
                    attr="OpenWeatherMap",
                    name=capa_seleccionada,
                    overlay=True,
                    control=True,
                    opacity=0.75,
                    show=True,
                    max_native_zoom=10,
                    max_zoom=18
                ).add_to(mapa)

            # Radar de lluvia con controles de reproducción y línea de tiempo
            if mostrar_radar:
                try:
                    frames_radar = obtener_frames_radar()
                    if frames_radar:
                        mapa.add_child(RadarAnimado(frames_radar))
                        st.caption(
                            "Radar reciente: " + frames_radar[-1]["fecha"]
                            + " | Usa ▶ Reproducir dentro del mapa."
                        )
                    else:
                        st.info("No hay imágenes de radar disponibles.")
                except (requests.RequestException, KeyError, ValueError) as error:
                    st.warning(f"No se pudo cargar el radar: {error}")

            # Marcador de ubicación
            if mostrar_marcador:

                informacion = (
                    f"<b>{html.escape(lugar['name'])}</b><br>"
                    f"Temperatura: "
                    f"{clima['temperature_2m']} °C<br>"
                    f"Humedad: "
                    f"{clima['relative_humidity_2m']} %<br>"
                    f"Nubosidad: "
                    f"{clima['cloud_cover']} %"
                )

                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(
                        informacion,
                        max_width=250
                    ),
                    tooltip=lugar["name"],
                    icon=folium.Icon(
                        color="blue",
                        icon="info-sign"
                    )
                ).add_to(mapa)

            folium.LayerControl(
                collapsed=False
            ).add_to(mapa)

            st_folium(
                mapa,
                width=None,
                height=520,
                returned_objects=[],
                key=f"mapa_{lugar['id']}_{zoom}_{capa_seleccionada}_{mostrar_radar}"
            )

        # =============================================
        # PANEL DE DATOS
        # =============================================

        with columna_datos:

            st.subheader("🌤️ Condiciones actuales")

            st.metric(
                "🌡️ Sensación térmica",
                f"{clima['apparent_temperature']} °C"
            )

            st.metric(
                "🌧️ Precipitación",
                f"{clima['precipitation']} mm"
            )

            st.metric(
                "☔ Lluvia",
                f"{clima['rain']} mm"
            )

            st.metric(
                "🧭 Dirección del viento",
                f"{clima['wind_direction_10m']}°"
            )

            st.info(
                f"☁️ Cobertura nubosa: "
                f"{clima['cloud_cover']} %"
            )

            st.caption(
                "Hora de los datos: "
                + clima["time"]
            )

        # =============================================
        # PRONÓSTICO POR HORAS
        # =============================================

        st.divider()

        st.subheader("📈 Pronóstico meteorológico")

        hourly = datos["hourly"]

        df = pd.DataFrame({
            "Fecha": pd.to_datetime(hourly["time"]),
            "Temperatura (°C)": hourly["temperature_2m"],
            "Probabilidad de lluvia (%)":
                hourly["precipitation_probability"],
            "Nubosidad (%)": hourly["cloud_cover"],
            "Viento (km/h)": hourly["wind_speed_10m"]
        })

        # Mostrar las próximas 24 horas
        hora_actual = pd.Timestamp(
            clima["time"]
        )

        df = df[
            df["Fecha"] >= hora_actual
        ].head(24)

        grafica1, grafica2 = st.columns(2)

        with grafica1:

            st.write("🌡️ Temperatura")

            st.line_chart(
                df.set_index("Fecha")[
                    ["Temperatura (°C)"]
                ]
            )

        with grafica2:

            st.write("☁️ Nubosidad")

            st.area_chart(
                df.set_index("Fecha")[
                    ["Nubosidad (%)"]
                ]
            )

        st.subheader("🌧️ Probabilidad de lluvia")

        st.bar_chart(
            df.set_index("Fecha")[
                ["Probabilidad de lluvia (%)"]
            ]
        )

        # =============================================
        # INFORMACIÓN GEOGRÁFICA
        # =============================================

        st.divider()

        st.subheader("📍 Información geográfica")

        g1, g2, g3 = st.columns(3)

        g1.metric(
            "Latitud",
            f"{lat:.4f}"
        )

        g2.metric(
            "Longitud",
            f"{lon:.4f}"
        )

        g3.metric(
            "Altitud",
            f"{lugar.get('elevation', 'N/D')} m"
            if lugar.get("elevation") is not None
            else "N/D"
        )

        st.caption(
            "Las condiciones actuales son datos "
            "meteorológicos estimados por Open-Meteo. "
            "El radar animado muestra precipitaciones recientes "
            "donde existe cobertura."
        )

    except requests.RequestException as error:

        st.error(
            f"Error al conectar con la API: {error}"
        )

    except (KeyError, ValueError, TypeError) as error:

        st.error(
            f"Error al procesar los datos: {error}"
        )

else:

    st.info(
        "Escribe una ciudad para comenzar."
    )
