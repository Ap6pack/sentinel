// Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.
// Forward-Looking Infrared (thermal) post-processing shader

uniform sampler2D colorTexture;
in vec2 v_textureCoordinates;

vec3 thermalPalette(float t) {
  if (t < 0.25) return mix(vec3(0.0, 0.0, 0.5), vec3(0.0, 0.0, 1.0), t * 4.0);
  if (t < 0.5)  return mix(vec3(0.0, 0.0, 1.0), vec3(0.0, 1.0, 0.0), (t - 0.25) * 4.0);
  if (t < 0.75) return mix(vec3(0.0, 1.0, 0.0), vec3(1.0, 1.0, 0.0), (t - 0.5) * 4.0);
  return mix(vec3(1.0, 1.0, 0.0), vec3(1.0, 0.0, 0.0), (t - 0.75) * 4.0);
}

void main() {
  vec4 c = texture(colorTexture, v_textureCoordinates);
  float lum = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
  out_FragColor = vec4(thermalPalette(lum), 1.0);
}
