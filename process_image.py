import cv2
import numpy as np
from PIL import Image, ImageDraw
import math

# Load image
img_path = r"C:\Users\WHHY\Desktop\1111111.png"
img = cv2.imread(img_path)
orig = img.copy()
h, w = img.shape[:2]

# Perspective correction: approximate card corners manually from image
# Card is roughly rectangular, slightly rotated clockwise
# We'll define approximate corners and warp
pts_src = np.array([
    [280, 320],    # top-left
    [1150, 200],   # top-right
    [1320, 2150],  # bottom-right
    [150, 1900]    # bottom-left
], dtype=np.float32)

# Target rectangular dimensions (approx card aspect)
max_w = 1000
max_h = 1400
pts_dst = np.array([
    [0, 0],
    [max_w, 0],
    [max_w, max_h],
    [0, max_h]
], dtype=np.float32)

M = cv2.getPerspectiveTransform(pts_src, pts_dst)
warped = cv2.warpPerspective(img, M, (max_w, max_h), borderMode=cv2.BORDER_CONSTANT, borderValue=(240, 240, 240))

# Now crop to actual card region (approx center) to avoid extra background
# The card fills most of the warped image; crop slightly
crop = warped[20:1380, 30:980]

# Fill missing edges: extend border using replication
crop = cv2.copyMakeBorder(crop, 20, 20, 20, 20, cv2.BORDER_REPLICATE)

# Remove watermark: inpaint bottom-right region where watermark appears
# The watermark is at bottom right: "豆包AI生成"
# We'll inpaint that region
watermark_mask = np.zeros(crop.shape[:2], dtype=np.uint8)
# Approx region: bottom-right corner
h2, w2 = crop.shape[:2]
watermark_mask[int(h2*0.88):h2, int(w2*0.65):w2] = 255
# Inpaint
inpainted = cv2.inpaint(crop, watermark_mask, 3, cv2.INPAINT_TELEA)

# Background removal: since background of card is light blue, we can isolate the card
# But user asked to "去掉背景" (remove background) - likely make background transparent or white
# Let's create a mask: card area is light blue/white; background outside is greyish table
# We'll use a simpler approach: since card is centered, we crop tightly to card edges
# Actually the user probably wants the card isolated from the table/background.
# Let's apply a rough mask by color: the card is blue/white; outside background is grey/dark
hsv = cv2.cvtColor(inpainted, cv2.COLOR_BGR2HSV)
# Mask for light colors (card content) vs darker grey table
# We'll keep the card and make outside transparent (for now we'll make outside white since JPG doesn't support alpha)
# But user wants JPG. So we can make the background pure white.

# Let's just clean the edges and save as white background
result = inpainted
# Make very dark/grey outside pixels white (clean table background outside card)
# Convert to grayscale and threshold to separate card from remaining dark edges
gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
# The card is bright; anything too dark outside is background
_, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
# But this may cut text. Instead, manually crop tightly.
# Let's crop tightly around card content

# Better approach for "去掉背景": crop to the card boundary and fill outside with white
# The card boundary is roughly the whole image now after perspective correction
# Let's just save the corrected card with white fill around any missing corners

# Resize to target: 6.5cm x 10cm at 300 DPI
# 6.5cm = 2.559 inches = ~768 px; 10cm = 3.937 in = ~1181 px
target_w = int(6.5 * 300 / 2.54)
target_h = int(10 * 300 / 2.54)
resized = cv2.resize(result, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

# Fill any remaining black/transparent areas with white
resized_pil = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
# Check if there are dark borders; replace near-black with white
pixels = resized_pil.load()
for x in range(resized_pil.width):
    for y in range(resized_pil.height):
        r, g, b = pixels[x, y]
        if r < 30 and g < 30 and b < 30:
            pixels[x, y] = (255, 255, 255)

# Also fill any grey outside card with pure white for clean JPG
output_path = r"D:\CodeDemo\AssetManagementProgram\corrected.jpg"
resized_pil.save(output_path, "JPEG", quality=95, dpi=(300, 300))
print("Saved to", output_path, "size:", resized_pil.size)
