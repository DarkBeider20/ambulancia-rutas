import { Component, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { OsmnxService } from './osmnx.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css'],
})
export class AppComponent {
  lugarInput = 'Lince, Lima, Peru';
  loadingGrafo = false;
  grafoData: any = null;
  grafoError = '';

  nodos: any[] = [];
  origenNodo: any = null;
  destinoNodo: any = null;
  seleccionandoTipo: 'origen' | 'destino' = 'origen';

  algoritmoSeleccionado = 'a_estrella';
  loadingRuta = false;
  rutaData: any = null;
  rutaError = '';

  paso = 1;

  constructor(
    private osmnxService: OsmnxService,
    private cdr: ChangeDetectorRef,
  ) {}

  // ═══════════════════════════════════════════════════════════
  // PASO 1
  // ═══════════════════════════════════════════════════════════
  procesarMapa() {
    this.loadingGrafo = true;
    this.grafoData = null;
    this.grafoError = '';
    this.nodos = [];
    this.rutaData = null;
    this.origenNodo = null;
    this.destinoNodo = null;
    this.cdr.detectChanges();

    this.osmnxService.generarGrafo(this.lugarInput).subscribe({
      next: (res) => {
        if (res.status === 'success') {
          this.grafoData = {
            ...res.data,
            url_imagen: this.osmnxService.getUrlAbsoluta(res.data.url_imagen),
            url_csv: this.osmnxService.getUrlAbsoluta(res.data.url_csv),
          };
          this.cargarNodos();
        }
        this.loadingGrafo = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.grafoError = 'Error al conectar con el backend. Intenta de nuevo en unos segundos.';
        this.loadingGrafo = false;
        this.cdr.detectChanges();
      },
    });
  }

  cargarNodos() {
    this.osmnxService.listarNodos().subscribe({
      next: (res) => {
        if (res.status === 'success') {
          this.nodos = res.nodos;
          this.paso = 2;
          this.cdr.detectChanges();
          setTimeout(() => this.inicializarMapa('mapa-leaflet'), 150);
        }
      },
    });
  }

