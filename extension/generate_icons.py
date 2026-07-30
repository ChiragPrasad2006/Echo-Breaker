import os
from PIL import Image, ImageDraw

# Extension icons directory setup
extension_dir = os.path.dirname(__file__)
icons_dir = os.path.join(extension_dir, "icons")
os.makedirs(icons_dir, exist_ok=True)

def generate_logo():
    # Create a 512x512 canvas with dark obsidian background
    size = 512
    bg_color = (8, 9, 10)  # #08090A
    surface_color = (15, 17, 19)  # #0F1113
    border_color = (27, 29, 32)  # #1B1D20
    white_color = (255, 255, 255)  # #FFFFFF
    cyan_color = (0, 242, 254)  # #00F2FE

    img = Image.new("RGBA", (size, size), bg_color)
    draw = ImageDraw.Draw(img)

    # Draw rounded rectangle container
    draw.rounded_rectangle([16, 16, 496, 496], radius=48, fill=surface_color, outline=border_color, width=4)

    # DRAW LETTER E (White)
    # Vertical stem
    draw.rectangle([130, 140, 170, 372], fill=white_color)
    # Top horizontal bar
    draw.rectangle([170, 140, 270, 178], fill=white_color)
    # Middle horizontal bar
    draw.rectangle([170, 236, 250, 274], fill=white_color)
    # Bottom horizontal bar
    draw.rectangle([170, 332, 270, 370], fill=white_color)

    # DRAW LETTER B (Cyan)
    # Vertical stem
    draw.rectangle([285, 140, 325, 372], fill=cyan_color)
    # Upper loop fill
    draw.ellipse([285, 140, 385, 256], fill=cyan_color)
    # Upper loop cutout
    draw.ellipse([325, 172, 355, 224], fill=surface_color)
    # Lower loop fill
    draw.ellipse([285, 256, 385, 372], fill=cyan_color)
    # Lower loop cutout
    draw.ellipse([325, 288, 355, 340], fill=surface_color)

    # Save 512x512 original logo
    logo_path = os.path.join(icons_dir, "logo.png")
    img.save(logo_path)
    print(f"Generated high-res monogram logo: {logo_path}")

    # Generate standard sizes: 16x16, 48x48, 128x128
    sizes = [16, 48, 128]
    for sz in sizes:
        resized = img.resize((sz, sz), Image.Resampling.LANCZOS)
        icon_path = os.path.join(icons_dir, f"icon{sz}.png")
        resized.save(icon_path)
        print(f"Generated icon: {icon_path} ({sz}x{sz})")

if __name__ == "__main__":
    generate_logo()
