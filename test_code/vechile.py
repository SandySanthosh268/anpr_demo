import cv2
from ultralytics import YOLO

# Load your custom model
model = YOLO("/home/ubuntu/Downloads/best (1).pt")      # Path to your trained model

# Read image
image = cv2.imread("/home/ubuntu/Pictures/Screenshots/Screenshot from 2026-07-01 11-58-51.png")

# Run inference
results = model(image, conf=0.25)

# Get class names from your model
class_names = model.names

# Draw detections
for result in results:
    for box in result.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])
        cls = int(box.cls[0])

        label = f"{class_names[cls]} {conf:.2f}"

        # Draw bounding box
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Draw label
        cv2.putText(
            image,
            label,
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

# Resize for display (optional)
display = cv2.resize(image, (1280, 720))

cv2.imshow("Vehicle Detection", display)
cv2.imwrite("output.jpg", image)

cv2.waitKey(0)
cv2.destroyAllWindows()