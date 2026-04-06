

import {
  Ion,
  Viewer,
  Cesium3DTileset,
  createWorldTerrainAsync,
} from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import { config } from './config.js';

/**
 * Initialise the CesiumJS globe inside the given container element.
 * requestRenderMode is always on — call viewer.scene.requestRender()
 * after every data mutation.
 * @param {string} containerId - DOM element ID for the viewer
 * @returns {Promise<Viewer>}
 */
export async function initGlobe(containerId) {
  Ion.defaultAccessToken = config.cesiumToken;

  const viewer = new Viewer(containerId, {
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    animation: false,
    timeline: false,
    fullscreenButton: false,
    shadows: false,
    requestRenderMode: true,
    maximumRenderTimeChange: 0.5,
  });

  // Google Photorealistic 3D Tiles
  try {
    const tileset = await Cesium3DTileset.fromIonAssetId(2275207);
    viewer.scene.primitives.add(tileset);
    viewer.scene.globe.show = false;
  } catch (e) {
    console.warn('Google 3D Tiles unavailable, falling back to terrain', e);
    viewer.scene.globe.show = true;
    try {
      viewer.terrainProvider = await createWorldTerrainAsync();
    } catch (te) {
      console.warn('World terrain unavailable', te);
    }
  }

  return viewer;
}
