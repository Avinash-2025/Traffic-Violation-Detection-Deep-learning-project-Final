import cv2
import numpy as np

def generate_sample_video(output_path="sample_video.mp4", duration_sec=10, fps=30):
    width, height = 1280, 720
    total_frames = duration_sec * fps
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    for frame_idx in range(total_frames):
        frame = np.full((height, width, 3), (40, 40, 40), dtype=np.uint8)

        # Draw road
        cv2.rectangle(frame, (200, 0), (1080, height), (70, 70, 70), -1)
        # Lane divider
        for y in range(0, height, 40):
            cv2.line(frame, (640, y), (640, y + 20), (255, 255, 255), 4)

        # Stop line
        cv2.line(frame, (200, 500), (1080, 500), (255, 255, 255), 6)

        # Traffic light box
        cv2.rectangle(frame, (1100, 100), (1160, 260), (20, 20, 20), -1)
        # Red light or Green light (cycles every 5 seconds)
        is_red = (frame_idx // (5 * fps)) % 2 == 0
        if is_red:
            cv2.circle(frame, (1130, 140), 20, (0, 0, 255), -1) # Red ON
            cv2.circle(frame, (1130, 220), 20, (0, 50, 0), -1)   # Green OFF
        else:
            cv2.circle(frame, (1130, 140), 20, (0, 0, 50), -1)   # Red OFF
            cv2.circle(frame, (1130, 220), 20, (0, 255, 0), -1) # Green ON

        # Moving vehicles
        # Vehicle 1: Car moving forward
        y1 = int(100 + (frame_idx * 4) % (height + 200)) - 100
        if 0 <= y1 <= height - 80:
            cv2.rectangle(frame, (400, y1), (520, y1 + 100), (0, 150, 255), -1)
            cv2.putText(frame, "Car", (410, y1 + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Vehicle 2: Motorcycle moving forward
        y2 = int(250 + (frame_idx * 5) % (height + 200)) - 100
        if 0 <= y2 <= height - 60:
            cv2.rectangle(frame, (750, y2), (810, y2 + 70), (200, 50, 50), -1)
            cv2.putText(frame, "Bike", (755, y2 + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        out.write(frame)

    out.release()
    print(f"Sample video created at {output_path}")

if __name__ == "__main__":
    generate_sample_video()

