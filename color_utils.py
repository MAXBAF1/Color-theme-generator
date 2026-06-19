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


def grayscale_value(rgb):
    """Return the sRGB gray channel that has the same relative luminance."""
    return clamp(linear_to_srgb(luminance(rgb)) * 255)


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


def adjust_hls_to_luminance(hue_degrees_value, saturation, target):
    """Find the HLS lightness that produces the requested WCAG luminance."""
    h = (hue_degrees_value % 360.0) / 360.0
    lo = 0.0
    hi = 1.0
    best = (0, 0, 0)
    best_err = float("inf")

    for _ in range(90):
        mid = (lo + hi) / 2
        rr, gg, bb = colorsys.hls_to_rgb(h, mid, saturation)
        candidate = (clamp(rr * 255), clamp(gg * 255), clamp(bb * 255))
        lum = luminance(candidate)
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


def generate_contrast_palette(base_rgb, count=4):
    """
    Generate colors with identical relative luminance and maximally separated hues.

    The first color is kept exactly as selected. The other colors are placed at
    equal hue intervals around the color wheel and generated with the highest
    available saturation that can still be adjusted to the base luminance.
    """
    target = luminance(base_rgb)
    base_hue = hue_degrees(base_rgb)
    palette = [base_rgb]

    for i in range(1, count):
        hue = base_hue + i * (360.0 / count)
        best = None
        best_score = -float("inf")

        for saturation_step in range(100, 34, -1):
            saturation = saturation_step / 100.0
            candidate, err = adjust_hls_to_luminance(hue, saturation, target)
            min_rgb_distance = min(rgb_distance(candidate, color) for color in palette)
            min_hue_distance = min(
                circular_hue_distance(hue_degrees(candidate), hue_degrees(color))
                for color in palette
            )
            score = min_rgb_distance + min_hue_distance - err * 100_000

            if score > best_score:
                best_score = score
                best = candidate

        palette.append(best)

    return palette
