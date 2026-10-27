import os
from pathlib import Path
from PIL import Image, ImageDraw

def create_coworkeros_icon(size: int = 512) -> Image.Image:
    """
    Generates the official CoworkerOS mascot icon.
    - Soft orange circle (#FF6B00) on transparent background with supersampled anti-aliasing.
    - Two pill-shaped white eyes (vertical rounded capsules tilted slightly inward).
    """
    scale = 4  # 4x supersampling for high-quality antialiasing
    canvas_size = size * scale

    # High-resolution canvas with full RGBA transparency
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # Main orange circle (#FF6B00)
    padding = int(24 * scale)
    circle_box = [padding, padding, canvas_size - padding, canvas_size - padding]
    draw.ellipse(circle_box, fill="#FF6B00")

    # Dimensions for pill-shaped eyes (capsules)
    eye_width = int(36 * scale)
    eye_height = int(82 * scale)
    eye_radius = eye_width // 2

    # Draw vertical pill eye on separate transparent canvas
    eye_canvas_pad = int(10 * scale)
    eye_img = Image.new("RGBA", (eye_width + eye_canvas_pad * 2, eye_height + eye_canvas_pad * 2), (0, 0, 0, 0))
    eye_draw = ImageDraw.Draw(eye_img)
    eye_draw.rounded_rectangle(
        [eye_canvas_pad, eye_canvas_pad, eye_canvas_pad + eye_width, eye_canvas_pad + eye_height],
        radius=eye_radius,
        fill="#FFFFFF"
    )

    # Inward tilt angles (clockwise for left eye, counter-clockwise for right eye)
    tilt_angle = 7.5
    # In Pillow, rotate(positive) rotates counter-clockwise; rotate(negative) rotates clockwise.
    left_eye = eye_img.rotate(-tilt_angle, resample=Image.Resampling.BICUBIC, expand=True)
    right_eye = eye_img.rotate(tilt_angle, resample=Image.Resampling.BICUBIC, expand=True)

    # Eye positions (slightly above vertical center for blob mascot cuteness)
    eye_center_y = int(canvas_size * 0.46)
    left_eye_center_x = int(canvas_size * 0.41)
    right_eye_center_x = int(canvas_size * 0.59)

    canvas.paste(
        left_eye,
        (left_eye_center_x - left_eye.width // 2, eye_center_y - left_eye.height // 2),
        left_eye
    )
    canvas.paste(
        right_eye,
        (right_eye_center_x - right_eye.width // 2, eye_center_y - right_eye.height // 2),
        right_eye
    )

    # Downsample using high-quality Lanczos resampling for ultra-smooth edges
    icon = canvas.resize((size, size), resample=Image.Resampling.LANCZOS)
    return icon

def main():
    script_dir = Path(__file__).parent.resolve()
    png_path = script_dir / "icon.png"
    ico_path = script_dir / "icon.ico"

    print("Generating CoworkerOS official icon (512x512 RGBA)...")
    icon = create_coworkeros_icon(size=512)

    # Save PNG
    icon.save(png_path, format="PNG")
    print(f"Saved PNG icon: {png_path} ({os.path.getsize(png_path)} bytes)")

    # Save ICO with multi-resolution icon sizes
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon.save(ico_path, format="ICO", sizes=ico_sizes)
    print(f"Saved ICO icon: {ico_path} ({os.path.getsize(ico_path)} bytes)")

if __name__ == "__main__":
    main()
