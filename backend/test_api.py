"""
Tests para la API de Optimización de Rutas de Ambulancias.
Uso: python test_api.py
Requiere: pip install requests
"""

import requests
import json
import time

BASE_URL = 'http://localhost:5000'


def test_home():
    """Test 1: Verificar que el servidor responde."""
    print("=" * 60)
    print("TEST 1: GET / — Estado del servidor")
    print("=" * 60)
    r = requests.get(f'{BASE_URL}/')
    assert r.status_code == 200, f"ERROR: Status {r.status_code}"
    data = r.json()
    assert "algoritmos" in data, "ERROR: Falta campo 'algoritmos'"
    print(f"✅ Servidor activo. Algoritmos: {data['algoritmos']}")
    print()


def test_generar_grafo():
    """Test 2: Generar grafo de Lince."""
    print("=" * 60)
    print("TEST 2: POST /api/generar_grafo — Descargar red vial")
    print("=" * 60)
    print("⏳ Descargando mapa (puede tomar 10-30s)...")

    r = requests.post(f'{BASE_URL}/api/generar_grafo',
                      json={"lugar": "Lince, Lima, Peru"})
    assert r.status_code == 200, f"ERROR: Status {r.status_code}"
    data = r.json()
    assert data["status"] == "success", f"ERROR: {data.get('message')}"
    print(f"✅ Grafo generado:")
    print(f"   Nodos: {data['data']['nodos']}")
    print(f"   Aristas: {data['data']['aristas']}")
    print(f"   CSV: {data['data']['url_csv']}")
    print()
    return data


def test_listar_nodos():
    """Test 3: Obtener lista de nodos."""
    print("=" * 60)
    print("TEST 3: GET /api/nodos — Listar nodos del grafo")
    print("=" * 60)
    r = requests.get(f'{BASE_URL}/api/nodos')
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    nodos = data["nodos"]
    print(f"✅ {data['total']} nodos disponibles")
    print(f"   Primeros 3: {nodos[:3]}")
    print()
    return nodos


def test_ruta_optima(nodos):
    """Test 4: Calcular ruta óptima con cada algoritmo."""
    origen = nodos[0]["id"]
    destino = nodos[len(nodos) // 2]["id"]

    for algo in ["dijkstra", "a_estrella", "bellman_ford"]:
        print("=" * 60)
        print(f"TEST 4.{algo}: POST /api/ruta_optima — {algo.upper()}")
        print("=" * 60)

        r = requests.post(f'{BASE_URL}/api/ruta_optima', json={
            "origen": origen,
            "destino": destino,
            "algoritmo": algo,
        })
        assert r.status_code == 200, f"ERROR: Status {r.status_code}"
        data = r.json()
        assert data["status"] == "success", f"ERROR: {data.get('message')}"

        res = data["resultados"][algo]
        print(f"✅ {res['algoritmo']}:")
        print(f"   Costo: {res['costo_total_segundos']}s ({res['costo_total_minutos']} min)")
        print(f"   Nodos en ruta: {res['nodos_camino']}")
        print(f"   Nodos visitados: {res['nodos_visitados']}")
        print(f"   Tiempo ejecución: {res['tiempo_ejecucion_ms']}ms")
        if algo == "bellman_ford":
            print(f"   Ciclo negativo: {res['ciclo_negativo']}")
        print()

    print(f"🏆 Mejor algoritmo: {data['mejor_algoritmo']}")
    print()


if __name__ == '__main__':
    print("\n🚑 TESTS — API de Rutas de Ambulancias\n")
    test_home()
    test_generar_grafo()
    nodos = test_listar_nodos()
    test_ruta_optima(nodos)
    print("✅ TODOS LOS TESTS PASARON\n")
