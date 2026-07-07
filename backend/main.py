"""
Backend - Optimización de Rutas de Ambulancias en Lima Metropolitana
Curso: 1ACC0184 - Complejidad Algorítmica (UPC)

Algoritmos: Dijkstra, A*, Bellman-Ford
Fórmula: w = (d / v) * (1 / f) + s
"""

import os
import math
import heapq
import random
import time

import pandas as pd
import matplotlib
matplotlib.use('Agg')

import osmnx as ox
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flasgger import Swagger

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)
FRONTEND_DIR = os.path.join(PROJECT_DIR, 'frontend', 'dist', 'ambulancia-rutas', 'browser')

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)

swagger_config = {
    "headers": [],
    "specs": [{
        "endpoint": "apispec",
        "route": "/apispec.json",
        "rule_filter": lambda rule: rule.rule.startswith("/api"),
        "model_filter": lambda tag: True,
    }],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs"
}

swagger_template = {
    "info": {
        "title": "API de Rutas de Ambulancias — Lima Metropolitana",
        "description": "API REST para optimización de rutas de ambulancias usando algoritmos de grafos (Dijkstra, A*, Bellman-Ford) sobre datos reales de OpenStreetMap.\n\n"
                       "**Fórmula de costo:** w = (d / v) × (1 / f) + s\n\n"
                       "**Curso:** 1ACC0184 - Complejidad Algorítmica (UPC) — 2026-1",
        "version": "1.0.0",
        "contact": {"name": "David Vivar", "email": "u202414424@upc.edu.pe"},
    },
    "tags": [
        {"name": "Grafo", "description": "Generación y consulta del grafo vial"},
        {"name": "Rutas", "description": "Cálculo de rutas óptimas con algoritmos de grafos"},
        {"name": "Sistema", "description": "Estado y salud de la API"},
    ],
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

STATIC_DIR = os.path.join(BACKEND_DIR, 'static')
os.makedirs(STATIC_DIR, exist_ok=True)

_cache = {"lugar": None, "G": None, "nodos_info": None}

PENALIDAD_SEMAFORO = 30
BONUS_OLA_VERDE = -15
UMBRAL_TRAFICO_FLUIDO = 0.85


# ═══════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════

def haversine(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calcular_peso(distancia_m, vel_max_kmh, factor_trafico, tiene_semaforo, modo="normal"):
    vel_ms = max(vel_max_kmh * 1000 / 3600, 0.1)
    factor = max(factor_trafico, 0.1)
    tiempo_base = (distancia_m / vel_ms) * (1.0 / factor)
    s = PENALIDAD_SEMAFORO if tiene_semaforo else 0
    peso = tiempo_base + s
    if modo == "bellman" and factor_trafico > UMBRAL_TRAFICO_FLUIDO:
        peso += BONUS_OLA_VERDE
    return round(peso, 2)


def construir_grafo_ponderado(G, modo="normal"):
    adj = {}
    for u, v, data in G.edges(data=True):
        distancia = data.get('length', 50.0)
        vel_max = data.get('maxspeed', 50)
        if isinstance(vel_max, list):
            vel_max = vel_max[0]
        vel_max_int = int(vel_max) if str(vel_max).isdigit() else 50
        factor_trafico = round(random.uniform(0.2, 1.0), 2)
        tiene_semaforo = random.choice([True, False, False])
        peso = calcular_peso(distancia, vel_max_int, factor_trafico, tiene_semaforo, modo)
        info = {
            'distancia_m': round(float(distancia), 2),
            'vel_max_kmh': vel_max_int,
            'factor_trafico': factor_trafico,
            'tiene_semaforo': tiene_semaforo,
            'peso_segundos': peso,
        }
        adj.setdefault(u, []).append((v, peso, info))
    return adj


def obtener_nombre_calle(G, nodo):
    """Obtiene el nombre de calle más cercano a un nodo."""
    nombres = set()
    for _, _, data in G.edges(nodo, data=True):
        name = data.get('name', None)
        if name:
            if isinstance(name, list):
                nombres.update(name)
            else:
                nombres.add(name)
    # También buscar aristas entrantes
    for _, _, data in G.in_edges(nodo, data=True):
        name = data.get('name', None)
        if name:
            if isinstance(name, list):
                nombres.update(name)
            else:
                nombres.add(name)
    if nombres:
        lista = sorted(nombres)
        return " / ".join(lista[:2])  # Máximo 2 nombres (intersección)
    return None


# ═══════════════════════════════════════════════════════════════
# ALGORITMOS
# ═══════════════════════════════════════════════════════════════

def dijkstra(adj, origen, destino):
    dist = {origen: 0}
    prev = {origen: None}
    visitados = set()
    heap = [(0, origen)]
    while heap:
        d, u = heapq.heappop(heap)
        if u in visitados:
            continue
        visitados.add(u)
        if u == destino:
            break
        for vecino, peso, _ in adj.get(u, []):
            if vecino in visitados:
                continue
            nueva_dist = d + peso
            if nueva_dist < dist.get(vecino, float('inf')):
                dist[vecino] = nueva_dist
                prev[vecino] = u
                heapq.heappush(heap, (nueva_dist, vecino))
    if destino not in prev:
        return None, [], len(visitados)
    camino = []
    nodo = destino
    while nodo is not None:
        camino.append(nodo)
        nodo = prev[nodo]
    camino.reverse()
    return dist[destino], camino, len(visitados)


def a_estrella(adj, origen, destino, nodos_info):
    lat_dest = nodos_info[destino]['y']
    lon_dest = nodos_info[destino]['x']
    VEL_MAX_TEORICA = 80 * 1000 / 3600

    def heuristica(nodo):
        lat = nodos_info[nodo]['y']
        lon = nodos_info[nodo]['x']
        return haversine(lat, lon, lat_dest, lon_dest) / VEL_MAX_TEORICA

    g_score = {origen: 0}
    f_score = {origen: heuristica(origen)}
    prev = {origen: None}
    visitados = set()
    heap = [(f_score[origen], origen)]
    while heap:
        _, u = heapq.heappop(heap)
        if u in visitados:
            continue
        visitados.add(u)
        if u == destino:
            break
        for vecino, peso, _ in adj.get(u, []):
            if vecino in visitados:
                continue
            tentativa_g = g_score[u] + peso
            if tentativa_g < g_score.get(vecino, float('inf')):
                g_score[vecino] = tentativa_g
                f_score[vecino] = tentativa_g + heuristica(vecino)
                prev[vecino] = u
                heapq.heappush(heap, (f_score[vecino], vecino))
    if destino not in prev:
        return None, [], len(visitados)
    camino = []
    nodo = destino
    while nodo is not None:
        camino.append(nodo)
        nodo = prev[nodo]
    camino.reverse()
    return g_score[destino], camino, len(visitados)


def bellman_ford(adj, origen, destino, todos_los_nodos):
    dist = {n: float('inf') for n in todos_los_nodos}
    prev = {n: None for n in todos_los_nodos}
    dist[origen] = 0
    aristas = []
    for u in adj:
        for v, peso, _ in adj[u]:
            aristas.append((u, v, peso))
    num_nodos = len(todos_los_nodos)
    nodos_relajados = set()
    for i in range(num_nodos - 1):
        alguna_mejora = False
        for u, v, peso in aristas:
            if dist[u] + peso < dist[v]:
                dist[v] = dist[u] + peso
                prev[v] = u
                alguna_mejora = True
                nodos_relajados.add(v)
        if not alguna_mejora:
            break
    for u, v, peso in aristas:
        if dist[u] + peso < dist[v]:
            return None, [], len(nodos_relajados), True
    if dist[destino] == float('inf'):
        return None, [], len(nodos_relajados), False
    camino = []
    nodo = destino
    while nodo is not None:
        camino.append(nodo)
        nodo = prev[nodo]
    camino.reverse()
    return dist[destino], camino, len(nodos_relajados), False


# ═══════════════════════════════════════════════════════════════
# GENERACIÓN DE GRAFO
# ═══════════════════════════════════════════════════════════════

def generar_dataset_y_grafo(lugar):
    print(f"📥 Descargando red vial de {lugar}...")
    G = ox.graph_from_place(lugar, network_type='drive')
    nodes_count = len(G.nodes)
    edges_count = len(G.edges)
    print(f"✅ Grafo: {nodes_count} nodos, {edges_count} aristas")

    # Imagen
    nombre_imagen = "grafo_visualizacion.png"
    ruta_imagen = os.path.join(STATIC_DIR, nombre_imagen)
    fig, ax = ox.plot_graph(
        G, bgcolor='#0f172a', node_color='#06b6d4',
        node_size=5, edge_color='#334155', edge_linewidth=0.5,
        show=False, save=True, filepath=ruta_imagen
    )
    print(f"📸 Imagen: {ruta_imagen}")

    # CSV
    registros = []
    for u, v, key, data in G.edges(keys=True, data=True):
        distancia = data.get('length', 50.0)
        vel_max = data.get('maxspeed', 50)
        if isinstance(vel_max, list):
            vel_max = vel_max[0]
        vel_max_int = int(vel_max) if str(vel_max).isdigit() else 50
        factor_trafico = round(random.uniform(0.2, 1.0), 2)
        tiene_semaforo = random.choice([True, False, False])
        registros.append({
            'origen': u, 'destino': v,
            'distancia_m': round(float(distancia), 2),
            'vel_max_kmh': vel_max_int,
            'factor_trafico': factor_trafico,
            'tiene_semaforo': tiene_semaforo,
        })
    df = pd.DataFrame(registros)
    nombre_csv = "dataset_vial.csv"
    ruta_csv = os.path.join(STATIC_DIR, nombre_csv)
    df.to_csv(ruta_csv, index=False)

    # Nodos info con nombres de calles
    nodos_info = {}
    for nodo, data in G.nodes(data=True):
        nodos_info[nodo] = {'x': data['x'], 'y': data['y']}

    _cache["lugar"] = lugar
    _cache["G"] = G
    _cache["nodos_info"] = nodos_info

    return {
        "nodos": nodes_count,
        "aristas": edges_count,
        "total_registros_csv": len(df),
        "url_imagen": f"/static/{nombre_imagen}",
        "url_csv": f"/static/{nombre_csv}",
    }


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.route('/api/health')
def health():
    """Estado de la API
    ---
    tags:
      - Sistema
    responses:
      200:
        description: API funcionando correctamente
        schema:
          type: object
          properties:
            message:
              type: string
              example: "API de Optimización de Rutas de Ambulancias — Lima Metropolitana"
            algoritmos:
              type: array
              items:
                type: string
              example: ["dijkstra", "a_estrella", "bellman_ford"]
    """
    return jsonify({
        "message": "API de Optimización de Rutas de Ambulancias — Lima Metropolitana",
        "algoritmos": ["dijkstra", "a_estrella", "bellman_ford"],
    })


@app.route('/')
def home():
    index_path = os.path.join(FRONTEND_DIR, 'index.html')
    if os.path.exists(index_path):
        return send_from_directory(FRONTEND_DIR, 'index.html')
    return jsonify({"message": "Frontend no compilado. Usa /api/health para verificar la API."})


@app.route('/api/generar_grafo', methods=['POST'])
def generar_grafo_endpoint():
    """Generar grafo vial desde OpenStreetMap
    ---
    tags:
      - Grafo
    description: |
      Descarga la red vial de un distrito de Lima desde OpenStreetMap usando OSMnx,
      construye un grafo dirigido ponderado, genera una imagen de visualización y
      exporta el dataset en CSV.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            lugar:
              type: string
              description: Nombre del distrito (formato OpenStreetMap)
              example: "Lince, Lima, Peru"
              default: "Lince, Lima, Peru"
    responses:
      200:
        description: Grafo generado exitosamente
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: "Grafo procesado: Lince, Lima, Peru"
            data:
              type: object
              properties:
                nodos:
                  type: integer
                  example: 1243
                aristas:
                  type: integer
                  example: 3102
                total_registros_csv:
                  type: integer
                  example: 3102
                url_imagen:
                  type: string
                  example: "/static/grafo_visualizacion.png"
                url_csv:
                  type: string
                  example: "/static/dataset_vial.csv"
      500:
        description: Error al descargar o procesar el grafo
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
              example: "No se encontró el lugar especificado"
    """
    data = request.get_json() or {}
    lugar = data.get('lugar', 'Lince, Lima, Peru')
    try:
        resultado = generar_dataset_y_grafo(lugar)
        return jsonify({"status": "success", "message": f"Grafo procesado: {lugar}", "data": resultado})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/nodos', methods=['GET'])
def listar_nodos():
    """Listar todos los nodos del grafo
    ---
    tags:
      - Grafo
    description: |
      Retorna todos los nodos del grafo cargado con sus coordenadas y nombre de calle.
      Requiere haber generado un grafo previamente con `/api/generar_grafo`.
    responses:
      200:
        description: Lista de nodos
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            total:
              type: integer
              example: 1243
            nodos:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    example: 267834521
                  lat:
                    type: number
                    example: -12.083456
                  lng:
                    type: number
                    example: -77.034521
                  nombre:
                    type: string
                    example: "Av. Arequipa / Calle Roma"
      400:
        description: No hay grafo cargado
    """
    if _cache["G"] is None:
        return jsonify({"status": "error", "message": "No hay grafo cargado."}), 400
    G = _cache["G"]
    nodos = []
    for nodo, data in G.nodes(data=True):
        nombre = obtener_nombre_calle(G, nodo)
        nodos.append({
            "id": nodo,
            "lat": round(data['y'], 6),
            "lng": round(data['x'], 6),
            "nombre": nombre,
        })
    return jsonify({"status": "success", "total": len(nodos), "nodos": nodos})


@app.route('/api/aristas', methods=['GET'])
def listar_aristas():
    """Listar todas las aristas del grafo
    ---
    tags:
      - Grafo
    description: |
      Retorna todas las aristas del grafo con coordenadas de origen y destino
      para dibujar la red vial en el mapa. Requiere grafo cargado.
    responses:
      200:
        description: Lista de aristas con coordenadas
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            aristas:
              type: array
              items:
                type: object
                properties:
                  from:
                    type: array
                    items:
                      type: number
                    example: [-12.083456, -77.034521]
                  to:
                    type: array
                    items:
                      type: number
                    example: [-12.084123, -77.035012]
      400:
        description: No hay grafo cargado
    """
    if _cache["G"] is None:
        return jsonify({"status": "error", "message": "No hay grafo cargado."}), 400
    G = _cache["G"]
    nodos_info = _cache["nodos_info"]
    aristas = []
    for u, v, data in G.edges(data=True):
        aristas.append({
            "from": [nodos_info[u]['y'], nodos_info[u]['x']],
            "to": [nodos_info[v]['y'], nodos_info[v]['x']],
        })
    return jsonify({"status": "success", "aristas": aristas})


@app.route('/api/ruta_optima', methods=['POST'])
def ruta_optima_endpoint():
    """Calcular ruta óptima con los 3 algoritmos
    ---
    tags:
      - Rutas
    description: |
      Ejecuta Dijkstra, A* y Bellman-Ford sobre el grafo cargado para encontrar
      la ruta óptima entre origen y destino. Compara los tres algoritmos y
      devuelve el mejor resultado junto con las coordenadas para visualización.

      **Fórmula de peso:** `w = (d / v) × (1 / f) + s`

      - Dijkstra y A* usan pesos normales (≥ 0)
      - Bellman-Ford aplica bonus de **−15s** en vías con tráfico fluido (ola verde)

      Se usa `random.seed(42)` antes de cada algoritmo para que los tres
      trabajen sobre el mismo grafo ponderado.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - origen
            - destino
          properties:
            origen:
              description: ID del nodo origen (entero) o coordenadas {lat, lng}
              example: 267834521
            destino:
              description: ID del nodo destino (entero) o coordenadas {lat, lng}
              example: 267834530
            algoritmo:
              type: string
              description: Algoritmo preferido (los 3 se ejecutan siempre para comparar)
              enum: [dijkstra, a_estrella, bellman_ford]
              default: dijkstra
    responses:
      200:
        description: Comparación de los 3 algoritmos con rutas calculadas
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            algoritmo_seleccionado:
              type: string
              example: dijkstra
            mejor_algoritmo:
              type: string
              description: Algoritmo que encontró la ruta de menor costo
              example: bellman_ford
            origen:
              type: object
              properties:
                id:
                  type: integer
                  example: 267834521
                lat:
                  type: number
                  example: -12.083456
                lng:
                  type: number
                  example: -77.034521
                nombre:
                  type: string
                  example: "Av. Arequipa / Calle Roma"
            destino:
              type: object
              properties:
                id:
                  type: integer
                  example: 267834530
                lat:
                  type: number
                  example: -12.090123
                lng:
                  type: number
                  example: -77.040567
                nombre:
                  type: string
                  example: "Av. Arenales / Calle Risso"
            resultados:
              type: object
              description: Resultados por cada algoritmo
              properties:
                dijkstra:
                  type: object
                  properties:
                    algoritmo:
                      type: string
                      example: Dijkstra
                    costo_total_segundos:
                      type: number
                      example: 245.67
                    costo_total_minutos:
                      type: number
                      example: 4.09
                    nodos_camino:
                      type: integer
                      example: 18
                    nodos_visitados:
                      type: integer
                      example: 850
                    tiempo_ejecucion_ms:
                      type: number
                      example: 12.34
                    ciclo_negativo:
                      type: boolean
                      example: null
                    coordenadas_ruta:
                      type: array
                      items:
                        type: array
                        items:
                          type: number
                      example: [[-12.083, -77.034], [-12.084, -77.035]]
            complejidades:
              type: object
              properties:
                dijkstra:
                  type: string
                  example: "O((V+E) log V)"
                a_estrella:
                  type: string
                  example: "O((V+E) log V)"
                bellman_ford:
                  type: string
                  example: "O(V·E)"
      400:
        description: No hay grafo cargado o nodo no encontrado
    """
    if _cache["G"] is None:
        return jsonify({"status": "error", "message": "No hay grafo cargado."}), 400

    data = request.get_json() or {}
    origen = data.get('origen')
    destino = data.get('destino')
    algoritmo = data.get('algoritmo', 'dijkstra')

    G = _cache["G"]
    nodos_info = _cache["nodos_info"]

    # Si se pasan coordenadas en vez de IDs
    if isinstance(origen, dict):
        origen = ox.nearest_nodes(G, origen['lng'], origen['lat'])
    if isinstance(destino, dict):
        destino = ox.nearest_nodes(G, destino['lng'], destino['lat'])

    if origen not in G.nodes or destino not in G.nodes:
        return jsonify({"status": "error", "message": "Nodo no encontrado en el grafo."}), 400

    nombres_algo = {
        'dijkstra': 'Dijkstra',
        'a_estrella': 'A* (A-estrella)',
        'bellman_ford': 'Bellman-Ford',
    }
    resultados = {}

    for algo in ['dijkstra', 'a_estrella', 'bellman_ford']:
        random.seed(42)
        modo = "bellman" if algo == "bellman_ford" else "normal"
        adj = construir_grafo_ponderado(G, modo=modo)

        inicio = time.perf_counter()
        if algo == 'dijkstra':
            costo, camino, visitados = dijkstra(adj, origen, destino)
            ciclo_negativo = False
        elif algo == 'a_estrella':
            costo, camino, visitados = a_estrella(adj, origen, destino, nodos_info)
            ciclo_negativo = False
        else:
            costo, camino, visitados, ciclo_negativo = bellman_ford(adj, origen, destino, list(G.nodes))
        tiempo_ms = round((time.perf_counter() - inicio) * 1000, 2)

        # Coordenadas de la ruta para pintar en el mapa
        coords = []
        if camino:
            for nodo in camino:
                nd = nodos_info[nodo]
                coords.append([nd['y'], nd['x']])

        resultados[algo] = {
            "algoritmo": nombres_algo[algo],
            "costo_total_segundos": round(costo, 2) if costo else None,
            "costo_total_minutos": round(costo / 60, 2) if costo else None,
            "nodos_camino": len(camino),
            "nodos_visitados": visitados,
            "tiempo_ejecucion_ms": tiempo_ms,
            "ciclo_negativo": ciclo_negativo if algo == 'bellman_ford' else None,
            "coordenadas_ruta": coords,
        }

    costos = {k: v["costo_total_segundos"] for k, v in resultados.items() if v["costo_total_segundos"] is not None}
    mejor = min(costos, key=costos.get) if costos else None

    # Info de origen y destino
    origen_info = {
        "id": origen,
        "lat": nodos_info[origen]['y'],
        "lng": nodos_info[origen]['x'],
        "nombre": obtener_nombre_calle(G, origen),
    }
    destino_info = {
        "id": destino,
        "lat": nodos_info[destino]['y'],
        "lng": nodos_info[destino]['x'],
        "nombre": obtener_nombre_calle(G, destino),
    }

    return jsonify({
        "status": "success",
        "algoritmo_seleccionado": algoritmo,
        "mejor_algoritmo": mejor,
        "resultados": resultados,
        "origen": origen_info,
        "destino": destino_info,
        "complejidades": {
            "dijkstra": "O((V+E) log V)",
            "a_estrella": "O((V+E) log V)",
            "bellman_ford": "O(V·E)",
        }
    })


@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)


@app.errorhandler(404)
def not_found(e):
    index_path = os.path.join(FRONTEND_DIR, 'index.html')
    if os.path.exists(index_path):
        return send_from_directory(FRONTEND_DIR, 'index.html')
    return jsonify({"error": "Not found"}), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
