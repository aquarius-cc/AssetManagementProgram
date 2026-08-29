import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import math

img_path = r"C:\Users\WHHY\Desktop\1111111.png"
img = cv2.imread(img_path)
h, w = img.shape[:2]
print("Original size:", w, h)

# Step 1: Detect card corners via contour detection
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
# The card is bright (light blue) against darker table background
_, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

# Find contours
contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
# Find largest contour
contours = sorted(contours, key=cv2.contourArea, reverse=True)
main_contour = contours[0]

# Approximate to polygon
epsilon = 0.02 * cv2.arcLength(main_contour, True)
approx = cv2.approxPolyDP(main_contour, epsilon, True)

print("Approx vertices:", len(approx))
for p in approx:
    print(p[0])

# If we have 4+ points, pick the 4 extreme corners
if len(approx) >= 4:
    # Sort by area to get the largest contour points
    # Use minAreaRect approach for robustness
    rect = cv2.minAreaRect(main_contour)
    box = cv2.boxPoints(rect)
    box = np.int32(box)
else:
    box = np.int32(approx)

# Sort corners: top-left, top-right, bottom-right, bottom-left
def order_points(pts):
    pts = pts.astype(np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)

src_pts = order_points(box)
print("Ordered corners:", src_pts)

# Target size: 6.5cm x 10cm at 300 DPI
target_w = int(6.5 * 300 / 2.54)  # 768
target_h = int(10 * 300 / 2.54)   # 1181
dst_pts = np.array([
    [0, 0],
    [target_w - 1, 0],
    [target_w - 1, target_h - 1],
    [0, target_h - 1]
], dtype=np.float32)

M = cv2.getPerspectiveTransform(src_pts, dst_pts)
warped = cv2.warpPerspective(img, M, (target_w, target_h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))

# Step 2: Remove watermark at bottom-right
h2, w2 = warped.shape[:2]
mask = np.zeros((h2, w2), dtype=np.uint8)
# Watermark is in bottom-right corner
mask[int(h2*0.85):h2, int(w2*0.60):w2] = 255
warped = cv2.inpaint(warped, mask, 3, cv2.INPAINT_TELEA)

# Step 3: Clean up any remaining dark/grey background pixels outside card
# Convert to RGB for PIL
result_pil = Image.fromarray(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))

# Fill any near-black or dark grey pixels with white (clean edges)
arr = np.array(result_pil)
# Mask dark pixels
dark_mask = (arr[:,:,0] < 40) & (arr[:,:,1] < 40) & (arr[:,:,2] < 40)
arr[dark_mask] = [255, 255, 255]

# Also fill greyish table background (approx RGB around 150-180 grey)
# But this might affect the blue card border. Let's be conservative.
# Only replace very dark or very different from blue card
# The card border is blue, so grey outside is distinguishable
# Let's just clean obvious artifacts
result_pil = Image.fromarray(arr)

output_path = r"D:\CodeDemo\AssetManagementProgram\corrected.jpg"
result_pil.save(output_path, "JPEG", quality=95, dpi=(300, 300))
print("Saved:", output_path, result_pil.size)
