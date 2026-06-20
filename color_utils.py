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
BROWN_HUE_RANGE = (15.0, 65.0)
BROWN_MIN_ORANGE_BRIGHTNESS = 210
MUTED_MIN_VIVIDNESS = 90
MIN_THEME_BRIGHTNESS = 150
QUALITY_SCORE_BASELINE = 6000.0
MIN_THEME_RGB_DISTANCE = 100.0
MIN_PRESET_COLOR_DISTANCE = 25.0


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


def brown_hue_penalty(rgb):
    """Return a penalty for muted/dark orange-brown colors; vivid orange is allowed."""
    hue = hue_degrees(rgb)
    min_hue, max_hue = BROWN_HUE_RANGE
    if not min_hue <= hue <= max_hue:
        return 0.0

    missing_brightness = max(0, BROWN_MIN_ORANGE_BRIGHTNESS - max(rgb))
    return missing_brightness / BROWN_MIN_ORANGE_BRIGHTNESS


def muted_color_penalty(rgb):
    """Return a penalty for grayish colors that are not vivid enough for themes."""
    vividness = max(rgb) - min(rgb)
    missing_vividness = max(0, MUTED_MIN_VIVIDNESS - vividness)
    return missing_vividness / MUTED_MIN_VIVIDNESS


def disallowed_theme_color(rgb):
    """Return True for brown or grayish colors that should not be selected."""
    return (
        max(rgb) < MIN_THEME_BRIGHTNESS
        or red_hue_penalty(hue_degrees(rgb)) > 0
        or brown_hue_penalty(rgb) > 0
        or muted_color_penalty(rgb) > 0
    )


def pairwise_palette_distances(palette):
    """Return RGB and hue distances for every color pair in a palette."""
    hues = [hue_degrees(color) for color in palette]
    rgb_distances = [
        rgb_distance(a, b) for i, a in enumerate(palette) for b in palette[i + 1:]
    ]
    hue_distances = [
        circular_hue_distance(a, b)
        for i, a in enumerate(hues)
        for b in hues[i + 1:]
    ]
    return rgb_distances, hue_distances


def palette_quality_score(palette, background=LIGHT_THEME_BACKGROUND):
    """Score a palette using the shared picker/preset quality formula."""
    hues = [hue_degrees(color) for color in palette]
    rgb_distances, hue_distances = pairwise_palette_distances(palette)
    min_rgb = min(rgb_distances, default=0.0)
    avg_rgb = sum(rgb_distances) / len(rgb_distances) if rgb_distances else 0.0
    min_hue = min(hue_distances, default=0.0)
    avg_hue = sum(hue_distances) / len(hue_distances) if hue_distances else 0.0
    brightnesses = [max(color) for color in palette]
    avg_brightness = sum(brightnesses) / len(palette)
    brightness_spread = max(brightnesses) - min(brightnesses)
    avg_vividness = (
        sum(max(color) - min(color) for color in palette) / len(palette)
    )
    contrasts = [contrast_ratio(color, background) for color in palette]
    min_contrast = min(contrasts)
    contrast_spread = max(contrasts) - min_contrast
    red_penalty = sum(red_hue_penalty(hue) for hue in hues)
    brown_penalty = sum(brown_hue_penalty(color) for color in palette)
    muted_penalty = sum(muted_color_penalty(color) for color in palette)
    if len(palette) >= 4:
        rgb_separation_penalty = max(0.0, MIN_THEME_RGB_DISTANCE - min_rgb)
        hue_separation_penalty = max(0.0, 90.0 - min_hue)
        brightness_balance_penalty = max(0.0, brightness_spread - 45.0)
    else:
        rgb_separation_penalty = 0.0
        hue_separation_penalty = 0.0
        brightness_balance_penalty = 0.0
    return (
        QUALITY_SCORE_BASELINE
        + min_rgb * 8.0
        + avg_rgb * 0.4
        + min_hue * 12.0
        + avg_hue * 0.8
        + avg_brightness * 2.0
        + avg_vividness * 1.4
        + min_contrast * 35.0
        - contrast_spread * 60.0
        - red_penalty * 35.0
        - brown_penalty * 1400.0
        - muted_penalty * 1400.0
        - rgb_separation_penalty * 18.0
        - hue_separation_penalty * 24.0
        - brightness_balance_penalty * 50.0
    )