  // ═══════════════════════════════════════════════════════════
  // MAPA LEAFLET
  // ═══════════════════════════════════════════════════════════
  inicializarMapa(containerId: string, soloRuta = false) {
    const L = (window as any).L;
    if (!L) return;

    // Limpiar mapa anterior en ese container
    const existing = (window as any)[`_mapa_${containerId}`];
    if (existing) existing.remove();

    const lats = this.nodos.map((n: any) => n.lat);
    const lngs = this.nodos.map((n: any) => n.lng);
    const centerLat = (Math.min(...lats) + Math.max(...lats)) / 2;
    const centerLng = (Math.min(...lngs) + Math.max(...lngs)) / 2;

    const map = L.map(containerId).setView([centerLat, centerLng], 15);
    (window as any)[`_mapa_${containerId}`] = map;

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap © CARTO',
      maxZoom: 19,
    }).addTo(map);

    // Dibujar aristas del grafo
    this.osmnxService.listarAristas().subscribe({
      next: (res: any) => {
        if (res.status === 'success') {
          res.aristas.forEach((a: any) => {
            L.polyline([a.from, a.to], { color: '#334155', weight: 1, opacity: 0.4 }).addTo(map);
          });
        }
      },
    });

    if (soloRuta && this.rutaData) {
      this.dibujarRutaResultado(map, L);
    } else {
      this.dibujarNodosClickeables(map, L);
    }
  }

  dibujarNodosClickeables(map: any, L: any) {
    const self = this;
    this.nodos.forEach((nodo: any) => {
      const circle = L.circleMarker([nodo.lat, nodo.lng], {
        radius: 4, color: '#06b6d4', fillColor: '#06b6d4', fillOpacity: 0.6, weight: 1,
      }).addTo(map);
      circle.bindTooltip(nodo.nombre || `Nodo ${nodo.id}`, { className: 'nodo-tooltip' });
      circle.on('click', () => self.seleccionarNodo(nodo, map, L));
    });
  }

  seleccionarNodo(nodo: any, map: any, L: any) {
    const key = this.seleccionandoTipo === 'origen' ? '_marcadorOrigen' : '_marcadorDestino';
    if ((window as any)[key]) map.removeLayer((window as any)[key]);

    if (this.seleccionandoTipo === 'origen') {
      this.origenNodo = nodo;
      const m = L.marker([nodo.lat, nodo.lng], {
        icon: L.divIcon({ className: 'custom-marker', html: '🟢', iconSize: [24,24], iconAnchor: [12,12] }),
      }).addTo(map).bindPopup(`<b>ORIGEN</b><br>${nodo.nombre || nodo.id}`).openPopup();
      (window as any)._marcadorOrigen = m;
      this.seleccionandoTipo = 'destino';
    } else {
      this.destinoNodo = nodo;
      const m = L.marker([nodo.lat, nodo.lng], {
        icon: L.divIcon({ className: 'custom-marker', html: '🔴', iconSize: [24,24], iconAnchor: [12,12] }),
      }).addTo(map).bindPopup(`<b>DESTINO</b><br>${nodo.nombre || nodo.id}`).openPopup();
      (window as any)._marcadorDestino = m;
      this.seleccionandoTipo = 'origen';
    }
    this.cdr.detectChanges();
  }

  resetSeleccion() {
    const map = (window as any)['_mapa_mapa-leaflet'];
    if ((window as any)._marcadorOrigen) map?.removeLayer((window as any)._marcadorOrigen);
    if ((window as any)._marcadorDestino) map?.removeLayer((window as any)._marcadorDestino);
    this.origenNodo = null;
    this.destinoNodo = null;
    this.seleccionandoTipo = 'origen';
    this.rutaData = null;
    this.cdr.detectChanges();
  }

  // ═══════════════════════════════════════════════════════════
  // CALCULAR RUTA
  // ═══════════════════════════════════════════════════════════
  calcularRuta() {
    if (!this.origenNodo || !this.destinoNodo) {
      this.rutaError = 'Selecciona origen y destino en el mapa.';
      this.cdr.detectChanges();
      return;
    }
    this.loadingRuta = true;
    this.rutaData = null;
    this.rutaError = '';
    this.cdr.detectChanges();

    this.osmnxService.calcularRuta(
      this.origenNodo.id, this.destinoNodo.id, this.algoritmoSeleccionado
    ).subscribe({
      next: (res) => {
        if (res.status === 'success') {
          this.rutaData = res;
          this.paso = 3;
          this.loadingRuta = false;
          this.cdr.detectChanges();
          setTimeout(() => this.inicializarMapa('mapa-resultado', true), 150);
        }
      },
      error: () => {
        this.rutaError = 'Error al calcular la ruta.';
        this.loadingRuta = false;
        this.cdr.detectChanges();
      },
    });
  }

  // ═══════════════════════════════════════════════════════════
  // DIBUJAR RUTA EN MAPA DE RESULTADOS
  // ═══════════════════════════════════════════════════════════
  dibujarRutaResultado(map: any, L: any) {
    const data = this.rutaData;
    const mejor = data.mejor_algoritmo;
    const coordsMejor = data.resultados[mejor]?.coordenadas_ruta;

    if (!coordsMejor || coordsMejor.length === 0) return;

    // Dibujar ruta principal gruesa y brillante
    const color = this.getColorAlgoritmo(mejor);
    L.polyline(coordsMejor, { color, weight: 6, opacity: 0.95 }).addTo(map);

    // Glow effect
    L.polyline(coordsMejor, { color, weight: 12, opacity: 0.2 }).addTo(map);

    // Nodos intermedios de la ruta
    coordsMejor.forEach((coord: any, i: number) => {
      if (i === 0 || i === coordsMejor.length - 1) return;
      L.circleMarker(coord, {
        radius: 3, color, fillColor: color, fillOpacity: 0.8, weight: 1,
      }).addTo(map);
    });

    // Marcador ORIGEN
    L.marker(coordsMejor[0], {
      icon: L.divIcon({
        className: 'marker-resultado',
        html: '<div class="marker-pin marker-green">🚑</div>',
        iconSize: [32, 32], iconAnchor: [16, 32],
      }),
    }).addTo(map).bindPopup(
      `<b>ORIGEN</b><br>${data.origen.nombre || data.origen.id}`
    );

    // Marcador DESTINO
    L.marker(coordsMejor[coordsMejor.length - 1], {
      icon: L.divIcon({
        className: 'marker-resultado',
        html: '<div class="marker-pin marker-red">🏥</div>',
        iconSize: [32, 32], iconAnchor: [16, 32],
      }),
    }).addTo(map).bindPopup(
      `<b>DESTINO</b><br>${data.destino.nombre || data.destino.id}`
    );

    // Zoom a la ruta
    map.fitBounds(L.latLngBounds(coordsMejor), { padding: [50, 50] });
  }

  // ═══════════════════════════════════════════════════════════
  // HELPERS
  // ═══════════════════════════════════════════════════════════
  volverAlMapa() {
    this.rutaData = null;
    this.paso = 2;
    this.cdr.detectChanges();
    setTimeout(() => this.inicializarMapa('mapa-leaflet'), 150);
  }

  getColorAlgoritmo(key: string): string {
    const colores: any = { dijkstra: '#3b82f6', a_estrella: '#f59e0b', bellman_ford: '#22c55e' };
    return colores[key] || '#f59e0b';
  }

  getMejorResultado(): any {
    if (!this.rutaData) return null;
    return this.rutaData.resultados[this.rutaData.mejor_algoritmo];
  }

  getAlgoritmos() {
    return [
      { key: 'dijkstra', nombre: 'Dijkstra', desc: 'Camino más corto clásico', complejidad: 'O((V+E) log V)' },
      { key: 'a_estrella', nombre: 'A*', desc: 'Heurística haversine', complejidad: 'O((V+E) log V)' },
      { key: 'bellman_ford', nombre: 'Bellman-Ford', desc: 'Pesos negativos (ola verde)', complejidad: 'O(V·E)' },
    ];
  }

  getResultadosArray(): any[] {
    if (!this.rutaData?.resultados) return [];
    return Object.entries(this.rutaData.resultados).map(([key, val]: [string, any]) => ({
      key, ...val,
      esMejor: key === this.rutaData.mejor_algoritmo,
    }));
  }

  irAPaso(p: number) {
    this.paso = p;
    this.cdr.detectChanges();
    if (p === 2 && this.nodos.length > 0) {
      setTimeout(() => this.inicializarMapa('mapa-leaflet'), 150);
    }
  }
}
