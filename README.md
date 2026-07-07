# 🚑 Optimizador de Rutas de Ambulancias — Lima Metropolitana

**Curso:** 1ACC0184 - Complejidad Algorítmica (UPC)

Aplicación web que optimiza rutas de ambulancias en Lima Metropolitana utilizando
algoritmos de grafos sobre datos reales de OpenStreetMap.

---

## Algoritmos implementados

| Algoritmo | Complejidad | Pesos negativos | Uso en el proyecto |
|-----------|-------------|-----------------|-------------------|
| **Dijkstra** | O((V+E) log V) | ❌ No | Camino más corto clásico |
| **A\*** | O((V+E) log V) | ❌ No | Búsqueda informada con heurística haversine |
| **Bellman-Ford** | O(V·E) | ✅ Sí | Modela bonus por "ola verde" (priorización semafórica) |

### Fórmula de costo por arista

```
w = (d / v) × (1 / f) + s
```

- **d** = distancia del tramo en metros
- **v** = velocidad máxima en m/s
- **f** = factor de tráfico [0.2 = congestionado, 1.0 = libre]
- **s** = penalización por semáforo (30 segundos si tiene, 0 si no)

**Bellman-Ford** aplica un bonus de **−15 segundos** en vías con tráfico fluido
(factor > 0.85), simulando la **"ola verde"** — priorización semafórica V2I
que da paso libre a la ambulancia.

---

## Estructura del proyecto

```
ambulancia-project/
├── backend/                  # Flask + Python
│   ├── main.py               # API REST con los 3 algoritmos
│   ├── requirements.txt      # Dependencias
│   └── test_api.py           # Script de pruebas
│
├── frontend/                 # Angular 22
│   ├── src/app/
│   │   ├── app.component.ts    # Lógica principal
│   │   ├── app.component.html  # Interfaz (3 pasos)
│   │   ├── app.component.css   # Estilos
│   │   ├── osmnx.service.ts    # Servicio HTTP → backend
│   │   ├── app.config.ts       # Configuración Angular
│   │   └── app.routes.ts       # Rutas
│   ├── src/index.html
│   ├── src/main.ts
│   ├── angular.json
│   └── package.json
│
└── README.md
```

---

## Cómo ejecutar

### 1. Backend (Flask)

```bash
cd backend
pip install -r requirements.txt
python main.py
```

El servidor inicia en `http://localhost:5000`.

### 2. Frontend (Angular)

```bash
cd frontend
npm install
ng serve
```

La app abre en `http://localhost:4200`.

### 3. Probar la API

Con el backend corriendo:

```bash
cd backend
pip install requests
python test_api.py
```

---

## Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Info general de la API |
| POST | `/api/generar_grafo` | Descarga grafo de OSM (`{"lugar": "Lince, Lima, Peru"}`) |
| GET | `/api/nodos` | Lista nodos del grafo cargado |
| POST | `/api/ruta_optima` | Calcula ruta (`{"origen": id, "destino": id, "algoritmo": "..."}`) |
| POST | `/api/ruta_por_coordenadas` | Ruta por lat/lng |
| GET | `/static/<filename>` | Descarga archivos generados |

---

## Flujo de la aplicación

1. **Generar Grafo**: El usuario ingresa un distrito de Lima. El backend descarga
   la red vial de OpenStreetMap vía OSMnx y genera un grafo dirigido ponderado.

2. **Definir Ruta**: Se selecciona un nodo origen (ubicación de ambulancia) y
   destino (hospital), más el algoritmo a usar.

3. **Resultados**: Se ejecutan los 3 algoritmos y se comparan: tiempo estimado,
   nodos visitados, tiempo de ejecución. Se genera la imagen de la ruta óptima.
