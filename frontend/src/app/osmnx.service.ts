import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class OsmnxService {
  private baseUrl = '';

  constructor(private http: HttpClient) {}

  generarGrafo(lugar: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/api/generar_grafo`, { lugar });
  }

  listarNodos(): Observable<any> {
    return this.http.get(`${this.baseUrl}/api/nodos`);
  }

  listarAristas(): Observable<any> {
    return this.http.get(`${this.baseUrl}/api/aristas`);
  }

  calcularRuta(origen: number, destino: number, algoritmo: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/api/ruta_optima`, { origen, destino, algoritmo });
  }

  getUrlAbsoluta(urlRelativa: string): string {
    return `${this.baseUrl}${urlRelativa}`;
  }
}
