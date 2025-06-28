"""
Clean GIF saver module with proper error handling and separation of concerns.
Fixed: Single continuous progress dialog without interruption.
"""

import sys
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Callable, Optional, Tuple
from dataclasses import dataclass
from contextlib import contextmanager

from .qt_imports import QImage, QFileDialog, QMessageBox, QProgressDialog, Qt, QT_VERSION, QApplication

try:
    from PIL import Image, ImageChops, ImageStat
except ImportError:
    print("Error: Pillow must be installed!")
    print("Installation: pip install pillow")
    sys.exit(1)


@dataclass
class GifSettings:
    """Configuration for GIF creation."""
    fps: int
    scale_factor: float
    num_colors: int
    use_dithering: bool
    skip_value: int
    lossy_level: int = 0  # 0-10 scale for quality reduction
    disposal_method: int = 0  # 0-3 for GIF disposal methods
    similarity_threshold: float = 0.95  # NEU: Schwellenwert für Ähnlichkeit (0-1)
    enable_similarity_skip: bool = True  # NEU: Frame-Ähnlichkeitsprüfung aktivieren
    
    def __post_init__(self):
        """Validate settings after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate all settings are within acceptable ranges."""
        if self.fps <= 0:
            raise ValueError("FPS must be positive")
        if not 0 < self.scale_factor <= 1.0:
            raise ValueError("Scale factor must be between 0 and 1")
        if self.num_colors < 2 or self.num_colors > 256:
            raise ValueError("Number of colors must be between 2 and 256")
        if self.skip_value < 1:
            raise ValueError("Skip value must be at least 1")
        if not 0 <= self.lossy_level <= 10:
            raise ValueError("Lossy level must be between 0 and 10")
        if not 0 <= self.disposal_method <= 3:
            raise ValueError("Disposal method must be between 0 and 3")
        if not 0 <= self.similarity_threshold <= 1.0:  # NEU
            raise ValueError("Similarity threshold must be between 0 and 1")
    
    @property
    def effective_num_colors(self) -> int:
        """Calculate effective color count after lossy compression."""
        if self.lossy_level == 0:
            return self.num_colors
        
        # Reduce colors based on lossy level, minimum of 2
        reduction_factor = 1 - (self.lossy_level / 10.0)
        return max(2, int(self.num_colors * reduction_factor))
    
    @property
    def frame_duration_ms(self) -> int:
        """Calculate frame duration in milliseconds, accounting for skipped frames."""
        base_duration = int(1000 / self.fps)
        return base_duration * self.skip_value
    
    @property
    def pil_dither(self) -> Image.Dither:
        """Get PIL dithering mode."""
        return Image.Dither.FLOYDSTEINBERG if self.use_dithering else Image.Dither.NONE
    
    @property
    def pil_resample(self) -> int:
        """Get PIL resampling mode with version compatibility."""
        if hasattr(Image, 'Resampling'):
            return Image.Resampling.LANCZOS
        return Image.LANCZOS