def adjust_hls_to_luminance(hue_degrees_value, saturation, target):
    """Find HLS lightness that produces requested Figma blend luminosity."""
    h = (hue_degrees_value % 360.0) / 360.0
    lo = 0.0
    hi = 1.0
    best = (0, 0, 0)
    best_err = float("inf")

    for _ in range(12):
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
    hue_step=None,
    beam_width=24,
):
    """Generate vivid, separated colors with sufficient, balanced contrast.

    The generator no longer tries to equalize Figma/grayscale luminosity. It
    searches for saturated colors that clear the requested contrast ratio on the
    light background, stay bright/vivid, remain visually distinct from each
    other, and keep their contrast ratios roughly close across the palette.
    It uses beam search instead of a purely greedy pick so later colors can
    recover combinations that have a better final shared palette score.

    When no hue step is supplied, several candidate hue spacings are evaluated
    and the highest-scoring full palette is returned.  This avoids locking user
    generation to a 90-degree tetrad when the app's own scoring formula prefers
    a different spacing for the chosen starting hue.
    """
    base_hue = hue_degrees(base_rgb)

    if hue_step is None:
        candidate_palettes = [
            generate_contrast_palette(
                base_rgb,
                count,
                background,
                min_contrast_ratio,
                float(step),
                beam_width,
            )
            for step in range(60, 151, 15)
        ]
        return max(
            candidate_palettes,
            key=lambda palette: palette_quality_score(palette, background),
        )

    def hls_candidate(hue, lightness, saturation):
        rr, gg, bb = colorsys.hls_to_rgb(
            (hue % 360.0) / 360.0, lightness / 100.0, saturation / 100.0
        )
        return (clamp(rr * 255), clamp(gg * 255), clamp(bb * 255))

    def candidates_for_hue(ideal_hue):
        candidates = []
        seen = set()

        for hue_offset in range(-45, 46, 15):
            hue = ideal_hue + hue_offset

            for saturation in (100, 88, 76):
                for lightness in (28, 36, 44, 52):
                    candidate = hls_candidate(hue, lightness, saturation)
                    candidate_contrast = contrast_ratio(candidate, background)
                    if candidate_contrast < min_contrast_ratio:
                        continue

                    candidate_hue = hue_degrees(candidate)
                    red_penalty = red_hue_penalty(candidate_hue)
                    if red_penalty > 0:
                        continue
                    if disallowed_theme_color(candidate):
                        continue

                    if candidate in seen:
                        continue

                    seen.add(candidate)
                    candidates.append((abs(hue_offset) * 0.8, candidate))

        return candidates

    candidate_groups = [
        (base_hue + i * hue_step, candidates_for_hue(base_hue + i * hue_step))
        for i in range(count)
    ]
    beams = [(0.0, [], 0.0)]
    for ideal_hue, candidates in candidate_groups:
        next_beams = []
        for _score, palette, hue_penalty_total in beams:
            for hue_penalty, candidate in candidates:
                if candidate in palette:
                    continue
                if any(
                    rgb_distance(candidate, selected) < MIN_THEME_RGB_DISTANCE
                    for selected in palette
                ):
                    continue

                next_palette = palette + [candidate]
                next_hue_penalty = hue_penalty_total + hue_penalty
                next_score = (
                    palette_quality_score(next_palette, background)
                    - next_hue_penalty
                )
                next_beams.append((next_score, next_palette, next_hue_penalty))

        if not next_beams:
            for _score, palette, hue_penalty_total in beams:
                for fallback_offset in (90, 180, 270):
                    fallback_candidates = candidates_for_hue(
                        ideal_hue + fallback_offset
                    )
                    for _hue_penalty, candidate in fallback_candidates:
                        if candidate not in palette and all(
                            rgb_distance(candidate, selected) >= MIN_THEME_RGB_DISTANCE
                            for selected in palette
                        ):
                            next_palette = palette + [candidate]
                            next_score = (
                                palette_quality_score(next_palette, background)
                                - hue_penalty_total
                            )
                            next_beams.append(
                                (next_score, next_palette, hue_penalty_total)
                            )
                            break
                    if next_beams:
                        break

        next_beams.sort(key=lambda item: item[0], reverse=True)
        beams = next_beams[:beam_width]

    if not beams:
        return generate_contrast_palette(
            rgb_from_hls_degrees(base_hue + 90),
            count,
            background,
            min_contrast_ratio,
            hue_step,
            beam_width,
        )

    return max(
        beams,
        key=lambda item: palette_quality_score(item[1], background) - item[2],
    )[1]


