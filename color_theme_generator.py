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
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QGroupBox,
    QVBoxLayout,
    QFrame,
    QScrollArea,
    QSizePolicy,
)

import color_utils as cu
from color_utils import (
    GENERATION_PARAMETERS,
    SCORING_PARAMETERS,
    apply_generation_parameters,
    default_generation_parameters,
    default_scoring_parameters,
    describe_color,
    generate_contrast_palette,
    generate_preset_palettes,
    grayscale_value,
    palette_quality_metrics,
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
        min_distance = min(
            rgb_distance(a, b)
            for a, b in combinations(palette, 2)
        )
        layout.addWidget(
            selectable_label(
                f"{title} · score {score:.1f} · "
                f"Минимальная дистанция между цветами: {min_distance:.1f} "
                f"(порог {cu.MIN_THEME_RGB_DISTANCE:.0f})"
            )
        )

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

            description = selectable_label(describe_color(color))
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
        self.scoring_parameters = default_scoring_parameters()
        self.generation_parameters = default_generation_parameters()
        self.scoring_inputs = {}
        self.generation_inputs = {}

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

        generation_group = QGroupBox("Основные правила генерации")
        generation_layout = QVBoxLayout(generation_group)
        generation_help = selectable_label(
            "Эти параметры задают базовые ограничения: какой фон считать фоном "
            "интерфейса, какой контраст нужен, какие цвета считать слишком "
            "похожими, тёмными или блеклыми. Измените значения и нажмите "
            "«Применить правила и пересчитать»."
        )
        generation_layout.addWidget(generation_help)

        generation_form = QFormLayout()
        generation_layout.addLayout(generation_form)
        for key, metadata in GENERATION_PARAMETERS.items():
            spinbox = QDoubleSpinBox()
            spinbox.setRange(metadata["min"], metadata["max"])
            spinbox.setSingleStep(metadata["step"])
            spinbox.setDecimals(metadata["decimals"])
            spinbox.setValue(self.generation_parameters[key])
            spinbox.valueChanged.connect(
                lambda value, parameter_key=key: self.on_generation_parameter_changed(
                    parameter_key, value
                )
            )
            self.generation_inputs[key] = spinbox
            generation_form.addRow(
                selectable_label(f"{key}\n{metadata['description']}"),
                spinbox,
            )

        self.apply_generation_button = QPushButton(
            "Применить правила и пересчитать"
        )
        self.apply_generation_button.clicked.connect(self.apply_generation_parameters)

        self.reset_generation_button = QPushButton(
            "Сбросить правила и пересчитать"
        )
        self.reset_generation_button.clicked.connect(self.reset_generation_parameters)

        generation_buttons_layout = QHBoxLayout()
        generation_buttons_layout.addWidget(self.apply_generation_button)
        generation_buttons_layout.addWidget(self.reset_generation_button)
        generation_layout.addLayout(generation_buttons_layout)
        layout.addWidget(generation_group)

        coefficients_group = QGroupBox(
            "Коэффициенты score для подбора цветов"
        )
        coefficients_layout = QVBoxLayout(coefficients_group)
        coefficients_help = selectable_label(
            "Эти коэффициенты объясняют генератору, что для вас важнее. "
            "Награда увеличивает score за хорошее свойство, штраф уменьшает "
            "score за проблему. Если не уверены — оставьте значения по умолчанию."
        )
        coefficients_layout.addWidget(coefficients_help)

        coefficients_form = QFormLayout()
        coefficients_layout.addLayout(coefficients_form)
        for key, metadata in SCORING_PARAMETERS.items():
            spinbox = QDoubleSpinBox()
            spinbox.setRange(metadata["min"], metadata["max"])
            spinbox.setSingleStep(metadata["step"])
            spinbox.setDecimals(2)
            spinbox.setValue(self.scoring_parameters[key])
            spinbox.valueChanged.connect(
                lambda value, parameter_key=key: self.on_scoring_parameter_changed(
                    parameter_key, value
                )
            )
            self.scoring_inputs[key] = spinbox
            coefficients_form.addRow(
                selectable_label(f"{key}\n{metadata['description']}"),
                spinbox,
            )

        self.apply_scoring_button = QPushButton(
            "Применить коэффициенты и пересчитать"
        )
        self.apply_scoring_button.clicked.connect(self.apply_scoring_parameters)

        self.reset_scoring_button = QPushButton(
            "Сбросить коэффициенты и пересчитать"
        )
        self.reset_scoring_button.clicked.connect(self.reset_scoring_parameters)

        coefficients_buttons_layout = QHBoxLayout()
        coefficients_buttons_layout.addWidget(self.apply_scoring_button)
        coefficients_buttons_layout.addWidget(self.reset_scoring_button)
        coefficients_layout.addLayout(coefficients_buttons_layout)
        layout.addWidget(coefficients_group)

        self.info_label = selectable_label()
        layout.addWidget(self.info_label)

        self.rows = []
        for i in range(4):
            row = ColorRow(f"Цвет {i + 1}")
            row.button.clicked.connect(lambda _, idx=i: self.open_picker(idx))
            layout.addWidget(row)
            self.rows.append(row)

        layout.addWidget(selectable_label("Готовые пресеты / палитры:"))
        self.presets_layout = QVBoxLayout()
        layout.addLayout(self.presets_layout)
        self.preset_rows = []
        self.rebuild_presets()

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

    def on_generation_parameter_changed(self, key, value):
        self.generation_parameters[key] = value

    def apply_generation_parameters(self):
        self.generation_parameters = apply_generation_parameters(
            self.generation_parameters
        )
        self.generate_from_first_color()
        self.rebuild_presets()

    def reset_generation_parameters(self):
        self.generation_parameters = default_generation_parameters()
        for key, spinbox in self.generation_inputs.items():
            spinbox.blockSignals(True)
            spinbox.setValue(self.generation_parameters[key])
            spinbox.blockSignals(False)

        self.apply_generation_parameters()

    def on_scoring_parameter_changed(self, key, value):
        self.scoring_parameters[key] = value

    def apply_scoring_parameters(self):
        self.generate_from_first_color()
        self.rebuild_presets()

    def reset_scoring_parameters(self):
        self.scoring_parameters = default_scoring_parameters()
        for key, spinbox in self.scoring_inputs.items():
            spinbox.blockSignals(True)
            spinbox.setValue(self.scoring_parameters[key])
            spinbox.blockSignals(False)

        self.apply_scoring_parameters()

    def rebuild_presets(self):
        while self.preset_rows:
            preset_row = self.preset_rows.pop()
            self.presets_layout.removeWidget(preset_row)
            preset_row.deleteLater()

        for preset_index, (score, palette) in enumerate(
            generate_preset_palettes(scoring_parameters=self.scoring_parameters),
            start=1,
        ):
            preset_row = PresetRow(f"Пресет {preset_index}", score, palette)
            self.presets_layout.addWidget(preset_row)
            self.preset_rows.append(preset_row)

    def generate_from_first_color(self):
        self.colors = generate_contrast_palette(
            self.original_colors[0], 4, scoring_parameters=self.scoring_parameters
        )
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
        bg_hex = rgb_to_hex(cu.LIGHT_THEME_BACKGROUND)
        palette_metrics = palette_quality_metrics(
            self.colors, scoring_parameters=self.scoring_parameters
        )
        self.info_label.setText(
            "Ч/б значение больше не участвует в подборе: "
            "главные критерии — достаточный и близкий контраст с фоном, "
            "яркость и различимость цветов. "
            f"Score: {palette_metrics['score']:.1f}. "
            f"Фон светлой темы: {bg_hex}. "
            f"Минимальный контраст с фоном: {palette_metrics['min_contrast']:.2f}:1 "
            f"(цель WCAG AA: {cu.WCAG_AA_NORMAL_TEXT_RATIO:.1f}:1). \n"
            f"Разброс контраста: {palette_metrics['contrast_spread']:.2f}. "
            f"Средняя яркость: {palette_metrics['avg_brightness']:.1f}/255. "
            f"Разброс яркости: {palette_metrics['brightness_spread']:.1f}. "
            f"Диапазон ч/б справочно: #{min_gray:02X}{min_gray:02X}{min_gray:02X}–"
            f"#{max_gray:02X}{max_gray:02X}{max_gray:02X}. "
            f"Минимальная RGB-дистанция между темами: {min(distances):.1f} "
            f"(порог {cu.MIN_THEME_RGB_DISTANCE:.0f})."
        )

        for i, rgb in enumerate(self.colors):
            color_gray = grayscale_value(rgb)
            color_gray_hex = f"#{color_gray:02X}{color_gray:02X}{color_gray:02X}"
            self.rows[i].color_preview.setStyleSheet(f"background:{rgb_to_hex(rgb)};")
            self.rows[i].gray_preview.setStyleSheet(f"background:{color_gray_hex};")
            self.rows[i].label.setText(describe_color(rgb))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
