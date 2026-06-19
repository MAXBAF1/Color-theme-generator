import sys
from itertools import combinations

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
)

from color_utils import (
    adjust_to_luminance,
    generate_contrast_palette,
    grayscale_value,
    hue_degrees,
    luminance,
    rgb_distance,
    rgb_to_hex,
)


class ColorRow(QWidget):
    def __init__(self, title):
        super().__init__()
        layout = QHBoxLayout(self)
        self.button = QPushButton(title)
        self.color_preview = QFrame()
        self.color_preview.setFixedSize(140, 60)
        self.gray_preview = QFrame()
        self.gray_preview.setFixedSize(140, 60)
        self.label = QLabel()

        layout.addWidget(self.button)
        layout.addWidget(self.color_preview)
        layout.addWidget(self.gray_preview)
        layout.addWidget(self.label)


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Equal Luminance Theme Colors")
        self.resize(1120, 560)

        self.original_colors = [
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0),
        ]
        self.colors = self.original_colors.copy()

        layout = QVBoxLayout(self)
        self.generate_button = QPushButton(
            "Сгенерировать 4 максимально контрастных цвета от Цвета 1"
        )
        self.generate_button.clicked.connect(self.generate_from_first_color)
        layout.addWidget(self.generate_button)

        self.info_label = QLabel()
        layout.addWidget(self.info_label)

        self.rows = []
        for i in range(4):
            row = ColorRow(f"Цвет {i + 1}")
            row.button.clicked.connect(lambda _, idx=i: self.open_picker(idx))
            layout.addWidget(row)
            self.rows.append(row)

        self.active_dialog = None
        self.active_index = None
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

        if index == 0:
            self.generate_from_first_color()
        else:
            self.recalculate_manual_palette()

    def generate_from_first_color(self):
        self.colors = generate_contrast_palette(self.original_colors[0], 4)
        self.original_colors = self.colors.copy()
        self.update_ui()

    def recalculate_manual_palette(self):
        self.colors[0] = self.original_colors[0]
        target = luminance(self.colors[0])
        for i in range(1, 4):
            self.colors[i] = adjust_to_luminance(self.original_colors[i], target)
        self.update_ui()

    def update_ui(self):
        target = luminance(self.colors[0])
        gray = grayscale_value(self.colors[0])
        gray_hex = f"#{gray:02X}{gray:02X}{gray:02X}"

        distances = [
            rgb_distance(self.colors[a], self.colors[b])
            for a, b in combinations(range(4), 2)
        ]
        self.info_label.setText(
            "Все цвета приведены к одинаковой WCAG relative luminance. "
            f"Общий ч/б цвет: {gray_hex}. "
            f"Минимальная RGB-дистанция между темами: {min(distances):.1f}."
        )

        for i, rgb in enumerate(self.colors):
            lum = luminance(rgb)
            self.rows[i].color_preview.setStyleSheet(f"background:{rgb_to_hex(rgb)};")
            self.rows[i].gray_preview.setStyleSheet(f"background:{gray_hex};")
            self.rows[i].label.setText(
                f"HEX: {rgb_to_hex(rgb)}\n"
                f"Hue: {hue_degrees(rgb):.1f}°\n"
                f"Luminance: {lum:.12f}\n"
                f"Error: {abs(lum - target):.12f}"
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
