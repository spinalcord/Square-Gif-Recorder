# utils/gif_saver.py

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Callable

from .qt_imports import QImage, QFileDialog, QMessageBox, QT_VERSION, QProgressDialog

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow must be installed!")
    print("Installation: pip install pillow")
    sys.exit(1)


def save_gif_from_frames(
    parent_widget,
    frames: List[QImage],
    fps: int,
    scale_factor: float,
    num_colors: int,
    use_dithering: bool,
    skip_value: int,
    lossy_level: int = 0, # New parameter for additional quality reduction (0-10)
    disposal_method: int = 0, # New parameter for GIF disposal method (0-3)
    progress_callback: Callable[[int], None] = None
):
    """
    Handles the entire process of saving frames to a GIF file, including
    file dialog, frame processing, and user feedback.
    """
    if not frames:
        QMessageBox.warning(parent_widget, "Error", "No frames to save!")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_name = f"recording_{timestamp}.gif"
    filename, _ = QFileDialog.getSaveFileName(
        parent_widget, "Save GIF", default_name, "GIF Files (*.gif)"
    )

    if not filename:
        return None

    # Determine Pillow constants based on library version
    dither = Image.Dither.FLOYDSTEINBERG if use_dithering else Image.Dither.NONE
    resample = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS

    try:
        progress_dialog = QProgressDialog("Saving GIF...", "Abort", 0, len(frames), parent_widget)
        progress_dialog.setWindowModality(2) # Qt.WindowModal
        progress_dialog.setWindowTitle("Saving GIF")
        progress_dialog.setMinimumDuration(0) # Show immediately

        pil_images = []
        for i, qimage in enumerate(frames):
            if progress_dialog.wasCanceled():
                return None

            progress_dialog.setValue(i)
            if progress_callback:
                progress_callback(i)

            # Convert QImage to PIL Image
            ptr = qimage.constBits()
            if QT_VERSION == 6:
                ptr.setsize(qimage.sizeInBytes())
            else:
                ptr.setsize(qimage.byteCount())
            
            pil_img = Image.frombuffer(
                'RGBA', (qimage.width(), qimage.height()), ptr, 'raw', 'BGRA', 0, 1
            )

            # Apply scaling
            if scale_factor < 1.0:
                new_size = (int(pil_img.width * scale_factor), int(pil_img.height * scale_factor))
                pil_img = pil_img.resize(new_size, resample=resample)

            # Apply additional lossy compression by reducing num_colors based on lossy_level
            effective_num_colors = num_colors
            if lossy_level > 0:
                # Scale num_colors down based on lossy_level (0-10)
                # Ensure a minimum of 2 colors
                effective_num_colors = max(2, int(num_colors * (1 - lossy_level / 10.0)))

            # Quantize to reduce palette size after all transformations
            pil_img_quantized = pil_img.convert('RGB').quantize(colors=effective_num_colors, dither=dither)
            pil_images.append(pil_img_quantized)

        progress_dialog.setValue(len(frames)) # Set to max when done with frame processing

        # The duration between frames must be adjusted if frames were skipped.
        # If we use every n-th frame, the time between them is n times longer.
        frame_duration = int(1000 / fps) * skip_value

        pil_images[0].save(
            filename,
            save_all=True,
            append_images=pil_images[1:],
            duration=frame_duration,
            loop=0,
            optimize=True,
            disposal=disposal_method # Apply the disposal method
        )

        QMessageBox.information(parent_widget, "Success", f"GIF successfully saved:\n{filename}")
        return Path(filename).name
    except Exception as e:
        QMessageBox.critical(parent_widget, "Error", f"Error saving GIF:\n{str(e)}")
        return None
    finally:
        if 'progress_dialog' in locals() and progress_dialog:
            progress_dialog.close()
