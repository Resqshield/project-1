/**
 * frontend/src/realmap/SimpleDemoMap.jsx
 * =========================================
 * Lightweight MapLibre wrapper shared by CitizenMap and FieldWorkerMap.
 * Deliberately minimal — no admin hierarchy layers, no viewport bbox
 * fetching. Just: an OSM raster basemap, point markers, one route line,
 * and an optional click handler (used for "report a road block").
 */

import { useEffect, useRef, useState, useCallback } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

export default function SimpleDemoMap({
  markers = [],
  route = null,
  routeColor = { core: "#ff8c00", casing: "#ffffff" },
  onMapClick = null,
  clickArmed = false,
  fitTo = null,
  center = [76.9954658, 31.7797769],
  zoom = 11,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRefs = useRef([]);
  const routeColorRef = useRef(routeColor);
  routeColorRef.current = routeColor;
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    if (mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          "osm-base": {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
            maxzoom: 19,
          },
        },
        layers: [
          { id: "background", type: "background", paint: { "background-color": "#0d1117" } },
          { id: "osm-base-layer", type: "raster", source: "osm-base", paint: { "raster-opacity": 0.85 } },
        ],
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
      },
      center,
      zoom,
      minZoom: 3,
      maxZoom: 17,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("load", () => {
      map.addSource("src-route", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "route-casing",
        type: "line",
        source: "src-route",
        paint: { "line-width": 8, "line-color": routeColorRef.current.casing, "line-opacity": 1 },
      });
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "src-route",
        paint: { "line-width": 5, "line-color": routeColorRef.current.core, "line-opacity": 1 },
      });
      setMapReady(true);
    });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Route updates
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const src = mapRef.current.getSource("src-route");
    if (!src) return;
    if (route && route.geometry) {
      src.setData(route);
    } else {
      src.setData({ type: "FeatureCollection", features: [] });
    }
  }, [route, mapReady]);

  // Route color (civilian orange vs. responder teal — set per-page via prop)
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const map = mapRef.current;
    if (map.getLayer("route-casing")) map.setPaintProperty("route-casing", "line-color", routeColor.casing);
    if (map.getLayer("route-line")) map.setPaintProperty("route-line", "line-color", routeColor.core);
  }, [routeColor, mapReady]);

  // Marker updates
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    markerRefs.current.forEach(m => m.remove());
    markerRefs.current = markers.map(m => {
      const el = document.createElement("div");
      el.style.width = "18px";
      el.style.height = "18px";
      el.style.borderRadius = "50%";
      el.style.background = m.color || "#3b82f6";
      el.style.border = "2px solid #fff";
      el.style.boxShadow = "0 0 0 2px rgba(0,0,0,0.4)";
      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([m.lon, m.lat])
        .addTo(mapRef.current);
      if (m.label) {
        marker.setPopup(new maplibregl.Popup({ offset: 12 }).setText(m.label));
      }
      return marker;
    });
  }, [markers, mapReady]);

  // Fit bounds
  useEffect(() => {
    if (!mapReady || !mapRef.current || !fitTo || fitTo.length === 0) return;
    if (fitTo.length === 1) {
      mapRef.current.flyTo({ center: fitTo[0], zoom: 13, duration: 800 });
      return;
    }
    const bounds = fitTo.reduce(
      (b, coord) => b.extend(coord),
      new maplibregl.LngLatBounds(fitTo[0], fitTo[0])
    );
    mapRef.current.fitBounds(bounds, { padding: 60, duration: 800 });
  }, [fitTo, mapReady]);

  // Click-to-report handler
  const handleMapClick = useCallback((e) => {
    if (onMapClick) onMapClick({ lat: e.lngLat.lat, lon: e.lngLat.lng });
  }, [onMapClick]);

  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const map = mapRef.current;
    if (clickArmed && onMapClick) {
      map.on("click", handleMapClick);
      map.getCanvas().style.cursor = "crosshair";
    }
    return () => {
      map.off("click", handleMapClick);
      if (map.getCanvas()) map.getCanvas().style.cursor = "";
    };
  }, [clickArmed, onMapClick, handleMapClick, mapReady]);

  return <div ref={containerRef} style={{ width: "100%", height: "100%" }} />;
}
