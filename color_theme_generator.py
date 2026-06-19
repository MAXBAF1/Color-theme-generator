import sys
from itertools import combinations

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QLabel,
    QColorDialog,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QScrollArea,
    QSizePolicy,
)

from color_utils import (
    LIGHT_THEME_BACKGROUND,
    WCAG_AA_NORMAL_TEXT_RATIO,
    contrast_ratio,
    generate_contrast_palette,
    generate_preset_palettes,
    figma_luminosity,
    grayscale_value,
    hue_degrees,
    rgb_distance,
    rgb_to_hex,
)


def selectable_label(text=""):
    label = QLabel(text)
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    return label


class ColorRow(QWidget):
    def __init__(self, title):
        super().__init__()
        layout = QHBoxLayout(self)
        self.button = QPushButton(title)
        self.color_preview = QFrame()
        self.color_preview.setFixedSize(140, 60)
        self.gray_preview = QFrame()
        self.gray_preview.setFixedSize(140, 60)
        self.label = selectable_label()

        layout.addWidget(self.button)
        layout.addWidget(self.color_preview)
        layout.addWidget(self.gray_preview)
        layout.addWidget(self.label)


class PresetRow(QWidget):
    def __init__(self, title, score, palette):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)
        layout.addWidget(selectable_label(f"{title} · score {score:.1f}"))

        colors_layout = QHBoxLayout()
        colors_layout.setContentsMargins(0, 0, 0, 0)
        colors_layout.setSpacing(10)
        layout.addLayout(colors_layout)

        for color in palette:
            color_widget = QWidget()
            color_widget.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
            )
            color_layout = QHBoxLayout(color_widget)
            color_layout.setContentsMargins(0, 0, 0, 0)
            color_layout.setSpacing(4)
            swatch = QFrame()
            swatch.setFixedSize(70, 60)
            swatch.setStyleSheet(f"background:{rgb_to_hex(color)};")
            color_layout.addWidget(swatch)

            lum = figma_luminosity(color)
            gray = grayscale_value(color)
            gray_hex = f"#{gray:02X}{gray:02X}{gray:02X}"
            description = selectable_label(
                f"HEX: {rgb_to_hex(color)}\n"
                f"Hue: {hue_degrees(color):.1f}°\n"
                f"Figma gray: {gray_hex} ({lum:.12f})\n"
                f"Contrast on #FCFCFC: "
                f"{contrast_ratio(color, LIGHT_THEME_BACKGROUND):.2f}:1"
            )
            color_layout.addWidget(description)
            colors_layout.addWidget(color_widget)

        colors_layout.addStretch(1)


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("High Contrast Theme Colors")
        self.resize(1920, 900)

        self.original_colors = [
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0),
        ]
        self.colors = self.original_colors.copy()

        main_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        scroll_area.setWidget(content)
        main_layout.addWidget(scroll_area)

        self.generate_button = QPushButton(
            "Сгенерировать 4 максимально контрастных цвета от Цвета 1"
        )
        self.generate_button.clicked.connect(self.generate_from_first_color)
        layout.addWidget(self.generate_button)

        self.info_label = selectable_label()
        layout.addWidget(self.info_label)

        self.rows = []
        for i in range(4):
            row = ColorRow(f"Цвет {i + 1}")
            row.button.clicked.connect(lambda _, idx=i: self.open_picker(idx))
            layout.addWidget(row)
            self.rows.append(row)

        layout.addWidget(selectable_label("Готовые пресеты / палитры:"))
        self.preset_rows = []
        for preset_index, (score, palette) in enumerate(
            generate_preset_palettes(), start=1
        ):
            preset_row = PresetRow(f"Пресет {preset_index}", score, palette)
            layout.addWidget(preset_row)
            self.preset_rows.append(preset_row)

        self.active_dialog = None
        self.active_index = None
        self.pending_recalculate_index = None
        self.recalculate_timer = QTimer(self)
        self.recalculate_timer.setSingleShot(True)
        self.recalculate_timer.timeout.connect(self.flush_pending_recalculate)
        self.generate_from_first_color()

    def open_picker(self, idx):
        dialog = QColorDialog(self)
        dialog.setCurrentColor(QColor(*self.original_colors[idx]))
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)
        dialog.currentColorChanged.connect(
            lambda color, index=idx: self.on_color_changed(index, color)
        )
        dialog.show()
        self.active_dialog = dialog
        self.active_index = idx

    def on_color_changed(self, index, color):
        rgb = (color.red(), color.green(), color.blue())
        self.original_colors[index] = rgb

        self.pending_recalculate_index = index
        if not self.recalculate_timer.isActive():
            self.apply_pending_recalculate()
            self.recalculate_timer.start(33)

    def flush_pending_recalculate(self):
        if self.pending_recalculate_index is not None:
            self.apply_pending_recalculate()
            self.recalculate_timer.start(33)

    def apply_pending_recalculate(self):
        index = self.pending_recalculate_index
        self.pending_recalculate_index = None

        if index == 0:
            self.generate_from_first_color()
        elif index is not None:
            self.recalculate_manual_palette()

    def generate_from_first_color(self):
        self.colors = generate_contrast_palette(self.original_colors[0], 4)
        self.original_colors = self.colors.copy()
        self.update_ui()

    def recalculate_manual_palette(self):
        self.colors = self.original_colors.copy()
        self.update_ui()

    def update_ui(self):
        gray_values = [grayscale_value(color) for color in self.colors]
        min_gray = min(gray_values)
        max_gray = max(gray_values)

        distances = [
            rgb_distance(self.colors[a], self.colors[b])
            for a, b in combinations(range(4), 2)
        ]
        bg_hex = rgb_to_hex(LIGHT_THEME_BACKGROUND)
        min_bg_contrast = min(
            contrast_ratio(color, LIGHT_THEME_BACKGROUND) for color in self.colors
        )
        self.info_label.setText(
            "Ч/б значение больше не участвует в подборе: "
            "главные критерии — достаточный и близкий контраст с фоном, "
            "яркость и различимость цветов. "
            f"Фон светлой темы: {bg_hex}. "
            f"Минимальный контраст с фоном: {min_bg_contrast:.2f}:1 "
            f"(цель WCAG AA: {WCAG_AA_NORMAL_TEXT_RATIO:.1f}:1). "
            f"Диапазон ч/б справочно: #{min_gray:02X}{min_gray:02X}{min_gray:02X}–"
            f"#{max_gray:02X}{max_gray:02X}{max_gray:02X}. "
            f"Минимальная RGB-дистанция между темами: {min(distances):.1f}."
        )

        for i, rgb in enumerate(self.colors):
            lum = figma_luminosity(rgb)
            color_gray = grayscale_value(rgb)
            color_gray_hex = f"#{color_gray:02X}{color_gray:02X}{color_gray:02X}"
            self.rows[i].color_preview.setStyleSheet(f"background:{rgb_to_hex(rgb)};")
            self.rows[i].gray_preview.setStyleSheet(f"background:{color_gray_hex};")
            self.rows[i].label.setText(
                f"HEX: {rgb_to_hex(rgb)}\n"
                f"Hue: {hue_degrees(rgb):.1f}°\n"
                f"Figma gray: {color_gray_hex} ({lum:.12f})\n"
                f"Contrast on #FCFCFC: "
                f"{contrast_ratio(rgb, LIGHT_THEME_BACKGROUND):.2f}:1"
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