class FrameSimilarityDetector:
    """Verbesserte Erkennung ähnlicher Frames mit mehreren Methoden."""
    
    def __init__(self, threshold: float = 0.95):
        self.threshold = threshold
        self.last_frame_hash: Optional[str] = None
        self.last_processed_image: Optional[Image.Image] = None
        self.last_histogram = None
        self.last_structural_hash = None
    
    def is_similar_to_previous(self, current_image: Image.Image) -> bool:
        if self.last_processed_image is None:
            self._update_reference(current_image)
            return False  # Erstes Frame immer behalten
        
        # 1. Schnelle Hash-Prüfung zuerst (identische Frames)
        current_hash = self._calculate_image_hash(current_image)
        if current_hash == self.last_frame_hash:
            return True  # Identische Frames überspringen
        
        # 2. Struktureller Hash für große Änderungen
        current_structural = self._calculate_structural_hash(current_image)
        if current_structural != self.last_structural_hash:
            # Große strukturelle Änderung -> Frame behalten
            self._update_reference(current_image)
            return False
        
        # 3. Detaillierte Ähnlichkeitsprüfung mit mehreren Methoden
        similarity_scores = self._calculate_multiple_similarities(
            self.last_processed_image, current_image
        )
        
        # Gewichteter Durchschnitt der verschiedenen Ähnlichkeitsmetriken
        combined_similarity = self._combine_similarities(similarity_scores)
        
        if combined_similarity < self.threshold:
            # Frame ist unterschiedlich genug -> behalten
            self._update_reference(current_image)
            return False
        else:
            # Frame ist zu ähnlich -> überspringen
            return True
    
    def _calculate_multiple_similarities(self, img1: Image.Image, img2: Image.Image) -> dict:
        """Berechnet verschiedene Ähnlichkeitsmetriken."""
        similarities = {}
        
        try:
            # Bilder auf gleiche Größe bringen
            if img1.size != img2.size:
                resample = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
                img2 = img2.resize(img1.size, resample)
            
            # 1. Pixel-basierte Ähnlichkeit (wie bisher)
            similarities['pixel'] = self._calculate_pixel_similarity(img1, img2)
            
            # 2. Histogramm-Ähnlichkeit
            similarities['histogram'] = self._calculate_histogram_similarity(img1, img2)
            
            # 3. Strukturelle Ähnlichkeit (vereinfacht)
            similarities['structural'] = self._calculate_structural_similarity(img1, img2)
            
            # 4. Lokale Änderungen (für Textbearbeitung wichtig)
            similarities['local_changes'] = self._calculate_local_changes_similarity(img1, img2)
            
        except Exception as e:
            print(f"Fehler bei Ähnlichkeitsberechnung: {e}")
            # Bei Fehler als unterschiedlich behandeln
            similarities = {'pixel': 0.0, 'histogram': 0.0, 'structural': 0.0, 'local_changes': 0.0}
        
        return similarities
    
    def _calculate_pixel_similarity(self, img1: Image.Image, img2: Image.Image) -> float:
        """Ursprüngliche pixel-basierte Ähnlichkeit."""
        diff = ImageChops.difference(img1, img2)
        stat = ImageStat.Stat(diff)
        avg_diff = sum(stat.mean) / len(stat.mean)
        return max(0.0, min(1.0, 1.0 - (avg_diff / 255.0)))
    
    def _calculate_histogram_similarity(self, img1: Image.Image, img2: Image.Image) -> float:
        """Histogramm-basierte Ähnlichkeit."""
        try:
            # RGB-Histogramme berechnen
            hist1 = img1.convert('RGB').histogram()
            hist2 = img2.convert('RGB').histogram()
            
            # Chi-Quadrat-Distanz zwischen Histogrammen
            chi_squared = 0
            for i in range(len(hist1)):
                if hist1[i] + hist2[i] > 0:
                    chi_squared += ((hist1[i] - hist2[i]) ** 2) / (hist1[i] + hist2[i])
            
            # Normalisieren und in Ähnlichkeit umwandeln
            max_chi_squared = len(hist1) * 2  # Theoretisches Maximum
            similarity = 1.0 - min(chi_squared / max_chi_squared, 1.0)
            
            return max(0.0, min(1.0, similarity))
            
        except Exception:
            return 0.0
    
    def _calculate_structural_similarity(self, img1: Image.Image, img2: Image.Image) -> float:
        """Vereinfachte strukturelle Ähnlichkeit."""
        try:
            # Bilder zu Graustufen konvertieren und verkleinern für Performance
            gray1 = img1.convert('L').resize((64, 64), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
            gray2 = img2.convert('L').resize((64, 64), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
            
            # Kanten mit einfachem Sobel-ähnlichen Filter
            def detect_edges(img):
                import numpy as np
                arr = np.array(img)
                # Horizontale und vertikale Gradienten
                grad_x = np.abs(arr[1:, :] - arr[:-1, :])
                grad_y = np.abs(arr[:, 1:] - arr[:, :-1])
                # Kanten kombinieren (kleinere Größe nehmen)
                min_h, min_w = min(grad_x.shape[0], grad_y.shape[0]), min(grad_x.shape[1], grad_y.shape[1])
                edges = grad_x[:min_h, :min_w] + grad_y[:min_h, :min_w]
                return edges
            
            edges1 = detect_edges(gray1)
            edges2 = detect_edges(gray2)
            
            # Korrelation zwischen Kantenkarten
            flat1 = edges1.flatten()
            flat2 = edges2.flatten()
            
            if len(flat1) == 0 or len(flat2) == 0:
                return 0.0
            
            # Pearson-Korrelationskoeffizient
            mean1, mean2 = np.mean(flat1), np.mean(flat2)
            std1, std2 = np.std(flat1), np.std(flat2)
            
            if std1 == 0 or std2 == 0:
                return 1.0 if np.array_equal(flat1, flat2) else 0.0
            
            correlation = np.mean((flat1 - mean1) * (flat2 - mean2)) / (std1 * std2)
            return max(0.0, min(1.0, (correlation + 1.0) / 2.0))  # Normalisierung auf [0,1]
            
        except Exception:
            return 0.0
    
    def _calculate_local_changes_similarity(self, img1: Image.Image, img2: Image.Image) -> float:
        """Bewertet lokale Änderungen - wichtig für Textbearbeitung."""
        try:
            # Differenzbild berechnen
            diff = ImageChops.difference(img1, img2)
            
            # Bild in Blöcke unterteilen (z.B. 8x8 Pixel)
            block_size = 8
            width, height = diff.size
            
            total_blocks = 0
            changed_blocks = 0
            
            for y in range(0, height - block_size + 1, block_size):
                for x in range(0, width - block_size + 1, block_size):
                    # Block extrahieren
                    block = diff.crop((x, y, x + block_size, y + block_size))
                    
                    # Durchschnittliche Änderung in diesem Block
                    stat = ImageStat.Stat(block)
                    avg_change = sum(stat.mean) / len(stat.mean)
                    
                    total_blocks += 1
                    
                    # Block als "geändert" betrachten wenn Änderung über Schwellenwert
                    if avg_change > 10:  # Schwellenwert für "signifikante" Änderung
                        changed_blocks += 1
            
            if total_blocks == 0:
                return 1.0
            
            # Anteil der unveränderten Blöcke
            unchanged_ratio = (total_blocks - changed_blocks) / total_blocks
            
            return max(0.0, min(1.0, unchanged_ratio))
            
        except Exception:
            return 0.0
    
    def _combine_similarities(self, similarities: dict) -> float:
        """Kombiniert verschiedene Ähnlichkeitsmetriken gewichtet."""
        # Gewichte für verschiedene Metriken
        weights = {
            'pixel': 0.2,          # Weniger Gewicht auf reine Pixeldifferenz
            'histogram': 0.2,      # Farbverteilung
            'structural': 0.3,     # Strukturelle Ähnlichkeit
            'local_changes': 0.3   # Lokale Änderungen (wichtig für Text)
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for metric, similarity in similarities.items():
            if metric in weights:
                weight = weights[metric]
                weighted_sum += similarity * weight
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return weighted_sum / total_weight
    
    def _calculate_structural_hash(self, image: Image.Image) -> str:
        """Berechnet einen Hash basierend auf Bildstruktur (Kanten)."""
        try:
            # Zu Graustufen und kleine Größe für schnellen Vergleich
            gray = image.convert('L').resize((16, 16), Image.Resampling.NEAREST if hasattr(Image, 'Resampling') else Image.NEAREST)
            
            # Einfache Kantenerkennung durch Differenzen
            import numpy as np
            arr = np.array(gray)
            
            # Horizontale und vertikale Gradienten
            grad_x = arr[1:, :] - arr[:-1, :]
            grad_y = arr[:, 1:] - arr[:, :-1]
            
            # Kombinierte Gradientenstärke
            min_h, min_w = min(grad_x.shape[0], grad_y.shape[0]), min(grad_x.shape[1], grad_y.shape[1])
            combined = np.abs(grad_x[:min_h, :min_w]) + np.abs(grad_y[:min_h, :min_w])
            
            # Binarisierung (starke Kanten vs. schwache)
            threshold = np.mean(combined) + np.std(combined)
            binary = (combined > threshold).astype(np.uint8)
            
            # Hash der Binärstruktur
            return hashlib.md5(binary.tobytes()).hexdigest()
            
        except Exception:
            # Fallback auf einfachen Hash
            return self._calculate_image_hash(image)
    
    def _update_reference(self, image: Image.Image) -> None:
        """Aktualisiert das Referenz-Frame."""
        self.last_processed_image = image.copy()
        self.last_frame_hash = self._calculate_image_hash(image)
        self.last_structural_hash = self._calculate_structural_hash(image)
    
    def _calculate_image_hash(self, image: Image.Image) -> str:
        """Berechnet einen schnellen Hash für das Bild."""
        small_image = image.resize((8, 8), Image.Resampling.NEAREST if hasattr(Image, 'Resampling') else Image.NEAREST)
        return hashlib.md5(small_image.tobytes()).hexdigest()
    
    def reset(self) -> None:
        """Setzt den Detektor zurück."""
        self.last_frame_hash = None
        self.last_processed_image = None
        self.last_histogram = None
        self.last_structural_hash = None

class ImageConverter:
    """Handles conversion between QImage and PIL Image formats."""
    
    @staticmethod
    def qimage_to_pil(qimage: QImage) -> Image.Image:
        """Convert QImage to PIL Image with proper format handling."""
        try:
            # Get image data pointer
            ptr = qimage.constBits()
            
            # Set buffer size based on Qt version
            if QT_VERSION == 6:
                ptr.setsize(qimage.sizeInBytes())
            else:
                ptr.setsize(qimage.byteCount())
            
            # Convert to PIL Image
            pil_image = Image.frombuffer(
                'RGBA', 
                (qimage.width(), qimage.height()), 
                ptr, 
                'raw', 
                'BGRA',  # Qt uses BGRA format
                0, 
                1
            )
            
            return pil_image
            
        except Exception as e:
            raise RuntimeError(f"Failed to convert QImage to PIL Image: {e}") from e
    
    @staticmethod
    def process_image(pil_image: Image.Image, settings: GifSettings) -> Image.Image:
        """Process a PIL image according to GIF settings."""
        try:
            # Apply scaling if needed
            if settings.scale_factor < 1.0:
                new_width = int(pil_image.width * settings.scale_factor)
                new_height = int(pil_image.height * settings.scale_factor)
                new_size = (max(1, new_width), max(1, new_height))  # Ensure minimum size
                pil_image = pil_image.resize(new_size, resample=settings.pil_resample)
            
            # Convert to RGB and quantize colors
            rgb_image = pil_image.convert('RGB')
            quantized_image = rgb_image.quantize(
                colors=settings.effective_num_colors, 
                dither=settings.pil_dither
            )
            
            return quantized_image
            
        except Exception as e:
            raise RuntimeError(f"Failed to process image: {e}") from e


class ProgressManager:
    """Manages progress dialog and callbacks with unified progress tracking."""
    
    def __init__(self, parent_widget, total_frames: int, 
                 progress_callback: Optional[Callable[[int], None]] = None):
        self.parent_widget = parent_widget
        self.total_frames = total_frames
        self.progress_callback = progress_callback
        self.dialog: Optional[QProgressDialog] = None
        
        # Calculate total steps: frame processing + saving
        self.frames_processing_steps = total_frames
        self.saving_steps = 1  # GIF saving is one step
        self.total_steps = self.frames_processing_steps + self.saving_steps
        self.current_step = 0
    
    @contextmanager
    def progress_context(self):
        """Context manager for progress dialog lifecycle."""
        try:
            self._create_dialog()
            yield self
        finally:
            self._cleanup_dialog()
    
    def _create_dialog(self) -> None:
        """Create and configure progress dialog."""
        self.dialog = QProgressDialog(
            "Starting...", 
            "Cancel", 
            0, 
            self.total_steps,  # Use total steps instead of just frames
            self.parent_widget
        )
        self.dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.dialog.setWindowTitle("Saving GIF")
        self.dialog.setMinimumDuration(0)  # Show immediately
        self.dialog.show()
        
        # Process events to ensure dialog is visible
        QApplication.processEvents()
    
    def update_frame_progress(self, current_frame: int, status: str = "") -> bool:
        """Update progress for frame processing phase."""
        if not self.dialog:
            return False
        
        if self.dialog.wasCanceled():
            return True
        
        # Current step is the frame number
        self.current_step = current_frame
        
        # Update dialog
        self.dialog.setValue(self.current_step)
        if status:
            self.dialog.setLabelText(status)
        
        # Process events to keep UI responsive
        QApplication.processEvents()
        
        # Call external callback
        if self.progress_callback:
            try:
                self.progress_callback(current_frame)
            except Exception as e:
                print(f"Progress callback error: {e}")
        
        return False
    
    def start_saving_phase(self) -> bool:
        """Start the GIF saving phase."""
        if not self.dialog:
            return False
        
        if self.dialog.wasCanceled():
            return True
        
        # Move to saving phase
        self.current_step = self.frames_processing_steps
        self.dialog.setValue(self.current_step)
        self.dialog.setLabelText("Writing GIF file...")
        
        # Process events to update UI
        QApplication.processEvents()
        
        return False
    
    def finish_saving(self) -> None:
        """Mark saving as complete."""
        if not self.dialog:
            return
        
        # Set to maximum value
        self.current_step = self.total_steps
        self.dialog.setValue(self.current_step)
        self.dialog.setLabelText("GIF saved successfully!")
        
        # Process events to show completion
        QApplication.processEvents()
    
    def is_cancelled(self) -> bool:
        """Check if operation was cancelled."""
        return self.dialog and self.dialog.wasCanceled()
    
    def _cleanup_dialog(self) -> None:
        """Clean up progress dialog."""
        if self.dialog:
            self.dialog.close()
            self.dialog = None


class GifSaver:
    """Main class for saving frames as GIF files."""
    
    def __init__(self):
        self.converter = ImageConverter()
    
    def save_gif_from_frames(
        self,
        parent_widget,
        frames: List[QImage],
        settings: GifSettings,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Optional[str]:
        """
        Save frames as GIF file with comprehensive error handling.
        
        Returns:
            Filename if successful, None if cancelled or failed.
        """
        # Validate inputs
        if not self._validate_inputs(parent_widget, frames):
            return None
        
        # Get save filename
        filename = self._get_save_filename(parent_widget)
        if not filename:
            return None
        
        try:
            return self._perform_save(parent_widget, frames, settings, filename, progress_callback)
        except Exception as e:
            self._show_error(parent_widget, f"Unexpected error during save: {e}")
            return None
    
    def _validate_inputs(self, parent_widget, frames: List[QImage]) -> bool:
        """Validate input parameters."""
        if not frames:
            self._show_error(parent_widget, "No frames to save!")
            return False
        
        if not parent_widget:
            print("Warning: No parent widget provided")
        
        return True
    
    def _get_save_filename(self, parent_widget) -> Optional[str]:
        """Get filename from user via file dialog."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"recording_{timestamp}.gif"
        
        filename, _ = QFileDialog.getSaveFileName(
            parent_widget, 
            "Save GIF", 
            default_name, 
            "GIF Files (*.gif);;All Files (*)"
        )
        
        return filename if filename else None
    
    def _perform_save(
        self, 
        parent_widget, 
        frames: List[QImage], 
        settings: GifSettings,
        filename: str,
        progress_callback: Optional[Callable[[int], None]]
    ) -> Optional[str]:
        """Perform the actual GIF saving process."""
        progress_manager = ProgressManager(parent_widget, len(frames), progress_callback)
        
        with progress_manager.progress_context():
            # Process all frames
            processed_images = self._process_frames(frames, settings, progress_manager)
            
            if not processed_images or progress_manager.is_cancelled():
                return None
            
            # Start saving phase
            if progress_manager.start_saving_phase():
                return None  # Cancelled
            
            # Save the GIF
            self._save_gif_file(processed_images, settings, filename, progress_manager)
            
            if progress_manager.is_cancelled():
                return None
            
            # Mark as complete
            progress_manager.finish_saving()
            
            # Show success message
            self._show_success(parent_widget, filename)
            return Path(filename).name
    
    def _process_frames(
        self, 
        frames: List[QImage], 
        settings: GifSettings, 
        progress_manager: ProgressManager
    ) -> Optional[List[Image.Image]]:
        """Process all frames and return PIL images mit Ähnlichkeitsprüfung."""
        processed_images = []
        
        # Ähnlichkeitsdetektor initialisieren
        similarity_detector = None
        if settings.enable_similarity_skip:
            similarity_detector = FrameSimilarityDetector(settings.similarity_threshold)
        
        skipped_count = 0
        
        for i, qimage in enumerate(frames):
            # Check for cancellation
            status_text = f"Processing frame {i + 1}/{len(frames)}"
            if skipped_count > 0:
                status_text += f" (skipped {skipped_count} similar)"
            
            if progress_manager.update_frame_progress(i, status_text):
                return None  # Cancelled
            
            try:
                # Convert and process image
                pil_image = self.converter.qimage_to_pil(qimage)
                processed_image = self.converter.process_image(pil_image, settings)
                
                # Ähnlichkeitsprüfung
                if similarity_detector and similarity_detector.is_similar_to_previous(processed_image):
                    skipped_count += 1
                    continue  # Frame überspringen
                
                processed_images.append(processed_image)
                
            except Exception as e:
                raise RuntimeError(f"Failed to process frame {i + 1}: {e}") from e
        
        # Final frame processing update
        final_status = f"Processed {len(processed_images)} frames"
        if skipped_count > 0:
            final_status += f" (skipped {skipped_count} similar frames)"
        progress_manager.update_frame_progress(len(frames), final_status)
        
        return processed_images
    
    def _save_gif_file(
        self, 
        images: List[Image.Image], 
        settings: GifSettings, 
        filename: str,
        progress_manager: ProgressManager
    ) -> None:
        """Save processed images as GIF file."""
        if not images:
            raise ValueError("No images to save")
        
        # Check for cancellation before starting save
        if progress_manager.is_cancelled():
            return
        
        try:
            # Save with PIL - this operation doesn't provide progress callbacks
            # so we just show a general "saving" message
            images[0].save(
                filename,
                save_all=True,
                append_images=images[1:],
                duration=settings.frame_duration_ms,
                loop=0,  # Infinite loop
                optimize=True,
                disposal=settings.disposal_method
            )
        except Exception as e:
            raise RuntimeError(f"Failed to save GIF file: {e}") from e
    
    def _show_success(self, parent_widget, filename: str) -> None:
        """Show success message to user."""
        if parent_widget:
            QMessageBox.information(
                parent_widget, 
                "Success", 
                f"GIF successfully saved to:\n{filename}"
            )
    
    def _show_error(self, parent_widget, message: str) -> None:
        """Show error message to user."""
        if parent_widget:
            QMessageBox.critical(parent_widget, "Error", message)
        else:
            print(f"Error: {message}")


# Global instance for backwards compatibility
_gif_saver = GifSaver()


def save_gif_from_frames(
    parent_widget,
    frames: List[QImage],
    fps: int,
    scale_factor: float,
    num_colors: int,
    use_dithering: bool,
    skip_value: int,
    lossy_level: int = 0,
    disposal_method: int = 0,
    similarity_threshold: float = 0.95,  # NEU
    enable_similarity_skip: bool = True,  # NEU
    progress_callback: Optional[Callable[[int], None]] = None
) -> Optional[str]:
    """
    Legacy function wrapper für Rückwärtskompatibilität mit neuen Ähnlichkeitsparametern.
    
    Saves frames as a GIF file with the specified settings.
    
    Args:
        parent_widget: Qt widget for dialogs
        frames: List of QImage objects to save
        fps: Frames per second for the GIF
        scale_factor: Scale factor for resizing (0.0-1.0)
        num_colors: Number of colors in the palette (2-256)
        use_dithering: Whether to use dithering
        skip_value: Use every nth frame (1 = all frames)
        lossy_level: Additional compression level (0-10)
        disposal_method: GIF disposal method (0-3)
        similarity_threshold: Threshold for frame similarity (0.0-1.0)
        enable_similarity_skip: Whether to skip similar frames
        progress_callback: Optional callback for progress updates
    
    Returns:
        Filename if successful, None if cancelled or failed.
    """
    try:
        settings = GifSettings(
            fps=fps,
            scale_factor=scale_factor,
            num_colors=num_colors,
            use_dithering=use_dithering,
            skip_value=skip_value,
            lossy_level=lossy_level,
            disposal_method=disposal_method,
            similarity_threshold=similarity_threshold,  # NEU
            enable_similarity_skip=enable_similarity_skip  # NEU
        )
        
        return _gif_saver.save_gif_from_frames(
            parent_widget, frames, settings, progress_callback
        )
        
    except ValueError as e:
        if parent_widget:
            QMessageBox.critical(parent_widget, "Invalid Settings", str(e))
        else:
            print(f"Invalid settings: {e}")
        return None
    except Exception as e:
        if parent_widget:
            QMessageBox.critical(parent_widget, "Error", f"Unexpected error: {e}")
        else:
            print(f"Unexpected error: {e}")
        return None


# Additional utility functions
def validate_gif_settings(
    fps: int,
    scale_factor: float, 
    num_colors: int,
    skip_value: int,
    lossy_level: int = 0,
    disposal_method: int = 0,
    similarity_threshold: float = 0.95,
    enable_similarity_skip: bool = True
) -> Tuple[bool, str]:
    """
    Validate GIF settings without creating a GifSettings object.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        GifSettings(
            fps=fps,
            scale_factor=scale_factor,
            num_colors=num_colors,
            use_dithering=True,  # Doesn't matter for validation
            skip_value=skip_value,
            lossy_level=lossy_level,
            disposal_method=disposal_method,
            similarity_threshold=similarity_threshold,
            enable_similarity_skip=enable_similarity_skip
        )
        return True, ""
    except ValueError as e:
        return False, str(e)


def estimate_gif_size(
    frame_count: int,
    width: int,
    height: int,
    scale_factor: float,
    num_colors: int,
    skip_value: int = 1
) -> int:
    """
    Estimate final GIF file size in bytes.
    This is a rough estimation and actual size may vary.
    
    Returns:
        Estimated size in bytes
    """
    # Calculate effective dimensions and frame count
    effective_width = int(width * scale_factor)
    effective_height = int(height * scale_factor)
    effective_frames = frame_count // skip_value
    
    # Rough estimation: palette + header + frame data
    palette_size = num_colors * 3  # RGB values
    header_size = 1024  # Approximate header size
    
    # Estimate bytes per pixel (compressed)
    if num_colors <= 2:
        bits_per_pixel = 1
    elif num_colors <= 4:
        bits_per_pixel = 2
    elif num_colors <= 16:
        bits_per_pixel = 4
    else:
        bits_per_pixel = 8
    
    bytes_per_pixel = bits_per_pixel / 8
    compression_ratio = 0.7  # Assume 30% compression
    
    frame_data_size = (effective_width * effective_height * bytes_per_pixel * 
                      effective_frames * compression_ratio)
    
    return int(header_size + palette_size + frame_data_size)