import cv2
from ultralytics import YOLO

# ==============================
# Configuration
# ==============================

MODEL_PATH = "/home/ubuntu/Documents/sandy_files/ANPR_web/models/number_plate_yolov8s_v2.pt"      # Path to your trained model
IMAGE_PATH = "/home/ubuntu/Pictures/Screenshots/Screenshot from 2026-06-29 10-10-46.png"  # Input image
OUTPUT_PATH = "output.jpg"          # Output image

CONFIDENCE = 0.1

# ==============================
# Load Model
# ==============================

model = YOLO(MODEL_PATH)

# ==============================
# Read Image
# ==============================

image = cv2.imread(IMAGE_PATH)

if image is None:
    print("Error: Image not found.")
    exit()

# ==============================
# Perform Detection
# ==============================

results = model.predict(
    source=image,
    conf=CONFIDENCE,
    save=False,
    verbose=False
)

# ==============================
# Draw Bounding Boxes
# ==============================

for result in results:

    boxes = result.boxes

    for box in boxes:

        x1, y1, x2, y2 = map(int, box.xyxy[0])

        confidence = float(box.conf[0])

        class_id = int(box.cls[0])

        class_name = model.names[class_id]

        cv2.rectangle(
            image,
            (x1, y1),
            (x2, y2),
            (0,255,0),
            2
        )

        label = f"{class_name} {confidence:.2f}"

        cv2.putText(
            image,
            label,
            (x1, y1-10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0,255,0),
            2
        )

# ==============================
# Save Output
# ==============================

cv2.imwrite(OUTPUT_PATH, image)

print("Detection completed.")
print("Saved:", OUTPUT_PATH)

# ==============================
# Display Image
# ==============================

cv2.imshow("Number Plate Detection", image)

cv2.waitKey(0)

cv2.destroyAllWindows()