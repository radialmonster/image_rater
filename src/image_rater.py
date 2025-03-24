import os
import shutil
import random
import tkinter as tk
import tkinter.ttk as ttk  # Add explicit import for ttk
import json
import subprocess
from tkinter import filedialog, messagebox, simpledialog
from PIL import ImageTk, Image, UnidentifiedImageError
import piexif
from piexif import TAGS
import fractions

# Import tkinterdnd2 with error handling
try:
    import tkinterdnd2
    TKDND_AVAILABLE = True
except ImportError:
    TKDND_AVAILABLE = False
    print("tkinterdnd2 not found. Drag and drop will not be available.")
    print("To enable drag and drop, install tkinterdnd2 with: pip install tkinterdnd2")

# Enhanced tooltips for UI elements
class ToolTip:
    """
    Create tooltips for any widget
    """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        # Create toplevel window
        self.tooltip = tk.Toplevel(self.widget)
        # Prevent it from having a taskbar icon
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        # Create tooltip content
        label = tk.Label(self.tooltip, text=self.text, bg="#FFFFDD", 
                        justify=tk.LEFT, relief=tk.SOLID, borderwidth=1,
                        font=("Arial", "9", "normal"))
        label.pack(padx=2, pady=2)
    
    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

# Function to convert rating to EXIF-compatible value
def rating_to_exif(rating_category):
    """Convert our rating category (1-5) to EXIF rating (0-5)"""
    # EXIF ratings are usually 0-5 where 0 means no rating
    # Our rated folders go from rated_1 to rated_5
    return rating_category  # Direct mapping since our range is already 1-5

# Function to add/update EXIF rating
def set_exif_rating(file_path, rating):
    """Add or update EXIF rating metadata in an image"""
    try:
        # Check if the file is a JPEG
        if not file_path.lower().endswith(('.jpg', '.jpeg')):
            print(f"Skipping EXIF rating for non-JPEG file: {file_path}")
            return False
            
        # Get existing EXIF data or create new
        try:
            exif_dict = piexif.load(file_path)
        except:
            # Create a new EXIF dictionary if loading fails
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        
        # Set the rating in the appropriate EXIF field
        # Microsoft Windows/Windows Explorer uses Rating tag
        if "0th" not in exif_dict:
            exif_dict["0th"] = {}
        
        # EXIF tag 18246 is the Windows Rating tag (1-5 stars)
        exif_dict["0th"][18246] = rating
        
        # Adobe uses XMP metadata, but we can't easily modify that with piexif
        # Many photo apps also check the EXIF:Rating tag
        if "Exif" not in exif_dict:
            exif_dict["Exif"] = {}
        
        # Some apps use this tag for rating
        exif_dict["Exif"][36864] = b'0230'  # Exif version
        
        # Serialize and save the EXIF data
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, file_path)
        
        return True
    except Exception as e:
        print(f"Error setting EXIF rating for {file_path}: {str(e)}")
        return False

