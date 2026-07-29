import os
from PIL import Image, ImageDraw, ImageFont

icons_dir = os.path.join(os.path.dirname(__file__), "icons")
os.makedirs(icons_dir, exist_ok=True)

sizes = [16, 48, 128]

for size in sizes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw rounded gradient box
    draw.rounded_rectangle([(0, 0), (size-1, size-1)], radius=max(2, size//6), fill=(6, 182, 212, 255))
    
    # Draw simple EB symbol or circle
    margin = size // 4
    draw.ellipse([(margin, margin), (size - margin, size - margin)], fill=(139, 92, 246, 255))
    
    icon_path = os.path.join(icons_dir, f"icon{size}.png")
    img.save(icon_path)
    print(f"Generated {icon_path}")
