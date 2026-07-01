import cv2
from ultralytics import YOLO

# ── CONFIG — edit these ───────────────────────────────────────────────────────
VIDEO_PATH     = "/home/ubuntu/Videos/anpr_videos/vid2.mp4"       # path to your video file
MODEL_PATH     = "/home/ubuntu/Documents/sandy_files/plate_paddleOCR/model/number_plate_yolov8s_v2.pt"     # path to your YOLO weights
FRAME_INTERVAL = 5               # process every Nth frame
OUTPUT_PATH    = "output.avi"      # where to save result video
CONF_THRESHOLD = 0.30               # minimum confidence to show bbox
WINDOW_WIDTH   = 1280          # ← set your desired width
WINDOW_HEIGHT  = 720  
# ─────────────────────────────────────────────────────────────────────────────




def detect_numbers_in_video():
    print(f"Loading model : {MODEL_PATH}")
    model = YOLO(MODEL_PATH)

    print(f"Opening video : {VIDEO_PATH}")
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {VIDEO_PATH}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps          = cap.get(cv2.CAP_PROP_FPS)
    width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"Video info    : {total_frames} frames | {fps:.1f} FPS | {width}x{height}")
    print(f"Frame interval: every {FRAME_INTERVAL}th frame")
    print("Controls      : [q] quit\n")
    print(f"Input Video FPS: {fps}")

    out = cv2.VideoWriter(
        OUTPUT_PATH,
        cv2.VideoWriter_fourcc(*"XVID"),
        max(fps / FRAME_INTERVAL, 1),
        (width, height),
    )

    # Create named resizable window once
    cv2.namedWindow("YOLO Number Detection", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("YOLO Number Detection", WINDOW_WIDTH, WINDOW_HEIGHT)

    frame_count     = 0
    processed_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        if frame_count % FRAME_INTERVAL != 0:
            continue

        processed_count += 1
        print(f"  Frame {frame_count:>6}/{total_frames}  |  processed: {processed_count}", end="\r")

        results   = model(frame, verbose=False)[0]
        annotated = frame.copy()

        for box in results.boxes:
            conf = float(box.conf[0])
            if conf < CONF_THRESHOLD:
                continue

            cls_id   = int(box.cls[0])
            cls_name = model.names[cls_id]
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            color = (0, 255, 0)
            label = f"{cls_name} {conf:.2f}"

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
            cv2.putText(annotated, label, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)

        overlay = f"Frame: {frame_count}/{total_frames}  |  Every {FRAME_INTERVAL}th"
        cv2.putText(annotated, overlay, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        out.write(annotated)

        cv2.imshow("YOLO Number Detection", annotated)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("\nStopped by user.")
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print(f"\nDone. Processed {processed_count} frames → saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    detect_numbers_in_video()