class ImageRater:
    def __init__(self, files_or_folder=None, is_folder=True, set_name=None, load_set_path=None):
        self.is_folder = is_folder
        self.folder_path = files_or_folder if is_folder else os.path.dirname(files_or_folder[0]) if files_or_folder else None
        self.set_name = set_name or "Default"
        self.file_paths = {}
        
        # If loading from a set file, handle this first before processing folder/files
        if load_set_path:
            self.load_set_from_file(load_set_path)
            # After loading, file_paths will be populated from the JSON
            # We need to use these files instead of scanning the folder
            if not self.is_folder and self.file_paths:
                self.image_files = list(self.file_paths.keys())
                self.num_images = len(self.image_files)
                return
        
        if is_folder and self.folder_path:
            self.image_files = [f for f in os.listdir(self.folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        elif not is_folder and files_or_folder:
            # For individual files, we'll use the basename (filename) as the key
            self.image_files = [os.path.basename(f) for f in files_or_folder if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
            # Create a mapping of filenames to their full paths
            self.file_paths = {os.path.basename(f): f for f in files_or_folder if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))}
        else:
            self.image_files = []
            
        self.num_images = len(self.image_files)
        self.ratings = {image: 1500 for image in self.image_files}
        self.comparisons = []
        self.current_comparison = None
        self.current_comparison_number = 0
        
        if is_folder and self.folder_path:
            # Create a directory for the rejected images as a subfolder of the original folder
            self.rejected_folder_path = os.path.join(self.folder_path, "rejected")
            os.makedirs(self.rejected_folder_path, exist_ok=True)
            
            # If we have a specific set file to load and haven't already loaded it
            if load_set_path and not hasattr(self, 'loaded_set'):
                self.load_set_from_file(load_set_path)
            elif not load_set_path:
                self.load_progress()
        else:
            # For drag and drop files, create a temporary directory for rejected files
            self.temp_dir = os.path.join(os.path.expanduser("~"), "ImageRaterTemp")
            self.rejected_folder_path = os.path.join(self.temp_dir, "rejected")
            os.makedirs(self.rejected_folder_path, exist_ok=True)

    def apply_tooltips(self):
        """Apply tooltips to all main UI elements"""
        tooltips = {
            "button_left": "Select the left image as better (keyboard: Left arrow)",
            "button_right": "Select the right image as better (keyboard: Right arrow)",
            "button_reject_left": "Move the left image to the rejected folder (keyboard: Shift+Left)",
            "button_reject_right": "Move the right image to the rejected folder (keyboard: Shift+Right)",
            "button_exif": "Write star ratings (1-5) directly to the image metadata",
            "button_exif_sort": "Finish rating and see options for handling rated images",
            "button_save_set": "Save your current progress with a custom name",
            "button_save_quit": "Save your progress and exit the application",
            "button_save_new": "Save progress and start a new rating session",
        }
        
        for widget_name, tooltip_text in tooltips.items():
            if hasattr(self, widget_name):
                widget = getattr(self, widget_name)
                ToolTip(widget, tooltip_text)

    def apply_theme(self):
        """Apply a consistent theme to the application"""
        style = ttk.Style(self.root)
        
        # Try to use a more modern theme if available
        try:
            style.theme_use('clam')  # 'clam' is generally more modern looking
        except tk.TclError:
            # If 'clam' is not available, use default theme
            pass
        
        # Configure common styles
        style.configure('TButton', font=('Arial', 10))
        style.configure('TLabel', font=('Arial', 10))
        style.map('TButton',
            background=[('active', '#4CAF50'), ('disabled', '#cccccc')],
            foreground=[('active', 'white'), ('disabled', '#999999')])
        
        # Set consistent padding and colors
        self.root.option_add('*Button.relief', 'flat')
        self.root.option_add('*Button.borderWidth', 0)
        self.root.option_add('*Button.highlightThickness', 0)
        self.root.option_add('*Button.padX', 10)
        self.root.option_add('*Button.padY', 5)
        
        # Apply hover effects to buttons
        for button_name in ['button_left', 'button_right', 'button_reject_left', 
                           'button_reject_right', 'button_exif', 'button_exif_sort',
                           'button_save_set', 'button_save_quit', 'button_save_new']:
            if hasattr(self, button_name):
                button = getattr(self, button_name)
                button.bind("<Enter>", self.on_button_enter)
                button.bind("<Leave>", self.on_button_leave)
    
    def on_button_enter(self, event):
        """Handle button hover enter event"""
        e = event
        e.widget['background'] = '#45a049' if e.widget['background'] == '#4CAF50' else \
                               '#1976D2' if e.widget['background'] == '#2196F3' else \
                               '#7B1FA2' if e.widget['background'] == '#9C27B0' else \
                               '#D84315' if e.widget['background'] == '#FF5722' else \
                               '#F57C00' if e.widget['background'] == '#FF9800' else \
                               '#e0e0e0'
    
    def on_button_leave(self, event):
        """Handle button hover leave event"""
        e = event
        e.widget['background'] = '#4CAF50' if '#45a049' in e.widget['background'] else \
                               '#2196F3' if '#1976D2' in e.widget['background'] else \
                               '#9C27B0' if '#7B1FA2' in e.widget['background'] else \
                               '#FF5722' if '#D84315' in e.widget['background'] else \
                               '#FF9800' if '#F57C00' in e.widget['background'] else \
                               '#f0f0f0'

    def setup_enhanced_keyboard_shortcuts(self):
        """Add enhanced keyboard shortcuts"""
        # Add Shift+Left/Right for reject
        self.root.bind("<Shift-Left>", lambda e: self.reject_image('left'))
        self.root.bind("<Shift-Right>", lambda e: self.reject_image('right'))
        
        # Add keyboard shortcut for saving progress
        self.root.bind("<Control-s>", lambda e: self.save_progress())
        
        # Escape to show the final options
        self.root.bind("<Escape>", lambda e: self.show_final_options())

    def enhance_image_comparison(self):
        """Enhance the image comparison visualization"""
        # Add visual indicator for selected image
        def highlight_left(event=None):
            self.canvas.delete("highlight")
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            self.canvas.create_rectangle(
                0, 0, width//2, height, 
                outline="#4CAF50", width=3, tags="highlight"
            )
        
        def highlight_right(event=None):
            self.canvas.delete("highlight")
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            self.canvas.create_rectangle(
                width//2, 0, width, height, 
                outline="#4CAF50", width=3, tags="highlight"
            )
        
        def clear_highlight(event=None):
            self.canvas.delete("highlight")
        
        # Add hover binding to show highlight
        self.canvas.bind("<Motion>", lambda e: highlight_left() if e.x < self.root.winfo_width()//2 else highlight_right())
        self.canvas.bind("<Leave>", clear_highlight)
        
        # Show image filename on hover
        def show_filenames(event=None):
            if not self.current_comparison:
                return
                
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = event.x
            
            # Clear existing filename texts
            self.canvas.delete("filename")
            
            if x < width//2:  # Left side
                image_name = os.path.basename(self.current_comparison[0])
                self.canvas.create_text(
                    width//4, height-30, 
                    text=image_name, fill="white", 
                    font=("Arial", 10), tags="filename",
                    anchor=tk.CENTER
                )
            else:  # Right side
                image_name = os.path.basename(self.current_comparison[1])
                self.canvas.create_text(
                    width*3//4, height-30, 
                    text=image_name, fill="white", 
                    font=("Arial", 10), tags="filename",
                    anchor=tk.CENTER
                )
        
        # Add bindings for filename display
        self.canvas.bind("<Motion>", show_filenames)
        self.canvas.bind("<Leave>", lambda e: self.canvas.delete("filename"))
        
        # Store original show_images method and enhance it
        original_show_images = self.show_images
        def enhanced_show_images(*args, **kwargs):
            self.canvas.delete("welcome_text")
            original_show_images(*args, **kwargs)
        
        self.show_images = enhanced_show_images

    def enhance_progress_display(self):
        """Enhance the progress display with a proper progress bar"""
        # Create a frame for the progress display
        progress_frame = tk.Frame(self.root, bg="black")
        progress_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        
        # Create a progress bar
        progress_style = ttk.Style()
        progress_style.configure("green.Horizontal.TProgressbar", 
                                background='#4CAF50', troughcolor='#333333')
        
        progress_bar = ttk.Progressbar(
            progress_frame, style="green.Horizontal.TProgressbar", 
            orient="horizontal", length=300, mode="determinate"
        )
        progress_bar.pack(pady=5)
        
        # Update the original progress label
        self.progress_label.pack_forget()
        self.progress_label = tk.Label(progress_frame, text="Comparison 0 of 0", 
                                      bg="black", fg="white")
        self.progress_label.pack(pady=3)
        
        # Store the progress bar in the rater object
        self.progress_bar = progress_bar
        
        # Override the update_progress_label method
        original_update = self.update_progress_label
        def enhanced_update_progress():
            original_update()
            total_comparisons = len(self.image_files) * (len(self.image_files) - 1) // 2
            if total_comparisons > 0:
                progress_percentage = (self.current_comparison_number / total_comparisons) * 100
                self.progress_bar["value"] = progress_percentage
        
        # Replace the method
        self.update_progress_label = enhanced_update_progress
        
        # Initial update
        self.update_progress_label()
        
    def display_welcome_message(self):
        """Show a welcome message that disappears when first comparison starts"""
        self.canvas.create_text(
            self.root.winfo_width()//2, self.root.winfo_height()//2,
            text="Welcome to Image Rater\n\nCompare images and choose the better one\n"
                "Use left/right arrow keys or buttons below\n\n"
                "Shift+Left/Right to reject images\nCtrl+S to save progress\nEsc for options",
            fill="white", font=("Arial", 14), justify=tk.CENTER,
            tags="welcome_text"
        )

    def setup_ui_enhancements(self):
        """Apply all UI enhancements to the application"""
        self.apply_tooltips()
        self.apply_theme()
        self.setup_enhanced_keyboard_shortcuts()
        self.enhance_image_comparison()
        self.enhance_progress_display()
        self.display_welcome_message()

    def compare_images(self):
        self.update_progress_label()

        # If we're working with a folder, check the rejected folder
        if self.is_folder:
            self.image_files = [f for f in self.image_files if f not in os.listdir(self.rejected_folder_path)]

        if not self.image_files or len(self.image_files) < 2:
            print("All comparisons complete or not enough images left to compare.")
            messagebox.showinfo("Rating Complete", "All image comparisons are complete!\nUse one of the buttons at the bottom to process or save your ratings.")
            self.update_progress_label()  # Ensure the label reflects the completed state
            return

        if not self.current_comparison:
            if len(self.comparisons) < self.num_images * (self.num_images - 1) // 2 and len(self.image_files) > 1:
                image1, image2 = self.get_next_comparison()
                self.current_comparison = (image1, image2)
                self.show_images(image1, image2)
            else:
                print("All possible comparisons have been made.")
                messagebox.showinfo("Rating Complete", "All image comparisons are complete!\nUse one of the buttons at the bottom to process or save your ratings.")
                self.update_progress_label()  # Ensure the label reflects the completed state
                return

    def get_next_comparison(self):
        while True:
            image1 = random.choice(self.image_files)
            image2 = random.choice(self.image_files)
            if image1 != image2 and (image1, image2) not in self.comparisons and (image2, image1) not in self.comparisons:
                self.comparisons.append((image1, image2))
                return image1, image2

    def show_images(self, image1, image2):
        self.canvas.delete("all")

        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()

        if window_width > 0 and window_height > 0:
            try:
                if self.is_folder:
                    img1_path = os.path.join(self.folder_path, image1)
                else:
                    # Use file_paths as the primary source of truth
                    img1_path = self.file_paths.get(image1)
                    if not img1_path or not os.path.exists(img1_path):
                        print(f"Warning: File path for {image1} not found or invalid")
                        self.current_comparison = None
                        self.compare_images()
                        return
                
                img1 = Image.open(img1_path)
                img1.thumbnail((window_width // 2, window_height))
                photo1 = ImageTk.PhotoImage(img1)
                img1_x = (window_width // 4) - (img1.width // 2)
                img1_y = (window_height // 2) - (img1.height // 2)
                self.canvas.create_image(img1_x, img1_y, anchor=tk.NW, image=photo1)
                self.canvas.image1 = photo1
            except (FileNotFoundError, UnidentifiedImageError) as e:
                print(f"Error loading image {image1}: {str(e)}")
                self.current_comparison = None
                self.compare_images()  # Skip current comparison and move to the next one
                return

            try:
                if self.is_folder:
                    img2_path = os.path.join(self.folder_path, image2)
                else:
                    # Use file_paths as the primary source of truth
                    img2_path = self.file_paths.get(image2)
                    if not img2_path or not os.path.exists(img2_path):
                        print(f"Warning: File path for {image2} not found or invalid")
                        self.current_comparison = None
                        self.compare_images()
                        return
                    
                img2 = Image.open(img2_path)
                img2.thumbnail((window_width // 2, window_height))
                photo2 = ImageTk.PhotoImage(img2)
                img2_x = (window_width // 4 * 3) - (img2.width // 2)
                img2_y = (window_height // 2) - (img2.height // 2)
                self.canvas.create_image(img2_x, img2_y, anchor=tk.NW, image=photo2)
                self.canvas.image2 = photo2
            except (FileNotFoundError, UnidentifiedImageError) as e:
                print(f"Error loading image {image2}: {str(e)}")
                self.current_comparison = None
                self.compare_images()  # Skip current comparison and move to the next one
                return

    def choose_left(self, event=None):
        if self.current_comparison:
            self.update_ratings(self.current_comparison[0], self.current_comparison[1], self.current_comparison[0])
            self.current_comparison_number += 1  # Increment only when a comparison is made
            self.current_comparison = None
            self.compare_images()

    def choose_right(self, event=None):
        if self.current_comparison:
            self.update_ratings(self.current_comparison[0], self.current_comparison[1], self.current_comparison[1])
            self.current_comparison_number += 1  # Increment only when a comparison is made
            self.current_comparison = None
            self.compare_images()

    def reject_image(self, side):
        if self.current_comparison:
            rejected_image = self.current_comparison[0 if side == 'left' else 1]

            # Move the rejected image to the rejected folder without deleting the original
            if self.is_folder:
                # Create rejected folder as a subfolder of the original folder
                self.rejected_folder_path = os.path.join(self.folder_path, "rejected")
                try:
                    os.makedirs(self.rejected_folder_path, exist_ok=True)
                    print(f"Rejected folder created at: {self.rejected_folder_path}")
                except Exception as e:
                    print(f"Error creating rejected folder: {e}")

                src_path = os.path.join(self.folder_path, rejected_image)
                dst_path = os.path.join(self.rejected_folder_path, rejected_image)
            else:
                # For drag and drop files, create the rejected folder in the same directory as the image
                src_path = self.file_paths.get(rejected_image, rejected_image)
                image_dir = os.path.dirname(src_path)
                self.rejected_folder_path = os.path.join(image_dir, "rejected")
                try:
                    os.makedirs(self.rejected_folder_path, exist_ok=True)
                    print(f"Rejected folder created at: {self.rejected_folder_path}")
                except Exception as e:
                    print(f"Error creating rejected folder: {e}")

                dst_path = os.path.join(self.rejected_folder_path, os.path.basename(src_path))

            # Copy the rejected image instead of moving it
            try:
                shutil.copy(src_path, dst_path)
                print(f"Copied {rejected_image} to rejected folder: {dst_path}")
            except Exception as e:
                print(f"Error copying rejected image: {e}")

            # Remove the rejected image from the comparison list but keep it in the source folder
            self.image_files.remove(rejected_image)
            del self.ratings[rejected_image]  # Remove the rejected image from the ratings dictionary
            self.num_images -= 1
            self.total_comparisons = self.num_images * (self.num_images - 1) // 2  # Update total_comparisons
            self.update_progress_label()

            # Get the remaining image from the current comparison
            remaining_image = self.current_comparison[1 if side == 'left' else 0]

            # Find a new image to compare with the remaining image
            new_image = self.get_next_image(remaining_image)

            if new_image:
                self.current_comparison = (remaining_image, new_image) if side == 'right' else (new_image, remaining_image)
                self.show_images(*self.current_comparison)
            else:
                self.current_comparison = None
                self.compare_images()

    def get_next_image(self, current_image):
        for image in self.image_files:
            if image != current_image and (current_image, image) not in self.comparisons and (image, current_image) not in self.comparisons:
                self.comparisons.append((current_image, image))
                return image
        return None

    def update_ratings(self, image1, image2, winner):
        k = 32  # K-factor, determines the maximum rating change
        r1 = self.ratings[image1]
        r2 = self.ratings[image2]
        expected1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        expected2 = 1 / (1 + 10 ** ((r1 - r2) / 400))
        if winner == image1:
            self.ratings[image1] += k * (1 - expected1)
            self.ratings[image2] += k * (0 - expected2)
        else:
            self.ratings[image1] += k * (0 - expected1)
            self.ratings[image2] += k * (1 - expected2)

    def update_progress_label(self):
        total_comparisons = self.num_images * (self.num_images - 1) // 2
        completed_comparisons = len(self.comparisons)
        progress_text = f"{completed_comparisons} comparisons completed!"
        self.progress_label.config(text=progress_text)

    def end_comparison(self):
        self.save_progress()
        # Show the final options dialog instead of automatically copying files
        self.show_final_options()
        
    def show_final_options(self):
        """Show a dialog with options for what to do with the rated images"""
        options_window = tk.Toplevel(self.root)
        options_window.title("Rating Complete")
        options_window.geometry("500x450")  # Slightly taller to accommodate new button
        options_window.configure(bg="#f0f0f0")
        options_window.transient(self.root)  # Make it appear as a dialog
        options_window.grab_set()  # Make it modal
        
        # Prevent closing the main window while dialog is open
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Title
        title_label = tk.Label(options_window, text="Rating Complete!", 
                              font=("Arial", 18, "bold"), bg="#f0f0f0")
        title_label.pack(pady=20)
        
        # Instructions
        instructions = tk.Label(options_window, text="Choose what to do with your rated images:",
                               font=("Arial", 12), bg="#f0f0f0", justify=tk.LEFT)
        instructions.pack(pady=10, padx=20, anchor=tk.W)
        
        # Options frame
        options_frame = tk.Frame(options_window, bg="#f0f0f0")
        options_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Option 1: Write ratings to EXIF
        write_exif_button = tk.Button(options_frame, text="Save Ratings to Images", 
                                     command=lambda: self.save_ratings_to_exif(options_window),
                                     font=("Arial", 12, "bold"), bg="#4CAF50", fg="white",
                                     padx=20, pady=10)
        write_exif_button.pack(fill=tk.X, pady=10)
        
        exif_desc = tk.Label(options_frame, text="Write star ratings to image metadata. Images stay in their original locations.",
                            font=("Arial", 10), bg="#f0f0f0", wraplength=400, justify=tk.LEFT)
        exif_desc.pack(anchor=tk.W, pady=(0, 15))
        
        # Option 2: Sort into folders
        sort_button = tk.Button(options_frame, text="Sort Images into Folders", 
                              command=lambda: self.copy_best_images(options_window),
                              font=("Arial", 12, "bold"), bg="#2196F3", fg="white",
                              padx=20, pady=10)
        sort_button.pack(fill=tk.X, pady=10)
        
        sort_desc = tk.Label(options_frame, text="Copy images into rated_1 to rated_5 folders based on their ratings.",
                           font=("Arial", 10), bg="#f0f0f0", wraplength=400, justify=tk.LEFT)
        sort_desc.pack(anchor=tk.W, pady=(0, 15))
        
        # Option 3: Both
        both_button = tk.Button(options_frame, text="Do Both", 
                              command=lambda: self.do_both_options(options_window),
                              font=("Arial", 12, "bold"), bg="#9C27B0", fg="white",
                              padx=20, pady=10)
        both_button.pack(fill=tk.X, pady=10)
        
        both_desc = tk.Label(options_frame, text="Write ratings to metadata AND copy images into rating folders.",
                           font=("Arial", 10), bg="#f0f0f0", wraplength=400, justify=tk.LEFT)
        both_desc.pack(anchor=tk.W, pady=(0, 15))
        
        # Add Option 5: Start New Rating Session
        new_rating_button = tk.Button(options_window, text="Start New Rating Session", 
                                    command=lambda: self.start_new_from_dialog(options_window),
                                    font=("Arial", 10, "bold"), bg="#FF9800", fg="white")
        new_rating_button.pack(pady=10)
        
        new_rating_desc = tk.Label(options_window, text="Save your progress and start rating new images.",
                                 font=("Arial", 9), bg="#f0f0f0")
        new_rating_desc.pack(pady=(0, 10))
        
        # Option 4: Exit without further action
        exit_button = tk.Button(options_window, text="Exit Without Further Actions", 
                              command=lambda: self.exit_application(options_window),
                              font=("Arial", 10))
        exit_button.pack(pady=10)
        
        # Handle the window close button
        options_window.protocol("WM_DELETE_WINDOW", lambda: self.exit_application(options_window))
    
    def save_ratings_to_exif(self, options_window=None):
        """Write ratings to EXIF data without copying files"""
        sorted_images = sorted(self.ratings.items(), key=lambda x: x[1], reverse=True)
        num_images = len(sorted_images)
        
        # Create a progress window
        if options_window:
            progress_window = tk.Toplevel(options_window)
            progress_window.title("Writing EXIF Data")
            progress_window.geometry("400x150")
            progress_window.configure(bg="#f0f0f0")
            progress_window.transient(options_window)
            progress_window.grab_set()
            
            progress_label = tk.Label(progress_window, text="Writing ratings to image files...",
                                    font=("Arial", 12), bg="#f0f0f0")
            progress_label.pack(pady=20)
            
            progress_bar = ttk.Progressbar(progress_window, orient="horizontal", 
                                          length=300, mode="determinate", maximum=num_images)
            progress_bar.pack(pady=10, padx=20)
            
            # Force the window to update
            progress_window.update()
        
        for i, (image, rating) in enumerate(sorted_images):
            # Calculate EXIF rating (1-5 scale)
            percentile = (i / num_images) * 100
            if percentile < 20:
                exif_rating = 5
            elif percentile < 40:
                exif_rating = 4
            elif percentile < 60:
                exif_rating = 3
            elif percentile < 80:
                exif_rating = 2
            else:
                exif_rating = 1

            if self.is_folder:
                src_path = os.path.join(self.folder_path, image)
            else:
                src_path = self.file_paths.get(image, image)
            
            # Only write to JPEG files
            if src_path.lower().endswith(('.jpg', '.jpeg')):
                try:
                    set_exif_rating(src_path, exif_rating)
                    print(f"Added {exif_rating} star rating to {src_path}")
                except Exception as e:
                    print(f"Error setting EXIF rating: {str(e)}")
            else:
                print(f"Skipping non-JPEG file: {src_path}")
                
            # Update progress bar if we're showing it
            if options_window:
                progress_bar["value"] = i + 1
                progress_label.config(text=f"Writing ratings: {i+1} of {num_images}")
                progress_window.update()
        
        print("Finished writing ratings to image files.")
        
        # Close progress window if we have one
        if options_window:
            progress_window.destroy()
            messagebox.showinfo("Complete", "Ratings have been saved to image files.")
            self.exit_application(options_window)

    def copy_best_images(self, options_window=None):
        """Copy images to folders based on their ratings"""
        sorted_images = sorted(self.ratings.items(), key=lambda x: x[1], reverse=True)  # Sort in descending order
        rating_folders = {}
        
        # Track which source directories we've created folders in
        created_dirs = set()
        
        # Create a progress window if called from options dialog
        if options_window:
            progress_window = tk.Toplevel(options_window)
            progress_window.title("Copying Files")
            progress_window.geometry("400x150")
            progress_window.configure(bg="#f0f0f0")
            progress_window.transient(options_window)
            progress_window.grab_set()
            
            progress_label = tk.Label(progress_window, text="Copying images to rating folders...",
                                    font=("Arial", 12), bg="#f0f0f0")
            progress_label.pack(pady=20)
            
            progress_bar = ttk.Progressbar(progress_window, orient="horizontal", 
                                          length=300, mode="determinate", maximum=len(sorted_images))
            progress_bar.pack(pady=10, padx=20)
            
            # Force the window to update
            progress_window.update()
        
        for i, (image, rating) in enumerate(sorted_images):
            # Calculate rating based on percentile
            percentile = (i / len(sorted_images)) * 100
            if percentile < 20:
                folder_name = "rated_5"
                exif_rating = 5
            elif percentile < 40:
                folder_name = "rated_4"
                exif_rating = 4
            elif percentile < 60:
                folder_name = "rated_3"
                exif_rating = 3
            elif percentile < 80:
                folder_name = "rated_2"
                exif_rating = 2
            else:
                folder_name = "rated_1"
                exif_rating = 1

            # Get source path and determine appropriate output directory
            if self.is_folder:
                # For folder mode, use the original folder path
                src_path = os.path.join(self.folder_path, image)
                output_base = self.folder_path
            else:
                # For drag-and-drop mode, use the directory of each original file
                src_path = self.file_paths.get(image, image)
                output_base = os.path.dirname(src_path)
            
            # Create a "rated_images" subfolder in the source directory
            rated_subfolder = os.path.join(output_base, "rated_images")
            
            # Create the output directory structure if needed
            if output_base not in created_dirs:
                os.makedirs(rated_subfolder, exist_ok=True)
                for rating_value in range(1, 6):
                    os.makedirs(os.path.join(rated_subfolder, f"rated_{rating_value}"), exist_ok=True)
                created_dirs.add(output_base)
            
            # Destination folder and path
            dst_folder = os.path.join(rated_subfolder, folder_name)
            dst_path = os.path.join(dst_folder, os.path.basename(src_path))
            
            # Check if the image file exists before copying
            if os.path.exists(src_path):
                # Copy the file
                shutil.copy(src_path, dst_folder)
                print(f"Copied {os.path.basename(src_path)} to {dst_folder}")
            else:
                print(f"File not found: {src_path}. Skipping copy.")
                
            # Update progress bar if we're showing it
            if options_window:
                progress_bar["value"] = i + 1
                progress_label.config(text=f"Copying files: {i+1} of {len(sorted_images)}")
                progress_window.update()

        print("Image rating completed. Images copied to rating folders.")
        
        # Show the output folder
        if created_dirs:
            try:
                # Open the first created directory (most likely the only one or the main one)
                first_dir = next(iter(created_dirs))
                rated_path = os.path.join(first_dir, "rated_images")
                if os.path.exists(rated_path):
                    if os.name == 'nt':
                        os.startfile(rated_path)
                    else:
                        subprocess.call(['xdg-open', rated_path])
            except Exception as e:
                print(f"Could not open folder: {str(e)}")
                
        # Close progress window if we have one
        if options_window:
            progress_window.destroy()
            messagebox.showinfo("Complete", f"Images have been sorted into 'rated_images' folders within their original directories.")
            # Don't exit the application automatically - let the user close manually
            options_window.destroy()
            # Set focus back to the main window
            self.root.deiconify()
            self.root.focus_force()

    def do_both_options(self, options_window):
        """First save EXIF data then copy to folders"""
        # Create a progress window
        progress_window = tk.Toplevel(options_window)
        progress_window.title("Processing")
        progress_window.geometry("400x150")
        progress_window.configure(bg="#f0f0f0")
        progress_window.transient(options_window)
        progress_window.grab_set()
        
        progress_label = tk.Label(progress_window, text="Writing ratings to images...",
                                font=("Arial", 12), bg="#f0f0f0")
        progress_label.pack(pady=20)
        
        # Force update of window
        progress_window.update()
        
        # First write EXIF data
        self.save_ratings_to_exif()
        
        # Update progress message
        progress_label.config(text="Now sorting images into folders...")
        progress_window.update()
        
        # Then copy to folders
        self.copy_best_images()
        
        # Close progress window
        progress_window.destroy()
        messagebox.showinfo("Complete", "Ratings saved to images and files sorted into folders.")
        self.exit_application(options_window)

    def exit_application(self, options_window):
        """Close dialog but keep main app running"""
        options_window.destroy()
        # Don't destroy root window, just put focus back on it
        self.root.deiconify()
        self.root.focus_force()

    def save_progress(self):
        progress_data = {
            "set_name": self.set_name,
            "ratings": self.ratings,
            "comparisons": self.comparisons,
            "current_comparison_number": self.current_comparison_number
        }
        if self.current_comparison:
            progress_data["current_comparison"] = self.current_comparison
        
        # For file mode, also save file paths
        if not self.is_folder:
            progress_data["file_paths"] = self.file_paths
        
        # Determine save location - in the folder where images are located
        if self.is_folder:
            save_path = self.folder_path
        else:
            # For drag-drop mode, use the directory of the first image
            if self.file_paths:
                first_file = next(iter(self.file_paths.values()))
                save_path = os.path.dirname(first_file)
            else:
                save_path = self.temp_dir
        
        # Sanitize set name for filename
        safe_set_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in self.set_name)
        
        # Save the file with the set name as part of the filename
        save_file = os.path.join(save_path, f"image_rater_set_{safe_set_name}.json")
        with open(save_file, "w") as file:
            json.dump(progress_data, file, indent=4)
        
        return save_file

    def load_progress(self):
        if not self.is_folder:
            return
        
        # Look for JSON files matching our naming pattern
        progress_files = [f for f in os.listdir(self.folder_path) 
                         if f.startswith("image_rater_set_") and f.endswith(".json")]
        
        if not progress_files:
            print("No progress sets found.")
            return
        
        # If we have a set name, try to find that specific set
        if self.set_name:
            safe_set_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in self.set_name)
            target_file = f"image_rater_set_{safe_set_name}.json"
            
            if target_file in progress_files:
                self.load_set_from_file(os.path.join(self.folder_path, target_file))
                return
        
        # If no specific set was found, use the most recent one
        if progress_files:
            most_recent = max(progress_files, key=lambda f: os.path.getmtime(os.path.join(self.folder_path, f)))
            self.load_set_from_file(os.path.join(self.folder_path, most_recent))

    def load_set_from_file(self, file_path):
        try:
            with open(file_path, "r") as file:
                progress_data = json.load(file)
                
                # Load the set name
                self.set_name = progress_data.get("set_name", self.set_name)
                
                # For file mode, load file paths first
                if "file_paths" in progress_data:
                    self.file_paths = progress_data["file_paths"]
                    # Check if the paths exist
                    valid_paths = {}
                    missing_files = []
                    
                    for filename, filepath in self.file_paths.items():
                        if os.path.exists(filepath):
                            valid_paths[filename] = filepath
                        else:
                            missing_files.append((filename, filepath))
                    
                    # If some files are missing, try to locate them in the JSON file's directory
                    if missing_files:
                        json_dir = os.path.dirname(file_path)
                        for filename, _ in missing_files:
                            potential_path = os.path.join(json_dir, filename)
                            if os.path.exists(potential_path):
                                valid_paths[filename] = potential_path
                                print(f"Found {filename} in JSON directory: {potential_path}")
                            else:
                                print(f"Warning: File {filename} not found at original path or in JSON directory")
                    
                    # Update file_paths with only valid paths
                    self.file_paths = valid_paths
                    
                    # Set is_folder to False when loading from file_paths
                    if self.file_paths:
                        self.is_folder = False
                        # Get the first directory as the folder path for display purposes
                        if self.file_paths.values():
                            first_path = next(iter(self.file_paths.values()))
                            self.folder_path = os.path.dirname(first_path)
                
                # Update image_files based on valid file paths
                if not self.is_folder:
                    self.image_files = list(self.file_paths.keys())
                
                # Load ratings and comparisons
                loaded_ratings = progress_data["ratings"]
                self.comparisons = progress_data["comparisons"]
                self.current_comparison_number = progress_data.get("current_comparison_number", 0)
                self.current_comparison = progress_data.get("current_comparison")

                # If any images in the set weren't in the loaded ratings, initialize them
                for img in self.image_files:
                    if img not in self.ratings:
                        self.ratings[img] = 1500

                # Update comparisons to remove references to missing images
                updated_comparisons = [(image1, image2) for image1, image2 in self.comparisons 
                                     if image1 in self.image_files and image2 in self.image_files]
                self.comparisons = updated_comparisons

                # Update current comparison if it contains deleted images
                if self.current_comparison:
                    image1, image2 = self.current_comparison
                    if image1 not in self.image_files or image2 not in self.image_files:
                        self.current_comparison = None

                # Recalculate current comparison number based on updated comparisons
                self.current_comparison_number = len(self.comparisons)
                
                # Update the number of images
                self.num_images = len(self.image_files)

                # Provide more informative feedback to the user
                if missing_files:
                    print(f"Warning: {len(missing_files)} images from the saved set were not found")
                    if self.root and hasattr(self, 'root'):
                        messagebox.showwarning(
                            "Some Images Missing", 
                            f"{len(missing_files)} images from the saved set '{self.set_name}' were not found.\n\n"
                            f"The comparison will continue with the {self.num_images} available images."
                        )
                
                print(f"Loaded progress set '{self.set_name}' from {file_path} with {self.num_images} images")
                
                # Flag that we've loaded this set
                self.loaded_set = True
                return True
                
        except Exception as e:
            print(f"Error loading progress set: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Show a more user-friendly error message
            if hasattr(self, 'root') and self.root:
                messagebox.showerror(
                    "Error Loading Set", 
                    f"Could not load the comparison set.\n\nError: {str(e)}\n\n"
                    f"Please check if the file format is correct and try again."
                )
            return False

    def start_new_from_dialog(self, options_window):
        """Save current progress and start a new rating session"""
        options_window.destroy()
        self.save_progress()
        self.root.destroy()
        # Create a new startup window to select different images
        startup = StartupWindow()
        startup.root.mainloop()

    def save_and_quit(self):
        self.save_progress()
        self.root.destroy()
        
    def start_new_rating(self):
        """Save current progress and start a new rating session"""
        self.save_progress()
        self.root.destroy()
        # Create a new startup window to select different images
        startup = StartupWindow()
        startup.root.mainloop()
        
    def run(self):
        self.root = tk.Tk()
        self.root.title(f"Image Rater - Set: {self.set_name}")
        self.root.configure(bg="black")

        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Left-right selection buttons
        self.button_left = tk.Button(self.root, text="Left is better", command=self.choose_left)
        self.button_left.pack(side=tk.LEFT, padx=10, pady=10)

        self.button_right = tk.Button(self.root, text="Right is better", command=self.choose_right)
        self.button_right.pack(side=tk.RIGHT, padx=10, pady=10)

        self.button_reject_left = tk.Button(self.root, text="Reject Left", command=lambda: self.reject_image('left'))
        self.button_reject_left.pack(side=tk.LEFT, padx=10, pady=10)

        self.button_reject_right = tk.Button(self.root, text="Reject Right", command=lambda: self.reject_image('right'))
        self.button_reject_right.pack(side=tk.RIGHT, padx=10, pady=10)

        self.root.bind("<Left>", self.choose_left)
        self.root.bind("<Right>", self.choose_right)

        # Progress label at bottom
        self.progress_label = tk.Label(self.root, text="Comparison 0 of 0", bg="black", fg="white")
        self.progress_label.pack(side=tk.BOTTOM, pady=5)

        # Create a horizontal button frame at the bottom
        bottom_frame = tk.Frame(self.root, bg="black")
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        # Create a subframe for the buttons to ensure they're centered and horizontal
        button_subframe = tk.Frame(bottom_frame, bg="black")
        button_subframe.pack(pady=5)

        # Define button styles
        button_width = 20  # Slightly reduced width to fit all buttons
        button_height = 1
        button_padx = 5
        
        # Add buttons in horizontal layout
        self.button_exif = tk.Button(
            button_subframe, 
            text="Save Ratings to EXIF", 
            command=lambda: self.save_ratings_direct(),
            width=button_width, height=button_height,
            bg="#4CAF50", fg="white"
        )
        self.button_exif.grid(row=0, column=0, padx=button_padx)
        
        self.button_exif_sort = tk.Button(
            button_subframe, 
            text="Save & Sort into Folders", 
            command=self.end_comparison,
            width=button_width, height=button_height,
            bg="#2196F3", fg="white"
        )
        self.button_exif_sort.grid(row=0, column=1, padx=button_padx)
        
        self.button_save_set = tk.Button(
            button_subframe, 
            text="Save Set", 
            command=self.save_set_with_name,
            width=button_width, height=button_height,
            bg="#9C27B0", fg="white"
        )
        self.button_save_set.grid(row=0, column=2, padx=button_padx)
        
        self.button_save_quit = tk.Button(
            button_subframe, 
            text="Save & Quit", 
            command=self.save_and_quit,
            width=button_width, height=button_height,
            bg="#FF5722", fg="white"
        )
        self.button_save_quit.grid(row=0, column=3, padx=button_padx)
        
        self.button_save_new = tk.Button(
            button_subframe, 
            text="New Rating Session", 
            command=lambda: self.start_new_rating(),
            width=button_width, height=button_height,
            bg="#FF9800", fg="white"
        )
        self.button_save_new.grid(row=0, column=4, padx=button_padx)
        
        # Add a set name label above the progress label
        self.set_name_label = tk.Label(bottom_frame, text=f"Set: {self.set_name}", 
                                     bg="black", fg="#aaaaaa", font=("Arial", 8))
        self.set_name_label.pack(side=tk.BOTTOM, pady=2)

        self.root.bind("<Configure>", lambda event: self.show_images(*self.current_comparison) if self.current_comparison else None)
        
        # Apply all UI enhancements
        self.setup_ui_enhancements()
        
        # Start the comparison process
        if self.current_comparison:
            self.root.after(100, self.show_images, *self.current_comparison)
        else:
            self.root.after(100, self.compare_images)
            
        self.update_progress_label()  # Initialize the progress label text correctly
        
        self.root.mainloop()

    # Add new method to save ratings directly to EXIF without dialog
    def save_ratings_direct(self):
        self.save_progress()
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Writing EXIF Data")
        progress_window.geometry("400x150")
        progress_window.configure(bg="#f0f0f0")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        sorted_images = sorted(self.ratings.items(), key=lambda x: x[1], reverse=True)
        num_images = len(sorted_images)
        
        progress_label = tk.Label(progress_window, text="Writing ratings to image files...",
                                font=("Arial", 12), bg="#f0f0f0")
        progress_label.pack(pady=20)
        
        progress_bar = ttk.Progressbar(progress_window, orient="horizontal", 
                                      length=300, mode="determinate", maximum=num_images)
        progress_bar.pack(pady=10, padx=20)
        
        # Force the window to update
        progress_window.update()

        for i, (image, rating) in enumerate(sorted_images):
            # Calculate EXIF rating (1-5 scale)
            percentile = (i / num_images) * 100
            if percentile < 20:
                exif_rating = 5
            elif percentile < 40:
                exif_rating = 4
            elif percentile < 60:
                exif_rating = 3
            elif percentile < 80:
                exif_rating = 2
            else:
                exif_rating = 1

            if self.is_folder:
                src_path = os.path.join(self.folder_path, image)
            else:
                src_path = self.file_paths.get(image, image)
            
            # Only write to JPEG files
            if src_path.lower().endswith(('.jpg', '.jpeg')):
                try:
                    set_exif_rating(src_path, exif_rating)
                    print(f"Added {exif_rating} star rating to {src_path}")
                except Exception as e:
                    print(f"Error setting EXIF rating: {str(e)}")
            else:
                print(f"Skipping non-JPEG file: {src_path}")
                
            # Update progress bar
            progress_bar["value"] = i + 1
            progress_label.config(text=f"Writing ratings: {i+1} of {num_images}")
            progress_window.update()

        print("Finished writing ratings to image files.")
        progress_window.destroy()
        messagebox.showinfo("Complete", "Ratings have been saved to image files.")

    def save_set_with_name(self):
        """Prompt user for a set name and save the progress"""
        new_name = simpledialog.askstring("Save Comparison Set", 
                                        "Enter a name for this comparison set:", 
                                        initialvalue=self.set_name)
        if new_name:
            self.set_name = new_name
            save_path = self.save_progress()
            self.root.title(f"Image Rater - Set: {self.set_name}")
            self.set_name_label.config(text=f"Set: {self.set_name}")
            messagebox.showinfo("Set Saved", f"Comparison set '{self.set_name}' saved successfully to:\n{save_path}")

class StartupWindow:
    def __init__(self):
        # Use tkinterdnd2 if available, otherwise use standard Tkinter
        if TKDND_AVAILABLE:
            self.root = tkinterdnd2.TkinterDnD.Tk()
        else:
            self.root = tk.Tk()
            
        self.root.title("Image Rater - Start")
        self.root.geometry("600x550")  # Increase height to accommodate new buttons
        self.root.configure(bg="#f0f0f0")
        
        self.selected_files = []
        self.set_name = "Default"
        
        # Title
        title_label = tk.Label(self.root, text="Image Rater", font=("Arial", 24, "bold"), bg="#f0f0f0")
        title_label.pack(pady=20)
        
        # Frame for buttons
        button_frame = tk.Frame(self.root, bg="#f0f0f0")
        button_frame.pack(pady=10)
        
        # Button to select folder
        folder_button = tk.Button(button_frame, text="Select Folder", command=self.select_folder, 
                                  font=("Arial", 12), padx=20, pady=10)
        folder_button.grid(row=0, column=0, padx=10)
        
        # Or label
        or_label = tk.Label(button_frame, text="OR", font=("Arial", 14), bg="#f0f0f0")
        or_label.grid(row=0, column=1, padx=20)
        
        # Button to select individual files
        files_button = tk.Button(button_frame, text="Select Files", command=self.select_files,
                                font=("Arial", 12), padx=20, pady=10)
        files_button.grid(row=0, column=2, padx=10)
        
        # Load saved set button - added to a new row
        load_set_button = tk.Button(button_frame, text="Load Saved Set", command=self.load_saved_set,
                                   font=("Arial", 12), padx=20, pady=10, bg="#9C27B0", fg="white")
        load_set_button.grid(row=1, column=0, columnspan=3, pady=10)
        
        # Drop zone info
        self.drop_frame = tk.Frame(self.root, bg="#e0e0e0", width=500, height=150,
                                   highlightbackground="#aaaaaa", highlightthickness=2)
        self.drop_frame.pack(pady=15, padx=20, fill=tk.BOTH, expand=True)
        self.drop_frame.pack_propagate(False)
        
        # Configure drop zone for drag and drop if tkinterdnd2 is available
        if TKDND_AVAILABLE:
            self.drop_frame.drop_target_register(tkinterdnd2.DND_FILES)
            self.drop_frame.dnd_bind('<<Drop>>', self.on_drop)
            self.drop_label = tk.Label(self.drop_frame, text="Drag and drop images or a saved set (.json) here\nor click Select Files", 
                                  font=("Arial", 14), bg="#e0e0e0")
        else:
            self.drop_label = tk.Label(self.drop_frame, text="Click Select Files to choose images\nor Load Saved Set to continue a comparison", 
                                  font=("Arial", 14), bg="#e0e0e0")
            
        self.drop_label.pack(expand=True)
        
        self.files_label = tk.Label(self.drop_frame, text="0 files selected", 
                                   font=("Arial", 10), bg="#e0e0e0")
        self.files_label.pack(side=tk.BOTTOM, pady=10)
        
        # Add set name frame
        set_name_frame = tk.Frame(self.root, bg="#f0f0f0")
        set_name_frame.pack(fill=tk.X, padx=20, pady=10)
        
        set_name_label = tk.Label(set_name_frame, text="Comparison Set Name:", 
                                 font=("Arial", 12), bg="#f0f0f0")
        set_name_label.pack(side=tk.LEFT, padx=5)
        
        self.set_name_entry = tk.Entry(set_name_frame, font=("Arial", 12), width=30)
        self.set_name_entry.insert(0, self.set_name)
        self.set_name_entry.pack(side=tk.LEFT, padx=5)
        
        # Add a visual separator
        separator = tk.Frame(self.root, height=1, bg="#aaaaaa")
        separator.pack(fill=tk.X, padx=20, pady=5)
        
        # Start button frame
        button_frame = tk.Frame(self.root, bg="#f0f0f0", height=100)  
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        # Add an instruction label
        instruction_label = tk.Label(button_frame, text="After selecting files and naming your set, click below to begin", 
                                    font=("Arial", 10, "italic"), bg="#f0f0f0")
        instruction_label.pack(pady=5)
        
        # Start button (initially disabled)
        self.start_button = tk.Button(button_frame, text="START RATING", command=self.start_rating, 
                                     font=("Arial", 16, "bold"), state=tk.DISABLED, 
                                     bg="#4CAF50", fg="white", padx=40, pady=15)
        self.start_button.pack(pady=10)
        
        # Clear selection button
        self.clear_button = tk.Button(button_frame, text="Clear Selection", command=self.clear_selection,
                                    font=("Arial", 10), state=tk.DISABLED)
        self.clear_button.pack(pady=5)
    
    def select_folder(self):
        folder_path = filedialog.askdirectory(title="Select Image Folder", initialdir=os.getcwd())
        if folder_path:
            self.selected_files = folder_path
            self.update_file_list(True)
    
    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Select Images", 
            initialdir=os.getcwd(),
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif"),
                ("All files", "*.*")
            ]
        )
        
        if files:
            # Filter only image files
            image_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
            self.selected_files = image_files if not self.selected_files else self.selected_files + list(image_files)
            
            self.update_file_list(False)
    
    def load_saved_set(self):
        file_path = filedialog.askopenfilename(
            title="Load Saved Comparison Set",
            initialdir=os.getcwd(),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path and file_path.lower().endswith('.json'):
            # Try to load the set file to extract info
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    set_name = data.get('set_name', os.path.basename(file_path).replace(".json", ""))
                    
                    # Check if this is a file paths set
                    is_file_paths_set = "file_paths" in data and data["file_paths"]
                    
                    if is_file_paths_set:
                        # For a set with file paths, we'll initialize in file mode
                        is_folder = False
                        # Just pass None for files_or_folder, as we'll load from the JSON
                        self.root.destroy()
                        rater = ImageRater(None, is_folder=is_folder, set_name=set_name, load_set_path=file_path)
                        rater.run()
                    else:
                        # For a folder-based set, use the folder the JSON is in
                        is_folder = True
                        folder_path = os.path.dirname(file_path)
                        self.root.destroy()
                        rater = ImageRater(folder_path, is_folder=is_folder, set_name=set_name, load_set_path=file_path)
                        rater.run()
                    
            except Exception as e:
                messagebox.showerror("Error", f"Could not load comparison set: {str(e)}")
                import traceback
                traceback.print_exc()
    
    def on_drop(self, event):
        # This function is only called when tkinterdnd2 is available
        files = self.root.tk.splitlist(event.data)
        
        # Check if the first file is a JSON file (a saved set)
        if files and files[0].lower().endswith('.json'):
            try:
                with open(files[0], 'r') as f:
                    data = json.load(f)
                    set_name = data.get('set_name', os.path.basename(files[0]).replace(".json", ""))
                    
                    # Check if this is a file paths set
                    is_file_paths_set = "file_paths" in data and data["file_paths"]
                    
                    # Launch the rater directly with this saved set
                    self.root.destroy()
                    if is_file_paths_set:
                        # For a set with file paths, use file mode
                        rater = ImageRater(None, is_folder=False, set_name=set_name, load_set_path=files[0])
                    else:
                        # For a folder-based set, use the folder the JSON is in
                        folder_path = os.path.dirname(files[0])
                        rater = ImageRater(folder_path, is_folder=True, set_name=set_name, load_set_path=files[0])
                    
                    rater.run()
                    return event.action
                
            except Exception as e:
                messagebox.showerror("Error", f"Could not load comparison set: {str(e)}")
                import traceback
                traceback.print_exc()
                return event.action
        
        # Filter only image files
        image_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        if image_files:
            self.selected_files = image_files if not self.selected_files else self.selected_files + list(image_files)
            self.update_file_list(False)
        
        return event.action
    
    def update_file_list(self, is_folder):
        if is_folder:
            folder_path = self.selected_files
            image_files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
            self.files_label.config(text=f"{len(image_files)} files found in folder")
            
            # Show some of the image files
            if image_files:
                file_names = [f for f in image_files[:5]]
                if len(image_files) > 5:
                    file_names.append("...")
                self.drop_label.config(text=f"Selected folder with images:\n{', '.join(file_names)}")
        else:
            # Update file count label for individual files
            self.files_label.config(text=f"{len(self.selected_files)} files selected")
            
            # Show some of the selected files
            if self.selected_files:
                file_names = [os.path.basename(f) for f in self.selected_files[:5]]
                if len(self.selected_files) > 5:
                    file_names.append("...")
                self.drop_label.config(text=f"Selected files:\n{', '.join(file_names)}")
        
        # Enable the start and clear buttons and make start button pulse
        self.start_button.config(state=tk.NORMAL, bg="#4CAF50")
        self.clear_button.config(state=tk.NORMAL)
        
        # Add a visual cue message
        self.files_label.config(text=f"{self.files_label.cget('text')} - Click 'Start Rating' to begin")
    
    def clear_selection(self):
        self.selected_files = []
        self.files_label.config(text="0 files selected")
        
        # Reset drop label based on whether drag-and-drop is available
        if TKDND_AVAILABLE:
            self.drop_label.config(text="Drag and drop images or a saved set (.json) here\nor click Select Files")
        else:
            self.drop_label.config(text="Click Select Files to choose images\nor Load Saved Set to continue a comparison")
            
        self.start_button.config(state=tk.DISABLED)
        self.clear_button.config(state=tk.DISABLED)
    
    def start_rating(self):
        # Get the set name from the entry field
        self.set_name = self.set_name_entry.get().strip() or "Default"
        
        if isinstance(self.selected_files, str):  # It's a folder path
            self.root.destroy()
            rater = ImageRater(self.selected_files, is_folder=True, set_name=self.set_name)
            rater.run()
        elif self.selected_files:  # It's a list of files
            self.root.destroy()
            rater = ImageRater(self.selected_files, is_folder=False, set_name=self.set_name)
            rater.run()
        else:
            messagebox.showinfo("No Files", "Please select image files first.")


# Start the application
if __name__ == "__main__":
    # Check for piexif library
    try:
        import piexif
    except ImportError:
        print("piexif module not found. EXIF ratings will not be available.")
        print("To enable EXIF ratings, install piexif with: pip install piexif")
        
    startup = StartupWindow()
    startup.root.mainloop()