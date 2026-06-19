import colorsys
import math


def clamp(value, low=0, high=255):
    return max(low, min(high, int(round(value))))


def srgb_to_linear(c):
    c /= 255.0
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1 / 2.4)) - 0.055


def luminance(rgb):
    r, g, b = rgb
    r = srgb_to_linear(r)
    g = srgb_to_linear(g)
    b = srgb_to_linear(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


LIGHT_THEME_BACKGROUND = (252, 252, 252)
WCAG_AA_NORMAL_TEXT_RATIO = 4.5
RED_HUE_CENTER = 0.0
RED_HUE_AVOID_DEGREES = 35.0


def figma_luminosity(rgb):
    """Return the non-linear RGB luminosity used by W3C/Figma blend modes."""
    r, g, b = [x / 255.0 for x in rgb]
    return 0.3 * r + 0.59 * g + 0.11 * b


def grayscale_value(rgb):
    """Return the gray channel produced by Figma-style blend-mode luminosity."""
    return clamp(figma_luminosity(rgb) * 255)


def contrast_ratio(foreground, background):
    """Return WCAG contrast ratio for two RGB colors."""
    lum1 = luminance(foreground)
    lum2 = luminance(background)
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def max_luminance_for_contrast(background, min_ratio):
    """Highest foreground luminance that reaches min_ratio on a light background."""
    background_lum = luminance(background)
    return max(0.0, ((background_lum + 0.05) / min_ratio) - 0.05)


def readable_target_luminance(
    base_rgb,
    background=LIGHT_THEME_BACKGROUND,
    min_ratio=WCAG_AA_NORMAL_TEXT_RATIO,
):
    """Legacy WCAG relative-luminance ceiling for contrast calculations."""
    return min(luminance(base_rgb), max_luminance_for_contrast(background, min_ratio))


def rgb_to_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def hue_degrees(rgb):
    r, g, b = [x / 255.0 for x in rgb]
    h, _l, _s = colorsys.rgb_to_hls(r, g, b)
    return h * 360.0


def circular_hue_distance(a, b):
    diff = abs(a - b) % 360.0
    return min(diff, 360.0 - diff)


def rgb_distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def red_hue_penalty(hue):
    """Return a penalty for explicit red hues used for errors in UI."""
    distance = circular_hue_distance(hue % 360.0, RED_HUE_CENTER)
    return max(0.0, RED_HUE_AVOID_DEGREES - distance)


def palette_quality_score(palette, background=LIGHT_THEME_BACKGROUND):
    hues = [hue_degrees(color) for color in palette]
    min_rgb = min(
        rgb_distance(a, b) for i, a in enumerate(palette) for b in palette[i + 1:]
    )
    min_hue = min(
        circular_hue_distance(a, b)
        for i, a in enumerate(hues)
        for b in hues[i + 1:]
    )
    avg_brightness = sum(max(color) for color in palette) / len(palette)
    min_contrast = min(contrast_ratio(color, background) for color in palette)
    red_penalty = sum(red_hue_penalty(hue) for hue in hues)
    return (
        min_rgb
        + min_hue * 2.0
        + avg_brightness * 2.5
        + min_contrast * 20.0
        - red_penalty * 35.0
    )


def adjust_hls_to_luminance(hue_degrees_value, saturation, target):
    """Find HLS lightness that produces requested Figma blend luminosity."""
    h = (hue_degrees_value % 360.0) / 360.0
    lo = 0.0
    hi = 1.0
    best = (0, 0, 0)
    best_err = float("inf")

    for _ in range(32):
        mid = (lo + hi) / 2
        rr, gg, bb = colorsys.hls_to_rgb(h, mid, saturation)
        candidate = (clamp(rr * 255), clamp(gg * 255), clamp(bb * 255))
        lum = figma_luminosity(candidate)
        err = abs(lum - target)

        if err < best_err:
            best_err = err
            best = candidate

        if lum < target:
            lo = mid
        else:
            hi = mid

    return best, best_err


def adjust_to_luminance(rgb, target):
    r, g, b = [x / 255.0 for x in rgb]
    h, _l, s = colorsys.rgb_to_hls(r, g, b)
    adjusted, _err = adjust_hls_to_luminance(h * 360.0, s, target)
    return adjusted


def generate_contrast_palette(
    base_rgb,
    count=4,
    background=LIGHT_THEME_BACKGROUND,
    min_contrast_ratio=WCAG_AA_NORMAL_TEXT_RATIO,
):
    """
    Generate bright colors with identical Figma-style grayscale and separated hues.

    The selected base color defines the first hue neighborhood. The shared blend-mode
    luminosity is darkened when needed so every color reaches the requested
    WCAG contrast ratio against the light-theme background. The other colors
    search around equal hue intervals and prefer high channel brightness, high
    saturation, hue separation, and RGB distance while preserving grayscale.
    """
    base_target = figma_luminosity(base_rgb)
    base_hue = hue_degrees(base_rgb)

    def choose_bright_candidate(ideal_hue, target, palette):
        best = None
        best_score = -float("inf")

        for hue_offset in range(-45, 46, 15):
            hue = ideal_hue + hue_offset

            for saturation_step in range(100, 34, -10):
                saturation = saturation_step / 100.0
                candidate, err = adjust_hls_to_luminance(hue, saturation, target)
                brightness = max(candidate)
                candidate_contrast = contrast_ratio(candidate, background)
                hue_penalty = abs(hue_offset) * 0.8
                red_penalty = red_hue_penalty(hue_degrees(candidate))
                if red_penalty > 0:
                    continue

                if palette:
                    min_rgb_distance = min(
                        rgb_distance(candidate, color) for color in palette
                    )
                    min_hue_distance = min(
                        circular_hue_distance(
                            hue_degrees(candidate), hue_degrees(color)
                        )
                        for color in palette
                    )
                else:
                    min_rgb_distance = 0.0
                    min_hue_distance = 0.0

                hue_collision_penalty = max(0.0, 60.0 - min_hue_distance) * 10.0
                score = (
                    min_rgb_distance
                    + min_hue_distance * 1.0
                    + brightness * 2.5
                    + candidate_contrast * 12.0
                    - hue_penalty
                    - hue_collision_penalty
                    - err * 100_000
                )

                if score > best_score:
                    best_score = score
                    best = candidate

        return best

    def build_palette(target):
        palette = [choose_bright_candidate(base_hue, target, [])]

        for i in range(1, count):
            ideal_hue = base_hue + i * (360.0 / count)
            palette.append(choose_bright_candidate(ideal_hue, target, palette))

        return palette

    def passes_contrast(palette):
        return min(
            contrast_ratio(color, background) for color in palette
        ) >= min_contrast_ratio

    brightest_palette = build_palette(base_target)
    if passes_contrast(brightest_palette):
        return brightest_palette

    low = 0.0
    high = base_target
    best_palette = build_palette(low)
    for _ in range(10):
        target = (low + high) / 2.0
        palette = build_palette(target)

        if passes_contrast(palette):
            low = target
            best_palette = palette
        else:
            high = target

    return best_palette


def rgb_from_hls_degrees(hue, lightness=0.5, saturation=1.0):
    r, g, b = colorsys.hls_to_rgb((hue % 360.0) / 360.0, lightness, saturation)
    return (clamp(r * 255), clamp(g * 255), clamp(b * 255))


def generate_preset_palettes(limit=5):
    """Compute ready-to-use bright palettes while avoiding explicit red hues."""
    seed_hues = (35, 55, 75, 100, 135, 165, 200, 230, 260, 290, 320)
    scored_palettes = []

    for hue in seed_hues:
        palette = generate_contrast_palette(rgb_from_hls_degrees(hue))
        score = palette_quality_score(palette)
        scored_palettes.append((score, palette))

    scored_palettes.sort(key=lambda item: item[0], reverse=True)

    unique_palettes = []
    for _score, palette in scored_palettes:
        palette_key = tuple(rgb_to_hex(color) for color in palette)
        existing_keys = {
            tuple(rgb_to_hex(color) for color in existing)
            for existing in unique_palettes
        }
        if palette_key not in existing_keys:
            unique_palettes.append(palette)
        if len(unique_palettes) == limit:
            break

    return unique_palettes
