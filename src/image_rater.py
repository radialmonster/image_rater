import os
import shutil
import random
import tkinter as tk
import json
from tkinter import filedialog
from PIL import ImageTk, Image, UnidentifiedImageError

class ImageRater:
    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.image_files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        self.num_images = len(self.image_files)
        self.ratings = {image: 1500 for image in self.image_files}
        self.comparisons = []
        self.current_comparison = None
        self.rejected_folder_path = os.path.join(self.folder_path, "rejected")
        self.current_comparison_number = 0
        os.makedirs(self.rejected_folder_path, exist_ok=True)
        self.load_progress()

    def compare_images(self):
        self.update_progress_label()
        self.image_files = [f for f in self.image_files if f not in os.listdir(self.rejected_folder_path)]  # Update to exclude rejected images
        if not self.image_files or len(self.image_files) < 2:  # Check if there are less than two images left
            print("All comparisons complete or not enough images left to compare.")
            self.end_comparison()
            return

        if not self.current_comparison:
            if len(self.comparisons) < self.num_images * (self.num_images - 1) // 2 and len(self.image_files) > 1:
                image1, image2 = self.get_next_comparison()
                self.current_comparison = (image1, image2)
                self.show_images(image1, image2)
            else:
                print("All possible comparisons have been made.")
                self.end_comparison()

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
                img1 = Image.open(os.path.join(self.folder_path, image1))
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
                img2 = Image.open(os.path.join(self.folder_path, image2))
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
            shutil.move(os.path.join(self.folder_path, rejected_image), os.path.join(self.rejected_folder_path, rejected_image))
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
        total_comparisons = len(self.image_files) * (len(self.image_files) - 1) // 2
        progress_text = f"Comparison {self.current_comparison_number} of {total_comparisons}"
        self.progress_label.config(text=progress_text)

    def end_comparison(self):
        self.save_progress()
        self.root.destroy()
        self.copy_best_images()

    def copy_best_images(self):
        sorted_images = sorted(self.ratings.items(), key=lambda x: x[1], reverse=True)  # Sort in descending order
        rating_folders = {}
        for i in range(5):
            folder_name = f"rated_{5-i}"  # Change the folder names to rated_5, rated_4, ..., rated_1
            rating_folders[i+1] = folder_name
            os.makedirs(os.path.join(self.folder_path, folder_name), exist_ok=True)

        num_images = len(sorted_images)
        for i, (image, rating) in enumerate(sorted_images):
            percentile = (i / num_images) * 100
            if percentile < 20:
                folder = "rated_5"
            elif percentile < 40:
                folder = "rated_4"
            elif percentile < 60:
                folder = "rated_3"
            elif percentile < 80:
                folder = "rated_2"
            else:
                folder = "rated_1"

            src_path = os.path.join(self.folder_path, image)
            dst_path = os.path.join(self.folder_path, folder)
            
            # Check if the image file exists before copying
            if os.path.exists(src_path):
                shutil.copy(src_path, dst_path)
            else:
                print(f"File not found: {src_path}. Skipping copy.")

        print("Image rating completed. Best images copied to subfolders.")

    
    def save_progress(self):
        progress_data = {
            "ratings": self.ratings,
            "comparisons": self.comparisons,
            "current_comparison_number": self.current_comparison_number
        }
        if self.current_comparison:
            progress_data["current_comparison"] = self.current_comparison
        with open(os.path.join(self.folder_path, "progress.json"), "w") as file:
            json.dump(progress_data, file)

    def load_progress(self):
        progress_file = os.path.join(self.folder_path, "progress.json")
        if os.path.exists(progress_file):
            with open(progress_file, "r") as file:
                progress_data = json.load(file)
                loaded_ratings = progress_data["ratings"]
                self.comparisons = progress_data["comparisons"]
                self.current_comparison_number = progress_data.get("current_comparison_number", 0)
                self.current_comparison = progress_data.get("current_comparison")

                # Update ratings dictionary with new images
                for image in self.image_files:
                    if image not in loaded_ratings:
                        loaded_ratings[image] = 1500

                self.ratings = loaded_ratings
                print("Progress loaded.")

                # Start the comparison process only if there is a current comparison
                if hasattr(self, 'canvas') and self.canvas and self.current_comparison:
                    self.show_images(*self.current_comparison)
        else:
            print("No progress found.")
    
    def save_and_quit(self):
        self.save_progress()
        self.root.destroy()
        
    def run(self):
        self.root = tk.Tk()
        self.root.title("Image Rater")
        self.root.configure(bg="black")

        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        button_left = tk.Button(self.root, text="Left is better", command=self.choose_left)
        button_left.pack(side=tk.LEFT, padx=10, pady=10)

        button_right = tk.Button(self.root, text="Right is better", command=self.choose_right)
        button_right.pack(side=tk.RIGHT, padx=10, pady=10)

        button_reject_left = tk.Button(self.root, text="Reject Left", command=lambda: self.reject_image('left'))
        button_reject_left.pack(side=tk.LEFT, padx=10, pady=10)

        button_reject_right = tk.Button(self.root, text="Reject Right", command=lambda: self.reject_image('right'))
        button_reject_right.pack(side=tk.RIGHT, padx=10, pady=10)

        self.root.bind("<Left>", self.choose_left)
        self.root.bind("<Right>", self.choose_right)

        button_end = tk.Button(self.root, text="End Now", command=self.end_comparison)
        button_end.pack(side=tk.BOTTOM, pady=10)

        button_save_quit = tk.Button(self.root, text="Save and Quit", command=self.save_and_quit)
        button_save_quit.pack(side=tk.BOTTOM, pady=10)

        self.root.bind("<Configure>", lambda event: self.show_images(*self.current_comparison) if self.current_comparison else None)

        # Start the comparison process only if there is a current comparison
        if self.current_comparison:
            self.root.after(100, self.show_images, *self.current_comparison)
        else:
            self.root.after(100, self.compare_images)

        self.progress_label = tk.Label(self.root, text="Comparison 0 of 0", bg="black", fg="white")
        self.progress_label.pack(side=tk.BOTTOM, pady=5)
        self.update_progress_label()  # Initialize the progress label text correctly
        
        self.root.mainloop()

# Prompt the user to select a folder
folder_path = filedialog.askdirectory(title="Select Image Folder")

if folder_path:
    rater = ImageRater(folder_path)
    rater.run()
else:
    print("No folder selected. Exiting.")