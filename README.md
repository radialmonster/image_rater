# Image Rater

Image Rater is a Python-based application that allows users to compare and rate images using an intuitive graphical user interface (GUI). It supports drag-and-drop functionality, EXIF metadata editing, and sorting images into folders based on their ratings. This tool is perfect for photographers, designers, or anyone who needs to organize and rate images efficiently.

## Features

- **Intuitive GUI**: Compare images side-by-side and rate them with ease.
- **Drag-and-Drop Support**: Quickly add images or saved sets by dragging them into the application.
- **EXIF Metadata Editing**: Save ratings directly into the image's metadata (JPEG only).
- **Folder Organization**: Automatically sort images into folders based on their ratings.
- **Progress Saving**: Save and load rating sessions to continue later.
- **Keyboard Shortcuts**: Use keyboard Left and Right arrow keys to select the Left or Right image is better

## Demo

Watch the demo video to see Image Rater in action:
[![Demo Video](https://img.youtube.com/vi/aqHT-Z7Lqiw/0.jpg)](https://youtu.be/aqHT-Z7Lqiw)

## Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/image-rater.git
   cd image-rater
   ```

2. **Install Dependencies**
   Make sure you have Python 3.7 or later installed. Then, install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Application**
   ```bash
   python src/image_rater.py
   ```

4. **Optional**: Install `tkinterdnd2` for drag-and-drop support:
   ```bash
   pip install tkinterdnd2
   ```

5. **Optional**: Install `piexif` for EXIF metadata editing:
   ```bash
   pip install piexif
   ```

## Usage

1. Launch the application by running the `image_rater.py` script.
2. Select a folder or individual image files to start rating.
3. Use the GUI to compare images, rate them, and organize them into folders.
4. Save your progress and continue later if needed.

## Support the Project

If you find this project helpful and would like to buy me a pizza, you may [Donate via PayPal](https://www.paypal.com/paypalme/radialmonster)

## Contributing

Contributions are welcome! Feel free to fork the repository and submit a pull request.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.