def rgb_from_hls_degrees(hue, lightness=0.5, saturation=1.0):
    r, g, b = colorsys.hls_to_rgb((hue % 360.0) / 360.0, lightness, saturation)
    return (clamp(r * 255), clamp(g * 255), clamp(b * 255))


def palette_distance(a, b):
    """Return average nearest-color RGB distance between two palettes."""
    return sum(min(rgb_distance(color, other) for other in b) for color in a) / len(a)


def preset_diversity_penalty(palette, selected_palettes, selected_colors=None):
    """Penalize palettes that are too close to any previously selected presets."""
    if not selected_palettes:
        return 0.0

    selected_colors = selected_colors or [
        selected_color
        for _score, selected_palette in selected_palettes
        for selected_color in selected_palette
    ]
    closest_color_distance = min(
        rgb_distance(color, selected_color)
        for color in palette
        for selected_color in selected_colors
    )

    return max(0.0, 130.0 - closest_color_distance) * 45.0


def unique_preset_color(color, selected_colors, palette_colors):
    """Return a vivid preset color that does not repeat earlier presets.

    The function keeps the 100 RGB-distance inside the current preset. Across
    presets it first looks for a color at least MIN_PRESET_COLOR_DISTANCE away
    from every previously selected color; if the finite candidate grid cannot
    satisfy that softer similarity buffer, it still returns the farthest exact
    non-duplicate candidate so preset colors do not repeat.
    """

    def reusable(candidate):
        if candidate in selected_colors or candidate in palette_colors:
            return False
        if disallowed_theme_color(candidate):
            return False
        if contrast_ratio(candidate, LIGHT_THEME_BACKGROUND) < WCAG_AA_NORMAL_TEXT_RATIO:
            return False
        return all(
            rgb_distance(candidate, palette_color) >= MIN_THEME_RGB_DISTANCE
            for palette_color in palette_colors
        )

    def distance_to_selected(candidate):
        if not selected_colors:
            return float("inf")
        return min(
            rgb_distance(candidate, selected_color)
            for selected_color in selected_colors
        )

    if reusable(color) and distance_to_selected(color) >= MIN_PRESET_COLOR_DISTANCE:
        return color

    base_hue = hue_degrees(color)
    best_candidate = color if reusable(color) else None
    best_distance = distance_to_selected(color) if best_candidate is not None else -1.0

    for hue_offset in range(0, 361, 5):
        offsets = (0,) if hue_offset == 0 else (-hue_offset, hue_offset)
        for offset in offsets:
            hue = base_hue + offset
            for saturation in (1.0, 0.94, 0.88, 0.82, 0.76):
                for lightness in (0.24, 0.28, 0.32, 0.36, 0.40, 0.44, 0.48):
                    candidate = rgb_from_hls_degrees(hue, lightness, saturation)
                    if not reusable(candidate):
                        continue

                    selected_distance = distance_to_selected(candidate)
                    if selected_distance >= MIN_PRESET_COLOR_DISTANCE:
                        return candidate
                    if selected_distance > best_distance:
                        best_candidate = candidate
                        best_distance = selected_distance

    return best_candidate


def preset_candidate_pool():
    """Return reusable vivid colors for filling globally unique presets."""
    candidates = []
    seen = set()

    def add_candidate(candidate):
        if candidate in seen:
            return
        if disallowed_theme_color(candidate):
            return
        if contrast_ratio(candidate, LIGHT_THEME_BACKGROUND) < WCAG_AA_NORMAL_TEXT_RATIO:
            return
        seen.add(candidate)
        candidates.append(candidate)

    for hue in range(0, 360, 5):
        for saturation in (1.0, 0.94, 0.88, 0.82, 0.76):
            for lightness in (0.24, 0.28, 0.32, 0.36, 0.40, 0.44, 0.48):
                add_candidate(rgb_from_hls_degrees(hue, lightness, saturation))

    for red in range(0, 256, 16):
        for green in range(0, 256, 16):
            for blue in range(0, 256, 16):
                add_candidate((red, green, blue))

    return candidates


