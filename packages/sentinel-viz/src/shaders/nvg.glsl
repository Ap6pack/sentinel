// Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.
// Night Vision Goggle post-processing shader

uniform sampler2D colorTexture;
in vec2 v_textureCoordinates;

void main() {
  vec4 c = texture(colorTexture, v_textureCoordinates);
  float lum = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
  float noise = fract(sin(dot(v_textureCoordinates, vec2(127.1, 311.7))) * 43758.5);
  float g = lum * 1.4 + (noise - 0.5) * 0.08;
  out_FragColor = vec4(0.0, g, 0.0, 1.0);
}
