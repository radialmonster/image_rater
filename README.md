# Image Rater

Image Rater is a Python-based application designed to help users compare and rate images in a specified folder. Users can visually compare pairs of images, choose the better one, and reject unwanted images. The program keeps track of progress and saves ratings for future use. At the end of the process, the best-rated images are copied to separate folders based on their ratings.

## Features

- **Image Comparison:** Visually compare two images at a time and choose the better one.
- **Image Rejection:** Reject unwanted images to remove them from the comparison process.
- **Rating System:** Uses a rating system to rank images based on user choices.
- **Progress Saving:** Saves progress and ratings, allowing users to continue where they left off.
- **Folder Organization:** Copies the top-rated images to separate folders for easy access.

## User Guide

### Prerequisites

- Python 3.x
- Required Python packages:
  - `PIL` (Pillow)
  - `tkinter`

### Installation

1. Clone the repository or download the source code.
2. Install the required Python packages using pip:
    ```sh
    pip install pillow
    pip install tkinter
    ```

### Running the Program

1. Navigate to the directory containing the `ImageRater` script.
2. Run the script:
    ```sh
    python image_rater.py
    ```
3. A file dialog will prompt you to select a folder containing images.

### Using the Application

1. **Starting the Comparison:**
   - After selecting the folder, the application will start and display pairs of images for comparison.

2. **Comparing Images:**
   - Use the "Left is better" button or the left arrow key to select the left image as better.
   - Use the "Right is better" button or the right arrow key to select the right image as better.

3. **Rejecting Images:**
   - Use the "Reject Left" button to reject the left image.
   - Use the "Reject Right" button to reject the right image.

4. **Ending the Comparison:**
   - Click the "End Now" button to end the comparison and save progress.
   - Click the "Save and Quit" button to save progress and exit the application.

5. **Progress:**
   - The current comparison number and total comparisons are displayed at the bottom of the window.

### Folder Organization

At the end of the comparison process, images are **copied** into the following folders based on their ratings:

- `rated_5` - Top 20% of images
- `rated_4` - 20-40% of images
- `rated_3` - 40-60% of images
- `rated_2` - 60-80% of images
- `rated_1` - Bottom 20% of images

During the comparison process, when an image is marked as Rejected using the "Reject Left" or "Reject Right" button, it is immediately **moved** to the "rejected" folder:
- `rejected` - Images that were marked as Rejected are moved here in real-time


These folders will be created in the same directory as the selected image folder.

### Saving Progress

The program automatically saves progress to a file named `progress.json` in the selected image folder. This file contains:

- Current ratings
- Completed comparisons
- Current comparison number

When the program is run again, it will load this file and resume the comparison from where it left off.

### Known Issues

- Images not found or invalid will be skipped with an error message.
- Ensure the selected folder contains only valid image files to avoid issues.

### License

This project is licensed under the MIT License.

### Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

### Contact

For any issues or questions, please open an issue on GitHub.

---

Enjoy rating your images with Image Rater!