def fill_unique_preset_palette(selected_colors, candidates):
    """Build one extra preset from colors unused by earlier presets."""
    palette = []

    while len(palette) < 4:
        best_candidate = None
        best_score = -1.0
        for candidate in candidates:
            if candidate in selected_colors or candidate in palette:
                continue
            if any(
                rgb_distance(candidate, palette_color) < MIN_THEME_RGB_DISTANCE
                for palette_color in palette
            ):
                continue

            if selected_colors:
                selected_distance = min(
                    rgb_distance(candidate, selected_color)
                    for selected_color in selected_colors
                )
            else:
                selected_distance = MIN_PRESET_COLOR_DISTANCE
            if selected_distance < MIN_PRESET_COLOR_DISTANCE:
                continue

            score = min(selected_distance, MIN_PRESET_COLOR_DISTANCE)
            score += palette_quality_score(palette + [candidate]) * 0.0001
            if score > best_score:
                best_candidate = candidate
                best_score = score

        if best_candidate is None:
            return None

        palette.append(best_candidate)

    return palette


def generate_preset_palettes(limit=12):
    """Compute ready-to-use bright palettes with quality and diversity scores."""
    seed_hues = range(0, 360, 15)
    hue_steps = tuple(float(step) for step in range(60, 151, 15))
    scored_palettes = []
    seen_keys = set()

    for hue in seed_hues:
        for hue_step in hue_steps:
            palette = generate_contrast_palette(
                rgb_from_hls_degrees(hue), hue_step=hue_step
            )
            palette_key = tuple(rgb_to_hex(color) for color in palette)
            if palette_key in seen_keys:
                continue

            seen_keys.add(palette_key)
            score = palette_quality_score(palette)
            scored_palettes.append((score, palette))

    scored_palettes.sort(key=lambda x: x[0], reverse=True)
    selected_palettes = []
    remaining_palettes = scored_palettes.copy()

    while remaining_palettes and len(selected_palettes) < limit:
        best_index = None
        best_adjusted_score = -float("inf")
        selected_colors = [
            color
            for _score, selected in selected_palettes
            for color in selected
        ]

        for index, (score, palette) in enumerate(remaining_palettes):
            adjusted_score = score - preset_diversity_penalty(
                palette, selected_palettes, selected_colors
            )
            if adjusted_score > best_adjusted_score:
                best_index = index
                best_adjusted_score = adjusted_score

        if best_index is None:
            break

        _base_score, palette = remaining_palettes.pop(best_index)
        unique_palette = []
        for color in palette:
            unique_color = unique_preset_color(color, set(selected_colors), unique_palette)
            if unique_color is None:
                unique_palette = []
                break

            unique_palette.append(unique_color)

        if not unique_palette:
            continue
        if min(pairwise_palette_distances(unique_palette)[0]) < MIN_THEME_RGB_DISTANCE:
            continue

        selected_palettes.append(
            (palette_quality_score(unique_palette), unique_palette)
        )

    selected_palettes.sort(key=lambda x: x[0], reverse=True)
    distinct_palettes = []
    distinct_colors = []
    for score, palette in selected_palettes:
        if all(
            rgb_distance(color, selected_color) >= MIN_PRESET_COLOR_DISTANCE
            for color in palette
            for selected_color in distinct_colors
        ):
            distinct_palettes.append((score, palette))
            distinct_colors.extend(palette)

    fill_candidates = preset_candidate_pool()
    while len(distinct_palettes) < limit:
        palette = fill_unique_preset_palette(set(distinct_colors), fill_candidates)
        if palette is None:
            break
        distinct_palettes.append((palette_quality_score(palette), palette))
        distinct_colors.extend(palette)

    distinct_palettes.sort(key=lambda x: x[0], reverse=True)
    return distinct_palettes
