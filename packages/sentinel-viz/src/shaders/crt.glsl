
// CRT monitor post-processing shader — scanlines + barrel distortion + vignette

uniform sampler2D colorTexture;
in vec2 v_textureCoordinates;

void main() {
  // Barrel distortion
  vec2 uv = v_textureCoordinates * 2.0 - 1.0;
  float r2 = dot(uv, uv);
  uv *= 1.0 + 0.15 * r2;
  uv = (uv + 1.0) * 0.5;

  if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
    out_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
    return;
  }

  vec4 c = texture(colorTexture, uv);

  // Scanlines
  float scanline = 0.8 + 0.2 * sin(uv.y * 800.0 * 3.14159);
  c.rgb *= scanline;

  // Vignette
  vec2 d = uv - 0.5;
  float vignette = 1.0 - dot(d, d) * 1.5;
  c.rgb *= clamp(vignette, 0.0, 1.0);

  // Slight green phosphor tint
  c.g *= 1.1;

  out_FragColor = c;
}
